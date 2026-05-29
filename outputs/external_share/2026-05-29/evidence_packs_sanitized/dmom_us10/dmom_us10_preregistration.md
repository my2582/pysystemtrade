> **EXTERNAL-REVIEW VERSION**: identifiers sanitised; quantitative metrics + paper citations preserved. See REVIEW_REQUEST.md for context.

# dmom_us10 — Pre-registration

**Date written**: 2026-05-29 (BEFORE run)
**Branch**: `feat/arki-backtest-toolkit`
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner).
**Owner**: <owner>
**Implementer**: Claude Opus 4.7
**Owner pre-registration sign-off**: 2026-05-29 by <owner>; locked by the git commit that creates this file.

This document is **pre-registered under `ars/PROMOTION.md`**. The grid, gates, and decision rules MUST NOT be changed after the run begins. Data and code snapshots are recorded at §5/§6 below and re-confirmed in `manifest.json` at run-start.

Framework-first genuine pre-registration. The preceding `martin_single_instrument` entry was Path Z (post-hoc grandfathering). This run is Path A.

---

## 1. Background and motivation

Two literature anchors:

- `references/research/Enhanced Momentum Strategies.pdf` (Hanauer & Windmüller 2022, TUM). Compares three enhanced momentum strategies on cross-sectional equity (66,905 stocks, 49 markets): constant volatility-scaled (cMOM, Barroso & Santa-Clara 2015), semi-vol-scaled (sMOM, Wang & Yan 2021), and dynamic-scaled (dMOM, Daniel & Moskowitz 2016). Paper's headline: all three reduce crashes; dMOM is least sensitive to overconfidence regimes. None consistently beats plain MOM in factor tests — they are crash-mitigators, not return boosters.
- `references/research/Design and analysis of momentum trading strategies.pdf` (Martin 2023) — establishes baseline EWMAC trend on US10 (validated in `ars/evidence_packs/martin_single_instrument/`).

Daniel & Moskowitz (2016) dMOM weight (Hanauer eq. 6-7):

```
w_dMOM,t = (1 / (2λ)) · μ̂_t / σ̂²_t

μ̂_t from time-series regression:
    R_MOM,t = γ0 + γ_int · I_Bear,t-1 · σ²_RMRF,t-1 + ε_t

I_Bear,t-1 = 1 if cumulative past 24-mo market return < 0, else 0
σ²_RMRF,t-1 = realized market variance over past 126 trading days
μ̂_t = fitted value from the expanding-window regression
λ = static scalar tuned ex-ante so the dMOM full-sample vol == baseline vol
```

The weight can go NEGATIVE in bear + high-vol regimes (flip momentum exposure).

Adaptation to single-instrument US10 (NO cross-section): substitute the underlying market = US10 itself. `R_MOM,t` = baseline EWMAC strategy daily return; `I_Bear` = 24-mo cumulative US10 back-adjusted price change < 0; `σ²_RMRF` = 126d realized variance of the US10 daily price-change-over-vol-norm return. λ tuned so dMOM full-sample vol == baseline full-sample vol.

Implementation choice (declared ex-ante): the overlay is applied as a **multiplicative scaler on baseline daily strategy returns** (`R_dMOM,t = R_MOM,t · w_dMOM,t`). Under fixed capital and continuous positions this is mathematically equivalent to scaling positions by the same factor; pysystemtrade's vol-target sizing is linear in the forecast, so the two are identical in expectation pre-rounding. We accept the small rounding mismatch from integer-contract trading; CPC v1 cross-checks via re-running with the multiplicative weight applied directly to the daily-return stream.

## 2. Hypotheses

- **H-D1 (Sharpe lift, primary)**: dMOM on US10 lifts gross Sharpe materially vs baseline. Material threshold = **+0.10** (sleeve-screening gate borrowed from b3 SRP Profile B convention).
- **H-D2 (crash reduction, primary)**: dMOM on US10 reduces geometric maxDD materially vs baseline. Material threshold = **+5.0 pp better** (less-negative).
- **H-D3 (skew preservation)**: dMOM does NOT destroy the per-trade positive skew of the baseline. Threshold = **`skew_per_trade ≥ 1.0`** (still long-option-shaped after the overlay; Hanauer notes dMOM can flip negative in bear+vol regimes).
- **H-D4 (SP500 control)**: dMOM does NOT rescue SP500 (baseline Sharpe ≈ 0). Threshold = **`SP500 dMOM Sharpe_gross < 0.20`** — if it does rescue, that would be suspicious data-mining and we should investigate.
- **H-D_recon (reconciliation)**: `|sum(R_dMOM_daily) − sum(R_MOM_daily) · ⟨w⟩|` consistent within 5% of the magnitude of the daily-return cumulative — the overlay is a pure multiplicative scaling, no creation/destruction of return.

## 3. Grid (one decision per row)

This experiment changes EXACTLY one design decision vs the Martin baseline: addition of the dMOM multiplicative overlay. No other parameters are varied.

| Cell | Variant | Notes |
|---|---|---|
| cell-0 (baseline) | Martin 6-speed EWMAC, equal-weight, carry off, soft cap 20, vol target 20%, <capital-token>, integer contracts | from `ars/evidence_packs/martin_single_instrument/` (US10 + SP500) |
| cell-1 (overlay) | cell-0 + dMOM multiplicative scaler on daily strategy return | US10 + SP500 |

Constants (ex-ante, FIXED):

- Bear lookback: 24 months (≈ 504 trading days).
- Market variance lookback: 126 trading days.
- Regression window: expanding-window with minimum 504 days warm-up (matches Hanauer's expanding OOS approach to avoid look-ahead).
- λ tuning: chosen by line-search ON BASELINE per-instrument such that dMOM full-sample std == baseline full-sample std (this is a single per-instrument scalar; not a free hyperparameter on the result metric).

No grid-search on H-D1/H-D2 thresholds (López de Prado AFML Ch.3).

## 4. Gates / decision rules

| Gate | Metric | Threshold | Hypothesis |
|---|---|---|---|
| G1 (primary) | US10 Sharpe_gross_lift = `Sharpe_dMOM − Sharpe_baseline` | `≥ +0.10` | H-D1 |
| G2 (primary) | US10 maxDD_geom improvement = `maxDD_dMOM − maxDD_baseline` (less negative) | `≥ +5.0 pp` | H-D2 |
| G3 | US10 dMOM `skew_per_trade` | `≥ 1.0` | H-D3 |
| G4 | SP500 dMOM `sharpe_gross` | `< 0.20` | H-D4 (control; FAIL means investigate) |
| G_recon | reconciliation diff of dMOM return cumsum vs baseline-scaled cumsum | `< 5%` | H-D_recon |

**Promotion paths:**

- **Path A (strict promotion)**: G1 PASS AND G2 PASS AND G3 PASS AND G_recon PASS → promote to evidence pack as a STRATEGY ENHANCEMENT candidate.
- **Path B (regime-conditional / crash-only)**: G2 PASS AND G3 PASS AND G_recon PASS (G1 may fail) → promote as a CRASH-MITIGATOR (not a return booster, consistent with Hanauer's actual paper conclusion). Owner sign-off required.
- **FALSIFY**: G3 FAIL (skew destroyed) OR both G1 and G2 FAIL → status `falsified`. Record finding: "dMOM on single-instrument US10 trend does not enhance Sharpe and does not reduce crashes; the cross-sectional equity result does not transfer."
- **INVESTIGATE**: G4 FAIL (SP500 unexpectedly profitable under dMOM) → halt, investigate for data leak or implementation bug.

## 5. Data snapshot

- Source: `data/futures/adjusted_prices_csv/US10.csv` and `SP500.csv` (pysystemtrade shipped panama-adjusted CSVs).
- Cutoff: 2026-04-03 (consistent with `martin_single_instrument` run).
- Baseline returns: re-derived live from the Martin baseline runner (`scripts/martin_single_instrument_backtest.py`), NOT loaded from the prior run dir (to avoid drift from any silent baseline change).

## 6. Code snapshot

- Runner: `scripts/dmom_overlay_backtest.py` (to be created in the same commit as this pre-registration is committed).
- git SHA at run-start: recorded in `manifest.json` at run time.
- Python: 3.10.15.
- Engine: native `systems.provided.futures_chapter15` for the baseline; dMOM overlay computed in numpy/pandas at the return-stream level.

## 7. CPC v1 comparison plan

This run is a 2-variant comparison (baseline vs dMOM-overlaid) on US10 + SP500. CPC v1 is **MANDATORY** per `ars/PROMOTION.md`. Plan:

| Series | Source kind | Path | is_benchmark |
|---|---|---|---|
| baseline_US10 | panel (daily-return stream from baseline runner) | derived | true |
| dmom_US10 | panel (daily-return stream after overlay) | derived | false |
| baseline_SP500 | panel | derived | (separate cohort) |
| dmom_SP500 | panel | derived | (separate cohort) |
| US10_buy_and_hold | panel (daily price-diff / σ_norm) | derived | (market reference) |

Output: `ars/runs/<UTC>_dmom_us10/cpc/dmom_vs_baseline.html` + `monthly_returns_usd.csv` + README.

Periods (pre-registered, ex-ante): `Full` = max history; `Last10y` = 2016-04 onward.
