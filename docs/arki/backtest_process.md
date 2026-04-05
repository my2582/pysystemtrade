# Backtesting Process

## Data Sources

pysystemtrade provides two data backends for backtesting:

| | `csvFuturesSimData` | `dbFuturesSimData` |
|---|---|---|
| **Prices** | `data/futures/adjusted_prices_csv/*.csv` (static) | `data/parquet_store/*.parquet` (updatable) |
| **Carry** | `data/futures/multiple_prices_csv/*.csv` (static) | `data/parquet_store/futures_multiple_prices/*.parquet` |
| **FX** | `data/futures/fx_prices_csv/*.csv` | `data/parquet_store/spotfx_prices/*.parquet` |
| **Spread Costs** | `data/futures/csvconfig/` (CSV) | **MongoDB** (auto-updatable) |
| **Update method** | Manual CSV replacement | IB Gateway → auto download → parquet |
| **Use case** | Quick prototyping, offline | **Production, automation, live data** |

### Why dbFuturesSimData?

CSV data is frozen at pysystemtrade's release date. To add new instruments (e.g. GOLD_micro) or backtest with the latest IB prices, the **parquet + MongoDB pipeline** is required.

Analogy: CSV = "snapshot photo", parquet = "live feed".

### Seeding Data

To populate parquet from CSV (one-time per instrument):
```python
from sysinit.futures.multiple_and_adjusted_from_csv_to_db import init_db_with_csv_prices_for_code
init_db_with_csv_prices_for_code("INSTRUMENT_CODE")
```

To seed spread costs into MongoDB:
```python
from sysinit.futures.repocsv_spread_costs import copy_csv_spread_costs_to_mongo
copy_csv_spread_costs_to_mongo()
```

---

## 5-Step Process

```
1. Data Check → 2. Config → 3. Run → 4. Compare → 5. Dashboard
     ↑                                                    |
     └────────────── iterate if needed ───────────────────┘
```

### Step 1: Data Check

```bash
python scripts/data_pipeline.py check
```

Verify:
- Last date of each instrument's parquet data
- MongoDB spread costs exist
- FX data coverage

### Step 2: Config

Config YAMLs live in `scripts/backtest_config/`.

**pysystemtrade Config Priority** (highest → lowest):
1. Backtest YAML file
2. `private/private_config.yaml` (global override)
3. `sysdata/config/defaults.yaml` (system defaults)

**Key parameters**:
- `instruments` — universe
- `instrument_weights` — fixed weights (or `use_instrument_weight_estimates: True`)
- `trading_rules` — strategy rules
- `forecast_weights` — rule weights (or `use_forecast_weight_estimates: True`)
- `percentage_vol_target` — volatility target

### Step 3: Run

```bash
python scripts/backtest_runner.py run \
  --label "descriptive_label" \
  --capital 200000 \
  --mode dynamic \
  --config scripts/backtest_config/arki_production.yaml
```

| Parameter | Description | Default |
|---|---|---|
| `--label` | Human-readable run name | Required |
| `--capital` | Capital in USD | 200,000 |
| `--mode` | `estimated` or `dynamic` | `estimated` |
| `--config` | Config YAML path | — |
| `--vol-target` | Vol target (%) | 25 |

> **Note**: `dynamic` mode uses Mr. Greedy integer position optimization. Required for small accounts ($200K).

### Step 4: Compare

```bash
# List all runs
python scripts/backtest_runner.py list

# Compare two runs
python scripts/backtest_runner.py compare <label_A> <label_B>
```

### Step 5: Dashboard

```bash
# Link run data to dashboard
ln -sf ../../results/runs/<run_id> scripts/dashboard/data

# Start server
python3 -m http.server 8889 -d scripts/dashboard
```

Dashboard at: http://localhost:8889

---

## Quick Reference: What Triggers a Re-run?

| Change | File to Edit | Re-run? |
|---|---|---|
| Add/remove instrument | Config YAML `instruments` + `instrument_weights` | Yes |
| Add/remove strategy rule | Config YAML `trading_rules` + `forecast_weights` | Yes |
| Change capital | CLI `--capital` | Yes |
| Change vol target | CLI `--vol-target` or Config YAML | Yes |
| Dashboard UI only | `scripts/dashboard/` JS/HTML | No |
