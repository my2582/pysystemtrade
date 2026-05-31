# tbm_meta_us10_baseline — Pre-registration  ✅ PATH A (pre-run lock)

<!-- pre_rule7_grandfathered: authored before Rule 7 (2026-05-31); see docs/arki/session_predictions_scorecard_2026-05-31.md -->

**Date written**: 2026-05-30 (PRE-RUN, before any cell executes)
**Branch**: `feat/arki-backtest-toolkit`
**Pre-reg git SHA at lock**: to be filled by the runner at first execution.
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner + meta-model training).
**Owner**: Minsu Yeom
**Implementer**: Claude Opus 4.7 (1M context)
**Owner pre-registration sign-off**: 2026-05-30 by Minsu Yeom (transitive via plan approval + handoff document `/Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md` which locks all key design decisions verbatim).

> **Path A.** Locked BEFORE any meta-model is trained. No post-hoc reframing
> permitted; falsifying any acceptance gate is recorded as a finding, not as
> cause to rewrite hypotheses.

---

## 1. Background and motivation

This is the first **Triple Barrier Method (TBM) + meta-labeling overlay**
experiment in the `futures_momentum` family. Queue item #1 from
[ars/families/futures_momentum/queue.md](../../families/futures_momentum/queue.md). Direct input is the design
handoff at `/Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md`.

**Q4 architectural posture (locked):** side from the existing Martin primary
signal (sign only), size from a learned meta-classifier. The engine is NOT
touched; the meta-labeler is a label-only attachment producing event-day
training data and a position scaler `g(m) ∈ [g_min, 1.0]`.

**Literature anchors:**

- López de Prado, *Advances in Financial Machine Learning* (2018):
  - ch.2 §2.5 (Symmetric CUSUM filter, eq.(2.5) for the event detector).
  - ch.3 §3.4 Eq. (3.6) (Triple Barrier labeling rule); §3.5 (vertical barrier
    + side-conditional barrier widths).
  - ch.4 §4.2 (Average Uniqueness for overlapping labels); §4.3 (sequential
    bootstrap sample weights).
  - ch.12 §12.4 (Combinatorial Purged Cross-Validation, CPCV).
  - ch.14 §14.6 (Deflated Sharpe Ratio).
- Bailey, Borwein, López de Prado, Zhu (2014). "The Probability of Backtest
  Overfitting" (arXiv:1602.04944), §3 Eq.(12) expected max-SR under N trials.
- Martin (2023) "Design and analysis of momentum trading strategies":
  - §1 Eq. (1) vol-normalised return `U_n = (X_{n+1}−X_n)/σ̂_n`.
  - §2.5 vol estimator (20-day EMA of squared price changes, γ=0.95).
  - §4 p.17 Eq. (20) — positive-skew preservation requires `Σ ρ_j A(α_j^{-1})² > 0`
    (the all-positive-weight regime). The size floor `g_min ≥ 0` keeps side·g
    in the same regime.

**Family DSR threshold context (Rule 6 awareness).** This pre-registration
joins the `futures_momentum` family. At pre-reg lock time
`n_configs_searched = 50`, `expected_max_sharpe_at_N = 0.325` annualised
(computed via `arki.utils.dsr.expected_max_sharpe(sr_trials_std=0.1426,
n_trials=50, annualization_factor=256)`). The TBM cell's ABSOLUTE promotion
test uses this threshold; its primary acceptance gate (see §4) is the
RELATIVE deflated_sharpe uplift over the `g=1` Martin baseline, which is a
strictly stronger requirement than the absolute family threshold when the
baseline already clears it.

**ZN diagnostics that drive this design** (computed 2026-05-30 from
[arki/results/2026-05-29/execution_friction_us10_regime_analysis_*](../../../arki/results/2026-05-29/) for the
`martin_primary_ema2_us10_1m` cell, paper-fidelity single-EMA2 N=20,40):

1. CUSUM single break 2003-06-13: pre-Sharpe 0.571 → post-Sharpe 0.019.
   The standalone strategy is essentially flat post-break, so any meta-layer
   must EITHER improve risk-shape (drawdown reduction, skew preservation) OR
   re-discover regime-dependent alpha that single-speed EMA2 alone misses.
2. Kaufman Efficiency Ratio (60d) bucket Sharpe: low −2.70 / mid +0.86 /
   high +2.95 (spread 5.64). ER is the dominant single conditioning feature
   on US10.
3. Per-trade asymmetry on raw σ (HANDOFF §1D): winners MFE median 20.9σ
   vs losers MAE median 4.68σ — 4.5× asymmetry justifies PT:SL = 2:1
   (PT=8σ, SL=4σ).
4. Single-instrument trade thinness: 106 sign-episode trades over 43 years.
   Per-trade meta-model training is too thin; CUSUM-day event sampling and
   6-speed pseudo-cross-section pooling are required mitigations.

## 2. Hypotheses

Each hypothesis maps to one acceptance gate in §4 (HANDOFF §6 gates carried
forward verbatim).

- **H-TBM1 (DSR uplift > 0 vs g=1).** Meta-sized strategy beats g=1 Martin
  baseline OOS on Deflated Sharpe at the cell-internal N. Paper anchor:
  López de Prado 2018 ch.14 §14.6 (DSR controls for selection bias under
  multiple-testing; comparing meta-sized vs g=1 over τ-grid × barrier ×
  feature-set sweep MUST be deflation-corrected).
- **H-TBM2 (PBO < 0.5).** Combinatorial Symmetric Cross-Validation
  probability of backtest overfitting over the full pre-registered config
  grid stays below the false-discovery threshold. Paper anchor: López de
  Prado 2018 ch.14 §14.6 + Bailey 2014 §3 Eq.(12) framework.
- **H-TBM3 (MaxDD reduction).** Meta-sized geometric MaxDD ≤ baseline
  geometric MaxDD. Drawdown reduction is the primary Stage-1 value (the
  side has no new alpha; size shapes risk).
- **H-TBM4 (positive-skew preservation).** Meta-sized daily-return skew ≥
  baseline daily-return skew − 0.20 (small tolerance for resampling noise).
  Paper anchor: Martin §4 Eq.(20) — the all-positive-weight regime that
  produces positive trading-return skew is preserved iff the meta-sizer's
  output stays in `[g_min, 1.0]` with `g_min ≥ 0`.
- **H-TBM5 (meta classifier F1 above naive base-rate).** Out-of-fold F1
  exceeds a base-rate (always-1 or always-majority-class) classifier's F1.
  This guards against the "meta-model rejects everything" degenerate case.

## 3. Grid (one cell with internal sweeps)

One Panel-A cell. Internal parameter sweep is fully enumerated below for
honest DSR N accounting.

| Cell | Spec axis | Value |
|---|---|---|
| `tbm_meta_us10_baseline_1m` | universe.instrument | US10 |
| | spec.vol_estimator | martin_20d_ema_of_sq (γ=0.95, absolute-change form per HANDOFF §2 code-fix) |
| | spec.rule_structure | single_ema2_20_40 (side from `martin_primary_ema2_us10_1m`) + 6-speed_pseudo_cross_section_pool (for label data thickness only; SIDE remains single-EMA2) |
| | spec.overlay | TBM_meta_label |
| | exec_profile.profile | carver_native (integer + cap ±20 + buffer) -- production-realistic |
| | exec_profile.capital_usd | 1,000,000 |

**Internal sweep (counts toward `n_configs_searched`):**

- `tau` (participation threshold on meta-model probability): grid {0.40, 0.50, 0.55, 0.60} (4 values). HANDOFF §5 — tuned via CPCV against OOS DSR.
- Feature subset: 2 sets — {ER_20d, ER_60d only} vs {ER + signal_dispersion + primary_strength + vol + vol_of_vol + autocorr_1 + drawdown}.
- Barrier fine-tune around lock: PT/SL fine-tune is REPORTING ONLY (locked at PT=8σ, SL=4σ, T_max=120 per HANDOFF §2 — measured on raw ZN σ).

**internal_grid_size**: 4 τ × 2 feature subsets = **8 configs**. This number is appended to `family.yaml § multiple_testing.n_configs_recorded` at pre-reg lock (raising the family DSR threshold per the self-correcting loop).

**Constants ex-ante (locked, HANDOFF §0-§2):**

- `t_max = 120` days (vertical barrier).
- `pt_mult = 8.0` × raw_sigma (price-point units, NOT vol-targeted pct).
- `sl_mult = 4.0` × raw_sigma.
- `g_min = 0.30` (lower bound on meta-sizer output; together with upper bound `max(|g_t|) ≤ 1.0` hard cap, this is the explicit declaration of the bounded multiplicative weight per Rule 2 of the pre-registration lint).
- `cusum_kappa = 1.0` × raw_sigma (CUSUM event threshold).
- `vol_span = 20` days; `gamma = 0.95` ⇒ `alpha = 0.05` for `(X_n − X_{n−1})²` EMA per Martin §2.5 (absolute-change form, NOT pct-returns — ZN panama price crosses zero so pct-returns explode; this is the HANDOFF §2 CODE FIX).
- Sigma-floor (no-look-ahead): `sigma.clip(lower = sigma.expanding(20).median()*0.2)`.

## 4. Gates / decision rules

All gates are evaluated **OUT OF SAMPLE** via Combinatorial Purged
Cross-Validation (CPCV) folds that MUST straddle the 2003-06-13 structural
break in BOTH train and test (regime-analysis finding; vanilla k-fold would
put easy decades in train and post-2020 in test). Embargo = `t_max` =
120 days around test windows to purge label-overlap.

| Gate | Metric | Threshold | Aggregation | Assumption set | Hypothesis |
|---|---|---|---|---|---|
| G-TBM1 | DSR uplift = DSR(meta-sized) − DSR(g=1 baseline), both computed via `arki.utils.dsr.deflated_sharpe_ratio` with `annualization_factor=256`, `n_trials = n_configs_searched (50)` | `> 0` | bootstrap CI on daily returns (1000 IID resamples), point estimate + CI | as-TBM-iid | H-TBM1 |
| G-TBM2 | PBO via `arki.utils.dsr.probability_of_backtest_overfitting` over the τ × feature-set × CPCV-fold grid (n_groups=8 → 70 combinatorial splits) | `< 0.5` | combinatorial logit-rank mean across IS/OOS pairings | as-TBM-iid | H-TBM2 |
| G-TBM3 | `max_drawdown_pct_geom(meta) − max_drawdown_pct_geom(baseline)` | `≤ 0` (i.e., meta no-worse-than baseline; ideally negative = reduction) | geometric compounded daily returns | none (engine identity) | H-TBM3 |
| G-TBM4 | `skew_daily(meta_returns) − skew_daily(baseline_returns)` | `≥ −0.20` | daily strategy returns, third central moment normalised | as-TBM-skew | H-TBM4 |
| G-TBM5 | meta-classifier OOS F1 vs naive base-rate (majority-class) F1 | `F1(meta) > F1(naive) + 0.02` | sign-episode-style class labels from TBM, per-fold OOS aggregation | as-TBM-iid | H-TBM5 |
| G-TBM6 (sanity) | `min(g_t) ≥ 0.30 AND max(g_t) ≤ 1.0` for every day in OOS | both | per-day series check, no aggregation | none (implementation identity) | implementation correctness (and Rule 2 bound declaration: `max(|g_t|) ≤ 1.0` hard cap as a finite safety bound) |
| G-recon | `\|reconciliation_diff_pct\|` between sum-of-trade-returns and cumulative daily-return sum | `< 5%` | sign-episode aggregation with lagged position attribution | none (engine identity) | trade attribution sanity |
| G-family-DSR (Rule 6 awareness, REPORTING) | meta-sized annualised Sharpe vs family-level `expected_max_sharpe_at_N = 0.325` | `> 0.325` for ABSOLUTE promotion claim | full-sample daily returns, point estimate | family multiple-testing context | not a falsification gate; required disclosure when reporting headline Sharpe |

**Stage-1 passes** only if **ALL of G-TBM1..G-TBM6 + G-recon hold**.
G-family-DSR is a reporting gate (per family.yaml multiple-testing block);
failing it means the absolute headline cannot be claimed but the relative
uplift result (G-TBM1) can still be valid.

### Assumption sets — Rule 3 declarations + empirical assumption_check

- **as-TBM-iid** (H-TBM1, H-TBM2, H-TBM5):
  - "Daily strategy returns after sample-uniqueness re-weighting and CPCV
    purging+embargo are approximately iid (López de Prado 2018 §4.2)."
  - `assumption_check`: report `average_uniqueness` distribution per CPCV
    fold + per-fold autocorrelation of residual returns; both included in
    the cell's `summary.csv` as `avg_uniqueness_p25/p50/p75` and
    `residual_autocorr_lag1`. If average_uniqueness < 0.20, the meta-model
    is mostly seeing redundant labels — flag in DECISIONS.
- **as-TBM-skew** (H-TBM4):
  - "Martin §4 Eq.(20) positive-skew preservation holds when the position
    weight stays in the all-non-negative regime; `g_t ∈ [0.30, 1.0]`
    enforces this by construction (HANDOFF Decision #5)."
  - `assumption_check`: report empirical fraction of OOS days where
    `g_t = g_min = 0.30` (the "minimum-participation" mode); if this
    fraction exceeds 80%, the meta-model is degenerate and G-TBM5 should
    still catch it. Also report `Σ ρ_j A(α_j^{-1})²` empirical sign on the
    realised position series for direct §4 Eq.(20) check.

## 5. Data snapshot

- Source: `data/futures/adjusted_prices_csv/US10.csv` (panama-adjusted,
  shipped with pysystemtrade upstream; same source as all Panel A cells).
- Cutoff: 2026-04-03 (latest available in the shipped CSV).
- Snapshot identifier: file at the runner's recorded git SHA, written into
  `manifest.json` per cell.

### 5.1 Verification anchor result (2026-05-30 pre-runner check)

Per HANDOFF §2 first-CC-step ("FIRST STEP is now verification, not derivation"),
the raw ZN sigma was reproduced on this repo's ZN feed BEFORE runner authoring,
confirming that the pipeline matches the HANDOFF barrier calibration.

| Quantity | Target (HANDOFF) | Observed (this repo) | Verdict |
|---|---:|---:|---|
| σ median (price points) | 0.39 ± 0.03 | **0.3871** (Δ −0.0029) | PASS |
| σ p25 | 0.32 | 0.3212 | bullseye |
| σ p75 | 0.48 | 0.4732 | bullseye |
| Zero-crossing region 1986-90 (\|price\|<5, 910 days) | σ no explosion | local/global ratio 1.14× (max 1.02) | PASS (confirms absolute-change form per Martin §2.5 Eq. (1); NOT pct-returns) |
| 2024-04 → 2025-04 gap presence | gap visible | 262 biz days expected, 0 observed (100% missing) | PASS |

**Effective barrier values at observed σ** (locked multipliers, σ auto-tracks
to the calibrated multipliers per HANDOFF §2): PT = 8σ = **3.097 price
points** (target 3.12), SL = 4σ = **1.548 price points** (target 1.56). Both
within 1% of HANDOFF calibration.

Reproducibility:

- Verification script: `scripts/tbm_sigma_verification.py` (`venv/bin/python scripts/tbm_sigma_verification.py`, ~30 sec).
- Audit row: `arki/results/2026-05-30/tbm_sigma_verification.csv` (one row per repo-state run; preserves the (σ_median, barrier_pp, gate_pass) tuple at the recorded git SHA).

### 5.1.1 Sensitivity sweep — T_max ablation (added 2026-05-31, single-variable diagnostic)

After the first run (`feat=ER_plus_rest_tau=0.50, t_max=120`) the meta-sizer
output was observed to be near-floor (`g_max_observed = 0.551`,
`g_mean = 0.314`) with `avg_uniqueness = 0.071` (BELOW the as-TBM-iid 0.20
threshold declared in §4). Two competing causes for the near-floor sizer:

1. **Effective-sample collapse** — T_max = 120 business days causes labels
   to overlap heavily (avg uniqueness 0.071 → effective sample ≈ 4143 ×
   0.071 ≈ 294 distinct units, far below the 4143 nominal). The
   meta-model is starved of independent training signal and rationally
   collapses to floor.
2. **No-signal regime** — ZN post-2003 standalone EMA2 is essentially
   flat (Sharpe 0.019 per the CUSUM-break finding in regime analysis).
   The meta-model correctly identifies the absence of edge and
   minimum-participates.

To discriminate, a SINGLE-VARIABLE sensitivity ablation is registered as
part of THIS pre-reg (not a new pre-reg):

**Ablation cell**: `tbm_meta_us10_tmax40` (status `sensitivity_run`).
**Single change vs §3**: `cfg.t_max = 40` business days (vertical barrier
only). All other parameters identical: `pt_mult = 8.0`, `sl_mult = 4.0`
(both as σ-multipliers, NOT absolute — barriers auto-track), single
tau = 0.50, single feature_subset = "ER_plus_rest", `cusum_kappa = 1.0`,
`g_min = 0.30`, Y-daily inference per fixes 1-3.

**Expected effect on labels (HANDOFF §3 algebraic prediction):**
- Label-window length × event count cuts to ~1/3 of T_max=120 case.
- Therefore `avg_uniqueness` should triple from ~0.07 to ~0.21 (above
  pre-reg as-TBM-iid 0.20 threshold).
- Effective sample triples from ~290 to ~870 distinct training units.

**Diagnostic-tree decision rule (single-variable disambiguation):**

| Observed `g_max_observed` (T_max=40) | Inference | Implication |
|---|---|---|
| **> 0.75** | meta-sizer NOW uses its full range when given enough effective sample → previous floor mode was **effective-sample collapse**, NOT a no-signal verdict | Stage-1 HAS value on ZN; re-tune T_max as the operational sweet spot |
| **< 0.60** | even with 3× effective sample meta still floors → ZN-post-2003 has NO learnable conditional edge for this feature set | Stage-1 on ZN single-instrument is at its ceiling; pursue Stage-2 speed-tilt or multi-instrument |
| **0.60 — 0.75** | partial response; T_max = 40 not the inflection point | Schedule T_max ∈ {60, 80} additional sweep cells, increment family n_configs accordingly |

**This is a DIAGNOSTIC, not an optimisation.** If T_max=40 looks better,
the conclusion is "Stage-1 has value, the T_max choice matters" — NOT
"adopt T_max=40 as the production value". Adopting any T_max as
"best of sweep" would itself require a separate, multi-T_max
selection-aware pre-reg under DSR with N_configs bumped accordingly.

**Family-scope accounting at T_max=40 lock:**

- `n_configs_searched`: 50 → **58** (this cell's internal_grid_size = 8
  contributes; single tau × single feature; the +8 reflects the
  CUSTOMARY sensitivity-sweep cost — even though THIS run is single-config
  internally, the family treats the T_max axis as one further selection
  dimension to be honest about).
- `expected_max_sharpe_at_N=58` annualised: **0.3326** (computed via
  `arki.utils.dsr.expected_max_sharpe(sr_trials_std=0.1426, n_trials=58,
  annualization_factor=256)`).

**Gates re-applied at T_max=40 cell:**

All G-TBM1..G-TBM6 + G-recon are re-evaluated. PBO stays N/A (single
config internal). G-family-DSR uses the bumped 0.3326 threshold.

The HEADLINE output of this ablation is NOT pass/fail of gates but the
`g_max_observed` and the `avg_uniqueness` numbers — those route the
diagnostic-tree decision above.

### 5.2 Gap-handling rules (3 explicit, supersede the prior single-line guidance)

The 2024-04 → 2025-04 gap (262 business days, 100% absent from the panama
feed) is visible in the data. The σ estimator's `ewm(alpha=0.05,
adjust=False)` does NOT reset on date gaps natively (verification confirmed:
σ pre-gap = σ post-gap = 0.3497 to 4 decimal places — the recursion carries
the last value across the gap). To preserve label integrity, the runner
MUST apply ALL THREE rules below to every gap of `> 5 business days`. These
are not alternative options; they cover three DIFFERENT failure modes.

**Rule 5.2.a — CUSUM reset (event-detector integrity).**

Inside the CUSUM event filter (López de Prado 2018 ch.2 §2.5 Eq.(2.5)),
whenever `(idx[t] − idx[t−1]).days > 5`: set the running cumulative
deviation state `s_pos = 0` and `s_neg = 0`. Prevents a pre-gap drift
accumulating across the gap and firing a spurious event on the first
post-gap bar.

**Rule 5.2.b — σ re-warmup (estimator integrity).**

For the first `vol_span = 20` BUSINESS DAYS after a gap end, mask events
from the label set (do not emit `(t, y, w)` triples for those days). The σ
recursion needs that many bars to re-converge from the stale pre-gap value
once new observations resume; using σ during re-warmup would set
barriers based on a contaminated scale.

**Rule 5.2.c — Cross-gap label drop (label integrity).**

Any CUSUM event whose triple-barrier window `[t_event, t_event + T_max = 120
business days]` OVERLAPS with any gap (start-edge, interior, or end-edge):
drop the event from sampling entirely. This covers:

- Events fired within `T_max` business days BEFORE a gap (barrier window
  would extend into the gap; outcome undefined).
- Events fired inside a gap (no observation series during the gap).
- Events fired within `vol_span` business days AFTER a gap end (already
  caught by Rule 5.2.b; included here for redundancy).

The label is either ill-defined or path-truncated; safer to drop than to
mis-label.

**Quantification + audit (assumption_check for label integrity):**

The runner MUST emit, to the cell's `summary.csv`:

- `n_cusum_events_total`: total CUSUM events fired pre-gap-filtering.
- `n_events_dropped_cusum_reset`: events suppressed by Rule 5.2.a (typically the spurious first-post-gap event).
- `n_events_dropped_rewarmup`: events suppressed by Rule 5.2.b.
- `n_events_dropped_cross_gap`: events suppressed by Rule 5.2.c.
- `n_events_used_for_labels`: final label sample count (= total − drops).

If `n_events_used_for_labels / n_cusum_events_total < 0.75`, the gap
filtering is too aggressive (or there are more gaps than known); log to
DECISIONS for investigation before downstream training.

## 6. Code snapshot + `depends_on` (Rule 6 input lineage)

**This experiment EXPLICITLY depends on prior family cells:**

```yaml
depends_on:
  family: futures_momentum
  panel: single_instrument
  baseline_cell: exec_friction_martin_baseline_us10_1m
    artifact_paths:
      side_source_daily_returns: ars/runs/20260529T172206Z_martin_baseline_us10_1m/equity_curves.csv
      side_source_trades:        ars/runs/20260529T172206Z_martin_baseline_us10_1m/trades_US10.csv
      manifest:                  ars/runs/20260529T172206Z_martin_baseline_us10_1m/manifest.json
  primary_cell:  exec_friction_martin_primary_us10_1m
    artifact_paths:
      side_source_daily_returns: ars/runs/20260529T172225Z_martin_primary_ema2_us10_1m/equity_curves.csv
      side_source_trades:        ars/runs/20260529T172225Z_martin_primary_ema2_us10_1m/trades_US10.csv
  regime_features_input: arki/results/2026-05-29/execution_friction_us10_regime_analysis_regime_buckets.csv
  per_trade_mfe_mae_input: arki/results/2026-05-29/execution_friction_us10_regime_analysis_per_trade_mfe_mae.csv
```

- **Runner** (to be written): `scripts/tbm_meta_us10_baseline_runner.py`.
- **Source skeleton**: `/Users/msyeom/Downloads/stage1_meta_labeling.py` —
  lift `cusum_events`, `triple_barrier_labels`, `average_uniqueness`,
  `sample_weights`, `build_features`, `MetaSizer`, `size_from_meta`,
  `position`, `purged_kfold_indices`. Adapt `purged_kfold_indices` →
  combinatorial purged + embargo for full CPCV.
- **DSR/PBO single source of truth**: `arki.utils.dsr` (NOT the skeleton's
  copies — the family-level utility was bug-fixed for per-period vs
  annualised unit consistency; see `python -m arki.utils.dsr` self-check).
  Skeleton functions MUST be replaced with `from arki.utils.dsr import
  deflated_sharpe_ratio, probability_of_backtest_overfitting,
  expected_max_sharpe`.
- **Critical implementation fix (HANDOFF §3 code-fix):** the skeleton's
  `daily_vol()` uses pct-returns which explode on ZN panama (sign-crossing
  price). Replace with absolute-change EMA-of-squares per Martin §2.5
  (formula in §3 constants above) AND the no-look-ahead sigma-floor.
- **Engine**: pysystemtrade native chapter-15 for the side (no engine
  edit); meta-layer is a standalone numpy/sklearn attachment that reads
  the engine's outputs.
- **Python**: 3.10.15 (project venv).

## 7. CPC v1 comparison plan

**Baseline (variant)**: `exec_friction_martin_baseline_us10_1m` (g=1 Martin
6-speed integer baseline) — Sharpe 0.355, MaxDD −58.13%, skew_per_trade
5.99 from the existing run.

**Candidate**: `tbm_meta_us10_baseline_1m` (this cell).

**Lifts reported** (each with point estimate + 1000-resample IID
bootstrap CI on daily returns):

- `sharpe_net(meta) − sharpe_net(baseline)`
- `DSR(meta) − DSR(baseline)` ← **primary acceptance gate G-TBM1**
- `max_drawdown_pct_geom(meta) − max_drawdown_pct_geom(baseline)`
- `skew_daily(meta) − skew_daily(baseline)`
- `ann_subsystem_turnover(meta) − ann_subsystem_turnover(baseline)`
- meta-model OOS F1 vs naive base-rate F1
- meta-model OOS precision, recall (class-imbalanced; HANDOFF §5
  reporting requirement)

**Common randomness control**: same daily ZN price series for both arms;
same vol estimator (Martin 20d EMA-of-sq absolute-change); same
exec_profile (carver_native, $1M). Only the position-scaler differs (g=1
vs g(m)).

**PBO scope**: over the FULL pre-registered τ × feature-set grid (8
configs × CPCV folds; HANDOFF §5 — "PBO must be computed over the real
config grid (≥ ~10 configs) to be meaningful"). 8 < 10 is a marginal
breach of HANDOFF guidance — log as a finding if PBO is borderline; do
NOT inflate the grid post-hoc to "make PBO meaningful".

## 8. Out of scope (explicit non-claims)

- **No engine change.** Martin side is consumed as `sign(position)`; no
  signal redesign, no rule-structure change. (HANDOFF §0 — locked.)
- **No multi-instrument transport.** τ tuned on ZN does NOT transfer to
  Bund / GTAA without re-tuning. Single-instrument scope.
- **No Stage-2 speed-tilt** `λ(s_t)` — separate queued cell.
- **No causal DAG** confounder adjustment (Q4 LdP layer ②) — separate
  family-level workstream.
- **No conformal OOD guardrail** (Q4 LdP layer ③ governor) — deferred to
  family scope when sweep CI gates are productionised.
- **No new live-trading recommendation** (project profile
  `live_trading: false` invariant).

## 9. Owner sign-off

Signed at the top of this document. Plan-approval and the HANDOFF design
document (`/Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md`) constitute
the audit trail.

## 10. Family scope (Rule 6 multiple-testing context — explicit)

This pre-registration JOINS the `futures_momentum` family. At lock time:

| Field | Value |
|---|---:|
| `n_cells_pre_registered_queued` (post-lock) | 13 |
| `n_configs_recorded` (post-lock, +8 for this cell) | 20 |
| `n_configs_unrecorded_upper_bound` | 30 (unchanged) |
| `n_configs_searched` (post-lock) | 50 |
| `selection_correction` | deflated_sharpe_lopez_de_prado_2014 |
| `expected_max_sharpe_at_N=50` (annualised) | **0.325** |

Locking this pre-reg therefore raises the family-level absolute Sharpe
threshold from 0.314 (N=41) to 0.325 (N=50) — the self-correcting loop
the family layer is built around. Any future cell that wants to claim
absolute promotion must clear 0.325 ann Sharpe AFTER its own internal
selection. This cell's primary acceptance gate G-TBM1 is RELATIVE (DSR
uplift vs baseline), which is strictly stronger than the absolute
family threshold when the baseline already clears it (baseline ann
Sharpe 0.355 > 0.325).

## 11. Verification anchors (sanity, not gates)

- HANDOFF §2 first-CC-task: reproduce raw ZN `sigma median ≈ 0.39` price
  points on the repo's ZN feed within ±0.02. Confirms same panama series
  + same vol formula. If miss > 0.05, halt and investigate before
  proceeding to TBM labeling.
- HANDOFF §2 first-touch checks: PT=8σ touch frequency ≈ 38%, SL=4σ touch
  frequency ≈ 38% on the in-sample portion of the labeled events. Large
  deviations (>10pp from these targets) suggest the sigma estimator or
  H/L touch detection differs from the calibration measurement; document
  in DECISIONS.
- After first label run: meta-feature ER_60d-tercile conditional Sharpe
  on the LABELED set should still show wide spread (calibration set
  showed spread 5.64). If spread collapses on labels, the labeling step
  is removing the regime signal — design problem.
