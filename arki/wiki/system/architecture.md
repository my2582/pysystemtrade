# Architecture — the pysystemtrade pipeline

Status: current. The engine is **unmodified upstream** pysystemtrade (Rob Carver framework);
`do_not_reimplement_engine: true`. Reference:
[`../../../docs/arki/pysystemtrade_core_architecture.md`](../../../docs/arki/pysystemtrade_core_architecture.md).

## Pipeline stages (risk-normalised)

Raw prices → **volatility estimate** → **trading-rule forecasts** (scaled, capped ±20) → **forecast
combination** (forecast weights + FDM) → **position sizing** (vol target ÷ instrument risk) → **portfolio
weighting** (instrument weights + IDM) → **subsystem positions** → **dynamic optimisation** ("Mr. Greedy"
integer rounding to tradable contracts) → buffering (execution smoothing).

All positions are expressed as **volatility-adjusted forecasts**, never raw contracts, then scaled to the
portfolio vol target. This is why the system behaves consistently across instruments and capital levels.

## Code map (where things live)
- `syscore` — calculation / pandas utilities.
- `sysdata` — data I/O (read-only during backtest).
- `sysobjects` — type definitions (instruments, prices, positions).
- `systems` — the pipeline stages above (trading rules, forecasting, position sizing, portfolio).
- `sysquant` — estimators / indicators.

## Engineering rules (from the reference)
- Instantiate via the project's `build_dynamic_system()`; read outputs from `system.accounts` /
  `system.portfolio`, not raw CSVs. Read every setting from `system.config` — no hardcoding.
- Lazy evaluation + caching: call specific `get_*()` methods; don't pre-compute matrices.
- The Arki toolkit (`scripts/backtest_runner.py`, configs in `scripts/backtest_config/`) wraps the engine
  and writes `results/runs/<id>/` — see [../process/index.md](../process/index.md).
