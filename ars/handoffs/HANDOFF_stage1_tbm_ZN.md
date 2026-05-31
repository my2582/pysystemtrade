# HANDOFF — Stage-1 Triple Barrier attachment to ZN Martin primary

**Target environment:** Claude Code, inside the Arki backtest repo (the one that
already runs `martin_primary_ema2_us10` / `martin_baseline_us10` on US10/ZN).
**Author of this doc:** design/analysis session (chat). **This doc is the first
input to the Claude Code session.**

**One-line goal:** attach Lopez de Prado Triple-Barrier *labeling* on top of the
EXISTING ZN Martin side (do NOT rebuild the signal), produce a meta-label
dataset, train a size-only meta-model, and validate with purged CV / Deflated
Sharpe / PBO — all on DAILY data.

---

## 0. Locked decisions (do not re-litigate)

| # | Decision | Value | Rationale (from ZN diagnostics) |
|---|---|---|---|
| 1 | **Labeling unit** | **CUSUM-day** (label every CUSUM event, not per-trade) | single-speed ZN gives only 106 trades → too thin for a meta-model. Event-day sampling thickens the training set. |
| 2 | **Barrier calibration** | **Recompute on RAW ZN daily σ** (first CC task) | MFE/MAE in the analysis are *strategy-pct (vol-target 20%)*, not raw price. Barriers must be raw-σ. |
| 3 | **Top meta-features** | **ER_20d & ER_60d first**, then the rest | conditional-Sharpe spread for ER is 4.35 / 5.64 — by far the strongest separator. |
| — | **Side source** | **EXISTING Martin primary, sign only** | Q4 lock: side = Martin (fixed), size = learned. Engine untouched. |
| — | **Sizing floor** | **g_min = 0.30** | Q5 lock: g(·) ∈ [0.30, 1.0], ≥ 0 ⇒ Martin positive-skew constraint (eq.20) preserved by construction. |

---

## 1. ZN diagnostic findings that drive this design

(Computed from the uploaded `execution_friction_us10_regime_analysis_*` files for
`martin_primary_ema2_us10_1m`, the paper-fidelity single-EMA2 N=20,40 cell.)

**A. Non-stationarity — edge decays then revives**
- Decade Sharpe: 1980s **0.51** → 1990s 0.35 → 2000s 0.30 → 2010s **0.11** → 2020s 0.37.
- CUSUM break **2003-06-13**: pre-Sharpe 0.571 → **post-Sharpe 0.019** (Δ −0.553).
  *Standalone EMA2 is essentially flat post-2003.*
- Daily skew flips sign: negative (1980s–2000s) → positive (2010s–2020s). Martin's
  "positive skew is a design property" only holds on ZN in the recent regime.

**B. Conditional performance — Efficiency Ratio is king**
Conditional Sharpe by regime bucket (spread = max−min):

| Axis | low | mid | high | spread |
|---|---|---|---|---|
| **ER_60d** | −2.70 | 0.86 | **+2.95** | **5.64** |
| **ER_20d** | −1.57 | −1.37 | **+2.78** | **4.35** |
| sign_agreement | 0.29 (all agree) | 0.53 | **4.12 (split)** | 3.84 |
| ZN_60d_return | −0.29 | −1.46 | +1.60 | 3.06 |
| realised_vol_60d | 1.29 | 1.80 | 0.22 | 1.58 |
| ZN_20d_autocorr | −0.49 (pos) | 0.43 | 0.56 (neg) | 1.05 |
| realised_vol_20d | 0.43 | 0.23 | −0.32 | 0.74 |

- **ER (trend efficiency) is the dominant separator** → primary meta-feature.
- **sign_agreement is COUNTER-INTUITIVE on ZN:** the `split_1_1_1` bucket has the
  HIGHEST Sharpe (4.12, n=136), not the lowest. Do NOT hard-code "split = de-risk".
  Keep the feature; let the model learn the sign.
- vol / autocorr are weak separators → lower priority.

**C. Event windows — 6-speed beats single-EMA2 in every crisis**
GFC 0.07 vs 0.60; COVID 2.55 vs 3.04; Fed-hike-2022 0.54 vs 0.93. (Motivates the
Stage-2 speed-tilt and the pseudo-cross-section breadth trick below.)

**D. Per-trade risk geometry (strategy-pct; gives scale-free asymmetry)**
- Hit-rate 26% (28W/78L) — few big winners, many small losers (Martin's prediction).
- winners MFE median **32.1%** vs losers MAE median **3.21%** → extreme asymmetry.
- losers MAE median ≈ **2.6 daily-σ**; holding days median **56**, p75 **138**, p90 214.

---

## 2. Calibrated barriers — MEASURED ON RAW ZN σ (replace skeleton defaults)

**These values are now measured on the actual raw ZN panama price** (`US10_panama_daily.csv`,
1982–2026, 10,818 days), not strategy-pct. The earlier strategy-pct figures (PT 3.0σ /
SL 1.5σ) were OFF IN SCALE by ~a factor of ~3 and are SUPERSEDED.

**Martin σ recomputation (CRITICAL — absolute change, not pct):**
ZN panama price crosses zero (−35 in 1982 → +139 in 2026; 910 days have |price|<5 in
1986–1990). **pct-returns explode there.** Use ABSOLUTE daily change — which is also exactly
Martin §2.5 for rate futures:
```
dpx = price.diff()
var = (dpx**2).ewm(alpha=0.05, adjust=False).mean()    # gamma=0.95 -> alpha=0.05
sigma = sqrt(var).clip(lower = sigma.expanding(20).median()*0.2)   # no-look-ahead floor
```
Result: **sigma median = 0.39 price points** (p25 0.32, p75 0.48).

**Random-walk yardstick:** over T_max=120d, typical travel ~ sigma*sqrt(120) ~ **11 sigma**.
So barriers live in the SINGLE-DIGIT sigma range, NOT 1.5–3 sigma.

| Param | Skeleton default | **RAW-σ calibrated** | Basis (measured) |
|---|---|---|---|
| `t_max` | 20 d | **120 d** | raw holding: median 58, p75 142, p90 216 d. |
| `sl_mult` (SL) | 2.0σ | **4.0σ** (raw ZN σ) | losers MAE median 4.68σ; SL=4σ ⇒ only 38% hit (avoids noise stops). |
| `pt_mult` (PT) | 2.0σ | **8.0σ** (raw ZN σ) | winners MFE median 20.9σ; PT=8σ ⇒ 38% reach it. PT:SL = **2:1**, as the win/loss MFE-MAE asymmetry (4.5×) demands. |
| touch detection | H/L | **H/L if ZN OHLC available**, else close-to-close | daily fidelity, not intraday. Same-day PT&SL tie ⇒ SL first (conservative). |

**Measured raw-σ geometry (104 trades remapped onto raw price):**
- winners (40%): MFE median **20.9σ**, MAE median 0.91σ — winners barely retrace.
- losers (60%): MFE median 1.67σ, MAE median **4.68σ**.
- touch frequencies: PT 4σ→53%, 6σ→46%, 8σ→38%, 10σ→34%; SL 2σ→62%, 3σ→51%, 4σ→38%.

**FIRST STEP in CC is now verification, not derivation:** reproduce sigma median ≈ 0.39
on your repo's ZN feed (confirms same panama series + same vol formula), then lock
PT=8σ / SL=4σ / T_max=120. After the first label run, fine-tune against YOUR raw MFE/MAE
(should match the table above within sampling noise).

**Caveat on 40% vs 26% hit-rate:** the raw remap shows 40% would-touch winners vs the
26% per-trade hit-rate in the analysis CSV. Difference = (a) would-touch ignores first-touch
ordering, (b) raw price path vs vol-targeted strategy path. Use 8σ/4σ as the START; the
CPCV τ-tuning step co-optimizes barrier choice against OOS DSR.

---

## 3. Integration = Option B (label-only attachment)

**Do NOT port the skeleton's signal generator.** Keep the repo's ZN Martin side.
Pull exactly THREE functions from `stage1_meta_labeling.py` and feed them the
repo's existing outputs:

```
repo ZN Martin primary ─► side_t (sign only), daily OHLC, Martin σ_t
                               │
        ┌──────────────────────┼───────────────────────┐
        ▼                      ▼                          ▼
  cusum_events()      triple_barrier_labels()     average_uniqueness()
  (κ = 1.0)           (PT 3.0σ / SL 1.5σ /        (overlap weights →
   → event days        T_max 120, side as input)    sequential bootstrap)
                               │
                               ▼
                    meta-label dataset (y, weights)
                               │
            build_features()  ►  ER_20d, ER_60d (TOP), signal_dispersion,
                                  primary_strength, vol, vol_of_vol,
                                  autocorr_1, drawdown   [sign_agreement: learn sign]
                               │
                               ▼
            MetaSizer (bagged trees, max_samples = avg_uniqueness)
                               │
                               ▼
            size_from_meta()  ►  g(m) ∈ [0.30, 1.0]
                               │
            position = side · g / σ · vol_target_scaler
```

**Functions to lift verbatim** (from `stage1_meta_labeling.py`, already smoke-tested):
`cusum_events`, `triple_barrier_labels`, `average_uniqueness`, `sample_weights`,
`build_features`, `MetaSizer`, `size_from_meta`, `position`, and the whole
validation rail (`purged_kfold_indices`, `deflated_sharpe_ratio`,
`probability_of_backtest_overfitting`, `perf_metrics`).

**Config edits** (in `Stage1Config`): `t_max=120`, `pt_mult=8.0`, `sl_mult=4.0`.
Keep `g_min=0.30`, `cusum_kappa=1.0`, `vol_span=20`. Leave `tau` for CPCV tuning.

**CODE FIX REQUIRED — `daily_vol()` uses pct-returns, which EXPLODE on ZN panama
(sign-crossing price).** Replace the pct-return vol with ABSOLUTE-change vol:
```python
def daily_vol(price, span=20):
    dpx = price.diff()                                   # absolute change (Martin §2.5)
    vol = np.sqrt((dpx**2).ewm(alpha=0.05, adjust=False).mean())   # gamma=0.95
    return vol.clip(lower=vol.expanding(min_periods=span).median()*0.2)
```
This σ is in PRICE POINTS, so barriers (PT=8σ/SL=4σ) and the position `side·g/σ`
are all in price-point units — consistent. The CUSUM filter must likewise use
absolute log-less drift on price points, NOT pct. (Also: drop the single 371-day
gap window 2024-04→2025-04 from event sampling, or let CUSUM reset across it.)

---

## 4. Breadth problem (single ZN) — required mitigation

106 trades is thin; even CUSUM-day sampling on one instrument risks meta-model
overfit. Apply BOTH:

1. **CUSUM-day labeling** (decision #1) — already raises sample count.
2. **6-speed pseudo-cross-section** — treat the 6 EWMAC speeds (ewmac2_8 … ewmac64_256)
   as pseudo-assets: generate side/label/features per speed and POOL them into one
   meta-model (re-uses the skeleton's cross-sectional pooling in `run_stage1`).
   Justified by finding (C): speeds carry genuinely different crisis behavior.

If after both the per-fold event count is still < ~300, SIMPLIFY the model:
bagged trees → L2-regularized logistic or a shallow single-feature (ER) threshold.

---

## 5. τ tuning + OOS validation (the productionize step)

- Tune participation threshold `tau` with **Combinatorial Purged CV (CPCV)** +
  purging/embargo (skeleton provides purged k-fold; extend to combinatorial).
- **Acceptance is RELATIVE, not absolute:** meta-sized must beat the `g=1` Martin
  baseline OOS on **Deflated Sharpe uplift** — not raw Sharpe. Set DSR `n_trials`
  to the TRUE number of configs searched (τ grid × barrier variants × feature sets),
  not a proxy.
- Report meta-model **precision / recall / F1** (class-imbalanced; accuracy is
  misleading), plus strategy-level Sharpe / Calmar / skew vs baseline.
- **PBO** must be computed over the real config grid (≥ ~10 configs) to be meaningful;
  the smoke-test PBO on 4 synthetic assets is NOT a signal.

---

## 6. Acceptance gates (Stage-1 passes only if ALL hold, OOS)

- [ ] meta-sized **Deflated-Sharpe uplift > 0** vs g=1 Martin baseline (raw-σ barriers).
- [ ] **PBO < 0.5** over the real config grid.
- [ ] MaxDD(meta) ≤ MaxDD(baseline) (DD reduction is the primary Stage-1 value).
- [ ] positive-skew preserved: realized strategy skew(meta) ≥ skew(baseline) − ε.
- [ ] meta-model OOS **F1 > naive base-rate classifier** on the held-out folds.
- [ ] sanity: g(·) never < 0.30, never > 1.0; no look-ahead in σ-floor or features.

---

## 7. Honest caveats to keep visible

1. **Strategy-pct vs raw — NOW RESOLVED for barriers.** Barriers are calibrated on
   raw ZN σ (§2): PT=8σ / SL=4σ / T_max=120, σ median 0.39 price points. The earlier
   strategy-pct figures are superseded. Remaining transfer caveat: the *conditional-Sharpe
   buckets* (§1B) and *event windows* (§1C) are still strategy-pct (vol-targeted) — fine,
   since those drive FEATURE selection, not barrier scale.
2. **Edge is regime-concentrated (ER) and post-2003 flat standalone.** Stage-1
   (size) mitigates drawdown but will NOT manufacture alpha where the side has none.
   The larger uplift is expected from **Stage-2 speed-tilt** (finding C). Set
   expectations accordingly: Stage-1 = risk shaping + precision, not new alpha.
3. **Single instrument.** τ tuned on ZN does NOT transfer to the GTAA universe;
   re-tune per instrument / pool when more contracts are added.

---

## 8. Out of scope for this CC session (later stages)

Stage-2 speed-tilt λ(s_t); activation aggressiveness; causal/DAG confounder
adjustment (Q4 layer ②); conformal OOD guardrail; Deflated-Sharpe governor as a
standing CI gate (Q4 layer ③) across the full GTAA book.
