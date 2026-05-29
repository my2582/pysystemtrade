#!/usr/bin/env python
"""Aggregate cost_actuals across all evidence packs to produce a session-cost
dashboard.

Honest framing: this is a SOFT-signal aggregator, not a real-time enforcement
tool. Helps the owner see which experiment classes are cheap vs expensive
across cumulative work, and helps the AI flag if a session is drifting
beyond the implied budget envelope.

Usage:
    venv/bin/python scripts/session_cost_report.py
    # → prints summary table to stdout
    # → optionally writes outputs/cost_dashboard.md
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_PACKS = ROOT / "ars" / "evidence_packs"


def load_verdict(pack: Path) -> dict | None:
    verdict_path = pack / "verdict.json"
    if not verdict_path.exists():
        return None
    try:
        return json.loads(verdict_path.read_text())
    except Exception:
        return None


def collect_cost_data() -> list[dict]:
    rows = []
    if not EVIDENCE_PACKS.exists():
        return rows
    for pack in sorted(EVIDENCE_PACKS.iterdir()):
        if not pack.is_dir() or pack.name == "_template":
            continue
        verdict = load_verdict(pack)
        if verdict is None:
            continue
        cost = verdict.get("cost_actuals") or {}
        rows.append({
            "slug": pack.name,
            "status": verdict.get("status", "unknown"),
            "tokens_used": cost.get("tokens_used"),
            "tokens_budget": cost.get("tokens_budget"),
            "tokens_over_budget_pct": cost.get("tokens_over_budget_pct"),
            "time_min": cost.get("time_min"),
            "time_budget_min": cost.get("time_budget_min"),
            "iterations": cost.get("iterations"),
            "budget_declared": cost.get("budget_declared", False),
            "retrospective": cost.get("cost_retrospective"),
        })
    return rows


def format_table(rows: list[dict]) -> str:
    if not rows:
        return "No evidence packs with cost data yet.\n"
    lines = []
    lines.append("| Slug | Status | Tokens used | Budget | Over % | Time min | Budget declared |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for r in rows:
        tu = f"{r['tokens_used']:,}" if r['tokens_used'] else "—"
        tb = f"{r['tokens_budget']:,}" if r['tokens_budget'] else "—"
        ov = f"{r['tokens_over_budget_pct']:+.1f}%" if r['tokens_over_budget_pct'] is not None else "—"
        tm = f"{r['time_min']:.0f}" if r['time_min'] else "—"
        bd = "✓" if r['budget_declared'] else "—"
        lines.append(f"| {r['slug']} | {r['status']} | {tu} | {tb} | {ov} | {tm} | {bd} |")
    return "\n".join(lines)


def summarise(rows: list[dict]) -> str:
    if not rows:
        return "No data."
    declared = [r for r in rows if r['budget_declared']]
    total_packs = len(rows)
    declared_pct = 100.0 * len(declared) / total_packs if total_packs else 0
    over_budget = [r for r in rows if r['tokens_over_budget_pct'] and r['tokens_over_budget_pct'] > 50.0]
    summary = [
        f"- Evidence packs scanned: {total_packs}",
        f"- Budget declared: {len(declared)} ({declared_pct:.0f}%)",
        f"- Over budget (>50%): {len(over_budget)}",
    ]
    return "\n".join(summary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None,
                    help="Optional path to write the dashboard markdown.")
    args = ap.parse_args()

    rows = collect_cost_data()
    table = format_table(rows)
    summary = summarise(rows)

    out_text = f"""# Session cost dashboard

**Date**: {date.today().isoformat()}
**Generator**: scripts/session_cost_report.py

## Summary

{summary}

## Per-experiment cost detail

{table}

## How to read this

- Budget declared 0% means the framework has data but no pre-registered budgets to compare against.
  This is fine for early adoption; the actuals accumulate so we can see cost patterns.
- "Over budget >50%" is a SOFT signal. Each over-budget entry should have a `cost_retrospective`
  field in its verdict.json describing why.
- Cumulative learning goal: identify experiment classes (single-instrument backtest, multi-variant
  overlay, paper compliance check, ...) and their typical token cost so future budgets are realistic.

## What this dashboard does NOT do

- Does not gate execution.
- Does not abort in-flight work.
- Does not replace verdict.json — it is an aggregation view only.

Updated by re-running this script. See docs/standards/ai_native_research_primitives.md §7 for design rationale.
"""

    print(out_text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out_text)
        print(f"\n[written to] {args.out}")


if __name__ == "__main__":
    main()
