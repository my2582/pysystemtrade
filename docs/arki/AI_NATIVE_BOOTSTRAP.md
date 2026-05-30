# AI-Native Bootstrap — pysystemtrade (fork-safe)

> **Purpose:** stand up the "AI-Native" operating layer in this repo, modelled on the reference
> implementation in `b3-saa-etf`. The defining piece is a **committed, LLM-maintained wiki as the
> project's source of truth**, plus a **SessionStart prime-card hook** so every agent session boots
> with current production truth in context.
>
> **Provenance:** handed off from the `b3-saa-etf` session on 2026-05-27. The gap analysis reflects a
> pre-flight read of this repo on that date (branch `feat/arki-backtest-toolkit`). **Re-verify the
> live tree before acting** — this repo is moving.
>
> **This is a FORK.** Read §0 before anything else. The entire AI-Native layer must live in an
> `arki`-named, upstream-free path so that future `git pull upstream` merges never conflict.

---

## 0. Fork-safety (READ FIRST — the binding constraint)

This repo tracks two remotes:
- `origin` → `pst-group/pysystemtrade` (the fork)
- `upstream` → `robcarver17/pysystemtrade` (the original; we periodically merge `upstream/develop`)

**Every merge conflict comes from locally editing a file that also exists upstream.** New files in
paths upstream never uses cannot conflict. Therefore:

### The two rules
1. **All AI-Native artifacts live under a single top-level `arki/` directory** (created by this
   bootstrap). The name carries "arki" so the separation is unmistakable. Upstream has no `arki/`.
2. **Never write to an upstream-tracked file.** Not the core library, not the original `docs/*.md`,
   not `README.md` / `pyproject.toml` / `setup.py` / `requirements.txt`.

### How to tell upstream-tracked from arki-local (use this before any edit)
```bash
# Returns 0 (and prints a hash) if the path exists upstream -> DO NOT EDIT.
# Returns nonzero (no output) if it's arki-local/new -> safe to create/edit.
git cat-file -e upstream/develop:<path> 2>/dev/null && echo "UPSTREAM — do not edit" || echo "arki-local — safe"
```

### Verified arki-local write zone (safe; confirmed absent upstream 2026-05-27)
- `arki/**` — **the AI-Native home (new; primary target of this bootstrap)**
- `.claude/**` — hooks, commands (Arki-added; upstream has no `.claude/`)
- `ars/**`, `docs/arki/**`, `docs/arki_references/**`, `references/**` — existing Arki-namespaced dirs
- `CLAUDE.md`, `AGENTS.md` — Arki-added root files (absent upstream; safe, but keep edits *minimal* — see Phase 3)
- `scripts/arki_*`, `_agents/**`, `.agents/**` — existing Arki additions

> Note: `scripts/`, `private/`, `data/` are partly upstream-tracked. The ops manual already
> restricts custom work to new files there. For this bootstrap you do **not** need to touch them —
> stay inside `arki/`, `.claude/`, and the existing Arki dirs.

> b3-saa-etf is **not** a fork, so it puts its wiki at repo-root `wiki/`. Here the *same wiki design*
> is relocated under `arki/wiki/` purely for fork-safety. The schema and conventions are identical.

---

## 1. What "AI-Native" means here (5 pillars)

The reference implementation is `b3-saa-etf`. AI-Native is not "uses an LLM" — it's a project
*structured so an LLM agent can operate it reliably across sessions*. Five pillars:

| # | Pillar | Reference (`b3-saa-etf`) | Target here (fork-safe) |
|---|---|---|---|
| 1 | **Wiki = source of truth** | `wiki/` (index, schema, log, strategy/, findings/, process/) | `arki/wiki/` |
| 2 | **Memory = cache, not store** | `~/.claude/.../memory/MEMORY.md` holds only pointers into the wiki | same — pointers into `arki/wiki/` |
| 3 | **Session-prime card + hook** | `wiki/strategy/prod-card.md` + `.claude/settings.json` SessionStart hook | `arki/wiki/system/system-card.md` + hook |
| 4 | **Agent Loop + maintenance discipline** | Plan → Execute → Verify → Retry/Pivot → **Ingest** (global `~/.claude/CLAUDE.md`) | same; Ingest step maintains `arki/wiki/` |
| 5 | **Robustness standard (ARS)** | `ars/` profile + `/ars-*` commands | already present — keep |

**This repo already has Pillar 5 (ARS) and the global Agent Loop (Pillar 4). The work of this
bootstrap is Pillars 1–3, built entirely inside `arki/`.**

### The one rule that matters (copy this mental model)
> **Agent memory is a cache. The committed wiki (`arki/wiki/`) is the source of truth.**
> Durable knowledge (how the system works, why a config was promoted, what a study concluded) lives
> in committed markdown. Auto/Serena memory holds only ephemeral session state and *pointers* into
> the wiki. A memory file growing into a knowledge base is a smell — migrate it.

---

## 2. Reference files to study in `b3-saa-etf`

Read these before designing the pysystemtrade wiki (paths absolute):
- `/Users/msyeom/Developer/b3-saa-etf/wiki/schema.md` — **how the wiki works** (3 layers, page conventions, ingest/query/lint). The canonical spec to adapt. (Relocate target `wiki/` → `arki/wiki/`.)
- `/Users/msyeom/Developer/b3-saa-etf/wiki/index.md` — catalog/entry-point structure.
- `/Users/msyeom/Developer/b3-saa-etf/wiki/strategy/prod-card.md` — the **session-prime card**: ≤30 lines, fact-only, with `derived_from:` / `update_on:` / `last_verified:` frontmatter.
- `/Users/msyeom/Developer/b3-saa-etf/.claude/settings.json` — the **SessionStart hook** (one `cat` command). Copy the shape; change the path to `arki/wiki/...`.
- `/Users/msyeom/Developer/b3-saa-etf/CLAUDE.md` §"#0 rule" — how the wiki-is-truth rule reads.

---

## 3. Gap analysis (as of 2026-05-27 — re-verify)

### Already present (keep / build on — do NOT duplicate)
- **ARS layer:** `CLAUDE.md` (ARS block), `AGENTS.md`, `ars/project_ars_profile.yaml`, `ars/runs/`, `ars/evidence_packs/`, `.claude/commands/ars-*.md`, `.agents/skills/arki-ars-review/`.
- **Ops manual:** `docs/arki_references/ai_agent_operations_manual.md` (routine ops, MCP strategy, frozen-core rule).
- **Rich knowledge dump (raw material for the wiki):** `docs/arki/` — `pysystemtrade_core_architecture.md`, `backtest_process.md`, `config_knowledge_map.md`, `estimation_reference.md`, `instrument_universe.md`, `strategy_evolution.md`, `universe_sweep_report.md`, `dashboard_research_upgrade_spec.md`, `handoff_*`.
- **Research outputs:** `references/{research,strategy,valuation}/`.
- **Production config + toolkit:** `scripts/backtest_config/arki_production.yaml`, `scripts/backtest_runner.py`, `scripts/arki_mcp_server.py`, `dashboard/`, `results/runs/`.
- **Serena** active (`.serena/`).

### Missing (this bootstrap delivers — all under `arki/`)
1. **No wiki** — knowledge is scattered across `docs/arki/`, `docs/arki_references/`, `references/` with no index/schema/log and no current-vs-superseded status discipline.
2. **No session-prime card** — nothing compact stating current production system state (config in force, universe size, latest promoted run + headline metrics).
3. **No SessionStart hook** — `.claude/` has only `commands/`, no `settings.json`. Sessions boot cold.
4. **No "#0 wiki = source of truth" rule** + no wiki ingest/query/lint workflow wired to the Agent Loop.

---

## 4. Build plan (phased — present a plan, get owner sign-off, then execute)

> Follow the Agent Loop. Phase 0 is mandatory verification before any writes. Additive, surgical
> changes only. English-only in committed artifacts. **Every write target must pass the §0
> arki-local check.**

**Phase 0 — Verify + design (no writes).**
- `git status`; confirm `arki/` and `.claude/settings.json` are absent.
- For each intended write path, run the §0 `git cat-file -e upstream/develop:<path>` check; proceed only on arki-local.
- Read the 5 b3 reference files (§2) and the existing `docs/arki/*` raw material.
- Decide the wiki's top-level entities for a *futures systematic* domain (suggested below). Confirm with owner.

**Phase 1 — Wiki scaffold (under `arki/`).** Create:
- `arki/README.md` — states the fork-safety rule (§0) and the canonical "#0 wiki = source of truth" rule. This is the substantive home of the rule (so CLAUDE.md only needs a pointer).
- `arki/wiki/index.md` — catalog/entry point. Sections for this repo:
  - **System** — system card, lineage/strategy-evolution, trading rules/forecasts, instrument universe, position sizing ("Mr. Greedy" dynamic optimisation), costs.
  - **Findings** — settled studies (universe sweep, abs-mom rotation, single-instrument momentum, min-account universe study — already in `references/strategy/`).
  - **Process** — backtest process, config knowledge map, estimation reference, ops-manual pointer, ARS pointer.
- `arki/wiki/schema.md` — adapt b3's, swapping the raw-source map to this repo (`results/runs/`, `scripts/backtest_config/`, `data/futures/`, `references/`) and noting the fork-safe location.
- `arki/wiki/log.md` — chronological changelog + pointer to the decisions log (Phase 4).
- Subdirs `arki/wiki/{system,findings,process}/`.
- **Do NOT copy `docs/arki/*` content in.** Summarise + link. The existing Arki dirs stay as the raw layer; the wiki points to them and labels each "current / superseded / settled finding."

**Phase 2 — Session-prime card + hook.**
- Write `arki/wiki/system/system-card.md` (≤30 lines, fact-only): production config in force (`arki_production.yaml`), run mode (`dynamic` / Mr. Greedy), instrument universe size, latest promoted `results/runs/<run>` + headline metrics, data-as-of, frozen-core + fork-safety reminder. Add `derived_from:` / `update_on:` / `last_verified:` frontmatter.
- Create `.claude/settings.json` (arki-local, confirmed safe):
  ```json
  {
    "hooks": {
      "SessionStart": [
        { "hooks": [ { "type": "command", "command": "cat \"$CLAUDE_PROJECT_DIR/arki/wiki/system/system-card.md\"" } ] }
      ]
    }
  }
  ```
- Verify the hook fires (fresh session → card injected).

**Phase 3 — Wire the rule (minimal-footprint edits only).**
- Put the full "#0 rule" text in `arki/README.md` (Phase 1).
- In `CLAUDE.md` and `AGENTS.md` (both arki-local), add only a **short pointer**: "Source of truth = `arki/wiki/` (start at `arki/wiki/index.md`); memory is a cache; see `arki/README.md`." Keep it to a few lines — these root files are arki-local but small edits minimise any future-conflict surface if upstream ever adds its own.

**Phase 4 — Seed + decisions log.**
- Promote the highest-value `docs/arki/*` into wiki pages by *summarising and linking*: `pysystemtrade_core_architecture.md` → `arki/wiki/system/`, `strategy_evolution.md` → `arki/wiki/system/lineage.md`, `universe_sweep_report.md` → `arki/wiki/findings/`.
- Decisions log: adopt `docs/arki/strategy_evolution.md` as the chronological promotion log, or create `arki/wiki/decisions.md`; have `arki/wiki/log.md` point to it (don't duplicate).
- Add a "to ingest" backlog section in `arki/wiki/index.md`.

---

## 5. Domain adaptations (b3 → pysystemtrade)

| b3-saa-etf concept | pysystemtrade analog |
|---|---|
| 4-sleeve ETF portfolio | futures system: trading rules → forecasts → combination → position sizing → dynamic optimisation |
| `prod/MANIFEST.yaml` (prod definition) | `scripts/backtest_config/arki_production.yaml` (+ promoted `results/runs/<run>`) |
| Growth picker `gate_int12m` | active forecast/rule set + Mr. Greedy dynamic optimiser |
| `growthy.yaml` universe | production instrument universe (`docs/arki/instrument_universe.md`) |
| PROD-vN lineage | strategy/config evolution (`docs/arki/strategy_evolution.md`) |
| SRP report packs | dashboard bundles (`scripts/bundle_dashboard.py` → `results/runs/`) |
| repo-root `wiki/` | `arki/wiki/` (relocated for fork-safety) |

---

## 6. What NOT to do
- **Do not edit any upstream-tracked file** (verify via §0). This includes the core `pysystemtrade`
  library, original `docs/*.md`, `README.md`, `pyproject.toml`, `setup.py`, `requirements.txt`.
- **Do not modify the core library** even within the "scripts/private/data" carve-out — not needed for this bootstrap; stay in `arki/`.
- **Do not duplicate** `docs/arki/*` or `references/*` into the wiki — summarise + link.
- **Do not invent production numbers** for the system card — derive each figure from a named `results/runs/<run>` artifact or config file, and cite it.
- **Do not delete or rewrite** the ARS block, `AGENTS.md` body, or the frozen-core rule.
- No non-English in committed artifacts.

## 7. Acceptance criteria (Verify step)
- [ ] `arki/wiki/{index.md, schema.md, log.md}` exist; `schema.md` adapted to this repo's raw-source map.
- [ ] `arki/wiki/system/system-card.md` ≤30 lines, fact-only, every number cited, frontmatter present.
- [ ] `arki/README.md` carries the fork-safety rule (§0) + the "#0 wiki = source of truth" rule.
- [ ] `.claude/settings.json` SessionStart hook fires and injects the card (verified in a fresh session).
- [ ] `CLAUDE.md` + `AGENTS.md` carry only a short pointer to `arki/wiki/`; ARS + frozen-core intact.
- [ ] ≥3 `docs/arki/*` files promoted to wiki pages by summary+link; decisions log wired to `arki/wiki/log.md`.
- [ ] **Fork-safety proof:** `git diff --stat upstream/develop...HEAD -- $(git diff --name-only)` touches only arki-local paths; **zero upstream-tracked files modified.** Quick check: `git diff --name-only` ∩ upstream files = ∅.
- [ ] Memory updated with a *pointer* to `arki/wiki/index.md` (not a copy of its content).
