---
name: ars-replicate
description: |
  Replicate a pre-registered experiment's headline metrics from JUST the
  Mechanism cheatsheet card (no access to the original code). Tests whether
  the cheatsheet's spec is COMPLETE enough that a clean re-implementation
  reaches the same numbers within tolerance. Closes the "Self-reproducibility
  independent re-impl agent" primitive (§4 of
  docs/standards/ai_native_research_primitives.md).

  Use when:
    - About to promote an experiment and want to verify the cheatsheet is
      self-sufficient as a spec (not just documentation).
    - User types `/ars-replicate <slug>` or asks to "verify the cheatsheet
      reproduces the headline."
    - Onboarding a new agent and using replication as a stress test of
      transferred understanding.

  Do NOT use when:
    - The strategy involves external services (Bloomberg, IB) whose
      outputs cannot be re-derived.
    - The original code is itself a heavy framework (you'd need to re-impl
      a whole engine — out of scope for Path A).
    - You only have full code access; the point of this skill is the
      Mechanism cheatsheet → spec test.
---

# ars-replicate — clean-room re-implementation from the Mechanism cheatsheet

**Status**: Path A (lightweight, single-skill, scoped to headline metrics).
**Path B** (full strategy re-impl with bit-exact tolerance) deferred.

**Closes**: 2026-05-29 design doc §4. The premise: a Mechanism cheatsheet
should be COMPLETE enough that an independent agent, given only that
card + the data path, can re-implement and reach the same numbers. If
they can't, the cheatsheet has a spec gap and needs updating.

## Why this matters

`tests/` verify that code reaches a known answer. This skill verifies
something different and stronger: that the **spec** (Mechanism cheatsheet)
is sufficient to recreate the code. A spec that fails this test is
documentation, not specification. A spec that passes it can be handed to
a new agent (or new collaborator) with confidence the work transfers.

## When to invoke

- `/ars-replicate <slug>` — replicate the experiment at
  `ars/evidence_packs/<slug>/`.
- After landing a new pre-registered + promoted experiment, as a
  promotion-quality check (within the AI's own loop; not a gate on the
  owner).
- During onboarding: spawn a clean session, give it only the cheatsheet,
  see if it can reproduce.

## Workflow (the orchestrating agent executes; no human gate)

1. **Resolve slug → cheatsheet card**. Find the Mechanism cheatsheet card
   for the experiment. Extract: Core formula (§1) + Triggering condition
   (§2) + Action table (§3) + (if present) Scenario verdict (§4) data.

2. **Extract the headline metrics to reproduce**. From the original
   `summary.csv` and `verdict.json`, identify ONE or TWO primary metrics
   (e.g. `sharpe_gross`, `max_drawdown_pct_geom`) on one primary instrument
   (e.g. US10). Path A scope: reproduce headline only, not full term
   structure.

3. **Spawn the clean-room agent**. The clean-room agent receives:
   - The Mechanism cheatsheet card text (only).
   - The data path (e.g. `data/futures/adjusted_prices_csv/US10.csv`).
   - The headline metrics to reproduce (e.g. "Sharpe_gross on US10").
   - The reference numbers it's matching (so it knows the target).
   - The tolerance specification.

   It does NOT receive:
   - The original scripts/martin_single_instrument_backtest.py or any
     other implementation file.
   - The pre-registration document beyond what the cheatsheet contains.
   - Any other ARS framework state.

   See `replicate_prompt.md` for the full system prompt.

4. **Clean-room agent re-implements**. Writes a minimal Python file with
   pandas/numpy only (no pysystemtrade engine). Computes the headline
   metrics from the cheatsheet's spec. Saves to
   `ars/evidence_packs/<slug>/replication/replicated_<slug>.py`.

5. **Compare**. Read `summary.csv`'s reference and the replicated value.
   Apply tolerance from `tolerance.yaml`. Tolerance defaults:
   - Sharpe: |Δ| < 0.05 (absolute)
   - maxDD: |Δ| < 2.0 percentage points (absolute)
   - skew: |Δ| < 0.3 (absolute)

6. **Report**. Generate `ars/evidence_packs/<slug>/replication/REPLICATION_REPORT.md`
   per the schema in `reporting_schema.md`. Include:
   - PASS / FAIL per metric.
   - Identified spec gaps (e.g. "Mechanism card doesn't specify whether
     positions are integer or fractional; replicator assumed integer; result
     within tolerance").
   - Recommendations for cheatsheet improvement.

7. **Feedback loop**. If replication FAILED:
   - Append the spec gap to `ars/LESSONS.md` (it's a real gap, not just
     a noisy result).
   - Suggest specific cheatsheet edits.
   - Mark the evidence pack with `replication_status: failed_spec_gap`.

   If replication PASSED:
   - Mark `replication_status: passed`.
   - Add a `📄 spec-verified` chip to the cheatsheet card.

## Path A scoping decisions (explicit)

- **Headline only, not term-structure**: replicate Sharpe / maxDD / one
  skew metric. Not the full M-horizon table.
- **Same data source**: don't ask the clean-room agent to source data
  independently. Give it the path. This isolates "is the spec sufficient?"
  from "is the data accessible?"
- **Pandas/numpy only**: no pysystemtrade engine in the clean-room. This
  tests whether the cheatsheet's formula is self-contained, not whether
  the engine wrapping is reproducible.
- **Tolerance-based**: bit-exact would force the clean-room to replicate
  pysystemtrade's internal conventions (vol estimator quirks etc.). We
  want the spec to be CORRECT, not pixel-perfect. Tolerance is the right
  trade.

## Limitations (honest)

- A clean-room agent that PASSES replication does NOT prove the strategy
  is correct — only that the cheatsheet is a complete spec.
- A clean-room agent that FAILS replication might fail because (a) the
  cheatsheet has a real gap, OR (b) the clean-room agent misunderstood
  the cheatsheet. The REPLICATION_REPORT.md must distinguish; the
  orchestrating agent uses judgement.
- This skill cannot detect a misalignment between the cheatsheet and
  the original code (use `ars-review-paper` for paper-vs-spec; use code
  review for spec-vs-code).

## Cross-references

- `replicate_prompt.md` — system prompt for the clean-room agent.
- `tolerance.yaml` — tolerance thresholds per metric type.
- `reporting_schema.md` — REPLICATION_REPORT.md template.
- `docs/standards/ai_native_research_primitives.md` §4 — design rationale.
