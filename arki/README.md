# arki/ — the AI-Native operating layer (fork-safe)

This directory is the home of pysystemtrade's **AI-Native operating layer**: a committed,
LLM-maintained knowledge base (`arki/wiki/`) plus the session-prime hook that boots every agent
session with current system truth. It is modelled on the `b3-saa-etf` reference implementation,
relocated under `arki/` for fork-safety.

## §0 — Fork-safety (the binding constraint)

This repo is a **fork**:
- `origin` → `pst-group/pysystemtrade` (the fork)
- `upstream` → `robcarver17/pysystemtrade` (the original; we periodically merge `upstream/develop`)

**Every merge conflict comes from locally editing a file that also exists upstream.** New files in
paths upstream never uses cannot conflict.

### The two rules
1. **All AI-Native artifacts live under `arki/`** (this directory). Upstream has no `arki/`.
2. **Never write to an upstream-tracked file** — not the core library, not the original `docs/*.md`,
   not `README.md` / `pyproject.toml` / `setup.py` / `requirements.txt`.

### How to tell upstream-tracked from arki-local (run before any edit)
```bash
# Exit 0 (prints a hash) → exists upstream → DO NOT EDIT.
# Nonzero (no output) → arki-local/new → safe to create/edit.
git cat-file -e upstream/develop:<path> 2>/dev/null && echo "UPSTREAM — do not edit" || echo "arki-local — safe"
```

### Verified arki-local write zone
`arki/**`, `.claude/**`, `ars/**`, `docs/arki/**`, `docs/arki_references/**`, `references/**`,
`CLAUDE.md`, `AGENTS.md`, `scripts/arki_*`. (`scripts/`, `private/`, `data/` are partly upstream-tracked
— do not touch them for AI-Native work; stay inside `arki/`.)

## #0 rule — the wiki is the source of truth; memory is a cache

Durable project knowledge (how the system works, why a config was promoted, what a study concluded)
lives in committed markdown under **`arki/wiki/`** — reviewable in PRs, versioned with the code.

- **Query the wiki first** for any project question; fall back to raw sources (`results/runs/`,
  `scripts/backtest_config/`, `references/`, `docs/arki/`) for detail.
- **Agent auto/Serena memory is a cache** — it holds only ephemeral session state and *pointers* into
  the wiki. A memory file growing into a knowledge base is a smell — migrate it to a wiki page and
  leave a one-line pointer.
- **Maintain it (Agent-Loop Ingest step):** after a promotion, a settled finding, or a closed
  workstream, update the affected wiki pages, add an `index.md` row, and append to `arki/wiki/log.md`.

Start at [`wiki/index.md`](wiki/index.md). How the wiki works: [`wiki/schema.md`](wiki/schema.md).
Session-prime card (auto-injected at session start): [`wiki/system/system-card.md`](wiki/system/system-card.md).
