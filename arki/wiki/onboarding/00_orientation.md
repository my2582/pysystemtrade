# 00 — Orientation (read first)

**Purpose**: A new AI agent (or new human collaborator) joining this repo. ~5 minutes to absorb. Then proceed to `01_lifecycle.md`.

**Last updated**: 2026-05-29 · **Next review**: when LESSONS.md grows by ≥3 entries

## What this repo is

A fork of [Rob Carver's `pysystemtrade`](https://github.com/robcarver17/pysystemtrade) — a modular systematic futures backtesting/trading engine. Owner is **Minsu Yeom** (PM, Arki Finance). This fork's purpose is **research at ARS Decision Level 2** (Backtest runner), not live trading.

The engine itself is **frozen-core**. We do not modify the upstream pysystemtrade code; we wrap it (adapters under `arki/scripts/`, configurations in `scripts/backtest_config/`, evidence under `ars/`).

## Three constraints you must internalize

1. **`do_not_reimplement_engine: true`** (`ars/project_ars_profile.yaml`). All research happens on top of the native pysystemtrade engine via configuration overrides + post-processing. Never re-derive what the engine already computes.

2. **`live_trading: false`** + **`client_specific_recommendation: not_allowed`**. This repo cannot promote to live trading or to a specific client portfolio. The downstream consumers (b3-saa-etf, arki-future-fund-engine, arki-gtaa) handle live promotion at ARS L5+.

3. **`max_ai_decision_level: 2`** — Backtest runner only. You do not advise on live positions, you do not recommend portfolio changes, you do not approve trades.

## What this repo delivers

| Output | Where | Consumed by |
|---|---|---|
| Pre-registered backtest evidence packs | `ars/evidence_packs/<slug>/` | downstream PROD repos |
| ARS run reports (Tier 1) | `ars/runs/<id>/report.html` | per-run audit |
| Mechanism cheatsheets (Tier 2a) | `arki/cheatsheets/` | owner HITL audit, external review |
| CPC v1 cohort cards (Tier 2b) | `ars/runs/<id>/cpc/` | multi-variant comparisons |
| Lessons log | `ars/LESSONS.md` | next AI session, framework evolution |

## Where actual PROD lives

You are NOT the live system. PROD-v12 (current) lives in:

- `~/Developer/b3-saa-etf/prod/` — SAA / ETF (current MANIFEST: v12, GTAA stop-loss overlay).
- `~/Developer/arki-future-fund-engine/` — GTAA / Macro.
- `~/Developer/arki-gtaa/` — GTAA tactical overlays.

If you need a number from PROD, READ from there; do not infer or simulate.

## Bootstrap reading order

1. **THIS file** (you are here) — 5 min.
2. `01_lifecycle.md` — how an experiment flows from idea to evidence pack. 5 min.
3. `02_worked_example_promoted.md` — `martin_single_instrument` walkthrough. 10 min.
4. `03_worked_example_falsified.md` — `dmom_us10` walkthrough. 5 min.
5. `04_lessons_distilled.md` — 5 actionable rules from `ars/LESSONS.md`. 5 min.
6. `05_API_gotchas.md` — pysystemtrade + `ata` + `arki-trade-analysis` API traps. Reference; consult as needed.

After these you should be able to: read a Mechanism cheatsheet, identify a pre-registration that violates the framework, write a falsification candidate gate.

## Three things NEVER to do (saved you a session)

1. **Do not cite paper Figures as gate sources.** Cite section + equation number. (See LESSONS 2026-05-29 "Fig-as-slogan.")
2. **Do not introduce a multiplicative weight without declaring a hard upper bound at pre-registration time.** (See LESSONS 2026-05-29 "unbounded w.")
3. **Do not propose blocking owner-sign-off gates.** The owner consumes audit surfaces asynchronously. The framework GENERATES, does not PAUSE. (See PROMOTION.md "What this standard does NOT do.")

## Where to go when something feels wrong

- Code: read the function's docstring, then the calling file, then the module README. Never modify upstream pysystemtrade source.
- Framework: `ars/PROMOTION.md` is the gate spec. `ars/LESSONS.md` is the failure log. `docs/standards/ai_native_research_primitives.md` is the future direction.
- People: ask owner before destructive operations (per global CLAUDE.md).
- Memory: scan `~/.claude/projects/-Users-msyeom-Developer-pysystemtrade/memory/MEMORY.md` for relevant pointers.

## Next

→ [01_lifecycle.md](01_lifecycle.md)
