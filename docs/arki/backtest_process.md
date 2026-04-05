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

## How the Engine Works (Daily Pipeline)

Every backtest day, pysystemtrade executes this pipeline:

```
Daily Close Price
    │
    ▼
┌─────────────────────────────────────┐
│  1. SIGNAL GENERATION               │
│  Each trading rule produces a       │
│  raw forecast per instrument        │
│  (e.g. EWMAC(8,32) → +12.5)        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. FORECAST SCALING & CAPPING      │
│  Raw forecast × scalar → capped    │
│  at ±20 (forecast_cap: 20.0)       │
│  Scalar: fixed or estimated        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3. FORECAST COMBINATION            │
│  Weighted average of all rules      │
│  × forecast_div_multiplier          │
│  → Combined forecast (-20 to +20)   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  4. POSITION SIZING                  │
│                     Capital × VolTarget │
│  Ideal Position = ──────────────────── × Forecast/10 │
│                   InstrVol × Multiplier │
│                                     │
│  → Fractional contract count        │
│    (e.g. +3.72 contracts)           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  5. INSTRUMENT WEIGHTING             │
│  Position × instrument_weight        │
│  × instrument_div_multiplier         │
│  (Fixed 4% each, or estimated)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  6. BUFFERING (Position Inertia)     │
│                                     │
│  IF current_pos within             │
│     ideal ± buffer → NO TRADE      │
│  ELSE → trade to buffer EDGE only  │
│                                     │
│  buffer_method: forecast            │
│  buffer_size: 0.10 (±10%)          │
│  buffer_trade_to_edge: True         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  7. INTEGER ROUNDING                 │
│  Round to nearest whole contract    │
│  (mode=dynamic uses Mr. Greedy)     │
└──────────────┬──────────────────────┘
               │
               ▼
  Final Position: +4 contracts GOLD_micro
```

### Key Implications

- **Rebalancing frequency**: The system evaluates positions **every day**
- **Actual trading frequency**: Much lower — the buffer system absorbs small position changes. Empirically, most instruments trade **every few days to weeks**
- **No fixed rebalancing calendar**: There is no "monthly rebalancing" schedule. The system trades only when the position drifts outside the buffer zone
- **Cost awareness**: The `small_system.shadow_cost` parameter (default: 50, Arki production: 10) penalizes trading in the dynamic optimizer, further reducing turnover

### Buffering Example

```
Day 1: Ideal = 4.2   → Rounded = 4   → Trade: BUY 4
Day 2: Ideal = 4.5   → Buffer: [3.78, 4.62] → Current 4 is INSIDE → NO TRADE
Day 3: Ideal = 4.0   → Buffer: [3.60, 4.40] → Current 4 is INSIDE → NO TRADE
Day 4: Ideal = 5.3   → Buffer: [4.77, 5.83] → Current 4 is OUTSIDE → BUY to edge → +1 = 5
Day 5: Ideal = 2.1   → Buffer: [1.89, 2.31] → Current 5 is OUTSIDE → SELL to edge → -3 = 2
```

The buffer width = `ideal_position × buffer_size × 2`. So a position of 10 contracts has a ±1 contract buffer.

---

## Instrument Weight Estimation (Handcraft Method)

When `use_instrument_weight_estimates: True`, the system uses the **Handcraft algorithm** (Rob Carver's method):

```
25 instruments
  │
  ▼
Hierarchical Clustering
(scipy, complete-linkage, based on return correlation matrix)
  │
  ▼
Binary Tree (cluster_size = 2)
  │
  ├── Cluster A (e.g. US5, US10)
  │     └── Within-cluster weight: Equal 1/N (50/50)
  │
  └── Cluster B (everything else)
        └── Recursively split into sub-clusters of 2
              └── Each sub-cluster: Equal 1/N
  │
  ▼
Between-cluster weights: Equal (50/50)
  × Diversification Multiplier per cluster
  │
  ▼
SR Adjustment (parametric bootstrap)
  Tilts weights toward higher-SR instruments
  but CONSERVATIVELY (shrunk toward equal weight)
  │
  ▼
Final Instrument Weights (e.g. US5: 14%, GOLD_micro: 1.8%)
```

### Important Properties

| Property | Detail |
|---|---|
| **Clustering basis** | Return correlations — NOT asset class labels |
| **Cluster size** | Fixed at 2 (binary splits only) |
| **Within-cluster** | Equal weight (1/N) |
| **Between-cluster** | Equal weight (50/50) × div_mult |
| **SR adjustment** | Bootstrap with uncertainty — high SR only gets small tilt |
| **Re-estimation** | Expanding window, updated weekly |
| **Shrinkage** | Built-in via uncertainty-aware bootstrap |

### Why High-Correlation Pairs Get Lower Weight

If US5 and US10 are highly correlated (ρ ≈ 0.9), they cluster together. Their sub-portfolio diversification multiplier is low (~1.05). Meanwhile, COCOA_LDN (uncorrelated with everything, ρ ≈ 0.1) pairs with another dissimilar instrument, getting a high div_mult (~1.4). The result: the system allocates **more risk** to diversifying instruments.

---

## Dynamic Optimization (Mr. Greedy)

When `--mode dynamic`, the system uses the **Mr. Greedy** algorithm for integer position optimization:

1. Start with zero positions for all instruments
2. For each day, consider adding ±1 contract to each instrument
3. Pick the change that improves portfolio Sharpe Ratio the most
4. Repeat until no single-contract change improves SR
5. Apply shadow cost penalty to suppress excessive trading

This produces integer positions directly, avoiding the rounding error of the standard pipeline.

**Trade-off**: Slower computation (~5 min for 25 instruments) but better results for small accounts where rounding error is significant.

---

## 5-Step Operational Process

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

