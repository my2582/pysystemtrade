# /ars-audit

Audit the current project against ARS.

Required actions:

1. Read project `CLAUDE.md`.
2. Read project `AGENTS.md` if present.
3. Read `ars/project_ars_profile.yaml`.
4. Inspect recent git state:
   - `git log -10 --oneline`
   - `git status --short`
5. Identify applicable ARS requirements.
6. Report:
   - compliant areas;
   - gaps;
   - risks;
   - minimum fixes;
   - whether work is exploratory, validation, or production candidate.
7. Do not change files unless explicitly asked.
