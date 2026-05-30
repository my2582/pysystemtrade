# Handoff — Futures-native trade analyzer (port of b3-saa-etf trade-analysis pattern)

- **Date**: 2026-05-27
- **Origin**: written from a `b3-saa-etf` session (cross-project handoff to disk per Arki session discipline). The build itself belongs in a **pysystemtrade session** — run `/ars-read` first (pysystemtrade is an ARS project).
- **Owner decision (confirmed 2026-05-27)**: **Option B — futures-native port** (respect direction long/short, contract size, costs) **+ candles required**.
- **Goal**: a backtest **trade-by-trade analyzer** for pysystemtrade runs that produces a per-trade ledger, per-trade price/candle charts, perf metrics, and ARS bootstrap CIs — mirroring the *report pattern* of b3's Growth-sleeve analyzer, but built on pysystemtrade's continuous long/short futures data model.

---

## 1. Why the b3 script cannot be reused directly (it is a data-model problem, not a path problem)

The source template is the b3 analyzer:
`/Users/msyeom/Developer/b3-saa-etf/scripts/build_growth_v10_trade_analysis.py` (1,016 lines).

It was purpose-built for a **long-only, monthly, top-N, equal-weight ETF picker**. pysystemtrade is a **continuous-position, daily, long/short, variable-size futures** system. Four structural mismatches:

| Axis | b3 analyzer assumes | pysystemtrade reality |
|---|---|---|
| Frequency | month-end `asof`, monthly gap detection | daily positions (`rounded_positions.csv`, 1-day index) |
| Direction | long-only "picked / not picked" (binary) | positions are signed; **shorts present** (verified) |
| Sizing | equal-weight; a trade has no size | integer contracts, size varies continuously |
| Price source | ETF OHLC from `etf_price_fact.parquet` | futures: continuous adjusted (close only) **or** per-contract OHLC |

So "repoint the paths" is impossible. What ports is the **report/ledger/candle/ARS pattern**, not the script.

---

## 2. pysystemtrade data sources (inputs for the new analyzer)

Per-run output dir: `results/runs/<run_id>/` (example confirmed: `20260414_2214_test_fail`). Relevant files:

| File | Schema | Use |
|---|---|---|
| `config.yaml` | `capital`, `vol_target`, `mode: dynamic`, `instruments: [...]`, `config_file` | run metadata, capital base |
| `rounded_positions.csv` | index=date (daily), cols=instruments, values=signed int contracts (NaN before listing) | **trade extraction** (sign-episodes) |
| `notional_positions.csv` / `subsystem_positions.csv` | same shape, pre-rounding | optional size detail |
| `daily_returns.csv` | index=date, cols=instruments | per-instrument P&L series — **confirm % vs currency in-session** |
| `equity_curve.csv` | index=date, single col `0` = **cumulative P&L in currency** (starts ~0; NOT a 1.0 NAV) | portfolio NAV (see §6) |
| `turnover.csv` | `instrument, annualized_turnover` | cost/context |
| `spread_costs.csv` | `instrument, spread_points, cost_usd, cost_bps` | per-trade cost attribution |
| `stats.yaml` | capital, instruments, summary stats | header/context |

**Prices (for candles):**
- Continuous back-adjusted: `data/futures/adjusted_prices_csv/<INST>.csv` → `DATETIME, 0` — **single daily price column, no H/L**. This is the P&L basis. 252 instruments.
- True OHLC: `data/parquet_store/futures_contract_prices/<INST>#<YYYYMMNN>.parquet` → cols `OPEN, HIGH, LOW, FINAL, VOLUME` (`FINAL`=close), **per individual contract**.
- Roll calendars: `data/futures/roll_calendars_csv/<INST>.csv` — needed to pick the **active contract** per date when stitching per-contract OHLC.
- Instrument config / multipliers / point sizes: `data/futures/csvconfig/` (for price→currency P&L if computing price-based, instead of using native per-instrument P&L).

**Prefer pysystemtrade-native series over re-deriving** (ARS rule: "Preserve native engine outputs"). For per-trade P&L, prefer the engine's per-instrument account P&L over a hand-rolled `(exit−entry)×mult×contracts`.

---

## 3. Three design decisions (defaults recommended — confirm in-session)

### D1 — Trade definition under continuous sizing  ★ most fundamental
b3 defines a trade as a **contiguous holding** (consecutive month-end picks of one ticker). The faithful futures analog is the **sign-episode**:

> A *trade* in instrument *X* = a maximal run of consecutive days where `sign(position)` is constant and non-zero. It **opens** when the position crosses from 0 (or the opposite sign) into a sign, and **closes** when it returns to 0 or flips sign. A flip = close old trade + open new trade same day.

Per-trade attributes: `instrument, direction (long/short), entry_date, exit_date (or open), days_held, entry_contracts, avg_contracts, max_contracts, exit_contracts, realized_pnl, costs, return_on_capital`.

- **Recommended default: sign-episode.** Cleanest port of b3's "contiguous holding" + respects direction.
- Alternatives: (a) **fill-level** (one record per position delta — more granular, not what b3 does); (b) **sign-episode with a size-flat tolerance** (ignore tiny contract jitter). Dynamic-opt positions persist for long stretches, so episodes can span years — flag this is expected, not a bug.

### D2 — Candle basis (owner wants candles)
- **Recommended default: per-contract OHLC stitched via roll calendar.** Real bars; select active contract per `roll_calendars_csv`; mark roll dates (price gaps at rolls are expected). Overlay entry/exit markers + a position-size sub-panel.
- Fallback (simpler): **continuous adjusted-price line** + entry/exit markers + size sub-panel. No real H/L, but matches the P&L basis exactly and avoids roll artifacts.
- Note: a single futures trade (sign-episode) can roll across several contracts; the chart must either stitch (adjusted) for the line and show the active contract's bars, or segment by contract.

### D3 — ARS benchmark for paired-block bootstrap
b3 compared the sleeve NAV vs ACWI. Futures portfolio benchmark options:
- **Recommended default: vs zero (absolute)** — bootstrap CI on the strategy's own daily P&L returns (CAGR/Sharpe/MDD CIs without a paired comparator), since a futures CTA has no natural long-only index.
- Alternatives: vs **long-only equal-weight buy-and-hold** of the same instruments; vs a **60/40**; vs **risk-free**. If a paired comparator is chosen, keep b3's paired stationary block bootstrap intact.

---

## 4. Port map — what to reuse vs swap (from the b3 source)

Source: `/Users/msyeom/Developer/b3-saa-etf/scripts/build_growth_v10_trade_analysis.py`

| b3 piece (lines) | Action | Futures-native change |
|---|---|---|
| `prime_ohlc` / `load_cache_ohlc` (115–147) | **REPLACE** | load futures OHLC (contract parquet + roll calendar) or adjusted-price line |
| `next_trading_day` (149) | reuse | — |
| `Trade` dataclass (157–169) | **EXTEND** | add `direction`, `entry/avg/max/exit_contracts`, `realized_pnl`, `costs` |
| `build_trades` (171–276) | **REWRITE** | sign-episode extraction from `rounded_positions.csv` (daily), not month-end pick explode |
| `trades_to_df` (278–296) | extend | add direction/size/pnl/cost columns |
| perf metrics (300–373): `annualize_ret/vol`, `sharpe`, `max_drawdown`, `ulcer_index`, `calmar`, `sortino`, `horizon_skew`, `metrics_block` | **reuse verbatim** | operate on the portfolio NAV/return series |
| `paired_block_bootstrap` + `_ret_to_*` + `ars_verdict` (377–438) | **reuse** | benchmark per D3 |
| `render_candle` (442–520) | reuse as template | feed futures OHLC; add size sub-panel + direction shading per D2 |
| `render_equity_chart` (524–564) | reuse | NAV per §6 |
| HTML builders (566–844): `build_summary_html`, `build_table_html`, `build_candles_html`, `build_perf_html`, `build_ars_html` | **reuse (relabel)** | ETF→futures, "sleeve"→"strategy/portfolio", drop SGD block |
| SGD conversion (848–903): `load_monthly_usdsgd`, `write_sgd_equity_curve` | **DROP** | futures P&L is in account currency; SGD not relevant |
| `load_acwi_benchmark` (905–917) | **REPLACE** | per D3 |
| `main` (919–1016) | **REWRITE** | add CLI: `--run-dir results/runs/<id>`, `--candle-basis {contract,adjusted}`, `--benchmark {zero,buyhold,...}`, `--out` |

Constants to parameterize (b3 hard-codes these as module globals — do NOT hard-code in the port): run dir, NAV source, price source, analysis window, output dir, capital, bootstrap block/B/seed.

---

## 5. Trade P&L + cost computation
- **Prefer native**: pull per-instrument account P&L from pysystemtrade's `accountCurveGroup` (the engine already computes costed/uncosted curves). Sum over the episode window for `realized_pnl`.
- If price-based instead: `pnl = direction × (exit_price − entry_price) × point_value × contracts`, using continuous adjusted prices and `csvconfig` multipliers — but this double-counts rolls unless adjusted prices are used (they are roll-adjusted). Document whichever basis is chosen.
- **Costs**: attribute `spread_costs.csv` (cost_bps / cost_usd) × the episode's traded contracts; cross-check against `turnover.csv`. Report gross + net per trade.

## 6. Portfolio NAV construction (for equity chart + ARS)
`equity_curve.csv` is **cumulative P&L in currency starting at 0**, not a 1.0-indexed NAV. Build NAV as either:
- `NAV_t = (capital + cumulative_pnl_t) / capital` → 1.0-based index; **or**
- cumprod of the portfolio daily return series (from the engine's percent account curve — preferred, native).
Clip/anchor the analysis window via a CLI `--start` (b3 used a fixed `ANALYSIS_START`; here make it a flag, default = first day capital is deployed).

## 7. Outputs + placement (ARS)
- Report dir under pysystemtrade conventions, e.g. `results/runs/<run_id>/trade_analysis/` or `ars/runs/<run_id>_trade_analysis/`:
  - `trades.xlsx` — trade ledger (signed, sized, costed)
  - `trade_report.html` — self-contained (summary + table + per-trade candles + perf + ARS CI)
  - `candles/<trade_id>_<inst>.png`
  - `equity_curve.csv` — NAV (strategy [+ benchmark])
- Store decision-grade evidence under `ars/evidence_packs/` if this feeds a promotion decision. Run `/ars-evidence-pack` after.

## 8. ARS compliance gates (pysystemtrade is an ARS project)
1. `/ars-read` BEFORE coding (read arki-standards core + AI-agent governance + `ars/project_ars_profile.yaml`).
2. State assumptions; surgical changes; **do not silently change** data/universe/costs/seeds.
3. **Preserve native engine outputs** — read pysystemtrade's own account/position series; do not re-derive P&L if a native series exists.
4. No external market-data API calls.
5. New script lives alongside `scripts/strategy_audit.py` (e.g. `scripts/trade_analysis.py`). It is **additive** — `strategy_audit.py` does current-snapshot/signals; this does **historical per-trade ledger** (the gap it fills).

## 9. Acceptance criteria
- Trade ledger reconciles to `rounded_positions.csv`: every sign-episode is captured; Σ per-trade days = Σ days with nonzero position (per instrument).
- Σ per-trade realized P&L (net) reconciles to the portfolio `equity_curve.csv` end value (within rounding / unallocated cash).
- Each trade with ≥1 trading day renders a candle (or is explicitly listed as skipped with reason).
- ARS bootstrap reproduces (seed fixed) and verdicts render.
- HTML is self-contained (base64 images), opens standalone.

---

## 10. Recommended next prompt (in a pysystemtrade session)

```
/ars-read
Then implement scripts/trade_analysis.py per docs/arki/handoff_futures_trade_analyzer_2026-05-27.md.
Use D1=sign-episode, D2=contract-OHLC stitched, D3=vs-zero unless I say otherwise.
Target run: results/runs/<RUN_ID>. Reuse the b3 perf/ARS/HTML functions cited in the port map (§4).
```

## 11. Open items to confirm in-session
- `daily_returns.csv` units (% vs currency) — drives P&L reconciliation.
- Whether dynamic-opt episodes are acceptably long (years) or owner wants a size-change sub-segmentation (D1 alt b).
- Candle behavior across contract rolls (stitch vs segment).
- Benchmark choice (D3) if owner wants a paired comparator rather than absolute.
