"""CPC v1 Arki — Cohort Performance Card v1, futures-momentum adaptation.

Adapts b3-saa-etf's `scripts/build_cpc_v1.py` to the Arki futures-momentum
family. ONE canonical HTML per cell (or per comparison), consolidating what was
previously split across ars/runs report.html + arki/results trade-analysis +
aggregator HTMLs.

Handoff: docs/arki/handoff_unified_cpc_reporting_2026-05-31.md (steps 3-4).

Key differences vs b3 CPC v1
----------------------------
- ann_factor = 256 (daily futures), not 12 (monthly SGD).
- No FX conversion — all cells are already in % / native-unit equity.
- Benchmark anchor = a prior family cell (e.g. martin_baseline_us10_1m), not ACWI.
- Risk/return table uses NATIVE summary.csv values (ARS: preserve engine
  outputs). The equity_curves.csv day-to-day diffs are LUMPY (a handful of real
  bond-crash days give ~160% annualised "vol") and do NOT reproduce the engine's
  summary Sharpe — they are the realised-equity PATH, not the clean vol-targeted
  daily-return stream. So:
    * risk table  -> native summary.csv only
    * cum chart   -> equity-curve path, rebased, "native units" (honest label)
    * monthly grid-> month-over-month delta of the equity path, sign-coloured
    * comparison  -> NATIVE-metric lift table (Sharpe / MaxDD / Skew), which is
                     exactly pre-reg §7's "Lifts reported". Capture / alpha-beta
                     regression are intentionally OMITTED (would require a
                     trustworthy daily-return series that was not persisted).

Arki extensions (TBM cells only; skipped gracefully for non-TBM):
  - acceptance gates table (G-TBM1..6 + G-recon + G-family-DSR)
  - TBM diagnostics block (uniqueness, g-distribution, CPCV F1, gap-rule audit)
  - per-trade ledger (sign-episode trades + summary stats)
  - family context block (multiple-testing N, expected_max_sharpe_at_N)
  - verification anchors block (sigma median + barrier values from manifest)

CLI (covers all four handoff outputs)
-------------------------------------
  # single cell vs a baseline (outputs 1, 2, 3)
  venv/bin/python scripts/build_cpc_v1_arki.py \
      --cells "tbm_meta_us10_baseline_1m=ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m;\
               exec_friction_martin_baseline_us10_1m=ars/runs/20260529T172206Z_martin_baseline_us10_1m" \
      --bench-slug exec_friction_martin_baseline_us10_1m \
      --title "TBM meta-label US10 baseline vs g=1 Martin — CPC v1" \
      --family-yaml ars/families/futures_momentum/family.yaml \
      --out arki/reports/2026-05-31/cells/tbm_meta_us10_baseline_1m_cpc.html

The FIRST cell in --cells is the focus cell (its gates / diagnostics / ledger /
mechanism card render). --bench-slug names which cell is the comparison anchor
for the native lift table. Omit --bench-slug for a stand-alone report.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
ANN = 256
MECH_CARD_DIR = ROOT / "arki/reports/_mechanism_cards"


# ============================================================================
# Cell loading
# ============================================================================
def _read_summary_row(run_dir: Path) -> dict:
    df = pd.read_csv(run_dir / "summary.csv")
    return df.iloc[0].to_dict()


def _read_manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _read_equity(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(run_dir / "equity_curves.csv", index_col=0, parse_dates=True)


def _read_trades(run_dir: Path) -> pd.DataFrame | None:
    cands = sorted(run_dir.glob("trades_*.csv"))
    if not cands:
        return None
    return pd.read_csv(cands[0])


class Cell:
    """A single experiment cell loaded from its ars/runs/<run> dir."""

    def __init__(self, slug: str, run_dir: str | Path):
        self.slug = slug
        self.run_dir = (ROOT / run_dir) if not Path(run_dir).is_absolute() else Path(run_dir)
        self.summary = _read_summary_row(self.run_dir)
        self.manifest = _read_manifest(self.run_dir)
        self.equity = _read_equity(self.run_dir)
        self.trades = _read_trades(self.run_dir)
        # TBM cells expose the meta-vs-g1 gate panel in summary.csv.
        self.is_tbm = "sharpe_meta_full_sample_ann" in self.summary

    # -- equity series for the primary curve (rebased path) -----------------
    def primary_equity_col(self) -> str:
        if "meta_best" in self.equity.columns:
            return "meta_best"
        return self.equity.columns[0]

    def primary_equity(self) -> pd.Series:
        return self.equity[self.primary_equity_col()].dropna()

    # -- native headline metrics for the risk table -------------------------
    def risk_rows(self) -> list[tuple[str, dict]]:
        """Return [(label, metrics_dict), ...]. TBM cells emit two rows
        (meta_best + g=1 baseline); exec cells emit one."""
        s = self.summary
        n = int(s.get("n_days", len(self.equity)))
        if self.is_tbm:
            meta = {
                "Ann Ret %": np.nan, "Vol %": np.nan,
                "Sharpe": _f(s.get("sharpe_meta_full_sample_ann")),
                "Sortino": np.nan,
                "Max DD %": _f(s.get("G_TBM3_dd_meta_pct")),
                "Calmar": np.nan,
                "Skew": _f(s.get("G_TBM4_skew_meta")),
                "n": n,
            }
            base = {
                "Ann Ret %": np.nan, "Vol %": np.nan,
                "Sharpe": _f(s.get("sharpe_baseline_g1_ann")),
                "Sortino": np.nan,
                "Max DD %": _f(s.get("G_TBM3_dd_baseline_pct")),
                "Calmar": np.nan,
                "Skew": _f(s.get("G_TBM4_skew_baseline")),
                "n": n,
            }
            return [(f"{self.slug} (meta-sized)", meta),
                    (f"{self.slug} (g=1 internal baseline)", base)]
        # exec / martin cell — native fields
        annret = _f(s.get("ann_return_net_pct"))
        maxdd = _f(s.get("max_drawdown_pct_geom"))
        calmar = (annret / abs(maxdd)) if (not np.isnan(annret) and not np.isnan(maxdd) and maxdd < 0) else np.nan
        row = {
            "Ann Ret %": annret,
            "Vol %": _f(s.get("ann_vol_pct")),
            "Sharpe": _f(s.get("sharpe_net")),
            "Sortino": np.nan,  # not persisted natively; not fabricated
            "Max DD %": maxdd,
            "Calmar": calmar,
            "Skew": _f(s.get("skew_daily")),
            "n": n,
        }
        return [(self.slug, row)]

    def headline(self) -> dict:
        """Single canonical metric dict for lift comparisons (native)."""
        s = self.summary
        if self.is_tbm:
            return {
                "Sharpe": _f(s.get("sharpe_meta_full_sample_ann")),
                "Max DD %": _f(s.get("G_TBM3_dd_meta_pct")),
                "Skew": _f(s.get("G_TBM4_skew_meta")),
            }
        return {
            "Sharpe": _f(s.get("sharpe_net")),
            "Max DD %": _f(s.get("max_drawdown_pct_geom")),
            "Skew": _f(s.get("skew_daily")),
        }


def _f(v) -> float:
    try:
        if v is None:
            return np.nan
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def _fmt(v, dp: int = 3) -> str:
    return "—" if (v is None or (isinstance(v, float) and pd.isna(v))) else f"{v:.{dp}f}"


# ============================================================================
# Renderers — reused from b3 (mechanism card) + Arki-specific
# ============================================================================
def _escape_latex_for_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_mechanism_card(mc: dict) -> str:
    """Three-subsection cheatsheet card (b3 render_mechanism_card, verbatim shape)."""
    cf, tr, ac = mc.get("core_formula", {}), mc.get("triggering", {}), mc.get("action", {})
    cf_block = ""
    if cf:
        latex = _escape_latex_for_html(cf.get("latex", ""))
        latex_html = f'<div class="mc-formula">\\[{latex}\\]</div>' if latex else ""
        cf_block = f"""
  <div class="mc-section"><h3 class="mc-h">1. Core formula tested</h3>
    {f'<p class="mc-name"><b>{cf["name"]}</b></p>' if cf.get("name") else ""}
    {latex_html}
    {f'<p class="mc-vars">{cf["vars"]}</p>' if cf.get("vars") else ""}
    {f'<p class="mc-note">{cf["note"]}</p>' if cf.get("note") else ""}</div>"""
    tr_block = ""
    if tr:
        scale_latex = _escape_latex_for_html(tr.get("scale_factor", "") or tr.get("latex", ""))
        scale_html = f'<div class="mc-formula">\\[{scale_latex}\\]</div>' if scale_latex else ""
        tr_block = f"""
  <div class="mc-section"><h3 class="mc-h">2. Triggering condition</h3>
    {f'<p class="mc-rule">{tr["rule"]}</p>' if tr.get("rule") else ""}
    {scale_html}
    {f'<p class="mc-cells"><b>Cells in sweep:</b> {tr["cells"]}</p>' if tr.get("cells") else ""}</div>"""
    ac_block = ""
    if ac:
        rows = []
        for k, label in [("trade_shape", "Trade shape"), ("observation", "Observation date (T)"),
                         ("trade", "Trade date (T+1)"), ("between_rebals", "Between rebals"),
                         ("leverage_cap", "Leverage / sizing cap"), ("re_entry", "Re-entry rule")]:
            v = ac.get(k)
            if v:
                rows.append(f'<tr><th class="mc-row-h">{label}</th><td>{v}</td></tr>')
        if rows:
            ac_block = f"""
  <div class="mc-section"><h3 class="mc-h">3. Action</h3>
    <table class="mc-action"><tbody>{"".join(rows)}</tbody></table></div>"""
    applies = mc.get("applies_to")
    applies_html = f'<p class="mc-applies"><b>Applies to:</b> {applies}</p>' if applies else ""
    return f"""<section class="mechanism-card"><h2>Mechanism cheatsheet</h2>
  {applies_html}{cf_block}{tr_block}{ac_block}</section>"""


def render_risk_table(rows: list[tuple[str, dict]]) -> str:
    head = ('<thead><tr><th>Series</th><th>Ann Ret %</th><th>Ann Vol %</th><th>Sharpe</th>'
            '<th>Sortino</th><th>Max DD %</th><th>Calmar</th><th>Skew</th><th>n (days)</th></tr></thead>')
    body = []
    for label, m in rows:
        body.append(
            f'<tr><td>{label}</td><td>{_fmt(m["Ann Ret %"], 2)}</td><td>{_fmt(m["Vol %"], 2)}</td>'
            f'<td>{_fmt(m["Sharpe"])}</td><td>{_fmt(m["Sortino"])}</td><td>{_fmt(m["Max DD %"], 2)}</td>'
            f'<td>{_fmt(m["Calmar"])}</td><td>{_fmt(m["Skew"])}</td><td>{m["n"]}</td></tr>')
    note = ('<p class="tnote">Native engine values from each cell\'s <code>summary.csv</code>. '
            'Sortino / (Ann Ret, Vol for TBM cells) are not persisted natively and shown as "—" '
            'rather than recomputed from the lumpy realised-equity path.</p>')
    return '<table class="risk">' + head + '<tbody>' + ''.join(body) + '</tbody></table>' + note


def render_lift_table(focus: Cell, bench: Cell) -> str:
    fh, bh = focus.headline(), bench.headline()
    head = (f'<thead><tr><th>Metric</th><th>{focus.slug}</th><th>{bench.slug}</th>'
            '<th>Lift (focus − bench)</th></tr></thead>')
    # For Max DD, "better" = less negative -> lift = focus - bench (positive = improvement).
    body = []
    for metric, better_hint in [("Sharpe", "higher better"), ("Max DD %", "less-negative better"),
                                ("Skew", "higher better")]:
        fv, bv = fh.get(metric, np.nan), bh.get(metric, np.nan)
        lift = fv - bv if (not pd.isna(fv) and not pd.isna(bv)) else np.nan
        cls = ""
        if not pd.isna(lift):
            cls = "pos" if lift > 0 else ("neg" if lift < 0 else "zero")
        body.append(f'<tr><td>{metric} <span class="hint">({better_hint})</span></td>'
                    f'<td>{_fmt(fv, 3 if metric != "Max DD %" else 2)}</td>'
                    f'<td>{_fmt(bv, 3 if metric != "Max DD %" else 2)}</td>'
                    f'<td class="{cls}">{("" if pd.isna(lift) else f"{lift:+.3f}")}</td></tr>')
    note = ('<p class="tnote">Native-metric lifts (pre-reg §7). Capture / alpha-β regression are '
            'intentionally omitted — they require a trustworthy daily-return series, but only the '
            'lumpy realised-equity path is persisted (its diffs do not reproduce the engine Sharpe).</p>')
    return '<table class="lift">' + head + '<tbody>' + ''.join(body) + '</tbody></table>' + note


def render_cum_chart(cells: list[Cell], bench_slug: str | None) -> str:
    """Overlay each cell's realised-equity path, rebased to start at 100."""
    traces = []
    palette = ["#265844", "#d97706", "#2563eb", "#9a1a8a", "#0891b2", "#dc2626", "#6b7280", "#71B775"]
    ci = 0
    for cell in cells:
        # TBM cells carry both meta_best and baseline_g1 -> show both.
        cols = ["meta_best", "baseline_g1"] if "meta_best" in cell.equity.columns else [cell.equity.columns[0]]
        for col in cols:
            s = cell.equity[col].dropna()
            rebased = 100.0 + (s - s.iloc[0])
            name = f"{cell.slug}" if col not in ("meta_best", "baseline_g1") else f"{cell.slug}:{col}"
            color = "#9ca3af" if cell.slug == bench_slug else palette[ci % len(palette)]
            traces.append({
                "x": [d.strftime("%Y-%m-%d") for d in rebased.index],
                "y": [round(v, 4) for v in rebased.tolist()],
                "name": name, "type": "scatter", "mode": "lines",
                "line": {"color": color, "width": 1.8,
                         "dash": "dot" if col == "baseline_g1" else "solid"},
            })
            ci += 1
    return (
        '<div id="cumchart" style="height:440px;"></div>\n'
        f'<script>Plotly.newPlot("cumchart", {json.dumps(traces)}, '
        '{margin:{l:55,r:20,t:30,b:60}, '
        'yaxis:{title:"realised equity (native units, rebased +100)"}, '
        'xaxis:{title:"Date"}, legend:{orientation:"h", y:-0.18}, '
        'title:"Cumulative realised equity (native units)"});</script>'
        '<p class="tnote">Realised-equity PATH (native engine cumulative). Rebased to 100 at series '
        'start; linear scale (the series is an additive cumulative, not a NAV). Day-to-day diffs are '
        'lumpy (real bond-crash days) — read shape, not absolute level.</p>'
    )


def render_monthly_grid(series: pd.Series, label: str) -> str:
    """Month-over-month delta of the realised-equity path, sign-coloured.
    Honest: native cumsum units, NOT a return %."""
    monthly = series.resample("M").last().diff().dropna()
    tmp = monthly.to_frame("v")
    tmp["Year"], tmp["Month"] = tmp.index.year, tmp.index.month
    pivot = tmp.pivot(index="Year", columns="Month", values="v")
    pivot["YTD"] = pivot.sum(axis=1, min_count=1)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    head = '<thead><tr><th>Year</th>' + ''.join(f'<th>{m}</th>' for m in months) + '<th>YTD</th></tr></thead>'
    body = []
    for yr, row in pivot.iterrows():
        cells = []
        for mo in range(1, 13):
            v = row.get(mo, np.nan)
            if pd.isna(v):
                cells.append('<td class="na">—</td>')
            else:
                cls = "pos" if v > 0 else ("neg" if v < 0 else "zero")
                cells.append(f'<td class="{cls}">{v:+.1f}</td>')
        ytd = row["YTD"]
        ycls = "pos" if ytd > 0 else ("neg" if ytd < 0 else "zero")
        cells.append(f'<td class="{ycls} ytd"><b>{("" if pd.isna(ytd) else f"{ytd:+.1f}")}</b></td>')
        body.append(f'<tr><td><b>{yr}</b></td>' + ''.join(cells) + '</tr>')
    return (f'<h4>{label} — monthly Δ realised equity (native units, sign-coloured)</h4>'
            f'<table class="heatmap">{head}<tbody>' + ''.join(body) + '</tbody></table>')


# ---- TBM extensions --------------------------------------------------------
GATE_DEFS = [
    ("G-TBM1", "DSR uplift vs g=1", "G_TBM1_dsr_uplift", "G_TBM1_pass", "> 0"),
    ("G-TBM2", "PBO (combinatorial)", "G_TBM2_pbo", "G_TBM2_pass", "< 0.5"),
    ("G-TBM3", "MaxDD reduction", "G_TBM3_dd_delta_pct", "G_TBM3_pass", "≤ 0 (meta no worse)"),
    ("G-TBM4", "Skew preservation", "G_TBM4_skew_delta", "G_TBM4_pass", "≥ −0.20"),
    ("G-TBM5", "F1 vs naive base-rate", "G_TBM5_f1_lift", "G_TBM5_pass", "> +0.02"),
    ("G-TBM6", "g ∈ [0.30, 1.0] sanity", "G_TBM6_g_max_observed", "G_TBM6_pass", "0.30 ≤ g ≤ 1.0"),
    ("G-family-DSR", "Sharpe vs expected-max (reporting)", "G_family_DSR_sharpe_meta_ann",
     "G_family_DSR_passes_absolute", "> threshold (disclosure)"),
]


def _pass_cell(v) -> str:
    sv = str(v).strip().lower()
    if sv in ("true", "1", "1.0"):
        return '<td class="pass">PASS</td>'
    if sv in ("false", "0", "0.0"):
        return '<td class="fail">FAIL</td>'
    return '<td class="na">N/A</td>'


def render_acceptance_gates_table(s: dict) -> str:
    head = '<thead><tr><th>Gate</th><th>Test</th><th>Value</th><th>Threshold</th><th>Verdict</th></tr></thead>'
    body = []
    for gid, test, val_key, pass_key, thr in GATE_DEFS:
        val = s.get(val_key)
        val_s = _fmt(_f(val), 4) if val is not None else "—"
        body.append(f'<tr><td><b>{gid}</b></td><td>{test}</td><td>{val_s}</td>'
                    f'<td>{thr}</td>{_pass_cell(s.get(pass_key))}</tr>')
    # G-recon from the gap-rule consistency note (TBM summary lacks recon_diff; use events fraction)
    recon = s.get("reconciliation_diff_pct")
    if recon is not None:
        rv = _f(recon)
        verdict = '<td class="pass">PASS</td>' if abs(rv) < 5 else '<td class="fail">FAIL</td>'
        body.append(f'<tr><td><b>G-recon</b></td><td>|trade-sum vs daily-sum|</td>'
                    f'<td>{_fmt(rv, 3)}%</td><td>&lt; 5%</td>{verdict}</tr>')
    note = ('<p class="tnote">Stage-1 passes only if ALL of G-TBM1..6 + G-recon hold. '
            'G-family-DSR is a reporting/disclosure gate, not a falsification gate '
            '(pre-reg §4). PBO is N/A for single-config internal runs.</p>')
    return '<table class="gates">' + head + '<tbody>' + ''.join(body) + '</tbody></table>' + note


def render_tbm_diagnostics_block(s: dict) -> str:
    def g(k):
        return _fmt(_f(s.get(k)), 4)
    rows = [
        ("avg_uniqueness (label mean)", g("avg_uniqueness_label_mean"),
         "as-TBM-iid threshold 0.20; below ⇒ redundant labels"),
        ("g mean (CUSUM days)", g("g_mean_cusum_days"), "meta-sizer output on event days"),
        ("g mean (all days)", g("g_mean_all_days"), "full-sample sizer mean"),
        ("g delta mean |·|", g("g_delta_mean_abs"), "meta vs baseline sizer divergence"),
        ("g_min observed / g_max observed", f"{g('G_TBM6_g_min_observed')} / {g('G_TBM6_g_max_observed')}",
         "diagnostic-tree router: g_max &gt;0.75 collapse, &lt;0.60 no-signal"),
        ("CPCV F1 meta / naive / lift", f"{g('G_TBM5_f1_meta')} / {g('G_TBM5_f1_naive')} / {g('G_TBM5_f1_lift')}",
         "out-of-fold classifier vs majority-class base rate"),
        ("DSR meta / baseline / uplift", f"{g('dsr_meta')} / {g('dsr_baseline')} / {g('G_TBM1_dsr_uplift')}",
         "deflated Sharpe (arki.utils.dsr, ann=256)"),
        ("PBO", g("G_TBM2_pbo"), "N/A for single-config internal grid"),
    ]
    diag = ''.join(f'<tr><th class="mc-row-h">{k}</th><td><b>{v}</b></td><td class="note">{n}</td></tr>'
                   for k, v, n in rows)
    # gap-rule audit counters (5.2.a/b/c)
    gap = [
        ("n_cusum_events_total", s.get("n_cusum_events_total")),
        ("n_resets_rule_5_2_a (CUSUM reset)", s.get("n_resets_rule_5_2_a")),
        ("n_events_dropped_rewarmup_5_2_b", s.get("n_events_dropped_rewarmup_5_2_b")),
        ("n_events_dropped_cross_gap_5_2_c", s.get("n_events_dropped_cross_gap_5_2_c")),
        ("n_events_used_for_labels", s.get("n_events_used_for_labels")),
        ("events_used_fraction", _fmt(_f(s.get("events_used_fraction")), 4)),
        ("n_gaps_detected", s.get("n_gaps_detected")),
    ]
    gap_rows = ''.join(f'<tr><th class="mc-row-h">{k}</th><td><b>{v}</b></td></tr>' for k, v in gap)
    return (
        '<section class="diag"><h2>TBM diagnostics</h2>'
        '<table class="mc-action"><tbody>' + diag + '</tbody></table>'
        '<h4>Gap-rule audit (pre-reg §5.2.a/b/c)</h4>'
        '<table class="mc-action"><tbody>' + gap_rows + '</tbody></table>'
        '<p class="tnote">If events_used_fraction &lt; 0.75 the gap filtering is too aggressive '
        '(pre-reg §5.2). Touch detection mode: '
        f'{s.get("touch_detection_mode", "—")}</p></section>')


def render_per_trade_ledger(trades: pd.DataFrame | None, slug: str) -> str:
    if trades is None or trades.empty:
        return ""
    ret_col = "trade_return_pp" if "trade_return_pp" in trades.columns else None
    days_col = "days" if "days" in trades.columns else ("days_held" if "days_held" in trades.columns else None)
    n = len(trades)
    med_days = trades[days_col].median() if days_col else np.nan
    win = (trades[ret_col] > 0).mean() * 100 if ret_col else np.nan
    med_ret = trades[ret_col].median() if ret_col else np.nan
    mean_ret = trades[ret_col].mean() if ret_col else np.nan
    skew = trades[ret_col].skew() if ret_col else np.nan
    summary = (
        '<table class="risk"><thead><tr><th>n trades</th><th>median days</th><th>win rate %</th>'
        '<th>mean ret</th><th>median ret</th><th>skew (per-trade)</th></tr></thead><tbody>'
        f'<tr><td>{n}</td><td>{_fmt(med_days, 1)}</td><td>{_fmt(win, 1)}</td>'
        f'<td>{_fmt(mean_ret, 3)}</td><td>{_fmt(med_ret, 3)}</td><td>{_fmt(skew, 3)}</td></tr>'
        '</tbody></table>')
    # show the 12 largest-magnitude trades as a sample (full table would be huge for TBM)
    sample = ""
    if ret_col:
        top = trades.reindex(trades[ret_col].abs().sort_values(ascending=False).index).head(12)
        cols = [c for c in ["start", "end", "days", "sign", "bin", ret_col] if c in top.columns]
        hdr = ''.join(f'<th>{c}</th>' for c in cols)
        body = ''.join('<tr>' + ''.join(
            f'<td>{(f"{v:.3f}" if isinstance(v, float) else v)}</td>' for v in (r[c] for c in cols)) + '</tr>'
            for _, r in top.iterrows())
        sample = (f'<h4>12 largest-magnitude trades (of {n})</h4>'
                  f'<table class="risk"><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>')
    return ('<section class="ledger"><h2>Per-trade ledger</h2>'
            f'<p class="tnote">Sign-episode / TBM-event trades from <code>trades_*.csv</code> for '
            f'{slug}.</p>' + summary + sample + '</section>')


def render_family_context_block(family_yaml_path: Path | None, focus_slug: str, panel: str | None) -> str:
    if not family_yaml_path or not family_yaml_path.exists():
        return ""
    fam = yaml.safe_load(family_yaml_path.read_text())["family"]
    mt = fam.get("multiple_testing", {})
    cell = None
    for c in fam.get("panel_A_single_instrument", {}).get("cells", []):
        if c.get("cell_id") == focus_slug:
            cell = c
            break
    rows = [
        ("family", fam.get("name")),
        ("panel", panel or (cell.get("panel") if cell else "—")),
        ("n_configs_searched (multiple-testing N)", mt.get("n_configs_searched")),
        ("expected_max_sharpe_at_N (annualised)", mt.get("expected_max_sharpe_at_N")),
        ("selection_correction", mt.get("selection_correction")),
        ("annualization_factor", mt.get("annualization_factor")),
    ]
    if cell:
        rows += [("cell status", cell.get("status")),
                 ("cell internal_grid_size", cell.get("internal_grid_size")),
                 ("cell sharpe (registry)", cell.get("sharpe_net"))]
    body = ''.join(f'<tr><th class="mc-row-h">{k}</th><td>{v}</td></tr>' for k, v in rows)
    return ('<section class="famctx"><h2>Family context</h2>'
            '<table class="mc-action"><tbody>' + body + '</tbody></table>'
            '<p class="tnote">Every cell report shows where it sits in the family multiple-testing '
            'budget. The absolute-promotion bar is expected_max_sharpe_at_N; the self-correcting loop '
            'raises it as configs are searched (pre-reg §10).</p></section>')


def render_verification_block(manifest: dict) -> str:
    if not manifest:
        return ""
    keys = [
        ("vol estimator", manifest.get("vol_estimator_tag")),
        ("barrier PT (σ mult)", manifest.get("barrier_pt_sigma_mult")),
        ("barrier SL (σ mult)", manifest.get("barrier_sl_sigma_mult")),
        ("T_max (business days)", manifest.get("t_max_business_days")),
        ("CUSUM κ (σ mult)", manifest.get("cusum_kappa")),
        ("g_min / g_max", f"{manifest.get('g_min')} / {manifest.get('g_max')}"),
        ("gap threshold (days)", manifest.get("gap_threshold_days")),
        ("ann_factor", manifest.get("ann_factor")),
        ("verification anchor", manifest.get("verification_anchor")),
        ("git_sha", manifest.get("git_sha")),
    ]
    keys = [(k, v) for k, v in keys if v is not None]
    if not keys:
        return ""
    body = ''.join(f'<tr><th class="mc-row-h">{k}</th><td><code>{v}</code></td></tr>' for k, v in keys)
    return ('<section class="verif"><h2>Verification anchors</h2>'
            '<table class="mc-action"><tbody>' + body + '</tbody></table>'
            '<p class="tnote">σ median 0.3871 (target 0.39±0.03) PASS 2026-05-30; PT=8σ=3.097pp, '
            'SL=4σ=1.548pp (pre-reg §5.1). Sanity anchors, not gates.</p></section>')


# ============================================================================
# CSS / HTML shell
# ============================================================================
CSS = """
  body { font-family: -apple-system, "SF Pro Text", Helvetica, sans-serif; max-width: 1140px; margin: 24px auto; padding: 0 18px; color: #1a1a1a; }
  h1 { font-family: "Cormorant Garamond", Georgia, serif; font-size: 30px; color: #265844; margin-bottom: 4px; }
  h2 { font-family: "Cormorant Garamond", Georgia, serif; font-size: 22px; color: #265844; border-bottom: 1px solid #d0d4cd; padding-bottom: 4px; margin-top: 32px; }
  h3 { font-size: 14px; color: #4a4a4a; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 22px; }
  h4 { font-size: 12px; color: #666; margin-top: 12px; margin-bottom: 4px; }
  table { border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 6px; }
  th, td { padding: 4px 6px; border-bottom: 1px solid #e5e7eb; text-align: right; }
  th { background: #f5f7f4; color: #265844; text-align: center; }
  td:first-child, th:first-child { text-align: left; }
  table.heatmap td { font-size: 10.5px; padding: 3px 4px; min-width: 40px; }
  td.pos { background: #e6f4ea; color: #166534; }
  td.neg { background: #fce8e6; color: #991b1b; }
  td.zero { background: #f5f5f5; color: #666; }
  td.ytd { border-left: 2px solid #265844; font-weight: 600; }
  td.na { color: #bbb; }
  td.pass { background: #e6f4ea; color: #166534; font-weight: 700; text-align: center; }
  td.fail { background: #fce8e6; color: #991b1b; font-weight: 700; text-align: center; }
  .hint { color: #9ca3af; font-weight: 400; font-size: 10.5px; }
  .tnote { color: #6b7280; font-size: 11px; margin: 2px 0 12px; line-height: 1.4; }
  td.note { text-align: left; color: #6b7280; font-size: 11px; }
  .caveat { background: #fffbe6; border-left: 3px solid #d4a017; padding: 8px 12px; font-size: 12px; margin: 12px 0; }
  .meta { color: #6b7280; font-size: 12px; margin-bottom: 14px; }
  .stamp { color: #9ca3af; font-size: 11px; }
  section.mechanism-card, section.diag, section.famctx, section.verif, section.ledger { background: #f8f9f6; border: 1px solid #d0d4cd; border-left: 4px solid #265844; padding: 12px 18px 16px; margin: 18px 0; border-radius: 4px; }
  section.mechanism-card h2, section.diag h2, section.famctx h2, section.verif h2, section.ledger h2 { margin-top: 0; }
  .mc-applies { font-size: 12px; color: #4a4a4a; margin: 4px 0 12px; }
  .mc-section { margin: 12px 0; padding: 8px 0 4px; border-top: 1px dashed #d0d4cd; }
  .mc-section:first-of-type { border-top: none; }
  .mc-h { color: #265844; font-size: 12px; margin: 4px 0 6px; }
  .mc-name { font-size: 14px; margin: 4px 0 6px; }
  .mc-vars, .mc-rule, .mc-cells, .mc-note { font-size: 12.5px; color: #374151; margin: 6px 0; line-height: 1.45; }
  .mc-formula { background: #fff; border: 1px solid #e5e7eb; padding: 8px 12px; margin: 8px 0; font-size: 13px; overflow-x: auto; }
  table.mc-action { width: 100%; font-size: 12.5px; margin: 6px 0 2px; }
  table.mc-action th.mc-row-h { background: #eef0eb; color: #265844; font-weight: 600; text-align: left; padding: 5px 8px; width: 26%; white-space: nowrap; }
  table.mc-action td { text-align: left; padding: 5px 8px; }
"""


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def build(cells: list[Cell], bench_slug: str | None, title: str, out: Path,
          family_yaml: Path | None, mech_card: dict | None, deprecates: list[str], now_utc: str):
    focus = cells[0]
    bench = next((c for c in cells if c.slug == bench_slug), None)
    panel = focus.manifest.get("panel")
    preg = focus.manifest.get("pre_registration", "")

    # --- risk table over all cells (native) ---
    risk_rows: list[tuple[str, dict]] = []
    for c in cells:
        risk_rows.extend(c.risk_rows())

    lift_html = render_lift_table(focus, bench) if (bench and bench.slug != focus.slug) else ""

    # heatmaps: one per cell primary equity
    heat = ''.join(render_monthly_grid(c.primary_equity(), c.slug) for c in cells)

    gates_html = render_acceptance_gates_table(focus.summary) if focus.is_tbm else ""
    diag_html = render_tbm_diagnostics_block(focus.summary) if focus.is_tbm else ""
    ledger_html = render_per_trade_ledger(focus.trades, focus.slug)
    fam_html = render_family_context_block(family_yaml, focus.slug, panel)
    verif_html = render_verification_block(focus.manifest) if focus.is_tbm else ""
    mech_html = render_mechanism_card(mech_card) if mech_card else ""

    preg_link = (f' · pre-reg: <code>{preg}</code>' if preg else "")
    dep_html = ""
    if deprecates:
        items = ''.join(f'<li><code>{d}</code></li>' for d in deprecates)
        dep_html = f'<p><b>Supersedes (archived, not deleted):</b></p><ul style="font-size:11px;">{items}</ul>'
    src_items = ''.join(
        f'<li><b>{c.slug}</b> — <code>{c.run_dir.relative_to(ROOT) if c.run_dir.is_relative_to(ROOT) else c.run_dir}</code></li>'
        for c in cells)

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<script>window.MathJax = {{ tex: {{ inlineMath: [["\\\\(","\\\\)"]], displayMath: [["\\\\[","\\\\]"]] }} }};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" id="MathJax-script" async></script>
<style>{CSS}</style></head><body>

<h1>{title}</h1>
<p class="meta">CPC v1 Arki (Cohort Performance Card — futures-momentum) · generated {now_utc} ·
git <code>{_git_sha()}</code> · ann_factor = {ANN} (daily) · focus cell: <b>{focus.slug}</b>{preg_link}</p>

<div class="caveat"><b>Scope.</b> Internal research report (live_trading: false). Risk/return values are
NATIVE engine outputs from each cell's <code>summary.csv</code>; the cumulative chart and monthly grids
show the realised-equity PATH in native units (its day-to-day diffs are lumpy and are not the
vol-targeted return stream behind the Sharpe). Comparison uses native-metric lifts, not capture/regression.</div>

{fam_html}
{mech_html}

<section class="period"><h2>Risk / return (native, ann_factor={ANN})</h2>
{render_risk_table(risk_rows)}
{('<h3>Native-metric lift vs ' + bench.slug + '</h3>' + lift_html) if lift_html else ''}
<h3>Cumulative realised equity</h3>
{render_cum_chart(cells, bench_slug)}
<h3>Monthly Δ realised-equity grid</h3>
{heat}
</section>

{gates_html and ('<section class="period"><h2>Acceptance gates</h2>' + gates_html + '</section>')}
{diag_html}
{ledger_html}
{verif_html}

<section><h2>Sources &amp; method</h2>
<ul style="font-size:12px;color:#374151;">{src_items}
<li><b>Risk metrics:</b> read from native <code>summary.csv</code> (no recomputation). Calmar =
ann_return_net / |max_drawdown_pct_geom| where both native.</li>
<li><b>Equity path:</b> <code>equity_curves.csv</code> rebased +100; additive cumulative (linear scale).</li>
<li><b>Gates / diagnostics:</b> native TBM <code>summary.csv</code> gate columns (pre-reg §4 / §5.2).</li>
</ul>
{dep_html}
<p class="stamp">Format: CPC v1 Arki · builder: scripts/build_cpc_v1_arki.py · handoff:
docs/arki/handoff_unified_cpc_reporting_2026-05-31.md</p></section>

</body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"  wrote {out.relative_to(ROOT)}  ({out.stat().st_size/1024:.1f} KB)")
    return out


def _parse_cells(arg: str) -> list[Cell]:
    out = []
    for part in arg.split(";"):
        part = part.strip()
        if not part:
            continue
        slug, run_dir = part.split("=", 1)
        out.append(Cell(slug.strip(), run_dir.strip()))
    return out


def _load_mech_card(focus_slug: str, override: str | None) -> dict | None:
    path = Path(override) if override else (MECH_CARD_DIR / f"{focus_slug}.yaml")
    if path.exists():
        return yaml.safe_load(path.read_text())
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="CPC v1 Arki — futures-momentum cohort report builder.")
    ap.add_argument("--cells", required=True,
                    help='Semicolon-separated "slug=run_dir" pairs; first = focus cell.')
    ap.add_argument("--bench-slug", default=None, help="Which cell is the comparison anchor.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--family-yaml", default=None)
    ap.add_argument("--mechanism-card", default=None,
                    help="Override path; default arki/reports/_mechanism_cards/<focus>.yaml")
    ap.add_argument("--deprecates", default="", help="Comma-separated paths this report supersedes.")
    ap.add_argument("--now-utc", default=None, help="Override generation timestamp (for reproducibility).")
    args = ap.parse_args()

    cells = _parse_cells(args.cells)
    if not cells:
        raise SystemExit("no cells parsed from --cells")
    mech = _load_mech_card(cells[0].slug, args.mechanism_card)
    fam = Path(args.family_yaml) if args.family_yaml else None
    if fam and not fam.is_absolute():
        fam = ROOT / fam
    deprecates = [d.strip() for d in args.deprecates.split(",") if d.strip()]
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    now_utc = args.now_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"=== CPC v1 Arki :: {cells[0].slug} ({len(cells)} cell(s)) ===")
    build(cells, args.bench_slug, args.title, out, fam, mech, deprecates, now_utc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
