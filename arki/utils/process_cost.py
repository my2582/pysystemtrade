#!/usr/bin/env python
"""Process-cost instrumentation for futures_momentum family cells.

Implements Handoff #3 item F: record 5 lifecycle timestamps in each cell's
``manifest.json`` and measure cell cycle time (pre-reg lock -> family commit).
Average cycle time > 1 business day is a framework-simplification trigger
(see ars/families/futures_momentum/queue.md "Process-cost measurement").

The five stages (recorded in ``manifest["timeline"]``):

    pre_reg_authored_at   -- pre-registration locked
    runner_started_at     -- runner began execution
    runner_finished_at    -- runner produced artifacts
    gates_evaluated_at     -- acceptance gates scored
    family_committed_at   -- cell written into family.yaml / registry

Cycle time = busdays(pre_reg_authored_at -> family_committed_at).

Usage:
    # stamp one stage (default time = now, UTC)
    venv/bin/python -m arki.utils.process_cost record \\
        --manifest ars/runs/<run>/manifest.json --stage runner_started_at

    # aggregate across all runs that have a complete timeline
    venv/bin/python -m arki.utils.process_cost report --runs-dir ars/runs

    # self-check (no filesystem writes)
    venv/bin/python -m arki.utils.process_cost --selfcheck
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np

STAGES = [
    "pre_reg_authored_at",
    "runner_started_at",
    "runner_finished_at",
    "gates_evaluated_at",
    "family_committed_at",
]

# Display + computation format. UTC, second precision.
_TS_FMT = "%Y-%m-%d %H:%M:%S UTC"
DEFAULT_THRESHOLD_BUSINESS_DAYS = 1.0


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime(_TS_FMT)


def _parse_ts(value: str) -> datetime:
    """Parse a timeline timestamp. Accepts the canonical '... UTC' format and a
    couple of common ISO fallbacks so hand-edited manifests still aggregate."""
    value = value.strip()
    for fmt in (_TS_FMT, "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Last resort: ISO-8601 with offset.
    return datetime.fromisoformat(value)


def business_days_between(start_iso: str, end_iso: str) -> float:
    """Whole business days between two timestamps (weekends excluded, holidays
    NOT excluded -- date granularity). End-inclusive of same-day work returns 0."""
    d0 = _parse_ts(start_iso).date()
    d1 = _parse_ts(end_iso).date()
    return float(np.busday_count(d0, d1))


def record_timestamp(manifest_path: Path, stage: str, when: str | None = None) -> dict:
    """Set (or overwrite) one timeline stage in a manifest.json, preserving all
    other keys. Returns the updated manifest dict."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; must be one of {STAGES}")
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    timeline = manifest.setdefault("timeline", {})
    timeline[stage] = when or _now_utc()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def cycle_time_days(manifest: dict) -> float | None:
    """Cell cycle time in business days, or None if either anchor is missing."""
    tl = manifest.get("timeline", {})
    a, b = tl.get("pre_reg_authored_at"), tl.get("family_committed_at")
    if not a or not b:
        return None
    return business_days_between(a, b)


def _complete(manifest: dict) -> bool:
    tl = manifest.get("timeline", {})
    return all(tl.get(s) for s in STAGES)


def aggregate(runs_dir: Path,
              threshold: float = DEFAULT_THRESHOLD_BUSINESS_DAYS) -> dict:
    """Scan ars/runs/<run>/manifest.json, collect cells whose timeline is
    complete, and summarise cycle times."""
    rows = []
    for mf in sorted(Path(runs_dir).glob("*/manifest.json")):
        try:
            manifest = json.loads(mf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        ct = cycle_time_days(manifest)
        if ct is not None:
            rows.append({"run": mf.parent.name,
                         "cycle_time_days": ct,
                         "complete": _complete(manifest)})
    vals = [r["cycle_time_days"] for r in rows]
    summary: dict = {
        "n_measured": len(vals),
        "rows": rows,
        "threshold_for_simplification": threshold,
    }
    if vals:
        ordered = sorted(vals)
        p75 = float(np.percentile(ordered, 75))
        summary.update({
            "cycle_time_days_mean": round(mean(vals), 3),
            "cycle_time_days_median": round(median(vals), 3),
            "cycle_time_days_p75": round(p75, 3),
            "simplification_triggered": mean(vals) > threshold,
        })
    return summary


def _print_report(summary: dict) -> None:
    n = summary["n_measured"]
    print(f"\n=== process-cost report ({n} cell(s) with complete timeline) ===")
    for r in summary["rows"]:
        flag = "" if r["complete"] else "  (partial timeline)"
        print(f"  {r['run']:<48} {r['cycle_time_days']:>6.2f} bd{flag}")
    if n == 0:
        print("  (no cells yet carry a pre_reg_authored_at + family_committed_at pair)")
        print("  -> instrument new cells with `record --stage ...` as they progress.")
        return
    print(f"\n  mean   = {summary['cycle_time_days_mean']:.3f} business days")
    print(f"  median = {summary['cycle_time_days_median']:.3f} business days")
    print(f"  p75    = {summary['cycle_time_days_p75']:.3f} business days")
    thr = summary["threshold_for_simplification"]
    if summary["simplification_triggered"]:
        print(f"\n  [TRIGGER] mean > {thr} bd -> framework simplification on the table"
              " (CPCV folds / drop a rule axis / simplify lint Rule 6).")
    else:
        print(f"\n  [OK] mean <= {thr} bd -- no simplification trigger.")
    if n < 3:
        print(f"  [note] only {n}/3 cells measured; aggregate is provisional until n>=3.")
    # Paste-ready block for family.yaml § multiple_testing.
    print("\n  family.yaml § multiple_testing paste-block:")
    print("    process_cost:")
    print(f"      cycle_time_days_mean: {summary['cycle_time_days_mean']}")
    print(f"      cycle_time_days_p75: {summary['cycle_time_days_p75']}")
    print(f"      n_measured: {n}")
    print(f"      threshold_for_simplification: {thr}  # business day")


def _selfcheck() -> int:
    # Two business days (Mon -> Wed), and a same-day zero.
    assert business_days_between("2026-06-01 09:00:00 UTC",
                                 "2026-06-03 09:00:00 UTC") == 2.0
    assert business_days_between("2026-06-01 09:00:00 UTC",
                                 "2026-06-01 17:00:00 UTC") == 0.0
    # Weekend skip: Fri -> Mon = 1 business day.
    assert business_days_between("2026-06-05 09:00:00 UTC",
                                 "2026-06-08 09:00:00 UTC") == 1.0
    fake = {"timeline": {"pre_reg_authored_at": "2026-06-01 09:00:00 UTC",
                         "family_committed_at": "2026-06-02 09:00:00 UTC"}}
    assert cycle_time_days(fake) == 1.0
    assert cycle_time_days({"timeline": {}}) is None
    assert _parse_ts("2026-06-01T09:00:00Z").year == 2026
    print("process_cost self-check PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selfcheck", action="store_true", help="run internal checks and exit")
    sub = ap.add_subparsers(dest="cmd")

    rec = sub.add_parser("record", help="stamp one timeline stage in a manifest.json")
    rec.add_argument("--manifest", type=Path, required=True)
    rec.add_argument("--stage", choices=STAGES, required=True)
    rec.add_argument("--when", default=None, help="override timestamp (default: now UTC)")

    rep = sub.add_parser("report", help="aggregate cycle times across runs")
    rep.add_argument("--runs-dir", type=Path, default=Path("ars/runs"))
    rep.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_BUSINESS_DAYS)

    args = ap.parse_args(argv)

    if args.selfcheck:
        return _selfcheck()
    if args.cmd == "record":
        m = record_timestamp(args.manifest, args.stage, args.when)
        print(f"recorded {args.stage} = {m['timeline'][args.stage]} -> {args.manifest}")
        return 0
    if args.cmd == "report":
        _print_report(aggregate(args.runs_dir, args.threshold))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
