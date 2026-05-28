# Strategy Spec — Single-Position Momentum Rotation (`absmom_rotation`)

**Status**: DRAFT v0.3 · **Date**: 2026-05-27 · **Author**: AI Ops (Claude) + owner
**ARS**: profile `pysystemtrade` (engine frozen, adapter+evidence role, `live_trading: false`, max AI decision level 2)
**Distinct from**: macro-mini (dm37/full24 — diversified 24-37 instrument continuous-position blend). This strategy holds **exactly one futures position at a time**, sized to a vol target.

> **v0.2 change-log**: architecture corrected — *no deliberate go-flat/cash state*. Always hold top-1, size contracts to hit 30% vol, residual capital = cash (margined-futures normal). Min capital → $50k. Signal v1 = research **both** native EWMAC-rank and academic dual-momentum. Absolute-filter threshold = research item.
> **v0.3 change-log**: vol/min-cap corrected to engine `mixed_vol_calc` on price diffs (prior `pct_change` numbers were artifacts of negative back-adjusted prices). **Data-currency found to be the binding universe constraint**: only 5 of 21 candidates are current (rest frozen 2024-03-28). IBEX_mini reinstated (not a glitch). Fuller pool needs a data-refresh prerequisite.

---

## 1. Objective & honest success criteria

Build a small-AUM, single-position momentum strategy that each week ranks a filtered mini/micro futures universe and **always holds the single strongest-momentum instrument**, sized to a 30% annualized vol target.

> ⚠️ **Reality anchor** (`references/research/2026-05-27-single-instrument-futures-momentum.md`): single-/rotational-position trend SR is structurally limited (~0.24 fixed-single → ~0.3–0.4 pseudo-diversified). The research's "0.7–1.0" claim is an unverified model estimate (0 citations) and contradicts Carver's empirics. We do **not** target 0.7–1.0.

**Success criteria (v1, full-sample + OOS):**
| Metric | Target | Rationale |
|---|---|---|
| Net Sharpe | ≥ 0.40 | realistic ceiling for single-position rotation |
| vs buy&hold (selected index) | higher Sharpe **and** lower MDD | rotation + vol-target must beat passive |
| vs fixed-single (ablation) | higher Sharpe | rotation must beat picking one instrument |
| Max Drawdown | materially < buy&hold | vol-targeting + rotation away from losers is the tail control |
| Executability @ $50k | ≥ 90% | integer-contract feasibility |
| Turnover | within 2× spread-cost budget | weekly rebalance keeps modest |

**Non-goal**: beating macro-mini on Sharpe. Macro-mini is the diversification reference, not the bar.

---

## 2. Locked parameters (owner-confirmed)

- **Target volatility**: **30% annualized, fixed.** Position sizing = adjust **integer contract count** of the held instrument to hit 30% vol; **unused capital sits in cash** (no go-flat state).
- **Holding**: **exactly 1 instrument**, always invested in the top-ranked. (No regime-off / no deliberate cash allocation.)
- **Rebalance**: **fixed weekly** (v1). Extensible to daily→weekly later (param, not redesign).
- **Min trading capital**: **$50k** (confirmed) — supports multi-contract granularity for the cheapest-vol USD instruments.

### Universe — **data-currency is the binding constraint**
Filter: name contains `mini`/`micro`, **exclude** FX, Oil&Gas, mainland-China, must have adjusted-price data → 21 survivors. **But only 5 have CURRENT data**; the other 16 are frozen at **2024-03-28** (not in the production backfill universe). A momentum rotation requires *aligned, current* series — stale instruments cannot be ranked on "current" momentum.

**Currently-tradeable rotation pool (5):**
| Asset | Instrument | Eng AnnVol (config `mixed_vol_calc`) |
|---|---|---|
| Equity | SP500_micro | 13.0% |
| Equity | NASDAQ_micro | 14.9% |
| Equity | IBEX_mini | 22.5% |
| Metals | GOLD_micro | 32.6% |
| Metals | COPPER-micro | 30.5% |

⚠️ **Thin-pool risk (top universe risk)**: 3 of 5 are equity indices (SP500/NASDAQ/IBEX — highly correlated) → little cross-sectional dispersion; real diversification only from GOLD/COPPER. A 5-name rotation with 3 correlated legs weakens the rotation premise.

**To reach the fuller ~12-instrument pool** (DOW/RUSSELL/AEX/KOSPI_mini, JGB-mini, CORN/WHEAT_mini, ALUMINIUM; GOLD-mini/COPPER-mini/JGB-SGX-mini are dedupes of the micro/primary contracts): refresh via `update_prices`/backfill **iff** those contracts are in the IB backfill universe — a **data-pipeline prerequisite (own task)**, not assumed.

**Corrected exclusions**: the earlier 348–534% annvol for IBEX/SOYBEAN was a **vol-calc artifact** (`pct_change` on additively back-adjusted prices that cross zero), NOT a data glitch. Correct vol uses **price diffs** (engine `mixed_vol_calc`). → IBEX_mini is fine & current → **included**. Still excluded: VIX_mini (mean-reversion), HANG_mini (China), ETHER-micro/ALUMINIUM_LME (short history) — all also stale anyway.

### Min capital (engine-method vol, 30% target)
**Meaning**: "30% vol basis, 1-contract min" = the capital at which a 30%-vol-targeted single position equals exactly 1 contract. Below it, 1 contract overshoots 30% vol; ~4× gives usable integer granularity.
`MinCap_local = pointsize × dailyDiffVol × √256 / 0.30` (price cancels; `dailyDiffVol` from engine `mixed_vol_calc` on **price diffs** → additive-adjustment-safe).
| Instrument | 1-ctr | 4-ctr | contracts @ $50k |
|---|---|---|---|
| SP500_micro | $13.6k | $54.5k | 3.7 ✓ |
| NASDAQ_micro | $21.2k | $84.8k | 2.4 |
| COPPER-micro | $10.8k | $43.1k | 4.6 ✓ |
| GOLD_micro | $39.9k | $159.6k | **1.3 (coarse)** |
| IBEX_mini | €9.4k | €37.4k | (EUR) ~5 |

At **$50k**: SP500/COPPER/IBEX get good 3–5 contract granularity; NASDAQ marginal (2.4); **GOLD_micro coarse (~1 contract)** → 1↔2 rounding is a large vol jump (executability caveat). Metals vols (GOLD 32.6%, COPPER 30.5%) are regime-elevated (2025–26).

### Minimum account size — definition (owner criterion)
The min account is **not** "1 contract = 30% vol per instrument." It is set so that vol-targeting lands in a workable integer range (**≥1, ideally 1–4 contracts**) for every tradeable instrument. Binding variable = **dollar-vol per contract** `DV = (multiplier × price) × %vol` — **not %vol alone** (a high-%vol but small-notional contract can still be cheap; a low-%vol large-notional contract — e.g. GOLD_micro — is the expensive one). The **binding instrument = max DV**.

`MinAccount(≥k contracts, all) = k × max_i(DV_i / 0.30)`. Current 5-pool (GOLD_micro binds):
| granularity | all 5 (GOLD binds) | excl. GOLD (NASDAQ binds) |
|---|---|---|
| ≥1 ctr (floor; <1 ⇒ vol overshoot) | $40k | $21k |
| ≥2 ctr | $80k | $42k |
| ≥3 ctr | $120k | $64k |
| **≥4 ctr (30% ±~12% rounding)** | **$160k** | **$85k** |

Caveats: (1) vol is time-varying — GOLD 32.6% is a 2025–26 high-vol regime (normal ~15% ⇒ ~half the MinCap); min account should be set against a **stressed/high vol** since a vol spike *reduces* N toward the <1 overshoot zone. (2) single-position ⇒ the held instrument's granularity *is* the whole-strategy granularity for that period.

**Implication for $50k**: insufficient for ≥4-ctr on GOLD_micro. Options: (a) raise min account ($160k all-5, or $85k excl. GOLD); (b) drop/deprioritize GOLD_micro (→ $50k covers the rest at 2.4–5 ctr); (c) keep $50k + a **`min_contracts` parameter**: if an instrument's vol-target N < `min_contracts` (e.g. 1), it is **excluded from selection that week** (refuse to hold what can't meet the 30% target) — preferred, makes the rule self-policing.

---

## 3. Signal — research BOTH standard implementations (v1 deliverable)

Owner directive: explore the **standard/canonical implementation** of each, then A/B empirically. Research note → `references/strategy/2026-05-27_signal_implementation_research.md`.

**Candidate A — pysystemtrade-native EWMAC ranking (max reuse).**
- Score per instrument = combined EWMAC forecast (multi-speed blend, vol-normalized, capped ±20) — already produced by the engine; cross-sectionally comparable.
- Native cross-sectional rule `systems.provided.rules.rel_mom.relative_momentum` is the in-repo precedent (used in macro-mini). Research: how to turn forecasts into a **rank → select top-1**.

**Candidate B — academic dual-momentum (3/6/12M).**
- Canonical time-series/relative momentum (Moskowitz-Ooi-Pedersen TSMOM; Antonacci dual-momentum): rank by blended 3/6/12-month vol-adjusted total return.
- Research: standard lookback construction, vol-adjustment, and how to implement as a pysystemtrade rule vs `src/` layer.

**Direction & absolute filter (RESEARCH — §7.4):** with no default go-flat, v1 holds the highest-*relative*-ranked instrument always. Whether an **absolute-momentum overlay** (e.g. reduce size / deviate when top-1's own trend ≤ threshold) improves risk-adjusted return — and the threshold (score > 0 vs whipsaw buffer) — is an **open empirical research question**, not a v1 default.

---

## 4. pysystemtrade integration (reuse the toolkit)

Standard `System` holds **all** instruments continuously → cannot express single-position rotation. Therefore:

- **NEW** `src/arki_strategies/absmom_rotation.py`: consumes the engine's per-instrument **forecast + vol + prices + costs**, applies weekly rank → select top-1 → **30%-vol integer sizing**, and **emits the standard run artifacts** (`stats.yaml`, `daily_returns.csv`, `position_snapshot.csv`, `dashboard_meta.json`) into `results/runs/<id>/`.
- **REUSE unchanged**: `update_prices` (data), `optimize_universe` (capital→pool sanity), `get_run_summary`, `generate_dashboard` (read emitted artifacts).
- **EXTEND**: add runner subcommand / MCP tool `run_rotation_backtest` (parallel to `run_backtest`); rotation-aware `run_strategy_audit` (1-position invariant, vol-target sanity).
- **Core pysystemtrade: untouched.** `src/` added to `sys.path` via runner entrypoint (no engine edit).

---

## 5. Validation plan

- **Windows**: full sample + OOS split (pre-2015 / post-2015); per-instrument history honored (no look-ahead on short-history names).
- **Benchmarks**: (1) buy&hold of most-selected instrument, (2) fixed-single momentum (ablation), (3) macro-mini (diversification reference).
- **Cost sensitivity**: 1× / 2× spread cost; report turnover.
- **Regime breakdown**: GFC '08, COVID '20, 2022 selloff.
- **Signal A vs B**: head-to-head on all the above.
- **Outputs**: run → `ars/runs/`; decision-grade comparison → `ars/evidence_packs/`.

## 6. Risks (single-position, irreducible)
- Fat-tail DD 30–50% even with vol target (no diversification cushion; no cash backstop in v1 default).
- Always-long-top-1 can be long the "least-bad" instrument in a broad downturn → motivates the §3 absolute-filter research.
- Regime dependence concentrated in whichever instrument is held.
- Overfit risk on signal/lookback/threshold → keep params few, validate OOS.

---

## 7. Open decisions for owner (redline before Step 2 code)
1. **Rotation pool** — given only **5 instruments are current** (§2), choose: (a) build v1 on the thin 5-name pool now, or (b) first run a **data-refresh prerequisite** (expand IB backfill universe → `update_prices`) to reach the ~12-name pool, then build. Thin-pool dispersion risk vs time-to-first-result tradeoff.
2. **Signal v1** — confirmed: research **both** A (native EWMAC-rank) and B (dual-momentum 3/6/12M), A/B empirically. ✅
3. **Min capital** — **$50k** confirmed. ✅
4. **Absolute filter / direction** — confirmed as **research item** (threshold score>0 vs whipsaw buffer; whether to add at all). ✅
