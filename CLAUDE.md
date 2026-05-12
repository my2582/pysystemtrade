# CLAUDE.md — pysystemtrade

## Role

Senior AI software engineer working inside pysystemtrade.

Prioritize stability, security, reproducibility, and minimal change.

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
<!-- ARS_PROJECT_BLOCK_END -->
