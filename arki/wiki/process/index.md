# Process — how we work

Status: current. This page links to the raw process specs; it does not duplicate them.

## Backtesting + config
- [`../../../docs/arki/backtest_process.md`](../../../docs/arki/backtest_process.md) — data backends
  (`csvFuturesSimData` for prototyping vs `dbFuturesSimData` for production automation).
- [`../../../docs/arki/config_knowledge_map.md`](../../../docs/arki/config_knowledge_map.md) — config
  hierarchy: `private_config.yaml` → `backtest_runner.py` + strategy `arki_*.yaml` → `results/runs/`.
- [`../../../docs/arki/estimation_reference.md`](../../../docs/arki/estimation_reference.md) — fixed vs
  estimated flags (forecast scalar, IDM, instrument weights) mapped to code.
- Run toolkit: `scripts/backtest_runner.py`; configs in `scripts/backtest_config/`; runs land in
  `results/runs/<id>/` (schema: `stats.yaml`, `equity_curve.csv`, `daily_returns.csv`, …). Per-trade
  analysis: `scripts/trade_analysis.py`.

## Operations + governance
- [`../../../docs/arki_references/ai_agent_operations_manual.md`](../../../docs/arki_references/ai_agent_operations_manual.md)
  — routine ops (IB backfill, backtest runs, position export); the **frozen-core rule** (never modify core
  pysystemtrade).
- **ARS** — `ars/project_ars_profile.yaml` (max AI decision level 2, `live_trading: false`,
  `do_not_reimplement_engine: true`); slash commands `/ars-read`, `/ars-audit`, `/ars-evidence-pack`,
  `/ars-handoff`. Run outputs → `ars/runs/`; decision-grade evidence packs → `ars/evidence_packs/`.
- Dashboard research-upgrade spec (planned):
  [`../../../docs/arki/dashboard_research_upgrade_spec.md`](../../../docs/arki/dashboard_research_upgrade_spec.md).
