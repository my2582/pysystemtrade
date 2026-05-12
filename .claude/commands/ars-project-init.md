# /ars-project-init

Initialize or repair ARS structure in the current project.

Before action:

1. Confirm project name.
2. Confirm engine type.
3. Confirm max AI decision level.
4. Confirm whether live trading is allowed.

Create or update:

- `ars/project_ars_profile.yaml`
- `ars/runs/.gitkeep`
- `ars/evidence_packs/.gitkeep`
- `.claude/commands/`
- project `CLAUDE.md` ARS section
- project `AGENTS.md` ARS section

Do not overwrite existing files without showing a diff or backup plan.
