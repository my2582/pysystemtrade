# queue — futures_momentum family (elasticity-ranked)

Pending experiments ranked by **expected information per cell**, derived
from `findings.md` clean-pair audit. NOT pure dependency order — items
high on elasticity but with deeper dependencies still rank above lower-
elasticity items with no dependencies. Promotion is gated on the
family-level DSR threshold (see family.yaml § multiple_testing).

Schema per item:
- **cell_id**: the slug it will get in registry + family.
- **depends_on**: input cells whose artifacts feed this experiment.
- **panel**: A or B (which panel it joins).
- **why**: what axis-level question it resolves.
- **pre_reg**: target file path (Path A discipline).
- **estimated internal_grid_size**: number of internal sweeps this cell
  will perform (feeds DSR N).
- **status**: `queued | blocked | in_progress | completed`.

---

## Authoring a pre-reg from this SOT (cold-start pointers)

Added 2026-05-31 after the cold-start handoff test
(docs/arki/coldstart_handoff_test_result_2026-05-31.md) found these were the
two HIGH-severity gaps for a fresh agent:

- **Template + section schema**: `ars/evidence_packs/_template/preregistration.md`
  (copy it; it carries a Rule-7 `predictions:` block). A locked worked example:
  `ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md`.
- **Full lint Rules 1-7 text + checker**: `scripts/validate_preregistration.py`
  (docstring enumerates all rules) and `arki/wiki/onboarding/04_lessons_distilled.md`.
  Lint before locking: `venv/bin/python scripts/validate_preregistration.py <prereg.md>`.

---

## Commitments (added 2026-05-31)

> Process discipline is *defensive* — to justify confidence we need *offensive* alpha hunt
> on a measured schedule. Top-3 queue items below are committed to time-bound deadlines.
> Missing a deadline triggers a process-cost review (per cell cycle-time target ≤ 1 business
> day from pre-reg lock to family commit; if exceeded, framework simplification is on the
> table).

| Item | Time commitment | Trigger if missed |
|---|---|---|
| #2 rule_structure de-confound (single_ema2 + carver_native) | pre-reg lock by **2026-06-07**; runner + result by **2026-06-10** | Review process-cost; consider simplifying CPCV folds |
| #1.2 sMOM capped G4 refinement (LESSONS Entry 3 rule applied) | pre-reg amendment + re-verdict by **2026-06-12** | Review G4 design (refined rule may not be sufficient) |
| #5 Panel B open — DM_rates_5 equal_weight TS-only | pre-reg lock by **2026-06-21** (after #2 confirms rule choice) | Re-prioritise; Stage-2 speed-tilt may take precedence |

**Future-evidence threshold**: after these three cells complete, total predictions for the
family will be ~30-40 (per the predict-then-measure scorecard convention introduced in
`docs/arki/session_predictions_scorecard_2026-05-31.md`). Hit rate at that point either
raises or lowers the current 75% baseline. If hit rate drops below 65%, framework
discipline review triggered.

**Process-cost measurement** (per `commitments`): each completed cell records 5
timestamps in its `manifest.json` (`pre_reg_authored_at`, `runner_started_at`,
`runner_finished_at`, `gates_evaluated_at`, `family_committed_at`). Average cycle time
> 1 business day → simplification trigger.

---

## Top of queue (do next)

### 1. tbm_meta_us10_baseline_1m  ✅ PRE-REG LOCKED 2026-05-30

- **status**: **in_progress** (pre-registration locked; runner pending)
- **pre_registration**: [ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md](../../evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md) — Path A, lint Rules 1-6 PASS at lock time
- **input handoff**: `/Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md` (locks PT=8σ / SL=4σ / T_max=120 raw-σ, CUSUM-day labeling, ER top features, g_min=0.30, single SOT DSR via `arki.utils.dsr`)
- **why**: `overlay` axis n=4 clean pairs with mixed direction (3 falsified, 1 pending remediation); TBM_meta_label is the one untested level. Highest expected information per cell.
- **depends_on**: see pre-reg §6; primary inputs are `exec_friction_martin_baseline_us10_1m` (side source) + regime analysis CSVs.
- **panel**: A
- **internal_grid_size**: **8** (τ ∈ {0.40, 0.50, 0.55, 0.60} × feature subset {ER-only, ER+rest})
- **acceptance gates (all OOS via CPCV with 2003-06-13 break straddling)**:
  - G-TBM1: Deflated-Sharpe uplift > 0 vs g=1 Martin baseline
  - G-TBM2: PBO < 0.5 over τ × feature-set × CPCV grid
  - G-TBM3: MaxDD(meta) ≤ MaxDD(baseline)
  - G-TBM4: skew_daily(meta) ≥ skew_daily(baseline) − 0.20
  - G-TBM5: meta-classifier F1 > naive base-rate F1 + 0.02
  - G-TBM6 (sanity): `g_t ∈ [0.30, 1.0]` always (bounded; preserves Martin §4 Eq.(20) positive-skew)
- **family DSR threshold awareness**: `n_configs_searched = 50` post-lock; `expected_max_sharpe_at_N=50 = 0.325` ann. Relative DSR uplift (G-TBM1) is the primary gate; absolute family-threshold disclosure is REPORTING only.
- **runner**: `scripts/tbm_meta_us10_baseline_runner.py` (to be written; integrates skeleton from `/Users/msyeom/Downloads/stage1_meta_labeling.py` minus its DSR/PBO sub-copies, which are replaced by `from arki.utils.dsr import ...`)
- **next action**: implement runner, execute, append registry entry, run aggregator

### 2. rule_structure_deconfound_us10

- **why**: rule_structure direction is the **only axis with n=0 clean
  pairs**. Resolves the largest "unknown" in the matrix.
- **depends_on**: existing Carver engine config (no new artifact needs).
- **panel**: A
- **design**: register single_ema2_20_40 + **carver_native** + cap ±20
  + integer (HOLD exec_profile constant). One new cell at $1M.
- **comparator (exact)**: `exec_friction_martin_baseline_us10_1m`
  (run_dir `ars/runs/20260529T172206Z_martin_baseline_us10_1m`; sharpe_net
  0.355). The $1M variant is the clean pair — it matches the new cell on every
  axis except rule_structure. (Was "vs martin_baseline_us10"; disambiguated
  2026-05-31 per cold-start test gap #5.)
- **estimated internal_grid_size**: 1 (no sweep — confirmatory)
- **pre_reg target**: `ars/evidence_packs/rule_deconfound_us10/...preregistration.md`
- **status**: queued

### 3. vol_estimator_transport_to_bund

- **why**: confirms or refutes the ≈0 vol_estimator finding outside US10.
  Tests transport assumption (no-inherit guard from Panel A to Panel B
  applies cross-instrument too).
- **depends_on**: Bund price data shipped with pysystemtrade (already
  available; check `data/futures/adjusted_prices_csv/BUND.csv`).
- **panel**: A
- **design**: replicate the `martin_baseline_us10 vs carver_6speed_us10`
  pair on Bund. Two cells at $1M.
- **estimated internal_grid_size**: 2
- **pre_reg target**: `ars/evidence_packs/vol_estimator_bund/...preregistration.md`
- **status**: queued

---

## Mid-queue

### 4. smom_remediation

- **why**: sMOM showed +0.255 Sharpe lift pre-downgrade. Remediating
  the sizing rule mismatch (see `ars/LESSONS.md`) and re-pre-registering
  is high-payoff but blocked on fix.
- **depends_on**: implementation fix in the smom runner (sizing rule
  alignment with baseline).
- **panel**: A
- **estimated internal_grid_size**: 2 (semivar lookback {63d, 126d})
- **status**: **blocked** (sizing fix required)

### 5. panel_B_open_dm_rates_5

- **why**: opens Panel B with the smallest universe step from single
  → portfolio. Best Panel A US10 spec replicated across 5 DM rates with
  TS-only equal-weight.
- **depends_on**: Panel A's best US10 spec (current candidate:
  `exec_friction_carver_6speed_us10_1m` Sharpe 0.317 — but post-2003
  sub-sample first per regime finding).
- **panel**: B (first cell)
- **estimated internal_grid_size**: 5 (one per instrument × portfolio config)
- **status**: queued (waits for de-confound #2 to confirm rule choice)

---

## Skipped / low priority

- **More vol_estimator on US10 single-instrument**: low information.
  Saved for Panel B where it MIGHT revive.
- **More overlay variants on US10 (carry-off-when-down, dMOM-with-shorter-lookback)**:
  per Hanauer & Windmüller's caveat, overlays are crash-mitigators not
  return boosters. Continued single-instrument overlay sweeps burn DSR N
  with limited expected payoff. Defer until multi-instrument tests
  motivate a specific revision.

---

## DSR N accounting

Every queued item, when pre-registered, adds its `estimated
internal_grid_size` to `family.yaml § multiple_testing.n_configs_recorded`.
If items 1-5 above all get pre-registered: +6 +1 +2 +2 +5 = +16 → new
`n_configs_searched` = 41 + 16 = 57. **The DSR threshold rises by adding
to queue, not just by completing**. This is the self-correcting loop
the family layer is built around — adding queue items raises the bar
for ALL future promotions including older cells.

> **Authority note (added 2026-05-31, cold-start test gaps #6/#7):** the
> arithmetic above is *illustrative* and predates the TBM sensitivity add. The
> LIVE multiple-testing state (current `n_configs_searched = 58`,
> `expected_max_sharpe_at_N = 0.3326`) is held in
> `family.yaml § multiple_testing` — treat that file as the single authority;
> this footer may lag.

---

## Update protocol

- New queue items are appended below "Mid-queue" with the same schema.
- Ranks change when findings.md is updated (after a cell completes or
  fails). Re-sort by elasticity priority, not by insertion date.
- Completing a cell:
  1. Add cell to `registry.yaml` + `family.yaml § cells`.
  2. Move queue item from here to a "completed" log at the bottom of
     this file (NOT delete).
  3. Re-run `scripts/family_elasticity.py` to refresh findings.md.
