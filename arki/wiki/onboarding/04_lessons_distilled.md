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

## Rule 2 — Declare upper bound on every DEGENERATE-DENOMINATOR multiplicative weight

**Source lesson**: 2026-05-29 "sMOM unbounded weight." Refined 2026-05-29 (later) per owner feedback that "every multiplicative weight" was too broad.

**What went wrong**: `w_sMOM,t = sqrt(target_var) / sqrt(semi_var_126d)` had no declared bound. In a 2020-24 window, downside variance collapsed; `w` spiked to **2,927** on 39 days. Effective leverage at peak: **6,439× on $50k capital**. The reported +0.255 Sharpe lift was substantially leverage-artifact.

**Refined rule (scope-corrected)**: A safety bound declaration is mandatory **when the weight formula has a denominator that can approach zero on a path the strategy will actually traverse** (degenerate-denominator class).

| Requires declaration | Does NOT require declaration |
|---|---|
| `1/σ`, `1/var`, `1/semi_var` (variance can collapse) | Constant or pre-tuned weights |
| `1/(F - threshold)` (denominator can cross zero) | `w = F / σ̂` where `σ̂` has a positive floor (pysystemtrade chapter-15 convention) |
| `(numerator)/(rolling estimator)` with no positive lower bound | Linear combinations with positive bounded coefficients (e.g. EWMAC equal-weight stack) |

**When in doubt: declare.** Cost of declaring an unneeded bound = zero. Cost of omitting a needed bound = the sMOM artifact.

**Compliance test**: locate every multiplicative weight in the pre-registration. For each, ask "can the denominator approach zero on a realistic data path?" If yes, the pre-registration MUST have `max(|w|) ≤ N` (finite) for that weight. If no, the bound is optional.

---

## Rule 3 — State the paper's assumption set and verify it empirically before applying the gate

**Source lesson**: 2026-05-29 "Martin §2.3 misreading" — point (2) on `κ_3(U_n) = 0`.

**What went wrong**: Martin (2023) §2 assumes vol-normalised one-period returns `U_n` are symmetric. SP500 has daily `κ_3(U) ≈ −0.25`. The paper's closed-form predictions do not apply. SP500 results being negative are explained by the assumption violation, not by SP500 being "bad for trend."

**Rule**: Every paper-derived gate lists the paper's assumption set. The pre-registration verifies each assumption empirically (or reports the violation) BEFORE applying the gate. Assumption violations downgrade the gate from "validation" to "context."

**Compliance test**: open the pre-registration. For every paper-cited gate, is there an `assumption_set:` field listing the paper's assumptions? Is there an `assumption_check:` step that measures each? PASS if both yes.

---

## Rule 4 — Aggregation discipline: verification mode vs reporting mode

**Source lesson**: 2026-05-29 "Martin §2.3 misreading" — point (4) on aggregation methods. Refined 2026-05-29 (later) per owner feedback that "always match the paper" was too restrictive.

**What went wrong**: We measured `skew_per_trade` using sign-episode aggregation (variable M). Paper §2.3 Eq. 12 closed-form is for fixed-M non-overlapping aggregation. Same English phrase ("trade-level skew") meant two different mathematical objects.

**Refined rule (two modes)**:

| Mode | When you are in it | What to do |
|---|---|---|
| **Verification mode** | Your gate text contains "validates §X" / "refutes Eq. Y" / asserts the paper's prediction held or failed | MUST use the paper's aggregation, OR downgrade the verdict from "validates / refutes" to "consistent with / compatible with" |
| **Reporting mode** | You are documenting a metric for owner / downstream consumption without claiming paper validation | Any aggregation OK provided the method is declared in the Mechanism cheatsheet |

The distinguishing test: read the gate's claim verb. "Validates," "refutes," "confirms" → verification mode. "Reports," "characterises," "shows" → reporting mode.

**Compliance test**: open the cheatsheet Mechanism card. Identify each gate's mode by verb. For verification-mode gates, the aggregation must match the paper OR the verdict text must use the softer verbs. For reporting-mode gates, the aggregation method must be declared but does not need to match a paper.

---

## Rule 5 — Default is passive generation; sign-off is appropriate as a deliberate exception

**Source lesson**: Owner directive 2026-05-29. Refined 2026-05-29 (later) per owner feedback that "never" was too absolute.

**What went wrong (in a proposal that was REJECTED)**: A proposal was made to add "owner must sign off on Mechanism cheatsheet before run starts" as a *default* gate. Owner rejected as a default because HITL should consume audit surfaces ASYNCHRONOUSLY. BUT sign-off remains appropriate in specific cases.

**Refined rule**:

> **Default**: passive generation + delivery (Mechanism cheatsheets, Obsidian inbox, LESSONS appends). Does not pause the Agent Loop.
>
> **Sign-off is appropriate when**:
> 1. **Decision-rights escalation** beyond ARS L2 (e.g. cross-project promotion to downstream PROD, client-specific recommendation).
> 2. **Large resource commitment** (run that consumes >1× session prior compute; artifact >100 MB).
> 3. **Cross-project handoff** (evidence pack being staged for `b3-saa-etf` / `arki-future-fund-engine` consumption).
> 4. **AI confidence-explicit-low** (paper assumption may not hold; sample sparse; the AI itself flags uncertainty).
> 5. **Owner-directed pauses** (per-experiment, owner asked for a checkpoint).
>
> **Not valid reasons** for sign-off: "abundance of caution," "want owner to confirm anyway," "framework wants to look careful."

**Compliance test**: when a primitive proposal includes a sign-off step, the proposal must name which of the five reasons applies. If none of the five applies, the sign-off is a default-blocker and should be removed. If one of the five applies, the sign-off is justified and should be requested explicitly.

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
