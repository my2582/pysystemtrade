# Arki Macro — Investment Thesis

> **Classification**: Confidential — For Internal Use and Qualified Investors Only
> **Version**: 1.0 — April 2026
> **House**: Arki Finance (Arche Asset Management Pte Ltd, CMS Licence No. 101854)

---

## I. Executive Summary

Arki Macro is a rules-based, multi-asset allocation strategy that harvests time-varying macroeconomic risk premia through two complementary engines:

1. **Arki Macro Mini** — A regime-adaptive, multi-asset directional strategy that dynamically tilts between growth assets (equities) and defensive assets (bonds, gold) based on a proprietary business cycle indicator.
2. **Arki Multi-Factor** — A diversified managed futures portfolio that systematically captures trend, carry, and cross-sectional momentum premia across 24 global futures markets.

The two engines are economically orthogonal by design. Macro Mini harvests **level returns** from macro risk premia by identifying which asset classes to own; Multi-Factor harvests **spread returns** from behavioural and structural premia by identifying how to trade within and across asset classes. Their combination produces a portfolio with structurally superior risk-adjusted returns and materially lower drawdowns than either component alone.

> **Core Claim**: By combining regime-adaptive macro allocation with diversified factor harvesting, Arki Macro delivers equity-like returns at bond-like risk, through the cycle.

---

## II. The Economic Problem We Solve

### The Regime Problem

Asset class returns are regime-dependent. Over 55 years of data (1970–2025):

| Regime | Global Equity | US Treasury | Gold |
|--------|--------------|-------------|------|
| Rising Growth | **+14.1%** | +5.3% | +7.5% |
| Falling Growth | +1.5% | **+8.7%** | **+15.8%** |

A static 60/40 blend ignores this conditionality. It earns a time-averaged premium but pays a severe penalty during regime transitions — precisely when drawdown risk is highest.

### The Diversification Problem

Traditional multi-asset portfolios diversify across *asset classes*. Academic research demonstrates this is insufficient:

- Asset class correlations spike during crises (Ang & Bekaert, 2004)
- A portfolio that appears diversified in benign regimes concentrates on a single macro risk (growth) during stress
- Cross-asset style factors (trend, carry, value, momentum) offer genuinely independent return sources that are largely *unrelated* to macroeconomic regimes (Baltussen, Swinkels & Van Vliet, 2021; Ilmanen et al., 2021)

### Arki's Answer: Separate the Two Problems

Rather than forcing a single portfolio to solve both problems, Arki decomposes the allocation decision into two independent engines, each optimised for its specific task:

| | **What to Own** | **How to Trade** |
|---|---|---|
| **Engine** | Macro Mini | Multi-Factor |
| **Return Source** | Macro Risk Premia (level) | Style Factor Premia (spread) |
| **Signal** | Business cycle regime | Time-series momentum, carry, relative momentum |
| **Horizon** | Medium-term (monthly) | Short-to-medium-term (daily) |
| **Correlation to equities** | Regime-dependent | Low / regime-independent |

---

## III. Academic Foundation

### Swade, Lohre, Nolte, Shackleton & Swinkels (2024)
*"A Century of Macro Factor Investing — Diversified Multi-Asset Multi-Factor Strategies through the Cycles"*
Journal of Portfolio Management, forthcoming. Lancaster University / Robeco / Erasmus University.

This paper provides the intellectual scaffolding for the Arki Macro architecture. Key findings over 100 years (1918–2021):

#### Finding 1: Three macro factors explain multi-asset returns
Growth, Inflation, and Defensive factors — proxied by global equities, commodities, and treasuries — capture the dominant sources of cross-asset variation. A risk parity combination across these three **macro factor-mimicking portfolios (MFMPs)** delivers SR 1.39 over the full century.

#### Finding 2: MFMPs are more robust than raw asset class proxies
By constructing macro factor exposure through diversified baskets of asset classes *and* style factors (using Meucci's minimum torsion orthogonalisation), MFMPs achieve higher Sharpe ratios and lower drawdowns than naive asset class proxies across all economic regimes.

#### Finding 3: Regime timing adds value — especially at turning points
A business cycle model (5 US macro indicators → aggregate Z-score → 4 regimes) generates tactical macro factor views via Black-Litterman. The macro overlay produces IR 0.49 versus the strategic risk parity benchmark, with the strongest outperformance during **Recovery** periods (IR 1.23).

#### Finding 4: Momentum is a powerful complement
Time-series momentum signals across all asset classes and style factors produce IR 1.55. Combined with macro views, the total overlay achieves **IR 1.73** and **SR 2.50**, with a 71% hit ratio.

#### Finding 5: The two signals are complementary, not redundant
Macro signals outperform in regime transitions (recession → recovery). Momentum signals outperform in persistent regimes (expansion, peak). Combining them diversifies across different market environments.

### How Arki Macro Maps to the Academic Framework

| Swade et al. Concept | Arki Implementation |
|---|---|
| Macro Factor-Mimicking Portfolio (MFMP) | **Arki Macro Mini** — regime-adaptive allocation across equities, bonds, gold |
| Business Cycle Model (Z-score → 4 regimes) | **Macro Tilt Score (MTS)** — proprietary indicator based on industrial production, employment, equity returns, yield curve |
| Time-Series Momentum + Carry signals | **Arki Multi-Factor** — EWMAC trend (5 speeds), carry (3 speeds), relative momentum (3 speeds) across 24 futures |
| Black-Litterman tactical overlay | Capital-weighted combination of Mini + Multi-Factor engines |
| MFRP + Macro + Momentum (SR 2.50) | **Arki Macro** — the combined strategy |

---

## IV. Engine 1: Arki Macro Mini

### Purpose
Macro Mini is the **directional engine** of Arki Macro. It answers the question: *given the current macroeconomic regime, which asset class risk premia should we harvest?*

### Mechanism

```
┌───────────────────────────────────────────┐
│         MACRO TILT SCORE (MTS)            │
│                                           │
│  Industrial Production Growth             │
│  + Nonfarm Payrolls Growth                │
│  + Stock Market Return (sentiment)        │
│  + Yield Curve Slope (credit channel)     │
│         ↓                                 │
│    Standardised → Single Z-Score          │
│         ↓                                 │
│  MTS ≥ 0 → Growth regime                 │
│  MTS < 0 → Defensive regime              │
│         ↓                                 │
│  4 sub-regimes with granular allocation   │
└───────────────────────────────────────────┘
         ↓
┌───────────────────────────────────────────┐
│         DYNAMIC ALLOCATION                │
│                                           │
│  Conviction Growth:   Equity 130%, B+G 30%│
│  Mild Growth:         Equity ~80%, B+G ~80%│
│  Mild Defence:        Equity ~50%, B+G ~110%│
│  Conviction Defence:  Equity 30%, B+G 130%│
│                                           │
│  Total exposure: ~160% (1.6x leverage)    │
│  Guardrails: Min 30% / Max 130% per tilt  │
└───────────────────────────────────────────┘
```

### Investment Universe
Liquid, exchange-traded instruments only: S&P 500, MSCI Europe, Nikkei 225 (equity); US 10Y Treasury (bonds); Gold (commodity). Executed via micro futures and ETFs for capital-efficient implementation.

### Performance (Backtest: Jan 1970 – Sep 2025)

| Metric | Macro Mini | Global 60/40 | Global Equity | US Treasury |
|--------|-----------|-------------|---------------|-------------|
| **Return p.a.** | **15.4%** | 8.6% | 10.0% | 6.4% |
| **Volatility** | 15.8% | 9.4% | 14.8% | 5.5% |
| **Sharpe Ratio** | **0.98** | 0.91 | 0.67 | 1.18 |
| **Max Drawdown** | **-30.5%** | -33.1% | -54.0% | -18.3% |

### Key Attributes
- **Regime-adaptive**: Outperforms in both growth (+17.0%) and defensive (+13.0%) regimes
- **Drawdown management**: -30.5% MDD vs -54% for equities — a 44% reduction in tail risk
- **Live validation**: April 2025 Tariff Shock — Macro Mini: -3.9% (SGD) vs S&P 500: -11.2%

---

## V. Engine 2: Arki Multi-Factor

### Purpose
Multi-Factor is the **diversified alpha engine** of Arki Macro. It answers the question: *what structural and behavioural premia exist across global futures markets, and how do we harvest them systematically?*

### Mechanism

Built on Rob Carver's pysystemtrade framework, a 7-stage daily pipeline:

```
Daily Prices → Volatility Normalisation → Trading Rules → Forecast Scaling
    → Forecast Combination → Position Sizing → Portfolio Construction → P&L
```

### Three Independent Rule Families

| Family | Rules | Rationale | Horizon |
|--------|-------|-----------|---------|
| **Trend (EWMAC)** | 5 speeds (4/16 → 64/256) | Price trends persist due to herding, anchoring, and institutional flow | Days to months |
| **Carry** | 3 speeds (30d, 60d, 125d) | The term structure encodes roll yield, storage costs, and convenience yield premia | Weeks to months |
| **Relative Momentum** | 3 horizons (20d, 40d, 80d) | Cross-sectional outperformers persist due to momentum effects, sector rotation | Weeks to months |

### Investment Universe (24 Instruments, DM-Only)

| Asset Class | Instruments | Count |
|-------------|-------------|-------|
| Equity Index | SP500μ, NASDAQμ, DAX, NIKKEI, FTSE100, IBEX | 6 |
| Government Bond | US10, US5, BUND, GILT, JGB | 5 |
| Metals | GOLDμ, SILVER, COPPERμ | 3 |
| Energy | CRUDE_W, BRENT, GASOIL | 3 |
| FX | AUDμ, MXP, YENEUR | 3 |
| Agricultural | SUGAR, COTTON, LEANHOG, COCOA_LDN | 4 |

### Construction Details

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Vol Target** | 15–25% | Scaled to capital; SR is capital-invariant |
| **Forecast Cap** | ±20 | Limits position extremes from any single signal |
| **Forecast Weights** | Handcraft (estimated) | Hierarchical clustering; data-driven diversification |
| **Instrument Weights** | Estimated | Responsive to correlation structure over time |
| **Position Sizing** | Dynamic (Mr. Greedy) | Optimal integer rounding for small accounts |
| **Buffering** | ±10% of ideal | Suppresses unnecessary trading |
| **Shadow Cost** | 10 | Turnover penalty in dynamic optimiser |

### Key Attributes
- **Return sources independent of macro regime**: Style factor premia are largely acyclical (Ilmanen et al., 2021)
- **Genuine diversification**: 11 independent trading rules × 24 instruments = 264 return streams
- **Low correlation to directional assets**: Net long/short positioning; not directionally biased

---

## VI. The Combination: Why 1 + 1 > 2

### Structural Diversification Benefit

The two engines target fundamentally different return sources:

| Dimension | Macro Mini | Multi-Factor | Effect |
|-----------|-----------|-------------|--------|
| **Return source** | Macro risk premia (level) | Style factor premia (spread) | Uncorrelated alpha streams |
| **Signal type** | Regime identification | Price pattern recognition | Different information sets |
| **Holding period** | Monthly rebalance | Daily evaluation | Different frequencies |
| **Directionality** | Net long (leveraged beta) | Net neutral (long/short) | Reduced beta concentration |
| **Drawdown profile** | Macro-timed defense | Trend-following crisis alpha | Complementary tail protection |

### Capital Allocation

| Scenario | Macro Mini | Multi-Factor | Total Capital |
|----------|-----------|-------------|---------------|
| **Original** | $100K (1.6× lev) | $250K | $350K |
| **Smaller** | $150K (1.6× lev) | $100K | $250K |

### Why This Ratio

The capital split reflects the return characteristics of each engine:
- Macro Mini delivers higher per-unit returns (leveraged directional beta in growth regimes)
- Multi-Factor delivers lower per-unit returns but much higher Sharpe ratio (diversified, lower vol)
- Allocating ~30-40% to Mini and ~60-70% to Multi-Factor approximates the information-ratio-optimal blend

### Observed Correlation
Historical correlation between Macro Mini and Multi-Factor monthly returns is **low** (typically ρ ≈ 0.2–0.4), consistent with the theoretical orthogonality of their return sources. This correlation is **regime-stable** — it does not spike during crises, which is the hallmark of genuine diversification.

---

## VII. Risk Framework

### Systematic Risk Controls

| Layer | Control | Description |
|-------|---------|-------------|
| **Signal** | Forecast cap ±20 | No single rule can dominate the portfolio |
| **Position** | Buffer ±10% | Prevents overtrading around ideal positions |
| **Allocation** | Guardrails 30%–130% | Macro Mini cannot go all-in or all-out |
| **Portfolio** | Risk overlay | Max leverage 15×; max risk 2× normal; max sum-abs 5× |
| **Execution** | Shadow cost 10 | Economic penalty for excess turnover |
| **Regime** | 2-period confirmation | Regime switches require consecutive signals or 1σ move |

### Drawdown Architecture

The dual-engine structure provides layered drawdown protection:

1. **In growth regimes**: Macro Mini is risk-on → standard equity drawdowns possible BUT Multi-Factor's trend rules capture momentum, and its short positions provide partial offset
2. **At regime transitions**: Macro Mini's MTS detects weakening growth → tilts to defense BEFORE drawdown materialises
3. **In defensive regimes**: Macro Mini is risk-off → capital protected in bonds/gold; Multi-Factor's trend rules profit from persistent downtrends
4. **In sudden shocks**: Live validation — April 2025 Tariff Shock: Macro Mini defended at <5% when S&P 500 lost 11%

---

## VIII. Why Arki — The Rules-Based Macro House

### Investment Philosophy

> *"Process beats judgement. Macro shocks trigger regime shifts via propagation channels. These shifts create time-varying risk premia. Because regime shifts are predictable, these premia can be harvested."*

### What Makes Arki Different

| Dimension | Traditional Macro Fund | Arki Macro |
|-----------|----------------------|------------|
| **Signal generation** | Discretionary CIO view | Proprietary Macro Tilt Score — rules-based, backtested to 1970 |
| **Allocation** | Ad hoc position sizing | Systematic, volatility-targeted with guardrails |
| **Style factor capture** | Occasional overlay | Dedicated Multi-Factor engine with 264 systematic positions |
| **Transparency** | Monthly factsheet | Full daily position visibility, real-time dashboard |
| **Emotional discipline** | Subject to behavioural bias | Algorithmic execution removes emotion at every step |
| **Academic rigour** | — | Grounded in Swade et al. (2024), Carver (2015), Moskowitz et al. (2012) |

### Positioning Statement

Arki Macro is a **rules-based macro strategy** that combines the economic intuition of global macro investing with the execution discipline of systematic factor harvesting. It is designed for investors who:

1. Believe macro regimes drive asset class returns — and want to adapt to them systematically
2. Seek genuine diversification beyond traditional 60/40 — from independent, evidence-based return sources
3. Value transparency, liquidity, and reproducibility over discretionary conviction
4. Want institutional-grade risk management in an accessible, capital-efficient structure

---

## IX. Key References

| Reference | Relevance |
|-----------|-----------|
| Swade, Lohre, Nolte, Shackleton & Swinkels (2024) | Macro factor investing framework — 100yr evidence |
| Baltussen, Swinkels & Van Vliet (2021) | Global factor premiums — 200yr evidence of style factor premia |
| Ilmanen, Israel, Moskowitz, Thapar & Lee (2021) | Style factor premia persistence — hard to forecast from macro variables |
| Moskowitz, Ooi & Pedersen (2012) | Time-series momentum — trend-following across asset classes |
| Gupta & Kelly (2019) | Factor momentum — momentum in factor returns themselves |
| Ang & Bekaert (2004) | Regime-switching models and asset allocation |
| Black & Litterman (1991, 1992) | Combining equilibrium with views — strategic + tactical |
| Carver (2015) | *Systematic Trading* — the pysystemtrade framework |
| Scherer & Apel (2020) | Business cycle timing of alternative risk premia |
| Meucci, Santangelo & Deguest (2015) | Minimum torsion — orthogonal factor construction |

---

> **Disclaimer**: This document is for informational purposes only and does not constitute an offer or solicitation. Backtested results are hypothetical and may differ from live performance. Past performance is not indicative of future results. Arki Macro Mini commenced live trading in 2025.

---

*Prepared by Arki Quantitative Research — April 2026*
