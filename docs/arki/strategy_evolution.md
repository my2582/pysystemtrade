# Strategy Evolution

## Version History

| Version | Date | Instruments | Sharpe | Return | MaxDD | Key Change |
|---|---|---|---|---|---|---|
| v1 (16-inst) | 2026-04-04 | 16 | 0.59 | 12.2% | -15.8% | Initial production config |
| v2 (micro) | 2026-04-04 | 16 | 0.62 | 12.2% | -16.0% | SP500→SP500_micro, GOLD→GOLD_micro |
| v2-db | 2026-04-05 | 16 | 0.62 | 12.2% | -16.0% | csvFuturesSimData → dbFuturesSimData |
| v3 (expanded) | 2026-04-05 | 25 | 0.84 | 20.7% | -14.9% | +9 instruments (Agri, FX, Equity) |
| **v4 (optimized)** | **2026-04-05** | **25** | **1.08** | **23.1%** | **-14.7%** | **Estimated IDM + forecast weights** |

## Config Files

```
scripts/backtest_config/
├── arki_production.yaml     ← v2 (16 instruments, fixed weights)
├── arki_v3_25inst.yaml      ← v3 (25 instruments, fixed IDM/FW)
├── arki_v4_optimized.yaml   ← v4 ★ CURRENT BEST
├── arki_optimal_7.yaml      ← Reference (optimizer 7-inst, SR 0.49)
├── arki_expanded.yaml       ← Experiment (47-inst, failed)
└── arki_expanded_v2.yaml    ← Experiment (35-inst, failed)
```

---

## Key Decisions

### Decision 1: Fixed Instrument Weights at $200K

**Problem**: With `use_instrument_weight_estimates: True`, pysystemtrade auto-removes instruments whose contract value exceeds capital capacity. At $200K, only 7 out of 47 instruments survived.

**Solution**: Keep `instrument_weights` explicitly fixed (equal weight 1/N), but let other parameters (IDM, forecast weights) be estimated.

**Result**: All 25 instruments remain active. Sharpe jumped from 0.50 (estimated) to 0.84 (fixed).

### Decision 2: 25-Instrument Universe (Not 7, Not 47)

**Context**: Greedy forward selection suggested 7 instruments as "optimal." But dynamic backtest showed 7-inst Sharpe = 0.49 vs 16-inst Sharpe = 0.62.

**Root cause**: Static optimizer maximizes subsystem-level SR, but diversification benefits at the portfolio level (via Mr. Greedy integer optimization) are much larger.

**Expansion criteria**: Contract value < $50K for "affordable," plus current-16 large-contract instruments that have proven to produce positions.

### Decision 3: Estimated IDM + Forecast Weights (v4)

**Rationale**: pysystemtrade can estimate these from historical correlations more accurately than manual fixed values.

| Parameter | v3 (fixed) | v4 (estimated) |
|---|---|---|
| IDM | 2.5 (manual guess) | Auto-calculated from instrument correlations |
| Forecast weights | Equal across 11 rules | Per-instrument optimal (some rules weighted higher for certain instruments) |
| Forecast div multiplier | Fixed | Auto-calculated |

**Result**: Sharpe 0.84 → 1.08 (+29%), volatility 24.6% → 21.3% (reduced!).

---

## Experiment Log

### Failed: 47-inst with Estimated Weights (Sharpe 0.50)

Config: `arki_expanded.yaml` — all 47 parquet instruments, `use_instrument_weight_estimates: True`.

Result: pysystemtrade assigned zero weight to 40 instruments. Only 7 active. Worse than 16-inst baseline.

Lesson: At $200K, estimated instrument weights are too aggressive in excluding instruments.

### Failed: 35-inst with Estimated Weights (Sharpe 0.50)

Config: `arki_expanded_v2.yaml` — curated 35 instruments (affordable + marginal + current-large).

Same result as 47-inst. Estimated weights killed diversity regardless of curation.

### Succeeded: 7-inst Static Selection

Tool: `scripts/static_instrument_selection.py --capital 200000`

Selected: NASDAQ_micro, DAX, COPPER-micro, CRUDE_W, GILT, BRENT-LAST, SILVER (in order).

Portfolio SR peaked at 8.17 (static, pre-cost) at 3 instruments, then declined. Useful as a diagnostic but not for production universe selection.
