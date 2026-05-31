# HANDOFF — TBM Stage-1 "NO SIGNAL" verdict on US10 — owner decision required

**Type:** Owner decision handoff (NOT implementation work).
**Owner:** Minsu Yeom.
**Implementer (if any):** TBD — only acts after owner decision.
**Date:** 2026-05-31.
**Status of work:** Stage-1 + sensitivity sweep COMPLETE; gates + diagnostics computed; verdict awaits owner sign-off.

---

## 0. One-line ask

**Pick one of three decision branches (§5) so the family layer can be
committed and the next experiment can be queued.**

The data is in. The question is what conclusion to draw and what to do
next. The technical work below ran to completion; only the
*interpretation-and-allocation* decision is pending.

---

## 1. What was run (two cells, both single-config, locked Path A)

| Cell | T_max | g_max obs | DSR uplift | MaxDD Δ | skew Δ | Sharpe (full sample) |
|---|---:|---:|---:|---:|---:|---:|
| `tbm_meta_us10_baseline_1m` | 120 d | **0.551** | +0.0115 PASS | −0.87% PASS | +0.015 PASS | 0.321 |
| `tbm_meta_us10_tmax40` (sensitivity) | 40 d | **0.591** | −0.0026 FAIL | −2.49% PASS | +0.006 PASS | 0.315 |

Run dirs:

- `ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m/`
- `ars/runs/20260530T164615Z_tbm_meta_us10_tmax40_1m/`

Pre-registration (single, Path A, lint Rules 1-6 PASS):

- `ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md`
  - §3 — primary cell spec
  - §5.1 — verification anchor (sigma median 0.3871 = HANDOFF target 0.39 ±0.03)
  - §5.1.1 — sensitivity sweep T_max ablation
  - §5.2 — three gap-handling rules (5.2.a / 5.2.b / 5.2.c)

Family state at decision time:

- `ars/families/futures_momentum/family.yaml` —
  `n_configs_searched = 58`, `expected_max_sharpe_at_N=58 = 0.3326` ann.
- Both cells: `status = pre_registered_queued` (not yet promoted to `measurement_passed`
  pending this decision).

---

## 2. Diagnostic-tree result (single-variable T_max ablation)

The pre-registered decision rule (§5.1.1 of the pre-reg):

| Observed `g_max_observed` at T_max=40 | Inference |
|---|---|
| > 0.75 | **"Coward"** — effective-sample collapse was the cause |
| 0.60 – 0.75 | partial; more T_max sweep needed |
| **< 0.60** | **"No signal"** — ZN-post-2003 has no learnable conditional edge |

Observed: **0.591**, which is in the **NO SIGNAL** branch.

Triple-evidence backing:

1. `g_max` moved 0.551 → 0.591 (+0.04 only) despite 1.4× effective-sample
   increase (avg_uniqueness 0.071 → 0.099). Real signal would have widened
   the sizer's used range more.
2. DSR uplift flipped +0.0115 → −0.0026 — symmetric oscillation around
   zero, no positive edge.
3. CUSUM break at 2003-06-13 (regime analysis) shows single-EMA2 ZN
   Sharpe collapsed 0.571 → 0.019 post-break. Stage-1 (size-only,
   side-fixed) cannot manufacture alpha when the side has none.

HANDOFF §7 caveat empirically vindicated: *"Stage-1 = risk shaping +
precision, not new alpha; larger uplift is expected from Stage-2
speed-tilt."*

---

## 3. What Stage-1 actually delivered (the residual value)

NOT zero. Stage-1 is acting as a **risk shaper**, just not an alpha
amplifier:

- MaxDD reduction vs g=1 baseline: −0.87% (T_max=120) to **−2.49%**
  (T_max=40). Real, monotone, consistent across barrier choice.
- Positive-skew preservation: skew Δ ∈ {+0.015, +0.006} — within the
  pre-reg's −0.20 tolerance, no degradation.
- g bounded in [0.30, ≤0.59] — Martin §4 Eq.(20) positive-skew constraint
  preserved by construction; F1 OOS lift +0.34 to +0.37 vs naive.
- Pre-reg G-TBM3, G-TBM4, G-TBM5, G-TBM6 all PASS in both runs.

What is NOT delivered:

- Headline Sharpe is essentially unchanged vs baseline (0.32 either way).
- Absolute family-DSR threshold (0.3326) is barely missed by both arms
  (0.321 / 0.315) — neither cell clears for absolute promotion.
- Relative DSR uplift is positive in one cell, negative in the other —
  not a confident relative-edge result either.

---

## 4. Honest caveats to keep visible

- **avg_uniqueness 0.071 (T_max=120) / 0.099 (T_max=40)** both BELOW the
  pre-reg as-TBM-iid 0.20 threshold. Labels are highly overlapping; the
  effective sample (`~290` / `~410`) is much smaller than nominal
  `n=4143`. Documented as an as-TBM-iid violation, not pretended away.
- **`detect_gaps = 0`** in both runs — pysystemtrade's
  `get_daily_prices()` fills the 2024-04→2025-04 gap with NaN-padded
  business-day rows so date-deltas stay ≤5 days. Rules 5.2.a/b/c are
  correctly implemented but had no work to do; gap is handled
  vestigially via NaN propagation. Not a bug, but worth knowing if
  another instrument's gap behaves differently.
- **`use_high_low = False`** (close-to-close touch detection) is
  conservative; production-grade would need OHLC wired in
  `system.rawdata.daily_open_high_low(US10)`.
- **`detect_gaps_in_calendar_jumps_only`** — the current `detect_gaps`
  triggers on calendar-day deltas > 5. A different implementation
  ("trading-day diff") would catch business-day skips even when
  forward-fill is in place.

---

## 5. The three decision branches (pick one)

### Branch A — Accept NO SIGNAL, close Stage-1 on ZN, queue Stage-2 / multi-instrument

**Action items the implementer would execute:**

1. `family.yaml`: promote both TBM cells to `status: measurement_completed_ZN_no_signal`.
2. `findings.md`: add a "TBM Stage-1 verdict" row with the three evidence lines and the
   "MaxDD reduction is the residual Stage-1 value" qualification.
3. `queue.md`: mark item #1 as `completed_with_verdict_no_signal_ZN`. Promote item #5
   (Panel B open with `DM_rates_5`) AND a new queue item for **Stage-2 speed-tilt** to
   the top.
4. `DECISIONS.md`: append a 2026-05-31 entry with the headline + verdict.
5. Multi-instrument Bund / BOBL / GILT / JGB replication pre-reg authored next.

**Rationale:** the diagnostic was pre-registered. The g_max threshold
fired. Burning more N on ZN single-instrument T_max sweeps will raise the
family DSR bar without changing the verdict. ROI lives in (a) Stage-2 speed-
tilt (different mechanism, queue item #2 / Bund replication) and (b)
multi-instrument expansion (queue item #5).

**Cost:** ~30 min implementer work (yaml updates + DECISIONS).
**Risk:** none — accepting an empirically determined result.

### Branch B — Re-run Stage-1 with relaxed `avg_uniqueness` violation

**Action items:**

1. Either drop `T_max` further (e.g., 20d) OR change `cusum_kappa` from
   1.0 → 2.0 (fewer, more spaced events → less overlap → higher
   uniqueness).
2. NEW pre-reg `ars/evidence_packs/tbm_meta_us10_uniqueness_remediation/`
   declaring the change as a single-variable sweep and explicitly
   testing whether avg_uniqueness ≥ 0.20 changes the verdict.
3. n_configs_searched bumps to ~66; family DSR threshold rises to ~0.34.

**Rationale:** the as-TBM-iid assumption was VIOLATED in both runs.
The "no signal" verdict was rendered under a violated assumption. If
fixing the assumption produces a different verdict, that's material.

**Cost:** ~30 min new pre-reg + ~10 min run + ~10 min report.
**Risk:** burns another ~8 configs on a single instrument. If still NO
SIGNAL, the family DSR bar is now ~0.34 — older "passing" cells like
`carver_6speed_us10_1m` (Sharpe 0.317) move BELOW threshold post-hoc.
Honest accounting cost.

### Branch C — Reframe Stage-1 as "risk-shaping only" and promote partially

**Action items:**

1. Promote `tbm_meta_us10_baseline_1m` to `status: promoted_for_risk_shaping`
   (not for alpha). Owner explicitly accepts MaxDD reduction as the value
   delivered.
2. `findings.md` and the cell's CPC report explicitly disclose:
   "Stage-1 has no alpha contribution; MaxDD reduction is the
   primary deliverable."
3. Queue Stage-2 speed-tilt as the alpha source.
4. No Bund / multi-instrument expansion of Stage-1 (since alpha was the
   transport question and there is none to transport).

**Rationale:** the OBSERVED uplift in risk metrics is real (MaxDD,
skew). Promoting this lets a downstream consumer (a portfolio
construction layer) use Stage-1 as a documented risk overlay even
though it doesn't add Sharpe.

**Cost:** ~20 min implementer work + clear owner-facing disclosure.
**Risk:** future agents may treat "promoted" as "alpha-validated" if
the qualification is not strictly enforced. Mitigation: tag prominent.

---

## 6. Recommendation for the implementer (NOT the owner)

If the owner picks A or C, execution is mostly yaml/markdown updates.

If the owner picks B, **author the new pre-reg first**, lint with all
six rules, lock at a git SHA, then run. Do NOT inflate the grid
post-hoc.

In all branches, do NOT touch the existing two run dirs — they are the
audit evidence. Add NEW cells / NEW pre-regs for any further work.

---

## 7. Files this handoff references

- Pre-reg: `ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md`
- Run dirs: `ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m/`, `ars/runs/20260530T164615Z_tbm_meta_us10_tmax40_1m/`
- Family registry: `ars/families/futures_momentum/family.yaml`
- Findings: `ars/families/futures_momentum/findings.md`
- Queue: `ars/families/futures_momentum/queue.md`
- Matrix dashboard (text): `ars/families/futures_momentum/matrix.md`
- Family-DSR utility: `arki/utils/dsr.py` (`python -m arki.utils.dsr` self-check)
- Sigma verification anchor: `scripts/tbm_sigma_verification.py` + `arki/results/2026-05-30/tbm_sigma_verification.csv`
- Runner: `scripts/tbm_meta_us10_baseline_runner.py` (CLI `--t_max INT`)
- Originating design HANDOFF: `/Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md` (§7 caveat anchored)
- DECISIONS log: `ars/DECISIONS.md` (entries dated 2026-05-30 for the family adoption + first TBM run)

---

## 8. Out of scope for this handoff

- Implementation of the chosen branch (separate work; for branch A see
  the ~30-min checklist in §5A).
- Report-building / matrix.html — see `docs/arki/handoff_unified_cpc_reporting_2026-05-31.md`.
- Stage-2 speed-tilt design — pre-reg to be authored only after
  branch A/C is locked.
