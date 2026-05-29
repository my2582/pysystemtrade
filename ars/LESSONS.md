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

## How to use this file

- **Before pre-registering a new experiment**: read every entry. The durable rules ARE the gates you must pass at design time.
- **Before promoting a run**: search this file for the experiment family and the paper. If the failure mode applies, the run fails the implicit gate and is downgraded.
- **When a reviewer surfaces a new failure**: append a new entry the same day, BEFORE updating the verdict. The lesson is the deliverable; the verdict update is the consequence.
- **Negative results are first-class**: a falsified or refuted run that produces a new lesson is more valuable than a promoted run that produces none.

Cross-link to: `ars/PROMOTION.md` (gates), `ars/DECISIONS.md` (verdicts), `docs/standards/ai_native_research_primitives.md` (the broader framework these lessons feed into).
