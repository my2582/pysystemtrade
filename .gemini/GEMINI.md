# pysystemtrade — Arki Project Rules

## 0. Core Principle: Native Utilization & Consistency (최상위 원칙)

> **pysystemtrade를 최대한 이용한다. pysystemtrade의 구현에 맞춰 일관성을 갖춘다.**

- 성과 지표, 수식, 상수를 구현할 때 pysystemtrade가 이미 제공하는 기능이 있는지 **반드시 먼저 확인**한다.
- 있으면 `System` 객체를 통해 사용한다 (CSV를 직접 파싱하거나 수식을 직접 구현하지 않는다).
- 없으면 `scripts/`에 새로 작성하되, pysystemtrade의 상수(N=256 등)와 수식 컨벤션을 따른다.
- KI 참조: `~/.gemini/antigravity/knowledge/pysystemtrade_architecture/` — 스테이지별 메서드, 파라미터 맵, 공식 기록.

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
ann_std  = std(returns) × √(times_per_year)   # BDay=256, Month=12
sharpe   = ann_mean / ann_std
```
Source: `systems/accounts/curves/account_curve.py:209-241`

### Constants:
- Business days/year: **256** (not 252)
- Months/year: **12**
- Vol scalar daily: **√256 = 16.0**

## 4. Data Layer

- **Production**: `dbFuturesSimData` (parquet + MongoDB)
- **Prototyping**: `csvFuturesSimData` (static CSVs)
- New instruments need: price seed to parquet, spread costs to MongoDB, entry in `instrumentconfig.csv`

## 5. Config Priority (highest → lowest)

1. Backtest YAML (`scripts/backtest_config/arki_production.yaml`)
2. Private config (`private/private_config.yaml`)
3. System defaults (`sysdata/config/defaults.yaml`)

## 6. Git Workflow

- **Branch**: Feature branches off `develop` (e.g., `feat/arki-backtest-toolkit`)
- **Never push** — only the user decides when to push
- **Conventional commits** — `feat:`, `fix:`, `docs:`, `refactor:`
- **Sync upstream**: `git fetch upstream && git merge upstream/develop`
