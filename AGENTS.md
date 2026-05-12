# AGENTS.md — pysystemtrade

Portable instructions for AI coding agents working in this repository.

<!-- ARS_AGENTS_BLOCK_START -->
## Arki Robust Standard, ARS

This project follows Arki Robust Standard.

Agents MUST:

1. Read `CLAUDE.md`.
2. Read `ars/project_ars_profile.yaml`.
3. Read relevant files in `/Users/msyeom/Developer/arki-standards/ars/`.
4. Preserve deterministic reproducibility.
5. Log material research decisions.
6. Keep exploratory and confirmatory claims separate.
7. Report failed validations and missing data explicitly.
8. Avoid unauthorized live-trading, client-specific, or rebalancing recommendations.

Agents MUST NOT:

- hardcode secrets;
- suppress errors;
- silently modify data, benchmark, costs, validation windows, or seeds;
- call external market-data APIs from downstream projects;
- use non-deterministic AI reasoning as the sole basis for portfolio-impacting decisions.
<!-- ARS_AGENTS_BLOCK_END -->

## Antigravity ARS Review Skill

This repository includes an Antigravity-compatible ARS review skill at:

`./.agents/skills/arki-ars-review/SKILL.md`

Use it for read-only independent ARS reviews. Do not let Antigravity modify files unless explicitly approved.
