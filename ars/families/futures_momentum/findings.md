# findings — futures_momentum family

This is **Layer 3** of the family system. It records axis-level elasticity
(which dimension moves performance) plus transport status (which
findings have been replicated outside their original cell). Cells live
in `registry.yaml`; matrix dashboard lives in `matrix.md`; this file
holds the *learned-from-the-cells* layer.

**Discipline:**

- **Direction-only when n_pairs ≤ 2.** With only one or two clean pairs,
  any "DEAD / active" label is over-claim. Numbers below are direction
  hints, not estimates. Upgrade to regression-based partial effects
  (ANOVA / Shapley) when Panel A cells ≥ 25.
- **Clean pairs only.** A pair counts only when *exactly one* axis differs
  between the two cells. Pairs that differ on multiple axes are
  **confounded** and excluded (we record their exclusion below for
  transparency).
- **No cross-panel inheritance.** Panel A elasticities do NOT predict
  Panel B elasticities (e.g. `vol_estimator` dead in single-instrument
  may revive in portfolio because the same estimator drives risk-parity
  weighting). Findings here are **Panel-A-only** until Panel B opens.
- **Multiple-testing context.** With `n_configs_searched = 41` in
  `family.yaml`, a single-cell promotion requires Sharpe clearing the
  DSR threshold computed via `arki.utils.dsr.expected_max_sharpe(...)`.
  None of the entries below have yet been DSR-checked at family scope.

---

## Panel A elasticity — clean-pair audit (US10 cells only)

`Δ Sharpe` is `|Sharpe(cell_i) − Sharpe(cell_j)|` averaged across clean
pairs. n is the number of clean pairs (other axes held fixed). For
n = 0, the column shows "no clean pair available -- confounded with
{axis}".

| Axis | Direction | mean Δ Sharpe | n clean pairs | Tentative read |
|---|---|---:|---:|---|
| `vol_estimator` (carver_mixed_35d vs martin_20d_ema_of_sq) | ≈ 0 | 0.0035 | **2** | direction: near-zero on US10 at integer+cap exec_profile; UNTESTED on other instruments + UNTESTED inside portfolio (Panel B) |
| `overlay` (none → carry / sMOM / dMOM / fast_tilt) | mixed: 3 falsified, 1 pending remediation | varies | **4** | high-RISK axis: most overlays kill perf, but sMOM (pre-remediation) showed +0.255 lift; TBM_meta_label UNTESTED |
| `rule_structure` (single_ema2_20_40 vs six_speed_ewmac_equal) | hint: 6sp > single | (0.039 *confounded*) | **0** | NO CLEAN PAIR — the only pair (martin_primary vs martin_baseline) ALSO varies exec_profile (numpy+continuous+capoff vs native+integer+cap). Δ 0.039 cannot be attributed to rule alone |
| `exec_profile` (paper_fidelity_numpy vs carver_native) | hint: native > numpy | (0.084 *confounded*) | **0** | NO CLEAN PAIR — same confound as above (varies rule simultaneously) |
| `capital_usd` (50k vs 1m within carver_native) | ≈ 0 Sharpe, big skew_per_trade effect | 0.020 Sharpe, 1.88 skew | **3** | Sharpe near-invariant to capital on US10; per-trade skew GROWS at $1M (4.1 → 6.0 / 4.4 → 6.7) as integer grid fines up |

### Clean pairs counted

- `vol_estimator` (n=2):
  - `exec_friction_carver_6speed_us10_50k` ↔ `exec_friction_martin_baseline_us10_50k`
  - `exec_friction_carver_6speed_us10_1m`  ↔ `exec_friction_martin_baseline_us10_1m`
- `overlay` (n=4): `martin_post_hoc_baseline_us10` ↔ each of
  {`dmom_us10`, `smom_us10`, `fast_tilt_ewmac`, `carry_toggle`} — all hold
  vol/rule/exec/capital constant, vary overlay only.
- `capital_usd` (n=3):
  - `exec_friction_carver_6speed_us10_50k` ↔ `_1m`
  - `exec_friction_martin_baseline_us10_50k` ↔ `_1m`
  - `exec_friction_martin_primary_us10_50k` ↔ `_1m` (continuous → trivially equal, scale-invariant)

### Confounded pairs (excluded from elasticity, recorded for transparency)

- `exec_friction_martin_primary_us10_*` vs `exec_friction_martin_baseline_us10_*`:
  varies `rule_structure` AND `exec_profile` simultaneously. Δ Sharpe
  0.039 (50k) / 0.039 (1m) reflects BOTH axes combined, not either alone.
  → adds 2 confounded pairs to the *un-attributable* pile.

---

## Transport status per axis

- `vol_estimator` direction (≈ 0 on US10): **untested elsewhere**. Do
  not assume dead on Bund / Gilt / Eurodollar; revive in Panel B is plausible
  (risk-parity weighting feeds on vol estimator).
- `overlay` direction (3 falsified, 1 pending): **untested elsewhere**.
  Each overlay's falsification is a US10-specific finding. dMOM may behave
  differently in a portfolio context (Hanauer & Windmüller's original
  motivation was cross-sectional equity).
- `rule_structure` direction (hint 6sp > single): **NOT cleanly attributed
  even on US10**. Resolution requires a pair holding exec_profile constant
  (e.g. single_ema2_20_40 + carver_native vs six_speed_ewmac_equal +
  carver_native). This is a NEW cell we have not yet pre-registered.

---

## Implied next experiments (elasticity-ranked, copied to queue.md)

1. **TBM_meta_label overlay** on `exec_friction_martin_baseline_us10_1m`
   — overlay axis is the only axis with both meaningful prior signal AND
   an untested level. Highest expected information per cell.
2. **rule_structure de-confound**: single_ema2 + carver_native cell. Cheap
   to register (existing Carver engine; just restrict rules to one EWMAC
   variant). Resolves the largest "unknown direction" in the matrix.
3. **vol_estimator transport** to Bund: replicate the
   `martin_baseline_us10 vs carver_6speed_us10` pair on Bund. Confirms or
   refutes the ≈0 finding outside US10.
4. **sMOM remediation** (blocked) — fix sizing rule mismatch first;
   re-pre-register.
5. **Panel B opens** with `DM_rates_5, equal_weight, TS_only` on the
   best Panel A spec. Smallest universe step from single → portfolio.

`vol_estimator` further sweeps on US10 alone: **skip** (low-information).

---

## Maintenance

- When a new cell is added to `registry.yaml` + `family.yaml`, re-run
  `scripts/family_elasticity.py` (to be written) which:
  - Recomputes clean-pair counts per axis.
  - Updates this file's elasticity table.
  - Recomputes `n_cells_registered`, `n_configs_recorded` in family.yaml.
  - Recomputes `expected_max_sharpe_at_N` via `arki.utils.dsr`.
- Promotion gate at family scope: candidate Sharpe must clear
  `expected_max_sharpe_at_N` (annualised, ann_factor=256). The pre-reg
  lint Rule 6 (added to `validate_preregistration.py`) flags pre-regs
  whose ex-ante headline target falls below current threshold.
