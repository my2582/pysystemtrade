# Finding — asset-class universe sweep

Status: **settled finding** (2026-04-07). Source:
[`../../../docs/arki/universe_sweep_report.md`](../../../docs/arki/universe_sweep_report.md) (bilingual;
summarised here in English).

**Question:** which asset-class combination maximises risk-adjusted return *and* skew for the diversified
CTA, holding Equity (7) + Bond (5) fixed and varying Ags (4) / FX (3) / Metals (3) / OilGas (3)?

**Method:** dynamic backtest of fixed subsets with `use_instrument_weight_estimates: True` (engine selects
weights); compare Sharpe, max drawdown, and skew.

**Results (Sharpe-sorted, top of table):**
- v4 Production (25, equal-weight): **SR 1.081**, vol 21.3%, skew +0.02.
- v6 Handcraft (25): **SR 1.056**, vol 22.9%, **skew +0.08** (the only positive-skew universe).
- Ags+FX+Metals, no OilGas (22): SR 0.942.
- Base, Equity+Bond only (12): SR 0.460, **skew −1.25** (severe left tail).

**Conclusions (settled):**
1. **Keep ≥25 instruments.** Cutting the universe worsens both Sharpe *and* skew sharply.
2. **Keep OilGas.** Removing the 3 oil/gas contracts costs ≈ −0.114 SR (25→22).
3. **Ags is the strongest diversifier** (+0.276 SR over base); Metals synergise with Ags; FX overlaps Ags.
4. **Handcraft weighting** is preferred for its positive skew (tail protection).
5. Expansion to 30+ is worth exploring (instrument-count ↔ SR positively correlated) — the direction the
   **dm37** 37-instrument candidate takes ([../system/lineage.md](../system/lineage.md)).
