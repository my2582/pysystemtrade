# Arki Dashboard: Strategy Research Upgrade Spec

**Purpose:** To upgrade the current `pysystemtrade` dashboard from a static "post-backtest viewer" into an interactive **Strategy Research Toolkit** capable of multi-dimensional attribution, parameter sweeps, and regime-based evaluation.

## 1. Architectural Strategy (Hybrid Compute Model)

To balance performance and interactivity, the dashboard will utilize a **Hybrid Compute Model**:
1. **Python Exporter (`backtest_runner.py`)**: Will calculate heavy statistical payloads, forecast convolutions, and regime classifications, outputting them as extended `.json/.csv` files.
2. **Javascript UI (`app.js`)**: Will act as the slicing, rendering, and filtering engine. It will not run portfolio mathematics, but it will allow real-time filtering of the dense JSON objects provided by python.

## 2. Python Backend Extensions (`backtest_runner.py`)

To support research capabilities, the `export_enhanced_data` method must be expanded to export three new dense datasets:

### A. Forecast X-Ray Dataset (`forecast_xray.json`)
The core problem in systematic trading is knowing "why did the system buy?".
We need a nested time-series dump for each instrument:
- Raw Trading Rule Signals (e.g., raw EWMA 32/128 crossover value)
- Standardized Forecasts (the unscaled -20 to +20 score)
- Clipped/Scaled Forecasts (after Forecast Cap is applied)
- Final Combined Forecast (After FCM estimates)
*Usage: This allows researchers to debug rule collision (e.g., when Carry is strongly long but Momentum is strongly short).*

### B. Factor Attribution Matrix (`factor_attribution.csv`)
Instead of just whole-portfolio returns, the system must export:
- Aggregate Portfolio PnL attributed strictly to **Yield/Carry** rules.
- Aggregate Portfolio PnL attributed strictly to **Trend/Momentum** rules.
- Aggregate Portfolio PnL attributed strictly to **Macro** rules.
*Usage: UI can plot which factor driver is generating outperformance under different macro regimes.*

### C. Parameter Stability / Sweep Profiler
In `stats.yaml` or a new `stability.json`, export not just the single chosen parameter path, but theoretical deviations:
- E.g., The system estimates a forecast weight of 30% for rule A. Python should export pre-calculated PnL vectors if that weight was rigidly set to 10% or 50%.
*Usage: Allows the dashboard to plot a 3D surface or line chart showing if the optimized parameter resides on a stable plateau or a brittle peak.*

### D. Buffer Drag (Execution Cost Isolation)
`pysystemtrade` maintains a strict buffering module to suppress excessive trading. We need to export:
- `Optimal Position` (what the pure math wants)
- `Actual Buffered Position` (what is actually sent inside `account_buffering_*`)
*Usage: A Quant can calculate the "Buffer Drag" (the PnL left on the table by delaying trades) versus the "Saved Spread Costs". This answers the age-old question: "Are my buffers too wide?"*

### E. Correlation Diversification Identifiers (FCM & IDM)
The core of Rob Carver's scaling is accounting for correlations. We must export:
- **Forecast Correlation Multiplier (FCM):** (`system.combForecast.get_forecast_diversification_multiplier`)
- **Instrument Diversification Multiplier (IDM):** (`system.portfolio.get_instrument_diversification_multiplier`)
*Usage: An IDM time-series directly works as a "Market Crisis Indicator". When the IDM violently compresses, it proves that all portfolio assets have suddenly become positively correlated. The dashboard must overlay IDM on top of Portfolio Drawdowns to diagnose if a loss was purely due to an IDM shock.*

### F. Return Volatility & Risk Parity Diagnostics
Instead of merely exporting `factor_returns.csv`, export **Rolling Volatility by Rule and Instrument**.
*Usage: The premise of the entire system is Risk Parity (Vol Targeting). By plotting the rolling standard deviation of "Momentum PnL" vs "Carry PnL", a Quant can instantly verify if the Volatility Target is holding true, or if extreme fat tails are breaking the parity model.*

## 3. UI Dashboard Additions (`dashboard/`)

### UI Tab 1: "Signal & Forecast Analyzer"
**Target:** Replace black-box position sizing with transparent signal tracking.
- **Component:** A master line chart spanning a specific instrument's history.
- **Interactivity:** A dropdown selects the instrument. Toggles allow overlaying the Raw Price, the Final Position Size, and the individual Rule Forecasts.
- **Value:** Researchers can visually pinpoint exactly when a Trading Rule degraded, or when a Forecast Cap forced the system to flatten a position.

### UI Tab 2: "Factor & Regime Attribution"
**Target:** Understand *when* the strategy makes money.
- **Component:** A stacked bar chart dissecting monthly/yearly Returns by Factor (Carry vs Trend).
- **Component:** An integration with Arki Macro Regime Indicators (Conviction Growth, Mild Defense, etc.). Python tags the regime of each month; JS displays the Sharpe Ratio of the *System under each Regime*.
- **Value:** Prevents the assumption that a strategy is "all weather" when it actually relies entirely on "Conviction Growth" environments.

### UI Tab 3: "Parameter Sensitivity Playground"
**Target:** Visual stress-testing of weights and scalars.
- **Component:** A "Tornado Chart" or sensitivity matrix. X-axis is Sharp Ratio. Y-axis lists different system config variations (e.g., Vol Target = 15, 20, 25; Slow Vol Proportion = 10%, 35%, 50%).
- **Interactivity:** Based on the static payloads dumped by Python, the user can click options to see the immediate effect on the Equity Curve.

## 4. Execution Roadmap (Next Steps)

1. **Phase 1: Factor Attribution Export.** Modify `backtest_runner.py` to extract and group PnL vectors by rule type.
2. **Phase 2: Forecast X-Ray Export.** Tap into `system.rules` to export raw signals vs. combined forecasts.
3. **Phase 3: JS Dashboard Wiring.** Build the D3/Chart.js models to ingest these dense files.
4. **Phase 4: Regime Tagging.** Integrate external Macro Regime data into the PnL evaluation loop.
