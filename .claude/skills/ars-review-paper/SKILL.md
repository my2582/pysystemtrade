---
name: ars-review-paper
description: |
  Read a pre-registered experiment + its Mechanism cheatsheet + the source paper,
  and produce a structured list of theoretical / implementation / methodological
  misalignments. Closes the "Domain reviewer LLM" primitive (Path A, lightweight)
  in docs/standards/ai_native_research_primitives.md §5.

  Use when:
    - About to promote a pre-registered run and want a paper-compliance pass.
    - An owner / reviewer flagged a possible misreading and you need a structured
      re-check.
    - A new agent is taking over and needs to validate the prior session's work.
    - The user types `/ars-review-paper <slug>` or asks to "review experiment
      X against paper Y".

  Do NOT use when:
    - There is no source paper (this skill is paper-compliance, not general critique).
    - The experiment is purely computational without a literature anchor.
    - The user wants a forward-looking re-design (use general agent for that).
---

# ars-review-paper — domain reviewer LLM for paper compliance

**Status**: Path A (lightweight, single-skill). Path B (MCP server with per-paper compliance tools) deferred.

**Closes**: 2026-05-29 LESSONS entries "Martin §2.3 misreading" and "sMOM unbounded weight" — both were caught by external reviewers, not by the framework. This skill automates that review pass.

**Hard constraint** (the discipline that makes this work): every `concern` MUST quote the paper verbatim. Paraphrase is forbidden. LLM hallucination is mitigated by literal-quote-only rule.

## When to invoke

- `/ars-review-paper <slug>` — review the experiment at `ars/evidence_packs/<slug>/`.
- Inline mention "review smom_us10 against Wang-Yan 2021" — the skill picks up the slug + paper hint.
- Auto-invoke: in promotion sequences AFTER all gates PASS but BEFORE writing the evidence pack README. (The skill is an additional gate inside the AI's loop, not blocking the owner.)

## Inputs the skill loads

1. `ars/evidence_packs/<slug>/<slug>_preregistration.md` — the pre-registration.
2. The Mechanism cheatsheet card for the experiment (find in the cheatsheet HTML by slug; or in `ars/evidence_packs/<slug>/mechanism_card.html` if standalone).
3. The cited paper(s) — references/research/ PDFs cited in the pre-registration.
4. `reviewer_prompt.md` — the system prompt template (this directory).
5. `assumption_checks.md` — known assumption-trap patterns from past LESSONS.
6. `schema.yaml` — output structure.

## Workflow (the agent executes; no human gate)

1. **Resolve slug → files**. If user gave `<slug>`, look up the pre-reg path. If multiple papers cited, run the review once per paper.

2. **Load the paper**. Use the Read tool on the PDF (with pages parameter for >10 pp). Extract the cited sections + equations + assumption sentences. If a paper file is missing, the skill REFUSES to review (cannot fabricate paper content).

3. **Identify the gate set**. Parse the pre-registration §4 to find every gate with a `paper + section + equation` citation. Slogan-only citations (paper + figure name) are auto-flagged as Rule 1 violations (no further review needed; flag the citation itself).

4. **Identify the assumption set**. For each cited section, list the paper's assumptions (linear class, κ_3=0, symmetric U, fixed-M aggregation, etc.). Use `assumption_checks.md` for known patterns; supplement with verbatim paper sentences.

5. **Match formulas**. For each gate's claim, find the corresponding equation in the paper. Test:
   - Is the gate metric computing the SAME quantity as the paper equation?
   - Is the aggregation method matching?
   - Are all variables in the gate identified in the paper?

6. **Test assumptions empirically (if measurements are in the run dir)**. Read `summary.csv` from the run. Compare against assumption set. E.g. paper says `κ_3(U) = 0`, measure US10 `κ_3(U)` → 0.18 (within tolerance), SP500 → -0.25 (violation, flag).

7. **Test safety bounds**. For every multiplicative weight series, check that `max(|w|) ≤ declared_cap` is in the pre-reg AND in the verdict.json. If not, flag as Rule 2 violation.

8. **Produce concerns**. Emit a list per `schema.yaml`. Each entry has:
   - `severity`: theoretical | implementation | methodological | framework | none.
   - `location`: file + section + claim text.
   - `paper_says`: literal quote from the paper with section + equation reference.
   - `misalignment`: one sentence explaining the gap.
   - `recommended_action`: retract | re-frame | re-run-with-fix | declare-out-of-scope.

9. **Output destination**. Write to `ars/evidence_packs/<slug>/paper_review/<paper>_review.md`. Append a one-line summary to `ars/LESSONS.md` if any concern is severity ≥ implementation.

## Output schema (concerns format)

Each concern as YAML block:

```yaml
- concern_id: <slug>_<sequence>
  severity: theoretical | implementation | methodological | framework | none
  location:
    file: <path>
    section: <section name or line range>
    claim_in_artifact: |
      <short quote from the pre-reg or cheatsheet>
  paper_says:
    paper: <author> (<year>) "<title>"
    section: <§ ref>
    equation: <Eq. number, optional>
    literal_quote: |
      <verbatim quote from the paper, max 3 sentences>
  misalignment: |
    <one sentence explaining the gap>
  recommended_action: retract | re-frame | re-run-with-fix | declare-out-of-scope
  confidence: high | medium | low
```

## Hard rules (enforced by the reviewer agent's own discipline)

1. **Literal quote**: every `paper_says.literal_quote` must be a verbatim string from the PDF. No paraphrase. If you cannot find the quote, you cannot raise the concern.
2. **Section + equation cited**: every concern names a specific section AND (if applicable) equation. Slogan citations from your own reasoning are forbidden.
3. **Empirical assumption checks**: if the paper assumes X and the run measures X, compare and report the comparison. Do not assume the assumption holds.
4. **Scope discipline**: review ONLY the alignment between the cited paper and the pre-registration. Do not opine on the strategy's economic merit, the owner's decisions, or alternative formulations.
5. **No fabrication**: if a concern requires knowledge you do not have, say so (`confidence: low` + reason).

## Example invocation (smoke test)

```bash
# Manual invocation — fed to a fresh agent session
cat .claude/skills/ars-review-paper/reviewer_prompt.md \
    ars/evidence_packs/smom_us10/smom_us10_preregistration.md \
    references/research/Enhanced\ Momentum\ Strategies.pdf
# (paper content extracted via Read tool with pages=)
```

Expected output (this is the kind of concern the skill should produce for `smom_us10`):

```yaml
- concern_id: smom_us10_001
  severity: theoretical
  location:
    file: ars/evidence_packs/smom_us10/smom_us10_preregistration.md
    section: §2 (H-S3 skew preservation)
    claim_in_artifact: |
      "skew_per_trade >= 1.0 (Martin §2.3 long-option preservation)"
  paper_says:
    paper: Martin (2023) "Design and analysis of momentum trading strategies"
    section: §4
    equation: Eq. 29
    literal_quote: |
      "An arbitrary nonlinear function of several momentum factors (of different
      speeds) would be very difficult to analyse, so we opt for nonlinearly
      transforming each momentum factor first, and then the position is a
      weighted sum of the transformed factors."
  misalignment: |
    sMOM weight w = sqrt(target_var)/sqrt(semi_var_neg) makes the position a
    nonlinear function ψ(V_n) where V_n = past R²_neg. This is §4 nonlinear
    class, NOT §2 linear class. Eq. 12 closed-form positive-skew theorem
    does not apply.
  recommended_action: re-frame
  confidence: high

- concern_id: smom_us10_002
  severity: implementation
  location:
    file: scripts/momentum_variants_backtest.py::smom_weight
    section: function body
    claim_in_artifact: |
      "raw_w = (np.sqrt(target_var)/np.sqrt(semi_var)).replace([np.inf, -np.inf], np.nan)"
  paper_says:
    paper: Hanauer & Windmüller (2022) "Enhanced Momentum Strategies"
    section: §3 / eq. 4 (cMOM definition)
    literal_quote: |
      "<find the relevant Hanauer sentence on capping or bounded leverage; if
      absent in the paper, report concern as low-confidence and note the gap
      in the paper itself, not a refutation>"
  misalignment: |
    The code has NO upper bound on w. Observed max(|w|) = 2927 (39 days),
    implying effective leverage ≈ 6,439× on declared capital. No safety
    gate defined at pre-reg time.
  recommended_action: re-run-with-fix
  confidence: high
```

## Limitations (be honest)

- LLM-based literal-quote checking can fail on poorly-extracted PDFs (tables, footnotes).
- The skill cannot detect a misreading where the cited equation is correct but the INTERPRETATION is subtly wrong (e.g. domain of validity). Mitigation: combine with §6 dependency graph in primitives doc.
- The skill cannot verify computational correctness — it only checks claim-vs-paper alignment. Code testing is a separate primitive (§4 self-reproducibility agent).

## Cross-references

- `reviewer_prompt.md` — the system prompt template.
- `assumption_checks.md` — common traps inventory.
- `schema.yaml` — output format spec.
- `docs/standards/ai_native_research_primitives.md` §5 — design rationale.
- `ars/LESSONS.md` — failure log this skill prevents recurrence of.
