# pysystemtrade Core Architecture & AI Engineering Guide

**Target Audience:** AI Agents (Antigravity), Human Engineeers (Arki OS)
**Purpose:** Natively leverage existing `pysystemtrade` modules without reinventing the wheel.
**Authoring Context:** Arki Unified Development Policy

---

## 1. The Core Philosophy (Carver Framework)

`pysystemtrade` is not a typical tick-based backtester (like Backtrader or Zipline). It is built on **Rob Carver's Mathematical Framework for Systematic Trading**. 
If you fail to understand these tenets, you will write incompatible, unscalable code.

### A. Risk-Normalized Position Sizing
Every decision in this system is scaled by **Volatility**.  
You *never* say "Buy 100 shares of Apple." You say "Buy a forecast of +10.0". 
The system translates +10.0 (the standard risk target) into a dollar-volatility target, then divides by the instrument's recent price volatility and multiplier to generate the actual contract quantity.
* **Forecast Range:** Usually capped at -20 to +20. A +10 means "Standard Conviction Long."
* **Volatility Target:** Systems aim for a portfolio-level annualized volatility (e.g., 25%). 

### B. Strict Decoupling of Operations (The Pipeline)
The system computes state via discrete, isolated "stages." Data flows sequentially:
`Raw Price Data` -> `Volatility Calculation` -> `Trading Rule Forecast` -> `Forecast Scaling (10.0)` -> `Forecast Combining` -> `Position Sizing (dividing by Vol)` -> `Portfolio Weighting` -> `Subsystem Positions` -> `Buffering (Execution smoothing)`

### C. Lazy Evaluation & Caching
Because the system runs millions of pandas operations, everything is evaluated lazily.
* `system.positionSize.get_subsystem_position(instrument)` won't calculate anything unless asked.
* Once calculated, the resulting Pandas DataFrame is cached. 
* **RULE:** Do NOT pre-calculate giant matrices in memory. Call the specific `get_()` function required for your instrument, and let `systen_cache` handle the memoization.

---

## 2. Directory & Module Autopsy

When writing new scripts or strategies, natively import from these locations:

| Package | Purpose & Key Classes | Usage Rule |
|---------|-----------------------|------------|
| `syscore` | Low-level Python/Pandas tools (`syscore.pandas.pd_readcsv`). | Extensively used for rolling calculations. Avoid writing custom rolling loops. Use `syscore`. |
| `sysdata` | Data I/O. Deals with DBs. `sysdata.config.configdata` | Treat as read-only in backtests. Provides Prices, FX, Multipliers. |
| `sysobjects` | Type definitions. `instruments`, `contracts`. | Use to parse config YAML logic. |
| `systems` | **The Brain.** Contains the pipeline stages (`TradingRules`, `Forecasting`, `PositionSizing`, `Portfolio`). | When extracting metrics, *always* interface via the `System` object, not by reading raw CSVs directly. |
| `sysquant` | Quantitative statistical indicators. | Natively use `sysquant` for calculations like EWMA instead of raw generic pandas. |

---

## 3. Engineering Guidelines for AI Agents

When the USER requests "a new script utilizing `pysystemtrade`", strictly follow these patterns:

### Pattern 1: Extending Trading Rules
Do not build custom dataframe loops. Write a rule function that takes a Pandas series of prices and returns a Pandas series of raw forecasts.
```python
# GOOD: Using the framework
from systems.provided.trading_rules.rules import vol_target_rule # or similar
def my_custom_rule(price_series, my_param_1):
    # Calculate raw signal (e.g., z-score of MA)
    # Return time-series of raw forecasts
    return raw_signal_series
```
Then register this in the YAML config under `trading_rules:`.

### Pattern 2: Building the System Object
Always instantiate a system using the standard builder.
```python
# ALWAYS DO THIS in your script:
from scripts.run_dynamic_backtest import build_dynamic_system
system = build_dynamic_system("arki_production.yaml", capital=200000, instruments=my_list)
```
Once `system` is built, you have access to the entire pipeline. 

### Pattern 3: Extracting Strategy Data For Research
Do not write custom math to calculate drawdown or turnover. Use the system's `accounts` stage.
```python
# TO GET PNL:
portfolio_pnl = system.accounts.portfolio()
rule_pnl = system.accounts.pandl_for_trading_rule("ewmac8_32")

# TO GET POSITIONS:
notional_pos = system.portfolio.get_notional_position("SP500_micro")
integer_contracts = notional_pos.round()
```

### Pattern 4: Global Config over Hardcoding
Any parameter (`vol_target`, `forecast_cap`, `costs`) must be read from `system.config`. Never hardcode an assumption.

---

## 4. Execution vs. Estimation (The Arki Distinction)
`pysystemtrade` supports both Fixed Rules and Estimated Rules.
* **Static/Fixed:** Weights for instruments, forecasts, and multipliers are set rigidly in the `.yaml`. 
* **Dynamic/Estimated:** The system learns weights dynamically.
* **Arki Standard:** Arki predominantly uses **Dynamic Estimation** (via `build_dynamic_system()`). Ensure any new script accounts for `use_instrument_weight_estimates` flags being true.
