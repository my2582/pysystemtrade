# martin_single_instrument — Pre-registration  ⚠️ POST-HOC

<!-- pre_rule7_grandfathered: authored before Rule 7 (2026-05-31); see docs/arki/session_predictions_scorecard_2026-05-31.md -->

> **POST-HOC DISCLOSURE.** This document was written on 2026-05-29 AFTER
> the runs at `ars/runs/20260528T161350Z_martin_single_instrument/`
> (initial `bb533839 feat(scripts): Martin (2023) single-instrument futures
> momentum backtest` and the corrected `5fa88c4c fix(martin): correct Fig 1
> attribution, vol-normalised market skew, geometric maxDD`) had already
> completed. The framework (`ars/PROMOTION.md`) was designed and adopted
> on 2026-05-29 as well. Treat this as a **post-hoc reconstruction** of
> the implicit hypothesis at the time of the run, not a true
> pre-registration. Owner-acknowledged grandfathering as the framework's
> first entry; future runs MUST be pre-registered before run-start git SHA.

**Date written**: 2026-05-29 (POST-HOC)
**Branch**: `feat/arki-backtest-toolkit`
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner).
**Owner**: Minsu Yeom
**Implementer**: Claude Opus 4.7
**Owner pre-registration sign-off**: 2026-05-29 by Minsu Yeom; grandfathered as Path Z (post-hoc) under `ars/PROMOTION.md`.

---

## 1. Background and motivation

Two literature anchors supplied by the owner:

- `references/research/Design and analysis of momentum trading strategies.pdf` (Richard J. Martin, 2023). Closed-form theory of single-instrument futures time-series momentum centered on skewness. §1 (vol-normalised returns U=dX/σ̂), §2 (linear strategies, EMA1 vs EMA2, optimal kernel `t·exp(-α t)`), §2.3 (skewness of trading returns: pure trend with all aⱼ>0 → positive skew, peaks at M ~ indicator response time, decays as M^(-1/2)), §3 (option-like nature: trend = long long-dated / short short-dated options), Fig 1 (skew of MARKET returns vs holding period for SG CTA, US TSY 7-10y, SPX).
- `references/research/Enhanced Momentum Strategies.pdf` (Hanauer & Windmüller 2022). Cross-sectional equity context; cMOM / sMOM / dMOM vol-scaling overlays. Treated here as background for the dMOM follow-up; not under test in this run.

A prior uncited deep-research synthesis (`references/research/2026-05-27-single-instrument-futures-momentum.md`) had claimed single-instrument trend Sharpe of 0.7-1.0, which conflicts with Martin's own framing and Rob Carver's empirical numbers. The owner asked for a faithful Martin reproduction to settle the claim.

## 2. Hypotheses

Implicit at run-time (reconstructed post-hoc):

- **H-M1 (Fig 1, rates side)**: on a single rates futures (US10), the term-structure of skewness of vol-normalised market returns is positive at intermediate holding horizons (M ≈ 40-60 days).
- **H-M2 (Fig 1, equity side)**: on a single equity-index futures (SP500), market-return skewness is negative across most M.
- **H-M3 (§2.3 trading skew)**: a multi-speed EWMAC pure-trend strategy with all aⱼ>0 (no carry, no mean reversion) produces per-trade returns whose skew is materially larger than the daily strategy-return skew.
- **H-M4 (§3 long-option signature)**: on US10, the strategy's per-trade distribution shows the long-option signature (low win rate AND strong positive trade skew).
- **H-M5 (Sharpe ceiling)**: US10 strategy gross Sharpe lies in `[0.2, 0.6]`, refuting the optimistic 0.7-1.0 range from the prior uncited deep-research run.

## 3. Grid (one decision per row)

Two instruments × one rule-set. No parameter sweep; this is a single-cell sanity reproduction.

| Cell | Instrument | Rules | Notes |
|---|---|---|---|
| cell-1 | US10 | 6-speed EWMAC `ewmac2_8, 4_16, 8_32, 16_64, 32_128, 64_256` equal-weighted | rates side |
| cell-2 | SP500 | same | equity contrast |

Constants (ex-ante): `capital_usd=50_000`, `vol_target_pct=20.0`, `forecast_cap=20.0`, `carry_included=false`, `idm=1.0`, `roundpositions=true`.

## 4. Gates / decision rules

Each gate corresponds to one hypothesis. Reconciliation tolerance is applied to the trade-attribution check.

| Gate | Metric | Threshold | Hypothesis |
|---|---|---|---|
| G1 | US10 mkt skew @ M=60 (vol-normalised non-overlapping blocks) | `> 0` | H-M1 |
| G2 | SP500 mkt skew @ M=60 | `< 0` | H-M2 |
| G3 | US10 `skew_per_trade − skew_daily` | `> 1.0` | H-M3 |
| G4 | US10 `win_rate_pct < 50` AND `skew_per_trade > 1.0` | both | H-M4 |
| G5 | US10 `sharpe_gross` | `in [0.2, 0.6]` | H-M5 |
| G_recon | `|reconciliation_diff_pct|` for both instruments | `< 5%` | trade attribution clean |

Path A: all gates PASS, recon clean → promote to evidence pack.
Path Z (this run only): post-hoc grandfathering — pre-registration missing, owner override per framework adoption.
Falsification: any required gate FAIL → status `falsified` in registry; finding note recorded.

## 5. Data snapshot

- Source: `data/futures/adjusted_prices_csv/US10.csv` and `SP500.csv` (panama-adjusted, shipped with pysystemtrade).
- Cutoff: 2026-04-03 (latest available in shipped CSVs as of run).
- Snapshot identifier: contents of the two CSVs at the run-start git SHA (no separate hash recorded; full file is tracked by upstream pysystemtrade).

## 6. Code snapshot

- Runner: `scripts/martin_single_instrument_backtest.py`.
- git SHA at run-start: `5fa88c4c` (commit `fix(martin): correct Fig 1 attribution, vol-normalised market skew, geometric maxDD`).
- Python: 3.10.15.
- Engine: native `systems.provided.futures_chapter15` (`do_not_reimplement_engine=true`).

## 7. CPC v1 comparison plan

Not applicable for this run. US10 and SP500 are two DIFFERENT instruments under the SAME strategy design; this is a within-experiment contrast, not a design-variant comparison. CPC v1 is mandatory only when 2+ variants of the strategy are compared against a baseline.
