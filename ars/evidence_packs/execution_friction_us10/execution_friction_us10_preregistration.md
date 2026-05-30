# execution_friction_us10 — Pre-registration  ✅ PATH A (pre-run lock)

**Date written**: 2026-05-30 (PRE-RUN, before any cell executes)
**Branch**: `feat/arki-backtest-toolkit`
**Pre-reg git SHA at lock**: `83e43dd6` (commit just prior to runner authoring; runs will record their own SHA)
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner).
**Owner**: Minsu Yeom
**Implementer**: Claude Opus 4.7 (1M context)
**Owner pre-registration sign-off**: 2026-05-30 by Minsu Yeom (transitive via `/Users/msyeom/.claude/plans/martin-baseline-misty-karp.md` plan approval, which contains this pre-reg's spec table verbatim).

> **Path A.** This document is locked BEFORE any of the 6 cells run; the runner records its own git SHA per cell. No post-hoc reframing permitted; falsifying any reporting gate is recorded as a finding, not as cause to rewrite hypotheses.

---

## 1. Background and motivation

The owner is benchmarking three single-instrument US10 momentum specifications at two capital tiers to **measure execution friction**, not to promote any single spec. The matrix isolates three causes of Sharpe and skew variation in single-instrument trend systems:

1. **Vol-estimator choice** — Martin 20-day EMA of `(X_n − X_{n−1})²` (γ = 0.95) vs Carver default `robust_vol_calc` (≈35-day EMA blend with long-run-vol overlay).
2. **Execution stack** — full Carver realism (6-speed EWMAC equal-weight + forecast cap ±20 + integer contracts + buffered position) vs strict Martin theory (single-speed EMA2 N=20,40 + cap OFF + continuous fractional position + no buffer).
3. **Capital tier** — $50K (sub-1-contract on US10/ZN front-month ~$110K notional → integer quantisation dominant) vs $1M (~8 contracts → continuous approximation acceptable).

Literature anchors supplied by the owner and pre-read:

- `references/research/Design and analysis of momentum trading strategies.pdf` (Richard J. Martin, Imperial, 2023). §1 Eq. (1) for vol-normalised return `U_n = (X_{n+1} − X_n)/σ̂_n`. §2.1 Eq. (4) for linear strategy `φ_n = Σ a_j U_{n−j}`. §2.4 Eq. (17) for EMA1 skew closed form, Eq. (18-19) for EMA2 skew closed form. §2.5 fixes the empirical vol estimator as "20-day EMA of squared price changes". §4.2.3 establishes the double-step / binary regime where integer quantisation destroys positive skew. §4.4 claim on forecast capping compressing the term-structure vertically (peak ≈2.1 → reduced).

A prior post-hoc Path Z run (`ars/runs/20260528T161350Z_martin_single_instrument/`, Sharpe 0.396 on US10) used the Carver default vol estimator, not the Martin 20-day EMA of squared changes. That mislabeling is acknowledged. This pre-registration treats the corrected Martin-vol version as Exp 1 ("martin_baseline") and the Carver-default-vol version as Exp 3 ("carver_6speed"); the former Sharpe-0.396 result is the latter's expected outcome and is used as a sanity anchor (see §10 verification).

## 2. Hypotheses

- **H-EF1 (capital sensitivity, integer specs).** For both integer-quantised specs (martin_baseline and carver_6speed), gross Sharpe at $1M minus gross Sharpe at $50K is bounded below by the integer-quantisation friction floor. Operationally we report the delta and its bootstrap CI; falsification is `Sharpe($1M) − Sharpe($50K) < −0.10` (i.e. $1M does materially worse than $50K, contradicting the friction-shrinks-with-capital prediction).
- **H-EF2 (vol-estimator effect).** At each capital tier, `|Sharpe(martin_baseline) − Sharpe(carver_6speed)|` is small. Operationally `≤ 0.15`. Paper anchor: Martin §4.3 claim — a faster or slower vol measure stretches the term structure horizontally without changing the peak skew, so single-statistic Sharpe should be close.
- **H-EF3 (paper-fidelity skew, Martin primary).** On `martin_primary_ema2_us10` at $1M, the per-trade skewness lies in `[+2.5, +5.5]`. Paper anchor: Martin §2.4 Eq. (18-19) gives peak central skew ≈ 2.1 at `M ≈ 1.7(N_α + N_β) ≈ 102 days` for EMA2(20, 40); per-trade aggregation (variable M ≈ median trade length) tends to land above central skew because trades are selected on sign episodes (a positive-bias selection). The empirical anchor from `martin_single_instrument` run was +4.382 on US10 — `[+2.5, +5.5]` brackets this.
- **H-EF4 (full-stack friction, headline).** Friction `F$50K = Sharpe(martin_primary_ema2_us10 @ $50K) − Sharpe(martin_baseline_us10 @ $50K)` is positive — i.e. continuous strict-Martin outperforms the full Carver execution stack at sub-1-contract capital because the integer + cap + buffer triad behaves like Martin §4.2.3 double-step with small ε. Operationally `F$50K > 0`. The same delta at $1M is the friction we expect to *shrink* (H-EF1 corollary): `F$1M < F$50K`. Both are reported with 1000-resample IID daily-return bootstrap CIs.

## 3. Grid (3 specs × 2 capitals = 6 cells)

| Cell | Spec | Capital | Instrument | Rules | Vol estimator | Cap | Quantisation |
|---|---|---|---|---|---|---|---|
| 1a | martin_baseline_us10_50k | $50,000 | US10 | 6-speed EWMAC equal-weight | Martin 20d EMA-of-sq, γ=0.95 | ±20 | integer + buffered |
| 1b | martin_baseline_us10_1m | $1,000,000 | US10 | same | same | ±20 | integer + buffered |
| 2a | martin_primary_ema2_us10_50k | $50,000 | US10 | single EMA2(20,40) | Martin 20d EMA-of-sq, γ=0.95 | OFF (∞) | continuous |
| 2b | martin_primary_ema2_us10_1m | $1,000,000 | US10 | same | same | OFF | continuous |
| 3a | carver_6speed_us10_50k | $50,000 | US10 | 6-speed EWMAC equal-weight | Carver default `robust_vol_calc` | ±20 | integer + buffered |
| 3b | carver_6speed_us10_1m | $1,000,000 | US10 | same | same | ±20 | integer + buffered |

Constants across all cells (ex-ante): `vol_target_pct = 20.0`; `idm = 1.0`; `carry_included = false`; `instrument_weights = {US10: 1.0}`; absolute price changes per Martin §1 ("we use the former definition in the ensuing algebra"); date range = full shipped `data/futures/adjusted_prices_csv/US10.csv` (1982 → 2026-04-03); no parameter sweep — exactly the 6 cells above run.

## 4. Gates / decision rules

This is a measurement experiment. No PROMOTE / FALSIFY gate at the spec level. All gates below are **reporting gates**: their fail-mode is "the headline is recorded with a flag", not "the spec is rejected".

| Gate | Metric | Threshold | Aggregation | Assumption set | Hypothesis |
|---|---|---|---|---|---|
| G-EF1 | `Sharpe(cell 1b) − Sharpe(cell 1a)` and `Sharpe(cell 3b) − Sharpe(cell 3a)` | both `> −0.10` | daily returns, full sample, IID bootstrap CI (1000 resamples) | as-EF-int | H-EF1 |
| G-EF2 | `|Sharpe(cell 1a) − Sharpe(cell 3a)|` and `|Sharpe(cell 1b) − Sharpe(cell 3b)|` | both `≤ 0.15` | daily returns, full sample, point estimate | as-EF-vol | H-EF2 |
| G-EF3 | `skew_per_trade` for cell 2b | `∈ [2.5, 5.5]` | sign-episode aggregation (Martin §2.3 type, variable M) on the continuous position series | as-EF-skew | H-EF3 |
| G-EF4 | `Sharpe(cell 2a) − Sharpe(cell 1a)` | `> 0` (reporting); also report `Sharpe(cell 2b) − Sharpe(cell 1b)` and the gap-shrinks check | daily returns, full sample, IID bootstrap CI | as-EF-stack | H-EF4 |
| G-recon | `|reconciliation_diff_pct|` between sum-of-trade-returns and cumulative daily-return sum | `< 5%` per cell | sign-episode aggregation with lagged position attribution per Martin §1 (position held entering day t = pos[t−1]) | n/a (engine identity) | trade attribution sanity |

### Assumption sets — Rule 3 declarations + empirical assumption_check

- **as-EF-int** (`H-EF1` and `H-EF4`): "Integer quantisation at $50K on US10/ZN reduces the effective position to {…, −1, 0, +1, …} most days; at $1M the position grid is fine enough to approximate the continuous strict-Martin position." `assumption_check`: histogram of integer positions per cell + report mean `|position|` and fraction of days at `|position|=0` (added to `summary.csv` as `frac_flat`, `mean_abs_pos`).
- **as-EF-vol** (`H-EF2`): "20d vs 35d vol estimators differ in the horizontal location of the skewness term-structure peak but not its height; aggregate Sharpe is therefore close." `assumption_check`: report rolling `σ̂_n` series correlation between Martin 20d and Carver default on US10 (`vol_estimator_corr` in summary). Martin §4.3 claim — empirical check.
- **as-EF-skew** (`H-EF3`): "Martin §1 Eq. (1) i.i.d. assumption on `U_n` and `E[U_n] = 0`; sign-episode trade definition aggregates over variable M ≈ median trade length." `assumption_check`: report market `skew(U_n)` and `mean(U_n)` for US10 on the same date range; the gate uses them as context (large `|mean(U_n)|` weakens the i.i.d.-symmetric base case).
- **as-EF-stack** (`H-EF4`): "Cap ±20 + integer + buffer triad behaves like Martin §4.2.3 double-step in the small-ε regime when capital is sub-1-contract; relaxing to continuous + cap-OFF + no-buffer recovers the linear regime." `assumption_check`: report forecast clipping fraction (days where `|forecast| ≥ 20`) for Exp 1 cells.

## 5. Data snapshot

- Source: `data/futures/adjusted_prices_csv/US10.csv` (panama-adjusted, shipped with pysystemtrade upstream).
- Cutoff: 2026-04-03 (latest available in the shipped CSV at lock time).
- Snapshot identifier: file at the runner's recorded git SHA (one per cell, written to that cell's `manifest.json`).
- No external data — fully reproducible from the repo at the recorded SHA.

## 6. Code snapshot

- Runner (specs 1, 3 — pysystemtrade engine): `scripts/execution_friction_runner.py` (to be authored after this pre-reg is locked).
- Runner (spec 2 — standalone numpy implementation of Martin §1 Eq. (1) + §2.1 Eq. (4) for EMA2 N=20,40): `scripts/execution_friction_runner.py` with branch `--spec martin_primary`.
- Vol estimator utility: `arki/utils/martin_vol.py` — implements Martin §2.5 explicit form `σ̂_n² = γ σ̂_{n−1}² + (1 − γ)(X_n − X_{n−1})²` with γ = 1 − 1/N.
- Aggregator (cross-cell report): `scripts/execution_friction_aggregator.py`.
- Engine for specs 1 and 3: native `systems.provided.futures_chapter15` (`do_not_reimplement_engine = true` in `ars/project_ars_profile.yaml`).
- Python: 3.10.15 (project venv).

## 7. CPC v1 comparison plan

CPC v1 applies because the 6 cells include explicit variants of a baseline (spec 1) under controlled perturbations of vol estimator (spec 3) and execution stack (spec 2). Comparison plan:

- **Baseline**: spec 1 (martin_baseline_us10) at each capital tier.
- **Variants**: spec 2 (paper-strict) and spec 3 (Carver default vol) at the same capital tier.
- **Lifts reported**: `Sharpe(variant) − Sharpe(baseline)`, `skew_per_trade(variant) − skew_per_trade(baseline)`, `ann_subsystem_turnover(variant) − ann_subsystem_turnover(baseline)`, `max_drawdown_pct_geom(variant) − max_drawdown_pct_geom(baseline)`.
- **Bootstrap CIs**: G-EF1 and G-EF4 deltas only (1000 IID resamples on daily returns).
- **Common randomness control**: same daily price series for all cells; only spec config and capital differ. No stochastic component in any cell.
- **Out of scope**: no parameter sweep (so PBO/CPCV from López de Prado are not applicable here — only 6 fixed cells).

## 8. Out of scope (explicit non-claims)

- No live-trading recommendation (project profile `live_trading: false`).
- No cost-by-size modelling — engine's default cost model is used; granular sub-1-contract slippage modelling is a future workstream.
- No micro-contract substitution — US10/ZN has no CME micro at the relevant tenor; sub-1-contract behaviour at $50K is part of the measurement, not an artefact to remove.
- No multi-instrument expansion — single instrument US10 is the locked design per owner instruction.
- No promotion claim — falsification of any reporting gate is logged in `ars/DECISIONS.md` as a finding, not as a rejection of the spec.

## 9. Owner sign-off

Signed at the top of this document. Plan-approval is the audit trail; runner records its own git SHA per cell into `manifest.json` for reproducibility.

## 10. Verification anchors (sanity, not gates)

- Cell 3a (carver_6speed_us10 @ $50K) should reproduce the historical Sharpe of `0.396` on US10 within `±0.02` because the prior post-hoc run used identical config (Carver default vol). A larger deviation indicates engine/version drift and must be investigated before any other cell is interpreted.
- Cell 2a vs 2b: continuous-position Sharpe should be very close (`|Δ| ≤ 0.05`) because at continuous quantisation the capital level is just a linear scaling on dollar P&L and Sharpe is scale-invariant. A large `|Δ|` indicates a bug in the standalone Martin primary implementation (e.g. accidental capital-dependence in vol-target scaling).
