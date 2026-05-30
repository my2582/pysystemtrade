"""Family matrix dashboard — single-page visual status of a research family.

Handoff: docs/arki/handoff_unified_cpc_reporting_2026-05-31.md (step 5).

Reads ars/families/<family>/family.yaml for the Panel-A status grid + the
multiple-testing header + the DSR threshold. The findings-elasticity table and
the queue top-5 are sourced from findings.md / queue.md as structured data with
a provenance stamp (markdown-table parsing is fiddly and these change rarely).

Output: arki/reports/family/<family>_matrix.html (plain HTML/CSS, no JS frameworks
beyond a single inline Plotly for the DSR timeline — same style as CPC v1 Arki).

  venv/bin/python scripts/build_family_matrix.py \
      --family-yaml ars/families/futures_momentum/family.yaml \
      --reports-date 2026-05-31 \
      --out arki/reports/family/futures_momentum_matrix.html
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Status code → (badge, css-class). Source: registry/family cell statuses.
STATUS = {
    "promoted": ("✅PRO", "pro"),
    "promoted_post_hoc": ("✅PRO*", "pro"),
    "measurement": ("📊MEAS", "meas"),
    "registered_pending_remediation": ("⚠REM", "rem"),
    "falsified": ("❌FAL", "fal"),
    "refuted": ("❌REF", "fal"),
    "pre_registered_queued": ("⏳QUE", "que"),
}

# DSR self-correcting-loop timeline. Source: family.yaml + pre-reg §10 / §5.1.1.
DSR_TIMELINE = [
    {"n": 41, "thr": 0.314, "lock": "pre-TBM family baseline", "date": "2026-05-29"},
    {"n": 50, "thr": 0.325, "lock": "tbm_meta_us10_baseline_1m lock (+8)", "date": "2026-05-30"},
    {"n": 58, "thr": 0.3326, "lock": "tbm_meta_us10_tmax40 sensitivity lock (+8)", "date": "2026-05-31"},
]

# Elasticity rows — sourced from findings.md (Panel A clean-pair audit) 2026-05-31.
ELASTICITY = [
    ("vol_estimator (carver vs martin)", "≈ 0", "0.0035", "2",
     "near-zero on US10 at integer+cap; UNTESTED elsewhere / in Panel B", "clean"),
    ("overlay (none → carry/sMOM/dMOM/fast/TBM)", "mixed", "varies", "4",
     "high-RISK axis: 3 falsified, sMOM +0.255 pre-remediation, TBM_meta UNTESTED→now MEAS", "clean"),
    ("rule_structure (single_ema2 vs 6-speed)", "hint 6sp>single", "0.039", "0",
     "NO CLEAN PAIR — confounded with exec_profile (de-confound cell queued #2)", "confound"),
    ("exec_profile (numpy vs carver_native)", "hint native>numpy", "0.084", "0",
     "NO CLEAN PAIR — same confound as rule_structure", "confound"),
    ("capital_usd (50k vs 1m)", "≈0 Sharpe, +skew", "0.020 / 1.88", "3",
     "Sharpe capital-invariant on US10; per-trade skew grows at $1M", "clean"),
]

# Queue top-5 — sourced from queue.md 2026-05-31.
QUEUE = [
    ("tbm_meta_us10_baseline_1m", "in_progress→MEASURED", "8",
     "overlay axis untested level — DONE: meta DSR-uplift +0.0115, near-floor sizer (g_max 0.551)"),
    ("rule_structure_deconfound_us10", "queued", "1",
     "resolves the only n=0-clean-pair axis (single_ema2 + carver_native vs 6-speed)"),
    ("vol_estimator_transport_to_bund", "queued", "2",
     "confirm/refute ≈0 vol_estimator finding outside US10"),
    ("smom_remediation", "blocked", "2",
     "sMOM +0.255 lift pre-downgrade; blocked on sizing-rule fix"),
    ("panel_B_open_dm_rates_5", "queued", "5",
     "opens Panel B (DM_rates_5, equal_weight, TS_only); waits on de-confound #2"),
]


def _cell_link(slug: str, reports_date: str) -> str | None:
    """Click-through to the cell's CPC v1 HTML if we generated one."""
    rel = f"../{reports_date}/cells/{slug}_cpc.html"
    p = ROOT / "arki/reports" / reports_date / "cells" / f"{slug}_cpc.html"
    return rel if p.exists() else None


def render_status_grid(fam: dict, reports_date: str) -> str:
    cells = fam.get("panel_A_single_instrument", {}).get("cells", [])
    head = ('<thead><tr><th>cell_id</th><th>inst</th><th>vol_est</th><th>rule</th>'
            '<th>overlay</th><th>exec_profile</th><th>cap</th><th>status</th>'
            '<th>Sharpe</th><th>report</th></tr></thead>')
    body = []
    for c in cells:
        dv = c.get("dim_values", {})
        spec = dv.get("spec", {})
        exe = dv.get("exec_profile", {})
        status = c.get("status", "")
        badge, cls = STATUS.get(status, (status, "que"))
        sh = c.get("sharpe_net", "")
        sh = "" if sh in (None, "pending") else (f"{sh:.3f}" if isinstance(sh, (int, float)) else sh)
        link = _cell_link(c["cell_id"], reports_date)
        link_html = f'<a href="{link}">CPC ↗</a>' if link else "—"
        body.append(
            f'<tr><td class="slug">{c["cell_id"]}</td>'
            f'<td>{dv.get("universe", {}).get("instrument", "")}</td>'
            f'<td>{spec.get("vol_estimator", "")}</td>'
            f'<td>{spec.get("rule_structure", "")[:24]}</td>'
            f'<td>{spec.get("overlay", "")}</td>'
            f'<td>{exe.get("profile", "")}</td>'
            f'<td>{exe.get("capital_usd", "")}</td>'
            f'<td class="st {cls}">{badge}</td>'
            f'<td>{sh}</td><td>{link_html}</td></tr>')
    return '<table class="grid">' + head + '<tbody>' + ''.join(body) + '</tbody></table>'


def render_dsr_timeline() -> str:
    trace = [{
        "x": [d["n"] for d in DSR_TIMELINE],
        "y": [d["thr"] for d in DSR_TIMELINE],
        "type": "scatter", "mode": "lines+markers+text",
        "text": [f'N={d["n"]}<br>{d["thr"]}' for d in DSR_TIMELINE],
        "textposition": "top left",
        "line": {"color": "#265844", "width": 2},
        "marker": {"size": 9, "color": "#d97706"},
        "name": "expected_max_sharpe_at_N",
    }]
    rows = ''.join(f'<tr><td>{d["date"]}</td><td>{d["n"]}</td><td>{d["thr"]}</td>'
                   f'<td>{d["lock"]}</td></tr>' for d in DSR_TIMELINE)
    return (
        '<div id="dsr" style="height:320px;"></div>'
        f'<script>Plotly.newPlot("dsr", {json.dumps(trace)}, '
        '{margin:{l:60,r:20,t:30,b:50}, yaxis:{title:"expected max Sharpe (ann)"}, '
        'xaxis:{title:"n_configs_searched (N)"}, '
        'title:"DSR threshold — self-correcting loop"});</script>'
        '<table class="grid"><thead><tr><th>lock date</th><th>N</th><th>threshold</th>'
        f'<th>triggering event</th></tr></thead><tbody>{rows}</tbody></table>'
        '<p class="tnote">Locking pre-regs RAISES the absolute-promotion bar for ALL cells '
        '(arki.utils.dsr.expected_max_sharpe, sr_trials_std=0.1426, ann=256).</p>')


def render_elasticity() -> str:
    head = ('<thead><tr><th>Axis</th><th>Direction</th><th>mean Δ Sharpe</th>'
            '<th>n clean pairs</th><th>Tentative read</th></tr></thead>')
    body = []
    for axis, direction, delta, n, read, kind in ELASTICITY:
        cls = "confound" if kind == "confound" else ""
        body.append(f'<tr class="{cls}"><td>{axis}</td><td>{direction}</td><td>{delta}</td>'
                    f'<td>{n}</td><td class="read">{read}</td></tr>')
    return ('<table class="grid">' + head + '<tbody>' + ''.join(body) + '</tbody></table>'
            '<p class="tnote">Direction-only (n_pairs ≤ 2). Confounded pairs (n=0) shaded. '
            'No cross-panel inheritance. Source: findings.md (2026-05-31).</p>')


def render_queue() -> str:
    head = ('<thead><tr><th>#</th><th>cell_id</th><th>status</th>'
            '<th>grid size</th><th>resolves</th></tr></thead>')
    body = ''.join(f'<tr><td>{i+1}</td><td class="slug">{c}</td><td>{s}</td>'
                   f'<td>{g}</td><td class="read">{w}</td></tr>'
                   for i, (c, s, g, w) in enumerate(QUEUE))
    return ('<table class="grid">' + head + f'<tbody>{body}</tbody></table>'
            '<p class="tnote">Elasticity-ranked. Source: queue.md (2026-05-31).</p>')


def build(family_yaml: Path, reports_date: str, out: Path, now_utc: str):
    fam = yaml.safe_load(family_yaml.read_text())["family"]
    mt = fam.get("multiple_testing", {})
    thesis = (fam.get("thesis", "").strip().split("\n\n")[0]).replace("\n", " ")

    legend = ' · '.join(f'<span class="st {cls}">{badge}</span>'
                        for badge, cls in STATUS.values())

    css = """
  body{font-family:-apple-system,"SF Pro Text",Helvetica,sans-serif;max-width:1180px;margin:24px auto;padding:0 18px;color:#1a1a1a;}
  h1{font-family:"Cormorant Garamond",Georgia,serif;font-size:30px;color:#265844;margin-bottom:2px;}
  h2{font-family:"Cormorant Garamond",Georgia,serif;font-size:22px;color:#265844;border-bottom:1px solid #d0d4cd;padding-bottom:4px;margin-top:30px;}
  table{border-collapse:collapse;width:100%;font-size:11.5px;margin-bottom:6px;}
  th,td{padding:4px 6px;border-bottom:1px solid #e5e7eb;text-align:left;}
  th{background:#f5f7f4;color:#265844;}
  td.slug{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;}
  td.read{color:#374151;font-size:10.5px;}
  td.st,span.st{text-align:center;font-weight:700;border-radius:3px;padding:2px 6px;font-size:10.5px;}
  .pro{background:#e6f4ea;color:#166534;} .meas{background:#e0f2fe;color:#075985;}
  .rem{background:#fef9c3;color:#854d0e;} .fal{background:#fce8e6;color:#991b1b;}
  .que{background:#ede9fe;color:#5b21b6;}
  tr.confound td{background:#fafafa;color:#9ca3af;}
  .meta{color:#6b7280;font-size:12px;margin-bottom:8px;}
  .thesis{background:#f8f9f6;border-left:4px solid #265844;padding:10px 14px;font-size:12.5px;line-height:1.5;border-radius:4px;margin:10px 0 4px;}
  .kpi{display:inline-block;background:#eef0eb;border-radius:4px;padding:6px 12px;margin:4px 8px 4px 0;font-size:12px;}
  .kpi b{color:#265844;font-size:15px;}
  .tnote{color:#6b7280;font-size:11px;margin:2px 0 14px;line-height:1.4;}
  .legend{font-size:11px;color:#4a4a4a;margin:6px 0 0;}
  a{color:#0891b2;text-decoration:none;} a:hover{text-decoration:underline;}
"""
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{fam['name']} — family matrix</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>{css}</style></head><body>

<h1>{fam['name']} — family matrix</h1>
<p class="meta">Single-page family status dashboard · generated {now_utc} ·
source: <code>{family_yaml.relative_to(ROOT)}</code> + findings.md + queue.md</p>

<div class="thesis">{thesis}</div>
<div>
  <span class="kpi">n_configs_searched <b>{mt.get('n_configs_searched')}</b></span>
  <span class="kpi">expected_max_Sharpe@N <b>{mt.get('expected_max_sharpe_at_N')}</b></span>
  <span class="kpi">cells registered <b>{mt.get('n_cells_registered')}</b></span>
  <span class="kpi">pre-reg queued <b>{mt.get('n_cells_pre_registered_queued')}</b></span>
  <span class="kpi">selection correction <b>{mt.get('selection_correction', '')}</b></span>
</div>
<p class="legend">Legend: {legend}</p>

<h2>Panel A — single-instrument status grid</h2>
{render_status_grid(fam, reports_date)}

<h2>DSR threshold timeline (self-correcting loop)</h2>
{render_dsr_timeline()}

<h2>Panel A elasticity (clean-pair audit)</h2>
{render_elasticity()}

<h2>Queue — top 5 (elasticity-ranked)</h2>
{render_queue()}

<h2>Linked artifacts</h2>
<ul style="font-size:12px;color:#374151;">
  <li><a href="../../../ars/families/futures_momentum/family.yaml">family.yaml</a> (Layer 2 SOT)</li>
  <li><a href="../../../ars/families/futures_momentum/findings.md">findings.md</a> (Layer 3 elasticity)</li>
  <li><a href="../../../ars/families/futures_momentum/queue.md">queue.md</a></li>
  <li>CPC v1 reports: <a href="../{reports_date}/cells/">cells/</a> · <a href="../{reports_date}/comparisons/">comparisons/</a></li>
  <li>Registry: <code>ars/runs/registry.yaml</code></li>
</ul>
<p class="tnote">Format: family matrix v1 · builder: scripts/build_family_matrix.py ·
handoff: docs/arki/handoff_unified_cpc_reporting_2026-05-31.md</p>

</body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"  wrote {out.relative_to(ROOT)}  ({out.stat().st_size/1024:.1f} KB)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Family matrix dashboard builder.")
    ap.add_argument("--family-yaml", required=True)
    ap.add_argument("--reports-date", required=True, help="date dir under arki/reports/ for CPC links")
    ap.add_argument("--out", required=True)
    ap.add_argument("--now-utc", default=None)
    args = ap.parse_args()
    fam = Path(args.family_yaml)
    fam = fam if fam.is_absolute() else ROOT / fam
    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    now_utc = args.now_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("=== family matrix ===")
    build(fam, args.reports_date, out, now_utc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
