# smom_us10_capped — Pre-registration

<!-- pre_rule7_grandfathered: authored before Rule 7 (2026-05-31); see docs/arki/session_predictions_scorecard_2026-05-31.md -->

**Date written**: 2026-05-31 (BEFORE run)
**Branch**: `feat/arki-backtest-toolkit`
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner).
**Owner**: Minsu Yeom · **Implementer**: Claude Opus 4.7
**Owner pre-registration sign-off**: 2026-05-31 by Minsu Yeom; locked by the git commit that creates this file.
**Path**: A (genuine pre-registration; remediation for `smom_us10` whose status is `registered_pending_remediation` in `ars/runs/registry.yaml`).

This document is **pre-registered under `ars/PROMOTION.md`**. The grid, gates, and decision rules MUST NOT be changed after the run begins. Code snapshot recorded at §6; manifest re-confirms git SHA at run-start.

This is the **first Rule 2 (degenerate-denominator bound) compliant** Path A pre-registration.

---

## 1. Background and motivation

`ars/runs/registry.yaml#20260528T181556Z_smom_us10` (status `registered_pending_remediation`) reported Sharpe lift +0.255 on US10 vs Martin baseline. Two reviewer-caught defects (see `ars/LESSONS.md` 2026-05-29 entries) downgraded that verdict:

1. **Unbounded `w` artefact**: `w_sMOM,t = sqrt(target_var) / sqrt(semi_var_126d)` had no declared upper bound. Observed `max(|w|) = 2,927` in a 2020-24 window when `semi_var` collapsed → effective leverage 6,439× on $50k capital. The +0.255 lift is partially leverage artefact; cannot be realised in any real-money implementation.

2. **Paper class misalignment**: sMOM is `ψ(V_n)` with `V_n = past R²_neg` → Martin §4 nonlinear class. The original pre-reg cited Martin §2.3 (linear class) — out of scope.

This remediation closes both defects:
- Adds an explicit `w ≤ 3` cap and a `semi_var ≥ 1e-4` floor (Rule 2 compliance).
- Reframes the paper class correctly as Hanauer-Wang-Yan §4-nonlinear application, NOT Martin §2.3 validation.
- Adds a new comparison gate vs uncapped result so we measure how much of the original +0.255 Sharpe lift survives a realistic cap.

## 1.1 Paper assumption set + empirical checks (Rule 3 compliance)

Source basis: Wang & Yan (2021) "Semivariance Premium" + Hanauer & Windmüller (2022) §3 (sMOM definition).

| Assumption | What the paper assumes | Empirical check on this run |
|---|---|---|
| Cross-sectional momentum context | Hanauer studies sMOM as a SLEEVE-level scaler on cross-sectional momentum portfolios (66,905 stocks × 49 markets). | **VIOLATED by construction.** Single-instrument application is OUT of paper's setting. Verdict framed as "transfer test of mechanism," not "validation of paper." |
| Practical bounded leverage | Practitioner implementations of sMOM/cMOM typically cap leverage at 2-4× to avoid degenerate denominators in calm periods. | Cap value `w ≤ 3` chosen ex-ante from this convention. Verified at run-time: `max(|w|) ≤ 3.0`. |
| κ_3(U_n) = 0 (Martin §2 inheritance) | Vol-normalised one-period returns symmetric. | US10 baseline κ_3(U) ≈ +0.18 (acceptable); SP500 κ_3(U) ≈ −0.25 (violated; SP500 read as informational context, not validation). |
| Crash mitigation, not Sharpe boost (Hanauer §3 explicit) | "All three [cMOM/sMOM/dMOM] reduce momentum crashes; none consistently beats plain MOM in factor tests." | Pre-reg gates support BOTH Path A (Sharpe lift) and Path B (crash mitigation only); a Path B promotion is acceptable under Hanauer's own framing. |

### Class membership statement
sMOM is **§4 nonlinear `ψ(V_n)`**. Martin §2.3 Eq. 12 closed-form positive-skew theorem **does NOT apply**. Verdicts must NOT cite §2.3 as validated.

## 2. Hypotheses

Material thresholds pre-registered ex-ante; no grid-search on result (López de Prado AFML Ch.3).

- **H-Sc1 (Sharpe lift, primary)**: capped sMOM lifts US10 gross Sharpe materially vs Martin baseline. Material threshold = **+0.05** (consistent with sleeve-screening; lower than uncapped pre-reg's +0.10 because the cap removes the leverage tail that drove most of the prior +0.255).
- **H-Sc2 (crash reduction, primary)**: capped sMOM reduces US10 geometric maxDD materially vs Martin baseline. Material threshold = **+3.0 pp better** (less negative).
- **H-Sc3 (skew preservation)**: US10 capped sMOM `skew_per_trade ≥ 1.0` (long-option signature survives the cap).
- **H-Sc4 (SP500 control)**: SP500 capped sMOM `Sharpe_gross < 0.20` (no false rescue).
- **H-Sc5 (cap-vs-uncap comparison, NEW)**: the ratio `(capped Sharpe lift) / (uncapped Sharpe lift = +0.255)` lies in **[0.30, 1.20]**. Interpretation:
  - `< 0.30` → original lift was dominated by leverage artefact; capped result is the realistic figure (sMOM essentially useless in practice).
  - `[0.30, 1.0]` → original lift was partially leverage artefact AND partially genuine; capped result quantifies the genuine fraction.
  - `[1.0, 1.20]` → cap was non-binding most of the time AND cap improves Sharpe by reducing noise during extreme days (rare but possible).
  - `> 1.20` → INVESTIGATE; cap shouldn't improve Sharpe materially beyond uncapped unless there's something we don't understand.
- **H-Sc_safety (Rule 2 compliance)**: `max(|w_t|) ≤ 3.0` strictly; AND `min(semi_var_t) ≥ 1e-4` strictly. Both verified at run-time and recorded in `verdict.json`.
- **H-Sc_recon (overlay reconciliation)**: `|sum(R_capped) − sum(R_baseline × w_capped)|` is approximately zero (overlay is a pure multiplicative scaling; no creation/destruction of return beyond the scaling).

**Aggregation discipline (Rule 4, reporting mode)**: `skew_per_trade` uses sign-episode aggregation (variable M; same as Martin baseline and original sMOM for cross-comparability). This is reporting-mode, NOT verification-mode — we do NOT claim it validates Martin §2.3 Eq. 12 (which requires fixed-M non-overlapping). Sharpe and maxDD use standard daily-return aggregation annualised by `sqrt(252)`.

## 3. Grid (one decision per row)

Single design change vs `smom_us10`: add bound + floor. All other parameters identical to original sMOM and to Martin baseline.

| Cell | Variant | Notes |
|---|---|---|
| cell-0 (Martin baseline) | 6-speed EWMAC equal-weight, no overlay | reference; from `ars/evidence_packs/martin_single_instrument/` |
| cell-1 (uncapped sMOM) | original `w_sMOM,t = sqrt(target_var)/sqrt(semi_var_126d) / λ` | reference; from `ars/runs/20260528T181556Z_smom_us10/` |
| cell-2 (capped sMOM, **this experiment**) | `w_capped,t = min(w_sMOM,t, 3.0)` AND `semi_var_t = max(semi_var_t, 1e-4)` | NEW |

Constants (FIXED ex-ante, NO grid-search):

- Semi-var lookback: 126 trading days (= original sMOM).
- `target_var` normalisation: full-sample baseline `mean(R²)` (same as original; full-sample scalar is invariant for Sharpe/skew ratios; only affects absolute lambda).
- λ normalisation: closed-form vol match (same as original).
- **NEW: `w_max = 3.0`** — chosen from industry practice (2-4× typical practitioner range); NOT tuned on result.
- **NEW: `semi_var_min = 1e-4`** (in same units as daily R² ≈ daily vol² ≈ 0.01²). Floor of `1e-4` corresponds to a daily downside-vol floor of ~1%, well below US10's typical daily vol ~1.4%. Chosen so the floor binds ONLY in degenerate "no down days in 126 days" windows.

## 4. Gates / decision rules

| Gate | Metric | Threshold | Hypothesis |
|---|---|---|---|
| G1 (primary) | US10 capped Sharpe_gross − baseline Sharpe_gross | `≥ +0.05` | H-Sc1 |
| G2 (primary) | US10 capped maxDD_geom − baseline maxDD_geom (less negative is positive) | `≥ +3.0 pp` | H-Sc2 |
| G3 | US10 capped skew_per_trade | `≥ 1.0` | H-Sc3 |
| G4 | SP500 capped Sharpe_gross | `< 0.20` | H-Sc4 (control) |
| G5 (NEW) | (capped Sharpe lift) / (uncapped Sharpe lift = 0.255) | `in [0.30, 1.20]` | H-Sc5 |
| G_safety | observed `max(|w_t|)` AND `min(semi_var_t)` | `≤ 3.0` AND `≥ 1e-4` strictly | H-Sc_safety (Rule 2) |
| G_recon | `|sum(R_capped) − sum(R_baseline × w_capped)|` | `< 1%` of `|sum(R_baseline)|` | H-Sc_recon |

**Promotion paths:**

- **Path A (strict promotion)**: G1 PASS AND G2 PASS AND G3 PASS AND G4 PASS AND G5 PASS AND G_safety PASS AND G_recon PASS → status `promoted`. Replaces `registered_pending_remediation` on the original `smom_us10` entry as the canonical capped variant.
- **Path B (crash-mitigator only)**: G2 PASS AND G3 PASS AND G4 PASS AND G_safety PASS AND G_recon PASS (G1 may fail, G5 may be at low end) → status `registered_path_b_candidate`. Owner sign-off required because Hanauer §3 explicitly acknowledges this is the more common outcome.
- **FALSIFY**: G_safety FAIL (implementation bug) OR G3 FAIL (skew destroyed by cap) OR (G1 AND G2 both FAIL AND G5 < 0.30) → status `falsified`. The pre-registered finding triggers: "capped sMOM (w ≤ 3) does not transfer to single-instrument US10 rates; the original uncapped +0.255 Sharpe lift was substantially leverage artefact."
- **INVESTIGATE**: G5 > 1.20 → status `investigate`. Cap should not improve Sharpe beyond uncapped by a large margin; suggests an implementation issue or misunderstanding.

## 5. Data snapshot

- Source: `data/futures/adjusted_prices_csv/US10.csv` + `SP500.csv` (pysystemtrade shipped panama-adjusted CSVs).
- Cutoff: 2026-04-03 (consistent with Martin baseline and original sMOM run).
- Baseline returns: re-derived live from `scripts/martin_single_instrument_backtest.py`-equivalent config (NOT loaded from prior run dir; avoids drift).

## 6. Code snapshot

- Runner: `scripts/smom_capped_backtest.py` (to be created in the same commit as this pre-registration is committed).
- git SHA at run-start: recorded in `manifest.json` at run time.
- Python: 3.10.15.
- Engine: native `systems.provided.futures_chapter15` for baseline; overlay computed in numpy/pandas at the return-stream level (same as original sMOM).

## 7. CPC v1 comparison plan

This run produces 3 series for cohort comparison: Martin baseline (existing) + uncapped sMOM (existing) + capped sMOM (NEW). Per `ars/PROMOTION.md` Tier-2b mandate, a CPC v1 comparison is required. Adapted plan:

| Series | Source kind | Path | is_benchmark |
|---|---|---|---|
| martin_baseline_US10 | panel | from prior run dir | true |
| smom_uncapped_US10 | panel | from prior run dir | false |
| smom_capped_US10 | panel | from this run (NEW) | false |

Output: `ars/runs/<UTC>_smom_us10_capped/cpc/smom_capped_vs_uncapped.html` + `monthly_returns_usd.csv` + README.

Periods (pre-registered, ex-ante): `Full` = max history (1985-2026); `Last10y` = 2016-04 onward; `LowDownsideVol_2020_2024` = 2020-01 to 2024-12 (the period where uncapped `w` spiked).

If implementation time is constrained, CPC v1 may be deferred to a follow-up commit; the headline Path A/B/FALSIFY decision is independent of CPC v1 narrative.

## 8. Cost budget (optional per primitive)

```yaml
budgets:
  pre_registration_phase: { tokens: 15000, time_min: 15 }
  experiment_phase: { tokens: 80000, time_min: 30 }
  register_phase: { tokens: 30000, time_min: 15 }
  total_budget: { tokens: 125000, time_min: 60 }
```

Soft signal; actuals recorded in `verdict.json.cost_actuals` field per `_template/verdict.json`.
