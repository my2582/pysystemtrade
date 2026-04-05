# Arki — pysystemtrade Customization Layer

This directory contains documentation for Arki's customizations built on top of pysystemtrade.
All files here are **Arki-specific** — pysystemtrade's original documentation lives in `docs/` (parent directory).

## Conventions

### Naming: `arki_` Prefix Rule

Use `arki_` prefix **only when our files coexist with pysystemtrade's files in the same directory**.
When a directory is exclusively ours, no prefix is needed — the directory itself is the namespace.

| Location | Mixed with pysystemtrade? | Use `arki_` prefix? |
|---|---|---|
| `scripts/backtest_config/` | Yes (e.g. `trend_carry_csmom.yaml`) | **Yes** → `arki_production.yaml` |
| `docs/arki/` | No (our directory) | **No** → `backtest_process.md` |
| `scripts/dashboard/` | No (our directory) | **No** |
| `results/` | No (our directory, gitignored) | **No** |

### Directory Ownership

| Directory | Owner | Description |
|---|---|---|
| `scripts/backtest_config/arki_*.yaml` | Arki | Strategy configs (16-inst, 25-inst, etc.) |
| `scripts/backtest_runner.py` | Arki | Multi-run backtest CLI |
| `scripts/dashboard/` | Arki | Performance dashboard |
| `scripts/data_pipeline.py` | Arki | Data freshness checks |
| `scripts/static_instrument_selection.py` | Arki | Instrument universe selection |
| `results/` | Arki | Backtest run outputs (gitignored) |
| `docs/arki/` | Arki | This documentation |
| `_agents/workflows/` | Arki | Antigravity workflow definitions |

### Data Infrastructure

| Component | Technology | Location |
|---|---|---|
| Price data | Parquet | `data/parquet_store/` |
| Spread costs | MongoDB | `localhost:27017` |
| Config | YAML | `scripts/backtest_config/` |
| Results registry | YAML | `results/runs/registry.yaml` |

## Config Quick Reference

### Config Priority (in backtest_runner.py)

```
CLI --instruments-from  >  config YAML instruments:  >  ALL available
```

Every `arki_*.yaml` is **self-contained** — instruments, rules, weights all in one file.

### Active Configs

| File | Status | Key Trait |
|------|--------|-----------|
| **`arki_production.yaml`** | ⭐ **PRODUCTION** | 25 instruments, all estimations ON, risk overlay |
| `arki_v5_dynamic.yaml` | Experiment | Dynamic instrument weights + 35/20/45 factor tilt |
| `arki_v5b_factor_tilt.yaml` | Experiment | Equal weights + 30/15/55 aggressive CS Momentum |
| `arki_v5c_combined.yaml` | Experiment | v5a + v5b combined (underperformed) |

### Legacy (reference only)

| File | Purpose |
|------|---------|
| `trend_carry_csmom.yaml` | Original Carver-style fixed weights (v4 simple baseline) |
| `trend_carry_csmom_estimated.yaml` | Early estimated variant (pre-arki naming) |
| `arki_v3_25inst.yaml` | 25-instrument expansion experiment |
| `arki_v4_optimized.yaml` | Intermediate optimization |

### What Controls Estimation

| Feature | Fixed Config | Production Config |
|---------|-------------|-------------------|
| Instrument weights | Equal 4% | `use_instrument_weight_estimates: True` |
| Forecast weights | Manual fractions | `use_forecast_weight_estimates: True` |
| Forecast scalars | Book values | `use_forecast_scale_estimates: True` |
| Risk overlay | None | Enabled |

## Documents

| # | Document | Description |
|---|---|---|
| 1 | [backtest_process.md](backtest_process.md) | 5-step backtesting process + data source explanation |
| 2 | [strategy_evolution.md](strategy_evolution.md) | v1→v5 history, decisions, and key findings |
| 3 | [instrument_universe.md](instrument_universe.md) | Universe criteria, contract size analysis, expansion log |
| 4 | [config_knowledge_map.md](config_knowledge_map.md) | Complete config file map, run management, quick reference |
| 5 | [estimation_reference.md](estimation_reference.md) | All 7 estimation flags explained with code traces |
