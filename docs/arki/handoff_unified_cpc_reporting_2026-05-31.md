# HANDOFF — Unified CPC v1 reporting + matrix.html + trade-arrow fix

**Type:** Implementation handoff (deterministic work, owner has signed off
on scope = option γ from the prior chat proposal).
**Owner:** Minsu Yeom.
**Implementer:** TBD (next session / next agent).
**Date authored:** 2026-05-31.
**Estimated effort:** ~50 min total (broken into 5 sequential steps in §3).
**Prerequisite:** none — this work is independent of `handoff_tbm_stage1_no_signal_decision_2026-05-31.md` and can run in parallel.

---

## 0. One-line ask

**Adopt b3-saa-etf's CPC v1 report format as the SINGLE unified standard,
adapt it to futures momentum + TBM extensions, generate it for the two
TBM cells + the 6-cell execution_friction umbrella, build the
family_momentum matrix dashboard, and fix the trade-analysis chart's
entry-arrow direction. All new outputs go to `arki/reports/<date>/`.**

---

## 1. Why this exists (owner's reasoning)

Current reporting is fragmented across THREE root directories with
overlapping content:

| Location | Content | Count |
|---|---|---|
| `ars/runs/<run>/report.{html,pdf}` | Per-cell Arki Green standardised stats | 13 reports |
| `arki/results/<date>/<spec>_<inst>_trade_analysis/<rep>.html` | Per-trade ledger + candles | 12 reports |
| `arki/results/<date>/*.html` | Cross-cell CPC / regime / aggregator | 2 reports |
| `outputs/external_share/<date>/cheatsheet_sanitized.html` | External-share one-pager | 2 cheatsheets |

Per cell, the owner has to open up to four files. Three different root
directories. Recent TBM Stage-1 runs (baseline + ablation) have NO HTML
report at all — owner-facing data lives only in CSV/JSON + this chat.

The decision (owner, 2026-05-31): adopt b3-saa-etf's CPC v1 as the
SINGLE standard for futures momentum reporting. Add our extensions
(acceptance gates, TBM diagnostics, gap-rule audit, per-trade ledger
embedded). One canonical root: `arki/reports/<date>/`.

---

## 2. Locked design decisions (do not re-litigate)

| # | Decision | Value |
|---|---|---|
| 1 | Canonical report root | `arki/reports/<date>/` |
| 2 | Report format | b3-saa-etf CPC v1 + Arki extensions (see §4) |
| 3 | Reports per cell | **ONE HTML file** (per-cell or per-comparison) — consolidates the previous 3-4 |
| 4 | `ars/runs/<run>/` going forward | RAW ARTIFACTS ONLY (manifest, csv, png). No HTML/PDF report. Reports are the curated deliverable; runs are reproducibility evidence. |
| 5 | Backward compatibility | EXISTING reports in `ars/runs/` and `arki/results/` are NOT touched (deletion = separate cleanup cycle). New reports use the new location. |
| 6 | External share (`outputs/external_share/`) | UNCHANGED — sanitized one-pagers stay separate from internal reports. |
| 7 | Family dashboards | `arki/reports/family/<family>/matrix.html` etc. — single-page visual status of the family |
| 8 | Trade-analysis arrow icons | Long entry = `^`, Short entry = `v`, Exit = `o` on both sides (per `trade_analysis.py` lines 592 / 597) |

---

## 3. Sequential implementation steps (run in this order)

### Step 1 — Fix `trade_analysis.py` arrow icons (3 min)

File: `scripts/trade_analysis.py`. Lines 590-599 region.

Current:

```python
e = _xy(trade.entry_date)
if e:
    ax.scatter([e[0]], [e[1]], marker="^", s=260, facecolor="#00d4ff",
               edgecolor="black", linewidths=1.6, zorder=10,
               label=f"ENTRY {trade.entry_date.date()} ({trade.direction})")
x = _xy(trade.exit_date)
if x:
    ax.scatter([x[0]], [x[1]], marker="v", s=260, facecolor="#ff2d75",
               edgecolor="black", linewidths=1.6, zorder=10,
               label=f"EXIT {trade.exit_date.date()} ({trade.exit_reason})")
```

Replace with:

```python
e = _xy(trade.entry_date)
if e:
    entry_marker = "^" if trade.direction == "long" else "v"   # Long ↑, Short ↓
    ax.scatter([e[0]], [e[1]], marker=entry_marker, s=260, facecolor="#00d4ff",
               edgecolor="black", linewidths=1.6, zorder=10,
               label=f"ENTRY {trade.entry_date.date()} ({trade.direction.upper()})")
x = _xy(trade.exit_date)
if x:
    ax.scatter([x[0]], [x[1]], marker="o", s=200, facecolor="#ff2d75",
               edgecolor="black", linewidths=1.6, zorder=10,
               label=f"EXIT {trade.exit_date.date()} ({trade.exit_reason})")
```

Rationale: entry-arrow direction now encodes position direction (visual
read of long vs short without legend lookup); exit uses a directionless
symbol because exit timing is the same regardless of position
direction.

**Verification:** regenerate one existing trade report (e.g. martin_us10)
and confirm long-trade charts show ^, short-trade charts show v at
entry. Existing call sites of `trade_analysis.py` are unchanged.

### Step 2 — Generate trade reports for the two TBM cells (5 min)

The two TBM runs lack any trade-analysis output. `scripts/trade_analysis.py`
expects pysystemtrade `rounded_positions.csv` + `daily_returns.csv` +
config — TBM runs don't produce that exact schema (they have
`equity_curves.csv`, `trades_US10.csv`, `manifest.json`).

Implementer choice:

- **(a) Trade-analysis-on-TBM adapter** — write a small adapter
  `scripts/tbm_trade_analysis.py` that maps the TBM run-dir schema to
  the inputs `trade_analysis.py` expects (positions reconstructed from
  trades_US10.csv side+start+end series; daily returns from
  equity_curves.csv). ~20 min not 5 — defer to a follow-up.
- **(b) Skip standalone trade reports for TBM** and instead embed the
  per-trade ledger directly in the CPC v1 cell report's "Per-trade
  ledger" section (§4 below). This is the RECOMMENDED path because
  the CPC v1 cell report consolidates everything anyway, and the TBM
  trades are sign-episode trades (start/end/days/sign/bin/trade_return_pp)
  with no per-day OHLC granularity needed.

**Recommended: (b).** No new file in this step; the per-trade table is
rendered inside the CPC report (Step 3, §4.7 below).

### Step 3 — Write `scripts/build_cpc_v1_arki.py` (Arki adaptation of b3 CPC builder) (~20 min)

Source: `/Users/msyeom/Developer/b3-saa-etf/scripts/build_cpc_v1.py` —
~1180 lines, well-organized. Key reusable renderers:

| Renderer | Reuse as-is? | Notes |
|---|---|---|
| `render_mechanism_card(mc)` | YES | Three-subsec card (formula / triggering / action). Accepts dict. |
| `render_risk_table(rows)` | YES | Ann Ret / Vol / Sharpe / Sortino / Max DD / Calmar / Skew / n. |
| `render_capture_table(rows)` | OPTIONAL | Up/Down capture vs benchmark — applies when a benchmark cell exists |
| `render_regression_table(rows, bench_label)` | OPTIONAL | Alpha / β / R² vs benchmark |
| `render_monthly_heatmap(series, label)` | YES | Year × month colored grid + YTD |
| `render_cum_chart(df, colors, period_label)` | YES | Cumulative NAV — multi-series |

Adaptations needed for futures momentum context:

| Adaptation | Reason |
|---|---|
| `ann_factor` = 256 (NOT 12) | We work daily, not monthly (b3 default monthly SGD) |
| Drop FX conversion (no `load_fx_eom`, no `_usd_daily_to_sgd_monthly`) | All cells already in % of capital |
| `bench_label` = baseline cell name (e.g., `martin_baseline_us10_1m`) | Comparison anchor is a prior family cell, not ACWI |

Arki extensions (NEW renderers to add to the builder):

| Renderer | Source data |
|---|---|
| `render_acceptance_gates_table(gates_dict)` | Pre-reg §4 gates (G-TBM1..6 + G-recon + G-family-DSR) with PASS/FAIL/N-A coloring |
| `render_tbm_diagnostics_block(summary_row)` | TBM-specific: avg_uniqueness, effective_sample, g distribution mean/std/max, CPCV F1/precision/recall, DSR uplift, PBO, gap-rule audit counters (5.2.a/b/c) |
| `render_per_trade_ledger(trades_df)` | Sign-episode trade table from `trades_US10.csv`, with summary stats (n_trades, median days, win rate, skew_per_trade, MFE/MAE if available) |
| `render_family_context_block(family_yaml_dict)` | The cell's family context: family name, panel, multiple-testing context (n_configs_searched, expected_max_sharpe_at_N) — every cell report shows where it sits in the family |

CLI:

```bash
venv/bin/python scripts/build_cpc_v1_arki.py \
    --slug tbm_meta_us10_baseline_1m \
    --run-dir ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m \
    --baseline-slug exec_friction_martin_baseline_us10_1m \
    --baseline-run-dir ars/runs/20260529T172206Z_martin_baseline_us10_1m \
    --out arki/reports/2026-05-31/cells/tbm_meta_us10_baseline_1m_cpc.html
```

Optional `--no-baseline` for stand-alone cell reports (no comparison
table); `--family-yaml ars/families/futures_momentum/family.yaml` to
pull the multiple-testing context.

The mechanism cheatsheet content for each cell comes from a small
hand-written yaml `arki/reports/_mechanism_cards/<slug>.yaml` (formula,
triggering rule, action description). For the TBM cells, the implementer
authors the card from the pre-reg §1-§3 content (Martin §1 Eq.(1), CUSUM
LdP §2.5 Eq.(2.5), barriers PT=8σ/SL=4σ, g(m) ramp formula, etc.).

### Step 4 — Apply CPC v1 to the two TBM cells + execution_friction 6-cell (~10 min)

Generates four files:

```
arki/reports/2026-05-31/
├── cells/
│   ├── tbm_meta_us10_baseline_1m_cpc.html
│   └── tbm_meta_us10_tmax40_cpc.html
└── comparisons/
    ├── tbm_baseline_vs_tmax40_cpc.html       # cross-cell CPC (variant vs baseline)
    └── execution_friction_us10_6cell_cpc.html  # umbrella backfill
```

For `tbm_baseline_vs_tmax40_cpc.html`: baseline = `tbm_meta_us10_baseline_1m`,
variant = `tbm_meta_us10_tmax40`. The COMPARISON CPC pulls both runs'
daily returns and produces capture / regression tables comparing
variant against baseline directly (a sensitivity-sweep one-pager).

For `execution_friction_us10_6cell_cpc.html`: 6 cells → 6 rows in the
risk table; comparisons pivot to martin_baseline_us10_1m as the
reference; per-cell heatmaps stacked; the existing 2026-05-29
aggregator HTML is superseded by this CPC version (link the
deprecation in DECISIONS).

### Step 5 — Build `arki/reports/family/futures_momentum_matrix.html` (~10 min)

Single-page visual dashboard for the family. Content sourced from:

- `ars/families/futures_momentum/family.yaml` — cells, dimensions, multiple-testing block
- `ars/families/futures_momentum/findings.md` — axis-level elasticity
- `ars/families/futures_momentum/queue.md` — pending items
- `ars/runs/registry.yaml` — registry entries linked from family cells

Sections (single HTML):

1. **Header** — family thesis (one-paragraph), `n_configs_searched`,
   `expected_max_sharpe_at_N` (annualised), last-update timestamp.
2. **Panel A status grid** (HTML table, color-coded cells):
   rows = overlay axis, columns = (spec, exec_profile, capital). Each
   cell shows status code (`✅PRO`, `📊MEAS`, `⚠REM`, `❌FAL`, `❌REF`,
   `⏳QUE`, `—`) + the Sharpe number where applicable. Click-through
   link to the cell's CPC v1 HTML if it exists.
3. **DSR threshold timeline** — small line plot: x-axis = pre-reg lock
   date, y-axis = `expected_max_sharpe_at_N`. Shows the self-correcting
   loop: locking pre-regs raised the bar from 0.314 (N=41) → 0.325
   (N=50) → 0.3326 (N=58). Each lock marked with the cell that
   triggered the bump.
4. **Findings elasticity table** — from findings.md, rendered as a
   color-coded table with `n_pairs` and confound flag prominent.
5. **Queue (top 5)** — top items from queue.md with status + expected
   internal_grid_size + estimated effort.
6. **Linked artifacts** — direct links to family.yaml, findings.md,
   queue.md, and the CPC reports under `arki/reports/<date>/cells/`.

Use plain HTML/CSS (no JS frameworks). Match the b3-saa-etf CPC visual
style for consistency.

### Step 6 — Update family.yaml + DECISIONS + Obsidian delivery (~5 min)

1. Add to `ars/families/futures_momentum/family.yaml` at the bottom:
   ```yaml
   reports_root: arki/reports/<date>/         # canonical reports location
   matrix_html:  arki/reports/family/futures_momentum_matrix.html
   ```
2. Append to `ars/DECISIONS.md` a 2026-05-31 entry summarising the
   adoption of CPC v1 + new directory convention + the two CPC reports
   + matrix.html generation. Reference deprecated paths
   (`arki/results/2026-05-29/execution_friction_us10_*.html` → now
   superseded by the CPC version, kept for archive).
3. Deliver to Obsidian inbox `_Inbox/2026-05-31/pysystemtrade_unified_cpc_reports/`:
   the 4 new HTML files + matrix.html + README.md cell-legend.

---

## 4. CPC v1 Arki — section spec for `build_cpc_v1_arki.py`

The Arki adaptation MUST emit these sections in this order:

```
HEAD
  <title>: <slug> -- CPC v1
  CSS: shared arki_green + cpc_v1
BODY
  1. Header (title, slug, generated-utc, git_sha, pre-reg link)
  2. Family context block (family name, panel, multiple-testing context)
  3. Mechanism cheatsheet (formula / triggering / action)
  4. Risk / return table (this cell + baseline if comparison mode)
  5. Cumulative NAV chart (overlay if comparison mode)
  6. Monthly heatmap (this cell; one per cell in comparison mode)
  7. Acceptance gates table (G-TBM1..6 + G-recon + G-family-DSR; color PASS/FAIL/N-A)
  8. TBM diagnostics block (only when overlay = TBM_meta_label; else skipped):
       avg_uniqueness, effective_sample, g distribution (mean/std/min/max),
       CPCV F1/precision/recall, DSR uplift, PBO, gap-rule audit counters
  9. Per-trade ledger (table + summary: n_trades, median days, win_rate, skew_per_trade)
 10. (comparison mode only) Capture vs baseline table
 11. (comparison mode only) Regression alpha/β/R² vs baseline
 12. Verification anchors block (sigma median + barrier values when applicable)
 13. Footer (deprecated-paths reference, raw artifact links)
```

Sections 8-9 are TBM-specific extensions; for non-TBM cells they are
skipped (the renderer should gracefully handle missing data, e.g. when
`overlay = none`).

---

## 5. Acceptance criteria (Stage-1 of THIS handoff passes only if ALL hold)

- [ ] `scripts/trade_analysis.py` patched per Step 1; one regenerated
      report shows long-trade ^ and short-trade v at entry, exit `o`
      both sides.
- [ ] `scripts/build_cpc_v1_arki.py` exists and emits a valid HTML for
      each of: `tbm_meta_us10_baseline_1m`, `tbm_meta_us10_tmax40`,
      `tbm_baseline_vs_tmax40` (comparison), and `execution_friction_us10_6cell`
      (umbrella).
- [ ] `arki/reports/family/futures_momentum_matrix.html` exists and
      renders correctly in browser (Panel A status grid populated,
      DSR threshold timeline visible, top-5 queue items shown).
- [ ] Family yaml updated with `reports_root` and `matrix_html` keys.
- [ ] DECISIONS.md entry appended.
- [ ] Obsidian inbox `_Inbox/2026-05-31/pysystemtrade_unified_cpc_reports/` populated.
- [ ] Git status: no diff in upstream-tracked dirs (`systems/`, `sysdata/`, `sysquant/`).

---

## 6. Files this handoff references

Source repos:

- This repo: `/Users/msyeom/Developer/pysystemtrade/`
- b3 source repo: `/Users/msyeom/Developer/b3-saa-etf/`
  - `scripts/build_cpc_v1.py` — CPC v1 builder
  - `output/reports/2026-05-29/rtv_xbondreit_sgd_cpc/rtv_xbondreit_sgd_cpc.html` — example output

Files to read before starting:

- `/Users/msyeom/Developer/b3-saa-etf/scripts/build_cpc_v1.py` — base builder (lines 820-1024 are the renderers)
- `/Users/msyeom/Developer/b3-saa-etf/output/reports/2026-05-29/rtv_xbondreit_sgd_cpc/rtv_xbondreit_sgd_cpc.html` — visual reference
- `scripts/trade_analysis.py` lines 590-600 — the arrow patch site
- `ars/families/futures_momentum/family.yaml` — schema for the family-context block
- `ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m/summary.csv` — TBM-specific column schema
- `ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md` — mechanism cheatsheet content source

Files NOT to touch:

- Any file under `systems/`, `sysdata/`, `sysquant/`, `syscore/`,
  `sysobjects/`, `sysproduction/`, `sysexecution/`, `sysbrokers/`,
  `private/` — upstream-tracked, fork-safety invariant.
- Existing `report.html` / `report.pdf` files under `ars/runs/<run>/`
  and existing files under `arki/results/2026-05-29/` — these are
  audit evidence; new reports live in `arki/reports/<date>/`.

---

## 7. Out of scope (explicit non-goals)

- Backfilling the OLDER 13 cells (martin_single_instrument, dmom_us10,
  smom_us10, fast_tilt_ewmac, carry_toggle, plus the 6-cell
  execution_friction sub-cells minus its umbrella) to the new CPC v1
  format — separate cleanup cycle. Track as a TODO under
  `ars/families/futures_momentum/queue.md` (low priority — these cells
  are stable and their existing reports are usable).
- Deleting deprecated reports under `arki/results/2026-05-29/` or
  `ars/runs/<run>/report.*` — keep as archive. Owner may purge in a
  future hygiene cycle.
- Re-rendering `outputs/external_share/<date>/cheatsheet_sanitized.html`
  to the new format — external-share sanitization is a separate
  pipeline; the CPC v1 unified reports are INTERNAL only.
- Authoring mechanism cheatsheets for cells that don't have one yet
  (most do via their pre-reg §1; the implementer pulls from there).
  Only the 4 cells in §3 Step 4 need a card for THIS handoff.

---

## 8. Estimated effort breakdown

| Step | Effort |
|---|---|
| 1 (trade_analysis arrows) | 3 min |
| 2 (TBM trade-report decision) | 1 min (decision; rec (b) skips standalone) |
| 3 (build_cpc_v1_arki.py) | ~20 min |
| 4 (apply to 4 outputs) | ~10 min |
| 5 (matrix.html) | ~10 min |
| 6 (family.yaml + DECISIONS + Obsidian) | ~5 min |
| **Total** | **~50 min** |

A focused agent should complete this in one turn if budget allows;
otherwise break into Step 1-2 (this turn) and Step 3-6 (next turn).
