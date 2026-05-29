# 04 — Lessons distilled (5 actionable rules)

**Prerequisite**: [03_worked_example_falsified.md](03_worked_example_falsified.md). **Time**: ~5 minutes.

The full append-only failure log is at [`ars/LESSONS.md`](../../../ars/LESSONS.md). This file extracts the 5 rules you must internalize before your first pre-registration. Each rule traces to a specific session lesson; each is enforceable.

---

## Rule 1 — Cite section + equation, NEVER figure name alone

**Source lesson**: 2026-05-29 "Martin §2.3 misreading — Figure-as-slogan vs Equation-as-test."

**What went wrong**: A pre-registered gate read "G1: US10 market skew positive at M=60 [Martin Fig 1]." This passed mechanically, but Fig 1 in the paper is market context, NOT §2.3 validation. The Figure name was a slogan satisfiable by any picture that visually resembled the cited figure.

**Rule**: Every gate cites `paper + section + equation_number` (or `paper + section + claim_sentence`). NEVER `paper + figure_name` alone.

**Compliance test**: open the pre-registration. For every gate, you should be able to fingerpoint a numbered equation in the source paper. If the citation is only a figure name, the gate fails this rule.

---

## Rule 2 — Declare upper bound on every multiplicative weight at pre-registration time

**Source lesson**: 2026-05-29 "sMOM unbounded weight."

**What went wrong**: `w_sMOM,t = sqrt(target_var) / sqrt(semi_var_126d)` had no declared bound. In a 2020-24 window, downside variance collapsed; `w` spiked to **2,927** on 39 days. Effective leverage at peak: **6,439× on $50k capital**. The reported +0.255 Sharpe lift was substantially leverage-artifact.

**Rule**: Every multiplicative overlay weight series declares `max(|w_t|) ≤ N` at pre-registration time. If undeclared, run is registered as `incomplete_safety_spec`. Cannot promote.

**Compliance test**: search the pre-registration for the string "max(|w" or "bound" or "cap" applied to the overlay's weight series. Present and a finite number? PASS. Absent? FAIL.

---

## Rule 3 — State the paper's assumption set and verify it empirically before applying the gate

**Source lesson**: 2026-05-29 "Martin §2.3 misreading" — point (2) on `κ_3(U_n) = 0`.

**What went wrong**: Martin (2023) §2 assumes vol-normalised one-period returns `U_n` are symmetric. SP500 has daily `κ_3(U) ≈ −0.25`. The paper's closed-form predictions do not apply. SP500 results being negative are explained by the assumption violation, not by SP500 being "bad for trend."

**Rule**: Every paper-derived gate lists the paper's assumption set. The pre-registration verifies each assumption empirically (or reports the violation) BEFORE applying the gate. Assumption violations downgrade the gate from "validation" to "context."

**Compliance test**: open the pre-registration. For every paper-cited gate, is there an `assumption_set:` field listing the paper's assumptions? Is there an `assumption_check:` step that measures each? PASS if both yes.

---

## Rule 4 — Sign-episode aggregation ≠ fixed-M aggregation; pick the one the paper uses

**Source lesson**: 2026-05-29 "Martin §2.3 misreading" — point (4) on aggregation methods.

**What went wrong**: We measured `skew_per_trade` using sign-episode aggregation (variable M). Paper §2.3 Eq. 12 closed-form is for fixed-M non-overlapping aggregation. Same English phrase ("trade-level skew") meant two different mathematical objects.

**Rule**: When measuring a metric to compare against a paper's prediction, use the paper's aggregation method. Sign-episode is NOT the same as fixed-M. If you choose a different aggregation, explicitly note that the paper's prediction does not apply.

**Compliance test**: open the cheatsheet Mechanism card. Section 1 (Core formula) should state the aggregation method. Section 4 (scenario verdict) should compare your aggregation against the paper's. PASS if both explicit.

---

## Rule 5 — Generate audit surfaces; never block the Agent Loop with sign-off pauses

**Source lesson**: Owner directive 2026-05-29.

**What went wrong (in a proposal that was REJECTED)**: A proposal was made to add "owner must sign off on Mechanism cheatsheet before run starts" as a gate. Owner rejected: HITL must consume audit surfaces ASYNCHRONOUSLY at owner's pace. Blocking the loop violates the velocity discipline.

**Rule**: The framework GENERATES Mechanism cheatsheets and DELIVERS them to Obsidian inbox. The framework does NOT pause for sign-off. Audit happens asynchronously. If a primitive proposal requires explicit owner action to unblock execution, REJECT.

**Compliance test**: every framework primitive must be (a) passive (generation + delivery, no human gate) or (b) active-on-AI-side (gates the AI applies to itself without owner mediation). If it requires owner action to unblock the AI, REJECT.

---

## Quick checklist before committing a pre-registration

```
[ ] Every gate cites paper + section + equation (Rule 1)
[ ] Every multiplicative weight has a declared upper bound (Rule 2)
[ ] Every paper-derived gate lists assumption set + verifies it (Rule 3)
[ ] Aggregation method matches the paper's (Rule 4)
[ ] No proposed primitive blocks the Agent Loop on owner sign-off (Rule 5)
[ ] Single design decision varies vs baseline (no bundled changes)
[ ] Pre-registration committed BEFORE any code runs (run-time SHA in manifest > pre-reg SHA)
[ ] Falsification rule pre-registered (which gate combinations trigger falsified status?)
```

If any box is unchecked, the pre-registration is incomplete. Don't run yet.

## Next

→ [05_API_gotchas.md](05_API_gotchas.md)
