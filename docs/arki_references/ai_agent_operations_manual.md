# Arki Ops: AI Agent Handoff & Operations Manual

**Role**: You are an AI Operations Engineer (Claude) managing the Arki Finance quantitative environment based on `pysystemtrade`.
**Primary Directive**: Maintain stability, run pipelines, and report results.

> [!CAUTION]
> **STRICT RULE: NEVER MODIFY THE CORE `pysystemtrade` CODEBASE.**
> The underlying `pysystemtrade` library is a frozen, complex system. Do not edit files outside of the `scripts/`, `private/`, or `data/` directories unless explicitly ordered by the human user. All custom operations are handled via dedicated scripts in the `scripts/` directory.

## 1. Routine Operations

### A. Updating Futures Prices (IBKR)
To update the price data for all production futures contracts (filling any data gaps up to the present day), use the backfill script. 

**Prerequisite**: Interactive Brokers TWS or IB Gateway MUST be running and listening on `127.0.0.1:4001` (Client ID: 99).

**Command**:
```bash
python3 scripts/backfill_from_ib.py
```
*How it works*: It connects to IB, downloads missing contract data for the 25+ production instruments, seeds the local MongoDB, rebuilds the multiple/adjusted prices, and exports them back to CSVs in `data/futures/adjusted_prices_csv/`. It automatically detects gaps and updates up to the latest available date. No date range parameters are needed.

### B. Running Production Backtests
To run a backtest using a specific configuration:
```bash
python3 scripts/backtest_runner.py full --label "run_name" --mode dynamic --config scripts/backtest_config/arki_production.yaml
```
*Note*: `--mode dynamic` uses "Mr. Greedy" optimization for integer position sizing, which is required for Arki. It takes about 8-10 minutes to run.

### C. Dashboard Generation
The dashboard consists of static HTML/JS and dynamic JSON data generated from the backtest results.
To bundle a backtest run into a shareable HTML dashboard:
```bash
python3 scripts/bundle_dashboard.py --run "run_name"
```
*Architecture*: 
- The dashboard frontend (`scripts/dashboard/app.js`) reads run metrics from `results/runs/<run_name>/dashboard_meta.json` and time-series data from `daily_returns.csv` and `position_snapshot.csv`.
- Static universe contract specs are loaded from `scripts/dashboard/arki_universe_info.json`.

## 2. Model Context Protocol (MCP) Integration Strategy

To allow you (Claude) to securely and predictably interact with this environment, we recommend establishing an **MCP (Model Context Protocol) Server**. 

### Recommended Handoff Approach
Do not try to build a massive, all-encompassing MCP server from scratch. Instead:
1. Start with a **minimal Python MCP server** (`arki_mcp_server.py`) that registers a few safe tools.
2. Extend the tools incrementally as needed.

### Essential MCP Tools Implemented in `arki_mcp_server.py`:
1. `update_prices()`: Triggers `scripts/backfill_from_ib.py` as a background subprocess and tails the log.
2. `optimize_universe(capital, target_count)`: Uses `scripts/universe_optimizer.py` to generate an optimal universe for the account size.
3. `run_strategy_audit(config_yaml)`: Runs `scripts/strategy_audit.py` to check for configuration errors before backtesting.
4. `run_backtest(config_yaml, label)`: Triggers `scripts/backtest_runner.py` and returns the path to the results.
5. `generate_macro_data()`: Runs `generate_arki_macro_data.py` and `generate_macro_universe_compare.py` to update the Macro Dashboard tabs after a backtest.
6. `get_run_summary(label)`: Reads `results/runs/<label>/dashboard_meta.json` and returns a concise JSON summary of Sharpe Ratio, CAGR, and Drawdown.
7. `generate_dashboard(label)`: Runs `bundle_dashboard.py` and returns the file path to the bundled HTML.

## 3. Environment Specs
- **Cwd**: `/Users/msyeom/Developer/pysystemtrade`
- **Python**: Use the environment's `python3`.
- **Backtest Configs**: `scripts/backtest_config/*.yaml`
- **Results**: `results/runs/`
- **Data**: `data/futures/`

If you encounter unexpected errors, **diagnose the root cause first**. Do not blindly retry commands. Check logs, verify IBKR connectivity, and ensure config YAMLs are strictly formatted.
