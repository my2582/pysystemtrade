# pysystemtrade wiki — index

The durable knowledge base for Arki's pysystemtrade fork. **Start here.** Read [schema.md](schema.md)
for how it works (the one rule: *agent memory is a cache, this wiki is the source of truth*).
Fork-safety + the rules: [`../README.md`](../README.md).

**Current state: IN TRANSITION** — documented baseline **v4** (`arki_production.yaml`, 24 inst, $200k)
→ leading candidate **dm37** (`dm37_1m.yaml`, 37 inst, $1M). Research only; `live_trading: false`; no
run is formally promoted. → [system/system-card.md](system/system-card.md) (session-prime card).

## System — how the live system works
- [system/system-card.md](system/system-card.md) — **session-prime card** (hook-injected); compact, cited production truth.
- [system/architecture.md](system/architecture.md) — the pysystemtrade pipeline (rules → forecasts → sizing → dynamic optimisation).
- [system/lineage.md](system/lineage.md) — version spine v1→v4-fresh + the dm37 candidate; flags config-name drift.
- [system/universe.md](system/universe.md) — instrument universe (24 v4.1 vs 37 dm37) + the stale-data caveat.

## Findings — settled research conclusions
- [findings/universe-sweep.md](findings/universe-sweep.md) — asset-class sweep: keep 25-inst + OilGas + handcraft (positive skew). Settled.

## Process — how we work
- [process/index.md](process/index.md) — backtest process, config map, estimation reference, ops manual, ARS.

## External structured indices (not duplicated here)
- `results/runs/registry.yaml` — run index (no promotion field).
- `docs/arki/strategy_evolution.md` — chronological promotion log (the wiki's `log.md` points to it).
- `scripts/backtest_config/*.yaml` — config definitions of record.
- `ars/` — ARS profile + evidence packs.

## To ingest (backlog — knowledge still only in raw sources / memory)
- **absmom single-position rotation** (active workstream) — promote `references/strategy/2026-05-27_absmom_rotation_spec.md` + the signal-implementation research once the design settles.
- **min-account universe study** (`references/strategy/2026-05-27_min_account_universe_study.html`) → findings page.
- **IBKR price-accumulation pipeline** (`references/research/2026-05-27-ibkr-panama-price-accumulation-pipeline.md`) → system/process page (root cause of stale data).
- **dashboard research upgrade spec** (`docs/arki/dashboard_research_upgrade_spec.md`) → process page when built.
- **macro investment thesis + century factor analysis** (`docs/arki_references/`) → findings pages.
