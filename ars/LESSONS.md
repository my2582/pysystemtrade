# ARS Lessons — pysystemtrade

Append-only log of failures the pre-registration framework did not catch on its own. Each lesson cites the specific session, the specific artifact that masked the issue, the specific reviewer/event that surfaced it, and the durable rule that prevents recurrence. Pair with `ars/PROMOTION.md` (the gates) and `ars/DECISIONS.md` (the verdicts).

## Schema

```markdown
## YYYY-MM-DD — <slug> — <one-line title>

**Failure mode**: <code-level / theoretical / methodological / process>.

**What the framework saw**:
<the artifact that PASSED the existing gates>

**What was actually wrong**:
<the specific defect, with quantitative evidence>

**How it was surfaced**:
<reviewer / event / external check>

**Why pre-reg gates didn't catch it**:
<the structural reason — usually "gate measured X, the defect was in Y">

**Durable rule** (to be enforced by future gates):
<the testable rule, with the exact gate language>

**Cross-references**: <runs, decisions, evidence packs>
```

---

## 2026-05-29 — sMOM unbounded weight — implementation bug masked by aggregate metrics

**Failure mode**: code-level (implementation), masked by methodology (aggregate-only metrics).

**What the framework saw**:
- `verdict.json` for `smom_us10` showed Sharpe lift +0.255 (PASS gate `>= +0.05`), maxDD improvement +11.19 pp (PASS gate `>= +3.0`), skew_per_trade +4.69 (PASS gate `>= 1.0`).
- Status: `promoted` (Path A). All 4 gates green.

**What was actually wrong**:
- `w_sMOM,t = sqrt(target_var) / sqrt(semi_var_126d)` had no upper bound. In a 2020-2024 window, downside variance collapsed; `w` spiked to **2926** on 39 days, producing effective leverage of **6,439× on $50k capital** (peak ±2,927 contracts on US10).
- Closed-form λ matched full-sample vol, but the time-pattern of leverage was dominated by these spikes. A realistic capped sMOM (e.g., `w ≤ 3`) would likely show Sharpe lift +0.10 to +0.15 (much less than the reported +0.255).

**How it was surfaced**:
- Owner asked "현재 US10 50K 기준 몇 계약까지 트레이드 가능한지" (a basic sanity question, not a framework check).
- Investigation showed the unbounded `w` series → revealed by histogramming effective contracts.

**Why pre-reg gates didn't catch it**:
- Gates measured aggregate Sharpe, maxDD, skew over the FULL sample. Aggregate metrics smear extreme-leverage outliers into the average — the 39 spike days contribute disproportionately to the mean (lifting Sharpe) without showing as obvious vol blow-ups (because λ closed-form matched).
- No `G_safety` gate was defined for implementation hygiene (e.g., "max(|w_t|) < some sane bound", "no full-sample variance used in OOS pipeline", "max single-day strategy return < N · ann_vol").

**Durable rule**:
> Every multiplicative overlay weight series MUST declare a hard upper bound at pre-registration time. The bound is a gate of type `G_safety` and is evaluated as `max(|w_t|) ≤ declared_cap`. If the bound is not declared, the pre-registration is incomplete and the run is registered as `incomplete_safety_spec`.

**Cross-references**:
- Run: `ars/runs/20260528T181556Z_smom_us10/`
- Evidence pack: `ars/evidence_packs/smom_us10/` (status pending remediation)
- Decision log: `ars/DECISIONS.md#2026-05-29-smom-us10-promoted`
- Downstream consequence: cheatsheet headline +0.255 is overstated.

---

## 2026-05-29 — Martin §2.3 misreading — Figure-as-slogan vs Equation-as-test

**Failure mode**: theoretical (paper misread), masked by Figure-citation rather than Equation-citation.

**What the framework saw**:
- `verdict.json` for `martin_single_instrument` showed 5/5 gates PASS, including G1 ("US10 market skew positive at M=60 [Martin Fig 1]") and G2 ("SP500 market skew negative [Martin Fig 1]").
- Cheatsheet F1 panel labeled "Martin Fig 1 reproduction" and led the reader to infer "rates good, equity bad for single-instrument trend."

**What was actually wrong**:
- Paper §1 explicit thesis: "skew is a product of the design of the strategy ... not a property of the asset class." Even on symmetric market returns, all-`a_j` positive linear trend produces positively skewed trading returns. The asset-attribution reading (rates vs equity) is the **opposite** of the paper's central claim.
- Paper §2 assumes `κ_3(U_n) = 0` (vol-normalised one-period returns symmetric). SP500's U has daily skew ≈ −0.25 → paper Eq. 12 does not apply cleanly. The negative SP500 strategy skew is a `κ_3(U)` leak, NOT a refutation of §2.3 nor evidence of "equity bad for trend."
- `forecast_cap = 20` is a §4 nonlinearity (any cap reduces max skew per §4); my framing of "soft cap = Martin-compliant" was reversed.
- `skew_per_trade` (sign-episode aggregation) ≠ Paper's fixed-M trading return skew (Eq. 12 closed form). Same word, different mathematical objects.
- "EWMAC = Martin EMA2" is approximate; EWMAC operates on price levels, EMA2 on price changes. Both inside the linear class, different `a_j`.

**How it was surfaced**:
- An external reviewer re-read Martin (2023) §2 and §4 carefully and wrote a critique pointing out the asset-attribution misread.
- A subsequent direct test (Step 2+3 ablation 2026-05-29) measured fixed-M strategy skew under cap=20 vs cap=∞ on US10 and SP500. Peak fixed-M skew on US10 baseline ≈ 1.9 at M=40 (cap=20) and M=60 (cap=∞), close to paper EMA2 prediction ≈ 2.1. SP500 daily skew ≈ −1.99 (cap=20) ≈ −1.54 (cap=∞) — confirms `κ_3(U)` leak.

**Why pre-reg gates didn't catch it**:
- Gates referenced "Martin Fig 1" by name (slogan), not "Martin Eq. 12" with the equation written out. A slogan-citation is satisfiable by any picture that visually resembles the cited figure. An equation-citation forces alignment with the assumption set and the predicted shape.
- No "what does this paper section actually claim" check was part of the framework.
- The framework treated PASS/FAIL outcomes as truth without requiring the verdict text to literally restate the paper's claim.

**Durable rule**:
> Every pre-registered gate MUST cite the source as `<paper> <section> <equation number>` (or `<paper> <section> <claim sentence>`), NOT as `<paper> <figure name>`. The pre-registration template enforces this structurally: a free-text "claim" field is not accepted; only an `eq:`-prefixed or `claim:`-prefixed reference is valid. Slogan citations cause the pre-registration to be rejected at commit time.

**Companion rule** (assumption-set check):
> Every paper-derived gate MUST list the paper's assumption set (e.g., `κ_3(U) = 0`, `linear class with all a_j > 0`, `fixed M aggregation`) and the pre-registration must verify or report each assumption empirically before applying the gate. Assumption violations downgrade the gate from "validation" to "context."

**Cross-references**:
- Run: `ars/runs/20260528T161350Z_martin_single_instrument/`
- Evidence pack: `ars/evidence_packs/martin_single_instrument/`
- Decision correction: `ars/DECISIONS.md#2026-05-29-post-review-correction`
- Direct test: `ars/runs/20260529T134903Z_martin_fixed_m_skew/`
- Downstream consequence: cheatsheet F1/F2 framing and Martin verdict text need correction; sMOM is similarly affected (claims "Martin-compliant" while sitting in §4 nonlinear class).

---

## 2026-05-29 (later) — framework expansion seeded (3 candidates landed)

Not a failure entry; a process expansion entry, recorded here so future agents see the framework's own evolution log next to the failure log.

**Triggered by**: owner directive to execute primitives ①②③ from `docs/standards/ai_native_research_primitives.md`.

**Landed**:

1. **Onboarding curriculum** — `arki/wiki/onboarding/` (6 files, 00 through 05). Bootstrap reading order for any new AI / human collaborator. Each lesson in this file has a corresponding actionable rule in `arki/wiki/onboarding/04_lessons_distilled.md`. Closes "next session won't repeat past mistakes" gap.

2. **Sanitizer for external review** — `scripts/sanitize_for_external_review.py` + `outputs/external_share/<date>/`. Smoke-tested: 11 replacements on cheatsheet (owner name, firm, $50k, downstream PROD repo names, extreme leverage figures), 0 PII leak verified by grep, sanitized cheatsheet still passes `verify_cheatsheet.py`. Closes "want external review but cannot share absolute paths / capital / owner identity" gap.

3. **Domain reviewer LLM (Path A)** — `.claude/skills/ars-review-paper/` (SKILL.md + reviewer_prompt.md + assumption_checks.md + schema.yaml). Hard discipline: every concern must include verbatim paper quote; no paraphrase. Schema parses cleanly. Closes "Martin §2.3 misreading" pattern by automating the kind of fresh-eyes paper-vs-pre-reg check that an external reviewer would do.

**Why this counts as a lesson**: the failure modes that surfaced in the 2026-05-29 sMOM unbounded-w and Martin §2.3 misreading entries were caught by ad-hoc owner / reviewer attention. The three primitives above turn that ad-hoc attention into either (a) pre-session reading (onboarding), (b) reproducible self-audit on demand (review skill), or (c) reproducible external review on demand (sanitizer). All three are PASSIVE generation + delivery primitives; none blocks the Agent Loop with sign-off pauses (per owner directive recorded in `ars/PROMOTION.md`).

**Cross-references**:
- Design rationale: `docs/standards/ai_native_research_primitives.md` §1-§5.
- Onboarding entry point: `arki/wiki/onboarding/00_orientation.md`.
- Sanitizer entry point: `scripts/sanitize_for_external_review.py --help`.
- Review skill entry point: `.claude/skills/ars-review-paper/SKILL.md`.
- First sanitized share package: `outputs/external_share/2026-05-29/`.

**Open follow-ups** (do not block this commit):
- ④ Self-reproducibility independent re-impl agent — design pending.
- ⑤ Cost-aware token budget per phase — design pending.
- Wave 2 of primitives doc: Paper-citation gate (§2 of design doc) needs schema in `_template/preregistration.md`; current implementation is enforced via the `ars-review-paper` skill rather than at commit time.

---

## 2026-05-29 (queue cleared) — primitives ④⑤ + paper-citation lint landed

Not a failure entry; the queue from the prior framework-expansion entry has been worked off.

**Landed**:

1. **④ Self-reproducibility skill** at `.claude/skills/ars-replicate/`: clean-room re-impl tests whether a Mechanism cheatsheet is a complete spec (not just docs). Tolerance-based PASS/FAIL per metric; `[ASSUMED]` flags surface spec gaps. Path A scope = headline metrics on a primary instrument; pandas/numpy only. Skill registered.

2. **⑤ Cost-aware token budget**: `_template/preregistration.md` gains §8 budgets; `_template/verdict.json` gains `cost_actuals`; `scripts/session_cost_report.py` aggregates across evidence packs. Honest framing: SOFT signal, not real-time enforcement.

3. **Paper-citation lint** at `scripts/validate_preregistration.py`: rules 1-4 (citations, weight bounds, assumption checks, aggregation declaration) checked statically; exit code 1 on Rule 1 violations. Smoke test against existing 7 pre-regs found 2 Rule 1 errors (Martin baseline POST-HOC Fig 1 citations — expected) and 11 warnings (mostly Rule 3 assumption-set sections not yet ported back). Working as designed.

4. **CLAUDE.md** lists the slash commands + lint + cost dashboard + onboarding entry point.

5. **LESSONS.md** also gained a refinement entry above this one: Rules 2, 4, 5 over-reached in original phrasing; corrected with degenerate-denominator scope (Rule 2), verification-vs-reporting mode (Rule 4), and enumerated sign-off exception cases (Rule 5).

**Why this counts as a lesson** (not just a deliverable): the refinement entry IS a lesson — original rule phrasing was over-confident. The fact that the queue items shipped within the same session as the refinement is itself a lesson about how fast framework primitives can be iterated when they are passive (generation + delivery) rather than blocking.

**Cross-references**:
- Replicate skill: `.claude/skills/ars-replicate/SKILL.md`.
- Token budget design: `docs/standards/ai_native_research_primitives.md` §7.
- Validator: `scripts/validate_preregistration.py --help`.
- Cost dashboard: `scripts/session_cost_report.py --help`.

**Open follow-ups** (truly remaining; not blocking commit):
- Pre-registration template Rule 3 fields (`assumption_set:` + `assumption_check:`) — adopted by sMOM pre-reg, not yet ported to dMOM/fast_tilt/carry/top1rot. Lint will WARN until ported.
- Settings.json hook wiring for paper-citation lint — defer to owner.
- Cumulative token budget data (currently 0 packs declared) — will accumulate naturally with new sessions.

---

## 2026-05-29 (refinement) — three rules over-reached; nuances codified

Owner pushed back on three rules from the earlier seed entries. The pushbacks are valid; this entry refines the rules so future agents apply them with the right scope.

### Refined Rule 2 — Safety-bound declaration scope (was: "every multiplicative weight")

**Original framing** (too broad): "every multiplicative overlay weight series MUST declare `max(|w_t|) ≤ N` at pre-registration."

**Why the original was too broad**: not every multiplicative weight is at risk of unbounded leverage. A weight like `w = constant` or `w = forecast / σ̂` (where σ̂ has a positive lower bound by construction) does not need a hard cap declaration.

**Refined rule** (scope-corrected):

> A safety bound declaration is mandatory **when the weight formula has a denominator that can approach zero on a path the strategy will actually traverse** (degenerate-denominator class). Examples that require declaration:
> - `1/σ`, `1/var`, `1/semi_var` (variance terms can collapse in low-vol windows).
> - `1/(F - threshold)` (denominator can cross zero).
> - any `(numerator) / (rolling estimator)` where the rolling estimator has no positive lower bound.
>
> Examples that do NOT require declaration:
> - Constant or pre-tuned weights.
> - Forecast-style weights `w = F / σ̂` where `σ̂` is the price vol used by pysystemtrade and has a small positive floor by chapter-15 convention.
> - Linear combinations with positive bounded coefficients (e.g. EWMAC equal-weight stack).
>
> When in doubt: declare the bound. Cost of declaring an unneeded bound = zero. Cost of failing to declare a needed bound = the sMOM 6,439× artifact.

**Rationale for refinement**: the seed lesson was the sMOM unbounded `w` driven by `sqrt(target_var)/sqrt(semi_var)`. The structural culprit is `semi_var → 0` (a degenerate denominator path). The original rule generalised one incident into "all multiplicative weights"; the corrected rule names the structural condition (degenerate denominator).

### Refined Rule 4 — Aggregation match scope (was: "match the paper's aggregation")

**Original framing** (too restrictive): "use the paper's aggregation method when measuring a metric to compare against a paper's prediction."

**Why the original needed qualification**: read literally, this forbids any measurement that doesn't match a paper's exact aggregation. Papers often use idealised aggregations (fixed-M non-overlapping, infinite-history limit, continuous-time) that real backtests cannot mirror exactly.

**Refined rule** (scope-corrected):

> Aggregation discipline applies in **two distinct modes**:
>
> 1. **Verification mode** — when you are claiming a paper's prediction is VALIDATED (or refuted) by your measurement. In this mode you MUST use the paper's aggregation, OR explicitly downgrade the verdict to "consistent with" / "compatible with" rather than "validates" / "refutes." Sign-episode-skew vs Eq. 12 fixed-M-skew is a verification-mode mismatch and must be flagged.
> 2. **Reporting mode** — when you are documenting a metric for owner / downstream consumption without paper-prediction comparison. In this mode you may use any aggregation as long as the aggregation method is declared in the Mechanism cheatsheet.
>
> The distinction: verification mode requires a paper-equivalent measurement OR a downgrade of the verdict's claim strength. Reporting mode requires only transparency about the method used.
>
> When in doubt about which mode applies: if the pre-registration gate text contains "validates §X" or "refutes Eq. Y" or any verb that asserts the paper's prediction held or failed, you are in verification mode and the strict rule applies.

**Rationale for refinement**: the seed lesson was sign-episode skew labelled as "Martin §2.3 verification" — verification-mode mismatch. The corrected rule preserves the verification-mode discipline while permitting reporting-mode flexibility for owner-facing summaries that don't claim paper validation.

### Refined Rule 5 — Sign-off discipline (was: "never block Agent Loop on owner sign-off")

**Original framing** (too absolute): "every framework primitive must be passive (generation + delivery) or active-on-AI-side ... never block the AI on owner sign-off."

**Why the original was too absolute**: there ARE legitimate cases where sign-off should be requested. Hardcoding "never" forces the framework to skip sign-off in cases where it is the right action.

**Refined rule** (cases enumerated):

> Default primitive design is **passive generation + delivery** — Mechanism cheatsheets, Obsidian inbox drops, LESSONS appends. These do not pause the Agent Loop and form the standard audit surface.
>
> Sign-off requests are **appropriate exceptions** in these cases:
> 1. **Decision-rights escalation** — the action would move beyond ARS L2 (e.g. promoting to a downstream PROD repo; signing off on a client-specific recommendation). Sign-off is appropriate; the framework's L2 cap prevents this happening at all here, so the case is mostly cross-project.
> 2. **Large resource commitment** — running an experiment that will consume >1× the session's prior cumulative compute, or producing artifacts >100 MB total. Sign-off avoids surprises.
> 3. **Cross-project handoff** — when an evidence pack is being staged for consumption by `b3-saa-etf` or `arki-future-fund-engine`, sign-off captures the cross-project intent.
> 4. **Confidence-explicit-low** — when the AI's own self-assessment of confidence in a verdict is `low` (e.g. paper assumption may or may not hold; sample is sparse). Sign-off is appropriate because the AI is honestly flagging uncertainty.
> 5. **Owner-directed pauses** — owner has explicitly asked for a pause at a checkpoint for that experiment. Per-experiment, not per-framework.
>
> In all other cases (default): generate + deliver + continue. Do not invent ritualistic pauses; do not pause for "abundance of caution" when the framework's audit surfaces are sufficient.
>
> The discipline: the framework should not silently CHOOSE sign-off as a way of stalling. Sign-off requests are explicit decisions with one of the five reasons above attached. "Sign-off because I want owner to confirm" is not a valid reason; "Sign-off because cross-project handoff" is.

**Rationale for refinement**: the seed lesson was a primitive proposal that added blocking sign-off as a default gate. The original directive was right to reject that as a default but wrong to forbid sign-off in all cases. The corrected rule preserves the default (passive generation) while enumerating exception cases.

---

These refinements supersede the seed framing in entries above. Onboarding `04_lessons_distilled.md` will be updated to match in the same session.

## How to use this file

- **Before pre-registering a new experiment**: read every entry. The durable rules ARE the gates you must pass at design time.
- **Before promoting a run**: search this file for the experiment family and the paper. If the failure mode applies, the run fails the implicit gate and is downgraded.
- **When a reviewer surfaces a new failure**: append a new entry the same day, BEFORE updating the verdict. The lesson is the deliverable; the verdict update is the consequence.
- **Negative results are first-class**: a falsified or refuted run that produces a new lesson is more valuable than a promoted run that produces none.

Cross-link to: `ars/PROMOTION.md` (gates), `ars/DECISIONS.md` (verdicts), `docs/standards/ai_native_research_primitives.md` (the broader framework these lessons feed into).
