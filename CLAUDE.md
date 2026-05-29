# CLAUDE.md — pysystemtrade

## Role

Senior AI software engineer working inside pysystemtrade.

Prioritize stability, security, reproducibility, and minimal change.

## #0 Source of truth — `arki/wiki/`

Durable project knowledge lives in the committed wiki **`arki/wiki/`** (start at `arki/wiki/index.md`).
The session-prime card `arki/wiki/system/system-card.md` is auto-injected at session start. Agent
auto/Serena **memory is a cache** — pointers into the wiki, not a knowledge store; maintain the wiki on
the Agent Loop's Ingest step. Full rule + fork-safety: `arki/README.md`. **Never edit upstream-tracked files.**

<!-- ARS_PROJECT_BLOCK_START -->
## Arki Robust Standard, ARS

This project uses Arki Robust Standard.

Before substantive work, Claude Code MUST read:

1. `/Users/msyeom/Developer/arki-standards/README.md`
2. `/Users/msyeom/Developer/arki-standards/CLAUDE.md`
3. `/Users/msyeom/Developer/arki-standards/ars/01_core_standard/ARS_CORE_STANDARD.md`
4. `/Users/msyeom/Developer/arki-standards/ars/07_ai_agent_governance/ARS_AI_AGENT_OPERATING_STANDARD.md`
5. `./ars/project_ars_profile.yaml`

### Required behavior

- State assumptions before coding.
- Make surgical changes only.
- Never suppress console errors.
- Preserve native engine outputs.
- Do not silently change data, universe, benchmark, costs, validation windows, or seeds.
- Do not call external market-data APIs from downstream projects.
- Do not recommend live trading unless the project profile explicitly permits it.
- Store ARS run outputs under `ars/runs/`.
- Store decision-grade evidence packs under `ars/evidence_packs/`.

### Slash commands

Use:

- `/ars-read` before substantive work
- `/ars-audit` for ARS gap checks
- `/ars-evidence-pack` after research/backtests
- `/ars-handoff` before ending substantive sessions
- `/ars-review-paper <slug>` — domain reviewer LLM for paper-vs-pre-reg compliance
- `/ars-replicate <slug>` — clean-room re-impl of a Mechanism cheatsheet (spec completeness test)

### Local lint before committing a pre-registration

```bash
venv/bin/python scripts/validate_preregistration.py ars/evidence_packs/<slug>/<slug>_preregistration.md
```

Checks Rules 1-4 from `arki/wiki/onboarding/04_lessons_distilled.md`:

- Rule 1: section + equation cited (not figure name alone)
- Rule 2: degenerate-denominator multiplicative weights have a finite bound
- Rule 3: paper-derived gates list assumption_set + verify empirically
- Rule 4: aggregation method declared per gate

Non-blocking by default; exit code 1 on Rule 1 violations. Wiring as a git hook deferred to owner.

### Cost dashboard

```bash
venv/bin/python scripts/session_cost_report.py --out outputs/cost_dashboard.md
```

Aggregates `cost_actuals` across all evidence packs. Soft signal only.

### New-agent onboarding entry point

Read `arki/wiki/onboarding/00_orientation.md` first, then follow the chain through `01_lifecycle.md` → `02_worked_example_promoted.md` → `03_worked_example_falsified.md` → `04_lessons_distilled.md` → `05_API_gotchas.md`. ~30 minutes total.
<!-- ARS_PROJECT_BLOCK_END -->
