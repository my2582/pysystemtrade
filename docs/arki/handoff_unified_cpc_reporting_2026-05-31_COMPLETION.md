# COMPLETION REPORT — Unified CPC v1 reporting + matrix.html + trade-arrow fix

**Status:** ✅ **COMPLETE** — all steps done, acceptance criteria 7/7 PASS, committed + pushed.
**Source handoff:** [handoff_unified_cpc_reporting_2026-05-31.md](handoff_unified_cpc_reporting_2026-05-31.md)
**Owner:** Minsu Yeom · **Implementer:** Claude Opus 4.8 (1M) · **Completed:** 2026-05-31
**Commit:** `c1076c77` (on `feat/arki-backtest-toolkit`, pushed to `origin`).
**Fork safety:** no diff in any upstream-tracked dir (`systems/ sysdata/ sysquant/ syscore/ sysobjects/ sysproduction/ sysexecution/ sysbrokers/ private/`).

---

## 1. Step-by-step outcome

| Step | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 | `trade_analysis.py` arrow fix (long `^`, short `v`, exit `o`) | ✅ | `scripts/trade_analysis.py:592,598`. Verified by regenerating `results/runs/20260405_0147_arki_v4_optimized` (reconcile ε=6.8e-13, no error). |
| 2 | TBM trade-report decision | ✅ | Chose rec **(b)** — ledger embedded in CPC, no standalone adapter. |
| 3 | `scripts/build_cpc_v1_arki.py` + 2 mechanism-card YAMLs | ✅ | 690-line builder; `arki/reports/_mechanism_cards/tbm_meta_us10_{baseline_1m,tmax40}.yaml`. |
| 4 | 4 CPC reports | ✅ | `arki/reports/2026-05-31/cells/{tbm_meta_us10_baseline_1m,tbm_meta_us10_tmax40}_cpc.html` + `comparisons/{tbm_baseline_vs_tmax40,execution_friction_us10_6cell}_cpc.html`. |
| 5 | `futures_momentum_matrix.html` | ✅ | `arki/reports/family/futures_momentum_matrix.html` — 14-cell status grid, DSR timeline (N=41→50→58), elasticity table, queue top-5, resolved CPC click-throughs. |
| 6 | family.yaml keys + DECISIONS + Obsidian | ✅ | `family.yaml` `reports_root`/`matrix_html`; `ars/DECISIONS.md` 2026-05-31 entry; Obsidian `_Inbox/2026-05-31/pysystemtrade_unified_cpc_reports/` (6 files). |

## 2. Acceptance criteria (handoff §5) — 7/7 PASS

- [x] trade_analysis.py patched; report regenerated without error (long `^` / short `v` / exit `o`).
- [x] `build_cpc_v1_arki.py` emits valid HTML for all 4 targets.
- [x] `futures_momentum_matrix.html` renders (status grid, DSR timeline, queue).
- [x] family.yaml has `reports_root` + `matrix_html`.
- [x] DECISIONS.md entry appended.
- [x] Obsidian inbox populated.
- [x] No diff in upstream-tracked dirs.

## 3. Key design judgment call (read before extending the builder)

The handoff assumed b3-style capture/regression vs benchmark. **That was not faithful for our artifacts** and was deliberately changed:

- `ars/runs/<run>/equity_curves.csv` is the **realised-equity PATH**. Its day-to-day diffs are **lumpy** (a handful of real bond-crash days → ~160% annualised "vol") and do **NOT** reproduce the engine's native Sharpe (diff-Sharpe 0.14 vs summary 0.355). So the equity curve is *not* the clean vol-targeted daily-return stream.
- Therefore (ARS: preserve native outputs, don't fabricate):
  - **Risk/return tables read native `summary.csv` values only** (no recompute).
  - Equity curve drives **only** the cumulative-path chart + sign-coloured monthly grids, honestly labelled "native units".
  - Comparison uses a **native-metric lift table** (Sharpe / MaxDD / Skew) = exactly pre-reg §7 "Lifts reported". **Capture / alpha-β regression are intentionally omitted** (no trustworthy daily-return series persisted).
- TBM `summary.csv` carries the full gate panel pre-computed (`G_TBM1_pass..6`, gap-rule counters `5_2_a/b/c`, `avg_uniqueness`, F1, DSR) → render, don't recompute. TBM extension blocks skip gracefully for non-TBM cells.

Memory pointer: `cpc-v1-arki-reporting-standard`. Full record: `ars/DECISIONS.md` 2026-05-31.

## 4. Headline read surfaced (not a promotion)

TBM baseline (T_max=120): meta-sized Sharpe **0.3208** vs g=1 **0.3165** → G-TBM1 DSR uplift **+0.0115 PASS**; G-TBM3/4/5/6 PASS; PBO N/A (single config); **G-family-DSR FAIL** (0.3208 < 0.3326 absolute, reporting gate only). Near-floor sizer (g_max 0.551, avg_uniqueness 0.071 < 0.20). T_max=40 ablation g_max **0.591** (still in the <0.60→0.75 band) → diagnostic leans **"no learnable conditional edge on ZN-post-2003"** over effective-sample collapse. **No promotion claimed** (`live_trading: false`).

## 5. Out of scope / follow-ups (tracked, NOT done here)

1. **TBM registry entries** — the two TBM cells executed (run dirs 2026-05-30/31) but `family.yaml` still marks them `pre_registered_queued` / `registry_ref: pending_first_run`. Creating `registry.yaml` entries is a separate follow-up.
2. **Backfill older 13 cells** to CPC v1 — separate cleanup cycle (handoff §7).
3. **Delete deprecated reports** (`arki/results/2026-05-29/execution_friction_us10_6cell.html` + regime HTML, superseded by the 6-cell CPC) — kept as archive; owner purge later.
4. **External-share re-render** — out of scope (separate sanitisation pipeline).

## 6. New / changed files (all Arki-added or Arki-owned; no upstream file touched)

```
scripts/build_cpc_v1_arki.py            (new, 690 lines)
scripts/build_family_matrix.py          (new, 257 lines)
scripts/trade_analysis.py               (arrow fix, lines 590-599)
arki/reports/_mechanism_cards/*.yaml    (new, 2)
arki/reports/2026-05-31/{cells,comparisons}/*.html   (new, 4)
arki/reports/family/futures_momentum_matrix.html     (new)
ars/families/futures_momentum/family.yaml            (+ reports_root, matrix_html)
ars/DECISIONS.md                        (+ 2026-05-31 entry)
docs/arki/handoff_unified_cpc_reporting_2026-05-31.md (source handoff)
```

## 7. Reproduce

```bash
# CPC cell report (focus + baseline)
venv/bin/python scripts/build_cpc_v1_arki.py \
  --cells "tbm_meta_us10_baseline_1m=ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m;\
           exec_friction_martin_baseline_us10_1m=ars/runs/20260529T172206Z_martin_baseline_us10_1m" \
  --bench-slug exec_friction_martin_baseline_us10_1m \
  --title "TBM meta-label US10 baseline (T_max=120) vs g=1 Martin — CPC v1" \
  --family-yaml ars/families/futures_momentum/family.yaml \
  --out arki/reports/2026-05-31/cells/tbm_meta_us10_baseline_1m_cpc.html

# Family matrix
venv/bin/python scripts/build_family_matrix.py \
  --family-yaml ars/families/futures_momentum/family.yaml \
  --reports-date 2026-05-31 \
  --out arki/reports/family/futures_momentum_matrix.html
```
