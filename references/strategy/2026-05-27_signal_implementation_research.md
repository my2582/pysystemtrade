# Signal Implementation Research — `absmom_rotation` v1

**Date**: 2026-05-27 · **Feeds**: [spec v0.2](2026-05-27_absmom_rotation_spec.md) §3 · **For**: owner directive "EWMAC-native 랭킹 + 학술 dual-momentum 둘 다 표준 구현법 탐색; 절대필터 임계 실연구"

Sources: in-repo pysystemtrade code; `references/research/Design and analysis of momentum trading strategies.pdf` (Martin 2023, 31p, time-series/trend theory); `references/research/Enhanced Momentum Strategies.pdf` (Hanauer & Windmüller 2022, 67p, cross-sectional **equity** momentum). **Citations as (Martin pX)/(Hanauer pX). "GK" = canonical general knowledge, NOT in the provided PDFs.**

---

## 0. TL;DR decisions
1. **No native top-N in pysystemtrade.** The mis-named `relative_momentum` rule is cross-sectional *mean-reversion*; `cs_mr.py` likewise. We build the cross-sectional rank ourselves in `src/`.
2. **Ranking score (Signal A)** = engine's combined EWMAC forecast (vol-normalized, capped ±20 → cross-sectionally comparable). Rank → `argmax` → top-1.
3. **Signal B** = academic blended momentum: rank by vol-adjusted trailing return over blended lookbacks. Note: 3/6/12 *blend* and Antonacci dual-momentum are **GK, not in the PDFs**.
4. **Sizing (both)** = vol-target `position ∝ φ/σ̂`, our σ_target = 30% — this is the sourced cMOM/Barroso recipe (Hanauer p10 eq.2-3; Martin p4).
5. **Absolute filter** = use a **dead-zone buffer**, not a hard `>0`. Sourced: Martin's whipsaw analysis (p22-23) favors ε≈0.6 in vol-normalized units; hard sign-flips churn in chop.
6. **Top-1 single-asset selection is unsourced** — literature is decile/quintile portfolios. We implement a degenerate `argmax` + deterministic tie-break.

---

## 1. In-repo reality (what the engine gives natively)
- `systems/provided/rules/rel_mom.py::relative_momentum` — docstring "Cross sectional **mean reversion** within asset class"; signals the *change* in outperformance vs asset-class average. Buys laggards, not leaders → **wrong sign for our momentum rank**. (Used by macro-mini as a diversifying reversion sleeve.)
- `systems/provided/rules/cs_mr.py`, `_TO_DELETE_OLD.py` — also cross-sectional mean reversion.
- `systems/forecast_scale_cap.py` cross-sectional code — only for forecast-scalar estimation, not selection.
- `systems/provided/rules/ewmac.py` — the EWMAC trend rule; its **combined, scaled, capped forecast** is the natural per-instrument momentum score (already vol-normalized → comparable across instruments).
- **Conclusion**: no rank/top-N/selection stage exists. The `src/` layer consumes per-instrument forecasts (or trailing returns) and does the cross-sectional selection + vol-target sizing, emitting standard run artifacts.

---

## 2. Signal A — pysystemtrade-native EWMAC ranking (max reuse)
**Standard recipe (GK + engine):**
1. Per instrument, compute the EWMAC combined forecast `f_i` for the chosen speeds (e.g. (8,32),(16,64),(32,128)) via the engine's rules + forecast scaling (target abs avg 10, cap ±20). These are vol-normalized → cross-sectionally comparable.
2. Weekly: rank instruments by `f_i`; candidate = `argmax_i f_i`.
3. Hold candidate, sized to 30% vol (§4); residual = cash.
4. (Optional overlay, §5) deviate only if candidate `f` inside dead-zone.

*Why this is the canonical engineering form:* Martin shows the EMA-difference ("EMA2"/MACD) on vol-normalized returns is the preferred finite-path trend signal (lower turnover than EMA1) (Martin p7-8) — EWMAC is exactly EMA2. Sizing `φ/σ̂` is his core rule (Martin p4).

## 3. Signal B — academic blended momentum
**Sourced pieces:**
- Cross-sectional formation window: **12−2 month** trailing return (skip last month), the Jegadeesh-Titman standard (Hanauer p7,p9).
- Excess returns over 1-month T-bill (Hanauer p8).
- Vol-normalized return base: `U = ΔX/σ̂`, σ̂ = 20-day EMA of squared changes (Martin p4 eq.1, p11).

**General knowledge (NOT in PDFs — flagged):**
- **3/6/12-month blend**: no multi-lookback blend in either paper. Sourced precedent for combining is **signal-level summation** (Martin p7 eq.4: `φ = Σ_j a_j U`), i.e. average the vol-normalized signals then rank once on the composite. Rank-/z-score-averaging is GK.
- **Antonacci dual momentum** (relative rank + absolute vs T-bill): entirely GK, not sourced.

**Standard recipe B (implementable):**
1. For L ∈ {63, 126, 252} trading days (≈3/6/12M), compute vol-adjusted trailing return `r_i,L / σ_i`.
2. Composite score `s_i = mean_L(z(r_i,L/σ_i))` (signal-level averaging per Martin precedent).
3. Weekly rank → `argmax`; size to 30% vol.

## 4. Position sizing (both signals — sourced)
- Constant-vol target: `weight = σ_target / σ̂_t` (Hanauer cMOM p10 eq.2-4: `σ̂² = 21·Σ_{j=1}^{126} R²/126`, i.e. 6-month daily realized vol annualized). Our σ_target = **30%**.
- Single futures position in contracts = `(capital × 0.30) / (σ_inst_annual_price × multiplier × fx)`, integer-rounded (Mr.Greedy logic). Residual capital = cash.
- **cMOM evidence** (US): Sharpe 0.47→0.87, MaxDD −69.1%→−38.6%, skew −2.18→−0.32 (Hanauer Table 2, p35). Strong support that vol-targeting (which we already do) is the single biggest momentum enhancement.

## 5. Absolute-momentum filter / whipsaw — research conclusion
Owner flagged "score>0 vs buffer = 실연구". Findings:
- **Hard `>0` / `sgn(z)` is explicitly discouraged** (Martin p22-23): a ±1 flip buys-and-dumps in non-trending markets, killing P&L and skew.
- **Sourced preference = dead-zone buffer**: trade/hold only when `|z| > ε`; ε≈0.6 (vol-normalized units) gave positive skew with no Sharpe loss; ε≳1.5 trades too rarely (Martin p22-23, p27).
- **More sophisticated overlay = dMOM bear-state down-weight** (Hanauer p11-12 eq.6-7): scale `∝ μ̂_t/σ̂²_t`, with bear indicator `I_Bear=1` if cumulative past-**24-month** market return < 0; can even go negative. US Sharpe 0.91, MaxDD −40.1%.
- **Recommendation**: v1 default = always-invested top-1 (per owner). Test as overlays: (i) dead-zone ε on the top-1 score, (ii) dMOM-style bear down-weight. A T-bill absolute threshold (Antonacci) is GK; test only as a third variant.

## 6. Recommended v1 build & A/B matrix
| Variant | Rank score | Absolute overlay | Sizing |
|---|---|---|---|
| A0 (baseline) | EWMAC combined forecast | none (always top-1) | 30% vol |
| A1 | EWMAC combined forecast | dead-zone ε (≈0.6) | 30% vol |
| B0 | blended 3/6/12M vol-adj return | none | 30% vol |
| B1 | blended 3/6/12M | dead-zone ε | 30% vol |
| (v2) | best of above | dMOM bear down-weight | dynamic |

A/B all on the §5 validation plan (full + OOS, cost 1×/2×, regime breakdown, vs buy&hold / fixed-single / macro-mini).

## 7. Honest gaps (unsourced — do not overclaim)
- Single-asset **top-1 selection**: no literature; degenerate argmax + deterministic tie-break (e.g. higher recent realized Sharpe, then fixed instrument priority). GK.
- **3/6/12 blend** weighting recipe: GK (signal-level averaging is the closest sourced analog).
- **Antonacci dual-momentum / T-bill absolute filter**: GK.
- 12-month "canonical TSMOM lookback": the often-cited claim is from Moskowitz-Ooi-Pedersen, **not** in these PDFs — do not cite these PDFs for it.
