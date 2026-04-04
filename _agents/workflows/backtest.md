---
description: Run a backtest, compare runs, and view dashboard
---
// turbo-all

# Backtest Workflow

## 1. Check Data Freshness

```bash
cd /Users/msyeom/Developer/pysystemtrade && source venv/bin/activate
python3 -c "
import pandas as pd, os, warnings; warnings.filterwarnings('ignore')
store = 'data/parquet_store/futures_adjusted_prices'
for f in sorted(os.listdir(store)):
    df = pd.read_parquet(f'{store}/{f}')
    print(f'{f.replace(\".parquet\",\"\"):25s} {str(df.index[-1].date()):>12s}  ({len(df)} rows)')
"
```

## 2. Run Backtest

```bash
cd /Users/msyeom/Developer/pysystemtrade && source venv/bin/activate
python3 scripts/backtest_runner.py run \
  --label "<LABEL>" \
  --capital 200000 \
  --mode dynamic \
  --config scripts/backtest_config/<CONFIG>.yaml
```

Replace `<LABEL>` with a descriptive name (e.g. "arki_v3_expanded").
Replace `<CONFIG>` with the config file name.

## 3. List All Runs

```bash
cd /Users/msyeom/Developer/pysystemtrade && source venv/bin/activate
python3 scripts/backtest_runner.py list
```

## 4. Compare Two Runs

```bash
cd /Users/msyeom/Developer/pysystemtrade && source venv/bin/activate
python3 scripts/backtest_runner.py compare <LABEL_A> <LABEL_B>
```

## 5. Switch Dashboard to a Run

```bash
cd /Users/msyeom/Developer/pysystemtrade
rm -f scripts/dashboard/data
ln -sf ../../results/runs/<RUN_ID> scripts/dashboard/data
```

Replace `<RUN_ID>` with the run directory name from `results/runs/`.

## 6. Start Dashboard Server

```bash
cd /Users/msyeom/Developer/pysystemtrade/scripts/dashboard
pkill -f "http.server 8889" 2>/dev/null; sleep 1
python3 -m http.server 8889 &
```

Dashboard available at: http://localhost:8889

## Quick Reference

| What to change | Where | Re-run needed |
|---|---|---|
| Add/remove instrument | Config YAML `instruments` + `instrument_weights` | Yes |
| Add/remove strategy rule | Config YAML `trading_rules` + `forecast_weights` | Yes |
| Change capital | CLI `--capital` | Yes |
| Change vol target | CLI `--vol-target` or Config YAML | Yes |
| Dashboard UI only | `scripts/dashboard/` JS/HTML | No |

## Data Source: dbFuturesSimData

The backtest uses `dbFuturesSimData` which reads from:
- **Prices**: `data/parquet_store/*.parquet` (updatable via IB)
- **Spread Costs**: MongoDB (seeded from CSV, updatable via IB sampling)
- **FX**: `data/parquet_store/spotfx_prices/*.parquet`

To seed a new instrument into parquet from CSV:
```python
from sysinit.futures.multiple_and_adjusted_from_csv_to_db import init_db_with_csv_prices_for_code
init_db_with_csv_prices_for_code("INSTRUMENT_CODE")
```
