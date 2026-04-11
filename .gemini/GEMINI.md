# pysystemtrade — Arki Project Rules

## 0. Core Principle: Native Utilization & Consistency

> **Maximize use of pysystemtrade's native modules. Align all custom code to pysystemtrade's conventions for consistency.**

- Before implementing any metric, formula, or data extraction, **always check first** whether pysystemtrade already provides it.
- If it does, use the `System` object (do not parse CSVs directly or re-implement formulas).
- If it does not, write new code in `scripts/` only, following pysystemtrade's constants (N=256) and formula conventions (arithmetic SR).
- KI reference: `~/.gemini/antigravity/knowledge/pysystemtrade_architecture/` — stage methods, parameter maps, canonical formulas.

## 1. Upstream Preservation (CRITICAL)

This repo is a **fork** of `robcarver17/pysystemtrade` (`upstream` remote).
The upstream code MUST remain untouched so that `git merge upstream/develop` stays conflict-free.

### Never modify these packages:
- `systems/` — pipeline stages, cache, trading rules
- `syscore/` — low-level utilities
- `sysdata/` — data I/O adapters
- `sysquant/` — quantitative estimators/optimisers
- `sysobjects/` — type definitions
- `sysproduction/` — production trading
- `sysbrokers/` — IB broker interface
- `sysexecution/` — order management
- `sysinit/` — initialisation scripts
- `syslogdiag/`, `syslogging/`, `syscontrol/` — logging/control

### Arki-only code goes here:
- `scripts/` — backtest runners, data generators, dashboard
- `scripts/backtest_config/` — YAML strategy configurations
- `scripts/dashboard/` — analytics UI
- `docs/arki/` — internal documentation
- `_agents/workflows/` — AI agent workflows
- `data/arki_macro/` — Arki-specific input data

### If you MUST extend pysystemtrade behaviour:
1. **Subclass**, don't modify. Create a new file in `scripts/` that inherits from the upstream class.
2. **Config override**, don't hardcode. Use YAML config (`scripts/backtest_config/`) to change parameters.
3. **Wrapper script**, don't patch. Write a script that calls `System(...)` and extracts what you need.

## 2. System Architecture

pysystemtrade uses a **stage-based pipeline** with lazy caching. See the KI at:
`~/.gemini/antigravity/knowledge/pysystemtrade_architecture/`

### Pipeline order:
```
RawData → Rules → ForecastScaleCap → ForecastCombine → PositionSizing → Portfolios → Accounts
```

### Always build systems using the standard pattern:
```python
from scripts.run_dynamic_backtest import build_dynamic_system
system = build_dynamic_system("config.yaml", capital=200000, instruments=[...])
```
Never construct pandas loops to replicate what `system.accounts.portfolio()` already does.

## 3. Performance Metrics

### Sharpe Ratio — use pysystemtrade's canonical formula:
```python
ann_mean = sum(returns) / number_of_years     # arithmetic, NOT CAGR
ann_std  = std(returns) * sqrt(times_per_year) # BDay=256, Month=12
sharpe   = ann_mean / ann_std
```
Source: `systems/accounts/curves/account_curve.py:209-241`

### Constants:
- Business days/year: **256** (not 252)
- Months/year: **12**
- Vol scalar daily: **sqrt(256) = 16.0**

## 4. Data Layer

- **Production**: `dbFuturesSimData` (parquet + MongoDB)
- **Prototyping**: `csvFuturesSimData` (static CSVs)
- New instruments need: price seed to parquet, spread costs to MongoDB, entry in `instrumentconfig.csv`

## 5. Config Priority (highest to lowest)

1. Backtest YAML (`scripts/backtest_config/arki_production.yaml`)
2. Private config (`private/private_config.yaml`)
3. System defaults (`sysdata/config/defaults.yaml`)

## 6. Git Workflow

- **Branch**: Feature branches off `develop` (e.g., `feat/arki-backtest-toolkit`)
- **Never push** — only the user decides when to push
- **Conventional commits** — `feat:`, `fix:`, `docs:`, `refactor:`
- **Sync upstream**: `git fetch upstream && git merge upstream/develop`
