# Wiki schema — how this knowledge base works

This `arki/wiki/` is the **durable, committed source of truth** for accumulated project knowledge on
pysystemtrade (Arki's fork). It follows the LLM-maintained-wiki pattern: a human curates the raw
sources and sets direction; the agent does the bookkeeping — summarising, cross-referencing, and
keeping pages consistent.

**Fork-safe location:** `b3-saa-etf` (not a fork) puts its wiki at repo-root `wiki/`. Here the *same
design* lives under `arki/wiki/` so that `git merge upstream/develop` never conflicts. See
[`../README.md`](../README.md) §0.

## The one rule that matters

**Agent memory is a cache. This wiki is the source of truth.**

- Durable knowledge lives **here**, in committed markdown.
- Agent auto/Serena memory holds only ephemeral session state and *pointers* into this wiki.
- A memory file growing into a knowledge base is a smell — migrate it and leave a pointer.

## Three layers (don't confuse them)

| Layer | What | Where |
|---|---|---|
| **Raw sources** (immutable) | runs, configs, prices, research, the raw knowledge dump | `results/runs/`, `scripts/backtest_config/`, `data/parquet_store/`, `references/`, `docs/arki/`, `docs/arki_references/` |
| **The wiki** (LLM-maintained) | summaries, entity pages, findings, cross-links | `arki/wiki/` (this dir) |
| **The schema** (config) | project rules + how the wiki is maintained | `CLAUDE.md` + this file |

## Layout
```
arki/wiki/
  index.md          ← catalog / entry point: current state + every page, by category
  schema.md         ← this file
  log.md            ← chronological wiki changelog + pointer to the promotion log
  system/           ← how the live system works (card, architecture, lineage, universe)
  findings/         ← settled research conclusions
  process/          ← how we work (backtest process, config map, estimation, ops manual, ARS)
```

## Page conventions

- Every page starts with a one-line **status** (`Status: current` / `Status: settled finding` /
  `Status: superseded by [[…]]` / `Status: draft/spec`).
- Cross-link liberally with relative markdown links.
- **Cite the source for every number:** the `results/runs/<id>/` artifact, config file, or doc that
  produced it. No un-sourced figures (ARS evidence principle).
- Keep pages short and factual. Long evidence stays in the raw sources; the wiki summarises + links.
- **English only** (committed-artifact rule) — even when a raw source is bilingual.

## Maintenance workflow (the agent runs these)

1. **Ingest** — after a promotion, a settled finding, or a closed workstream: create/update the
   relevant pages in one pass, add an `index.md` row, append to `log.md`.
2. **Query** — to answer a project question, read the relevant wiki pages first; fall back to raw
   sources for detail. Cite pages in the answer.
3. **Lint** (periodic) — check for contradictions between pages, stale "current" labels after a
   promotion, orphaned pages (not in `index.md`), and dead cross-links.

## Relationship to what already exists (linked, never duplicated)

- `docs/arki/strategy_evolution.md` **is** the chronological promotion log → `log.md` points to it.
- `results/runs/registry.yaml` is the structured run index → `index.md` links to it.
- `docs/arki/` + `docs/arki_references/` hold the raw knowledge dump → wiki pages summarise + link.
- `scripts/backtest_config/*.yaml` are the config definitions of record → `system/` pages link to them.
- `ars/` holds the ARS profile + evidence packs → `process/index.md` links to it.
