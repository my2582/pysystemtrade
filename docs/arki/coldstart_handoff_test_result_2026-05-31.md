# Cold-start handoff test — result (Handoff #3 item D)

**Date:** 2026-05-31.
**Test type:** 3-file SOT self-sufficiency stress test (ARS AI-Native primitive).
**Origin:** docs/arki/handoff_session_retrospective_cheatsheet_2026-05-31.md §2.
**Executed by:** isolated sub-agent (fresh context), driven from the main session.

---

## 1. Method (as run)

A fresh Claude session was given ONLY four files and one task:

- `ars/families/futures_momentum/family.yaml`
- `ars/families/futures_momentum/findings.md`
- `ars/families/futures_momentum/queue.md`
- `CLAUDE.md`

Task: **advance queue item #2 (rule_structure de-confound)** by authoring a
Path A pre-registration, reading NO other files unless one of the four
explicitly referenced a file it could not proceed without (and logging every
such excursion). It was NOT told the expected design (success criterion (d)) —
that intent is encoded in queue.md item #2, so arriving at it is the test.

The agent read **zero files outside the 4-file set** and produced a full pre-reg
draft + design rationale + failure-mode log in ~143 s / 12 tool uses.

---

## 2. Success-criteria scoring (handoff §2.3)

| Criterion | Verdict | Evidence |
|---|---|---|
| (a) reads the 3 files without confusion | **PASS** | Correctly reconstructed the 2-panel no-inherit structure, metric-unit locking, and the de-confound rationale (rule_structure = the only n=0-clean-pair axis). |
| (b) authors a pre-reg the owner would author similarly | **PASS (substance ~90%)** | Spec, clean-pair table, identification-vs-quality gate split, relative-uplift-as-primary, family-threshold-as-reporting-only — all match house conventions lifted from queue item #1. |
| (c) lint Rules 1-6 PASS | **INCONCLUSIVE → SOT gap** | Agent could not self-verify: the **text of lint Rules 5-6 is not in the 4-file SOT** (only Rules 1-4 are paraphrased in CLAUDE.md), and it deliberately did not open the canonical template. Science is sound; lint-conformance is at risk *because of the SOT*, not the agent. |
| (d) design matches "single_ema2_20_40 + carver_native, cap ±20, integer, exec_profile constant vs martin_baseline_us10_1m" | **PASS** | Reached this design from queue.md item #2, and correctly resolved the under-specified comparator to the **$1M** variant by capital-matching logic (the SOT never states the exact cell_id). |

**Overall:** the SOT is sufficient for the *science* (a, b, d) but **not for
guaranteed lint/format conformance** (c). The deliverable of this test —
per §2.4/§2.5 — is the failure-mode log below; each entry is a fix to the SOT.

---

## 3. Failure-mode log (hidden SOT dependencies)

Ranked by severity. These are defects in the 3-file SOT, exposed by a context
that could not lean on session memory.

| # | Severity | Hidden dependency | Fix to SOT |
|---|---|---|---|
| 1 | **HIGH** | No pre-reg template or section schema in the SOT. Agent invented the section layout from queue item #1's summary. Canonical template (`ars/evidence_packs/_template/preregistration.md`, and the locked TBM pre-reg) exists but the SOT never points to it. | Add a pointer in queue.md's schema header to the `_template` + the lint script. ✅ applied. |
| 2 | **HIGH** | Lint Rules 5-6 text absent. CLAUDE.md lists Rules 1-4; the family dir has nothing. Agent asserted 5/6 compliance blind. | Point queue.md at `scripts/validate_preregistration.py` (now documents Rules 1-7 in its docstring) + `arki/wiki/onboarding/04_lessons_distilled.md`. ✅ applied. |
| 3 | MED | Rule-1 citation borrowed, not verifiable. Agent cited "Martin 2023 §4 Eq.(20)" by copying queue item #1, not from the paper (paper not in SOT, correctly). Inherited-citation risk. | Acceptable — primary sources are intentionally out of the lightweight SOT; flagged so reviewers know cross-cell citations are transitive. |
| 4 | MED | Comparator `skew_daily` + `max_drawdown_pct_geom` not in family.yaml (only `sharpe_net`, `skew_per_trade` are). Relative gates had to defer those numbers to eval-time artifacts. | Optional: extend family.yaml cell entries with skew_daily + MaxDD, or accept eval-time read. Deferred to owner (adds yaml bloat). |
| 5 | MED | Ambiguous comparator id: queue item #2 says "vs `martin_baseline_us10`" — no cell has that exact id. Resolved by capital-matching to `exec_friction_martin_baseline_us10_1m`. | Tighten queue item #2 to name the exact cell_id. ✅ applied. |
| 6 | LOW | Internal contradiction: queue.md "DSR N accounting" footer writes "+6" for item #1, but family.yaml records item #1 = 8 (+8 for the tmax40 sensitivity). Footer is pre-tbm-add stale. | Add authority note: family.yaml § multiple_testing is the live N source; footer is illustrative. ✅ applied. |
| 7 | LOW | `n_configs_searched` drift: queue footer "= 57"; family.yaml current = 58. Same staleness as #6. | Same authority note covers it. ✅ applied. |
| 8 | LOW | `expected_max_sharpe` recompute at N+1 needs `sr_trials_std`; it IS in family.yaml (0.1426) but the agent left N=59 as TBD rather than computing by hand. | No fix — correct caution; recompute is the runner's job at lock. |

The agent read zero external files (perfect constraint adherence), so every gap
above is a *true* SOT insufficiency, not an artifact of it peeking.

---

## 4. Verdict

**Cold-start = CONDITIONAL PASS.** A fresh agent reconstructs the *research
design* of queue item #2 from the 3-file SOT + CLAUDE.md with ~90% fidelity and
correctly resolves the one genuine ambiguity (the $1M comparator). It CANNOT
guarantee a lint-clean pre-reg, because the SOT carries neither a template nor
the full Rule 1-7 text. The two HIGH-severity fixes (template pointer + lint-rule
pointer) close that gap; with them, a future cold start should reach (c) as well.

This is the first non-trivial evidence that the family SOT transfers across
sessions. It does NOT change any experimental verdict; it grades the *process
artifact* (the 3-file SOT) and finds it B+ → A- once the two pointers land.

---

## 5. Forward note

Re-running this test AFTER the SOT fixes (template + lint-rule pointers in
queue.md) would test whether (c) flips to PASS. That is the natural next
iteration and is the cleanest single signal of "SOT is now self-sufficient."
Recommended trigger: before locking queue item #2's real pre-reg (deadline
2026-06-07).
