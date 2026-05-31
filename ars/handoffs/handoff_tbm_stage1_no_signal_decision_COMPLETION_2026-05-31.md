# COMPLETION REPORT — TBM Stage-1 "NO SIGNAL" decision handoff

**Closes:** `docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md` (the owner-decision menu)
**Via:** `docs/arki/HANDOFF_risk_shaping_family_closeout.md` (the detailed execution spec)
**Decision taken:** **4th branch** = Branch C extended — bundle capped sMOM (Path B) + TBM Stage-1 into a `risk_shaping_size_overlays` sub-group and close the size-overlay line on ZN solo.
**Owner:** Minsu Yeom · **Implementer:** Claude Code · **Date:** 2026-05-31
**Status:** ✅ **DONE** (metadata-layer only; no backtest; run dirs untouched; upstream 0 diff)

---

## 0. Handoff status (for multi-handoff state management)

| Handoff doc | Type | State after this session |
|---|---|---|
| `handoff_tbm_stage1_no_signal_decision_2026-05-31.md` | Owner decision menu (A/B/C) | ✅ **CLOSED** — 4th branch (extends C) chosen + executed |
| `HANDOFF_risk_shaping_family_closeout.md` | Execution spec | ✅ **EXECUTED** — all §1–§5 applied |
| `handoff_unified_cpc_reporting_2026-05-31.md` | Reporting | ⏳ open (matrix.html still pending — separate) |
| Registry full entries for the 2 TBM runs | Follow-up | ⏳ open (family.yaml refs run_dirs; registry.yaml rows not yet created) |

---

## 1. Decision recap

Branch chosen was **not vanilla A/B/C**. The decision menu's Branch C promoted TBM alone for
risk-shaping. The 4th branch (proposed in the sMOM briefing's open question, formalised in
`HANDOFF_risk_shaping_family_closeout.md`) **also** promotes capped sMOM to Path B and unifies
both under one sub-family.

**Unified thesis (written verbatim into findings.md):** *On ZN single-instrument, size-layer
overlays shape risk but do not generate directional alpha. The alpha levers are breadth and
Stage-2 speed-tilt.*

---

## 2. What was executed (6 steps)

| # | Step | File(s) | Result |
|---|---|---|---|
| 1 | capped sMOM → Path B (G4 MECHANISM_NOTE via LESSONS Entry 3) | `ars/runs/registry.yaml` | `smom_us10_capped` → `registered_path_b` (+`promotion_path`, `path_b_note`); uncapped `smom_us10` → `superseded_by_smom_us10_capped` (reference) |
| 2 | TBM Stage-1 verdict recorded (no new run) | `family.yaml` | both cells → `relative_pass_absolute_fail` + observed metrics + real `run_dir` refs |
| 3 | `risk_shaping` sub-group + capped cell | `family.yaml` | `sub_groups.risk_shaping_size_overlays` (3 members, layer=size, CLOSED) + new `smom_us10_capped` cell |
| 4 | findings conclusion + comparison table | `findings.md` | "Risk-shaping size-overlays — CLOSED" section + overlay elasticity row updated |
| 5 | queue re-rank | `queue.md` | #1 → `completed_with_verdict_no_signal_ZN`; Stage-2 speed-tilt (A) + Panel B (B) promoted to top |
| 6 | decision log + self-correction | `DECISIONS.md`, `LESSONS.md` | 2026-05-31 closeout entry; Entry 1 prediction self-correction |

---

## 3. Final statuses (as required by the decision prompt)

- `smom_us10_capped` = **`registered_path_b`** (owner sign-off Minsu 2026-05-31; crash-mitigator only, NOT alpha)
- `smom_us10` (uncapped) = **`superseded_by_smom_us10_capped`** (reference; 6,439× leverage artifact, unrealizable)
- `tbm_meta_us10_baseline_1m` = **`relative_pass_absolute_fail`**
- `tbm_meta_us10_tmax40` = **`relative_pass_absolute_fail`**

---

## 4. Verify-before-write anchors (confirmed from existing artifacts)

From `ars/runs/20260530T170606Z_smom_us10_capped/verdict.json`:

| Check | Required | Observed | Verdict |
|---|---|---|---|
| G3 skew_per_trade | ≥ 1.0 | 4.616 | PASS |
| G_recon | < 1% | 0.0 | PASS |
| maxDD improvement | +11.19pp (±0.5) | +11.185pp (−55.347 → −44.162) | PASS |
| G4 SP500 control | reframe | 0.305, vol ratio 6.23/24.3 = 0.26 ≤ 0.7 | MECHANISM_NOTE |

→ promote-stop conditions (G3 or G_recon fail) **not** triggered. Promotion was valid.

---

## 5. Invariants & guardrails (all held)

- **`n_configs_searched = 58`** — unchanged. (capped = remediation re-run of already-counted `smom_us10`; TBM verdict recording = status change, not new config.)
- **`expected_max_sharpe_at_N = 0.3326`** — unchanged.
- **Existing run dirs** (`...154455Z`, `...164615Z`, `...170606Z`) — 0 modifications (untracked only).
- **No new backtest** executed.
- **Upstream 0 diff** — `git status --porcelain systems/ sysdata/ sysquant/ syscore/` empty.
- **No `TBM_x_sMOM` composed cell** created (same size layer; L6).

## 6. Files changed (diff summary)

- `ars/runs/registry.yaml` — +4/−2 (2 status regions only; **verified no unintended lines**)
- `ars/families/futures_momentum/family.yaml` — sub_groups + capped cell + 2 TBM verdicts + multiple_testing note
- `ars/families/futures_momentum/findings.md` — risk-shaping section + elasticity row
- `ars/families/futures_momentum/queue.md` — re-rank + #1 closed
- `ars/DECISIONS.md` — 2026-05-31 closeout entry
- `ars/LESSONS.md` — Entry 1 self-correction note

---

## 7. ⚠ Findings to surface (not part of this task; owner decision)

1. **`ars/runs/registry.yaml` is not machine-parseable (pre-existing).** Line ~364:
   `vol_estimator: martin_20d_ema_of_sq (gamma=0.95, custom: arki.utils.martin_vol...)` — an
   unquoted scalar containing a mid-value colon breaks `yaml.safe_load`. **This fails at HEAD
   too** (before this session's edits); it was NOT introduced here. Any tool that parses the
   registry will choke. Recommend a one-line fix (quote the value) in a separate hygiene commit.
   *Left untouched here — out of scope + surgical-change discipline.*

2. **Cell-count counters** (`n_cells_registered`, `n_cells_pre_registered_queued`) in
   `family.yaml § multiple_testing` were **left as the last reconciled snapshot** with a dated
   note, rather than re-incremented, to avoid miscounting the interdependent buckets. The
   DSR-relevant numbers (N, threshold) are correct and frozen. If you want exact cell-count
   bookkeeping, that's a small follow-up.

---

## 8. Next (queued, not started)

1. **Stage-2 speed-tilt λ(s_t)** — alpha lever, side/forecast layer (additive). Author Path A pre-reg.
2. **Panel B open (breadth)** — rates-only is breadth-limited (0.5–0.8 corr); a low-correlation
   universe (rates + commodities + equity + FX) is the higher-information step.

Size-overlay line on ZN solo = **CLOSED**. No more single-instrument size overlays.
