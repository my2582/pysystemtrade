#!/usr/bin/env python3
"""
Arki Futures Trade Analyzer
───────────────────────────
Per-trade ledger + per-trade candle charts + performance metrics + ARS
bootstrap confidence intervals for a pysystemtrade backtest run.

This is the futures-native port of the b3-saa-etf Growth-sleeve trade analyzer
(`build_growth_v10_trade_analysis.py`). The *report pattern* is reused; the data
model is rebuilt for pysystemtrade's continuous, daily, long/short, variable-size
futures runs. See docs/arki/handoff_futures_trade_analyzer_2026-05-27.md.

It is ADDITIVE to scripts/strategy_audit.py: that script does a current-snapshot /
signal decomposition off a live System; this one does a historical per-trade
ledger off committed run artifacts (results/runs/<run_id>/). The core engine is
not touched and no live System is built.

Design decisions (owner-confirmed 2026-05-27):
  D1  Trade = sign-episode: a maximal run of consecutive days with constant,
      non-zero sign in rounded_positions.csv. Opens on 0/opposite→sign; closes on
      sign→0 ('flat'), sign→opposite ('flip', same-day close+open), or runs to the
      last available date ('open').
  D2  Candle basis = per-contract OHLC stitched via the roll calendar, WHERE
      coverage exists; trades whose window has no contract parquet / roll calendar
      are listed as skipped with a reason. (Per-contract parquet is recent-only and
      roll calendars are stale for many instruments, so full-history bars are not
      available — this is expected, not a bug.)
  D3  Benchmark = vs zero (absolute): block-bootstrap CI on the strategy's own
      daily returns (no paired comparator); a metric is "significant" when its CI
      excludes 0.

P&L basis (ARS — preserve native engine outputs):
  daily_returns.csv holds per-instrument daily returns in PERCENT of capital. The
  portfolio daily return is the row-sum across instruments, and equity_curve.csv is
  their cumulative arithmetic sum (verified to reconcile at ~1e-12). This is the
  native, fixed-capital, NON-compounding account curve. We therefore:
    • report per-trade realized P&L as the sum of the instrument's native daily
      returns over the trade (shift-attributed: the return at day t is earned by the
      position held into t), so Σ per-trade P&L reconciles to equity_curve.csv up to
      a small flat-day settlement/cost residual that is reported explicitly;
    • compute perf metrics on the additive fixed-capital basis (so the equity curve
      and drawdown match the engine), and PRESERVE stats.yaml verbatim alongside.
  No price-derived (exit−entry)×mult×contracts P&L is used.

Usage:
  python scripts/trade_analysis.py 20260414_0130_dm37_1m_v25
  python scripts/trade_analysis.py --run-dir results/runs/<id> --top-n 50
  python scripts/trade_analysis.py <id> --candle-basis adjusted --out results/runs/<id>/trade_analysis

Outputs (default results/runs/<run_id>/trade_analysis/):
  trades.xlsx               signed/sized/costed per-trade ledger (all episodes)
  trade_report.html         self-contained report (summary + ledger + perf + ARS + candles)
  equity_curve.csv          portfolio NAV (additive native basis) + cumulative % P&L
  candles/<id>_<inst>.png   per-trade candle charts (top-N by |realized P&L|)
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── futures data roots ────────────────────────────────────────────────────────
ADJ_DIR = PROJECT_ROOT / "data/futures/adjusted_prices_csv"
CONTRACT_DIR = PROJECT_ROOT / "data/parquet_store/futures_contract_prices"
ROLLCAL_DIR = PROJECT_ROOT / "data/futures/roll_calendars_csv"
INSTR_CONFIG = PROJECT_ROOT / "data/futures/csvconfig/instrumentconfig.csv"
RUNS_DIR = PROJECT_ROOT / "results/runs"

PPY = 252  # trading days / year


# ════════════════════════════════════════════════════════════════════════════
# 1. Run-artifact loading
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class RunData:
    run_id: str
    run_dir: Path
    config: dict
    capital: float
    instruments: list[str]
    positions: pd.DataFrame      # rounded_positions: index=date, cols=inst, signed int
    returns: pd.DataFrame        # daily_returns: index=date, cols=inst, PERCENT of capital
    equity_curve: pd.Series      # cumulative % P&L (== returns.sum(axis=1).cumsum())
    turnover: pd.DataFrame
    spread_costs: pd.DataFrame
    stats: dict                  # stats.yaml (native engine stats, preserved verbatim)


def _read_csv_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df


def load_run(run_arg: str) -> RunData:
    """Resolve a run id or a run dir path and load the committed artifacts."""
    p = Path(run_arg)
    run_dir = p if p.is_dir() else (RUNS_DIR / run_arg)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run dir not found: {run_dir}")
    run_dir = run_dir.resolve()

    config = yaml.safe_load((run_dir / "config.yaml").read_text())
    stats = yaml.safe_load((run_dir / "stats.yaml").read_text())
    capital = float(config["capital"])
    instruments = list(config["instruments"])

    positions = _read_csv_dated(run_dir / "rounded_positions.csv")
    returns = _read_csv_dated(run_dir / "daily_returns.csv")

    eq = pd.read_csv(run_dir / "equity_curve.csv", index_col=0)
    eq.index = pd.to_datetime(eq.index)
    equity_curve = eq.iloc[:, 0].rename("cum_pnl_pct")

    turnover = pd.read_csv(run_dir / "turnover.csv")
    spread_costs = pd.read_csv(run_dir / "spread_costs.csv")

    return RunData(
        run_id=config.get("run_id", run_dir.name),
        run_dir=run_dir,
        config=config,
        capital=capital,
        instruments=instruments,
        positions=positions,
        returns=returns,
        equity_curve=equity_curve,
        turnover=turnover,
        spread_costs=spread_costs,
        stats=stats,
    )


# ════════════════════════════════════════════════════════════════════════════
# 2. Sign-episode trade extraction (D1)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Trade:
    trade_id: int
    instrument: str
    direction: str               # 'long' | 'short'
    entry_date: pd.Timestamp     # first day the position is held
    exit_date: pd.Timestamp      # settle day (first flat/flip day) or last date if open
    exit_reason: str             # 'flat' | 'flip' | 'open'
    days_held: int               # number of trading days the position was non-zero
    entry_contracts: int
    avg_contracts: float
    max_contracts: int
    exit_contracts: int
    realized_pnl_pct: float      # native: Σ daily_returns over the trade (% of capital)
    realized_pnl_usd: float      # realized_pnl_pct/100 * capital
    entry_price: float           # continuous adjusted price at entry (illustrative)
    exit_price: float            # continuous adjusted price at exit  (illustrative)
    est_cost_usd: float          # diagnostic only; native P&L is already net of costs
    _epid: int = field(default=-1, repr=False)


def _episode_ids(sign: pd.Series) -> pd.Series:
    """Episode id per day for a sign series; NaN on flat (sign==0) days.

    An episode starts on each day where the sign changes to a new non-zero value.
    """
    new_ep = (sign != sign.shift(1)) & (sign != 0)
    epid = new_ep.cumsum()
    return epid.where(sign != 0)


def build_trades(run: RunData, adj_prices: dict[str, pd.Series]) -> tuple[list[Trade], dict]:
    """Extract every sign-episode across all instruments as a Trade.

    Per-trade realized P&L is shift-attributed: the daily return at day t is earned
    by the position held INTO day t (i.e. the prior day's position). This makes the
    sum over all trades reconcile to the portfolio return up to the flat-day residual
    (returns on days when no position was held, e.g. post-exit settlement / costs).
    """
    cost_usd = run.spread_costs.set_index("instrument")["cost_usd"].to_dict()
    trades: list[Trade] = []
    diag = {"sum_pnl_pct": 0.0, "sum_days_held": 0, "nonzero_cells": 0}

    for inst in run.positions.columns:
        pos = run.positions[inst].fillna(0.0)
        sign = np.sign(pos)
        epid = _episode_ids(sign)
        diag["nonzero_cells"] += int((sign != 0).sum())

        ret = run.returns[inst].reindex(pos.index).fillna(0.0) if inst in run.returns.columns \
            else pd.Series(0.0, index=pos.index)
        # return at t is earned by the episode that held into t (prior-day position)
        earn_ep = epid.shift(1)
        pnl_by_ep = ret.groupby(earn_ep).sum()

        adj = adj_prices.get(inst)
        last_date = pos.index[-1]

        for ep, ep_days in pos[sign != 0].groupby(epid[sign != 0]):
            ep_dates = ep_days.index
            entry_date = ep_dates[0]
            last_held = ep_dates[-1]
            contracts = ep_days.abs()
            direction = "long" if ep_days.iloc[0] > 0 else "short"

            # exit/settle day = first day after the last held day (where return tail lands)
            after = pos.index[pos.index > last_held]
            if len(after) == 0:
                exit_date, exit_reason = last_held, "open"
            else:
                exit_date = after[0]
                nxt_sign = sign.loc[exit_date]
                if last_held == last_date:
                    exit_reason = "open"
                elif nxt_sign == 0:
                    exit_reason = "flat"
                else:
                    exit_reason = "flip"

            pnl_pct = float(pnl_by_ep.get(ep, 0.0))
            ec = int(round(abs(ep_days.iloc[0])))
            xc = int(round(abs(ep_days.iloc[-1])))
            trades.append(Trade(
                trade_id=-1,
                instrument=inst,
                direction=direction,
                entry_date=entry_date,
                exit_date=exit_date,
                exit_reason=exit_reason,
                days_held=int(len(ep_dates)),
                entry_contracts=ec,
                avg_contracts=float(contracts.mean()),
                max_contracts=int(round(contracts.max())),
                exit_contracts=xc,
                realized_pnl_pct=pnl_pct,
                realized_pnl_usd=pnl_pct / 100.0 * run.capital,
                entry_price=_price_at(adj, entry_date),
                exit_price=_price_at(adj, exit_date),
                est_cost_usd=(ec + xc) * float(cost_usd.get(inst, 0.0)),
                _epid=int(ep),
            ))
            diag["sum_days_held"] += int(len(ep_dates))
            diag["sum_pnl_pct"] += pnl_pct

    trades.sort(key=lambda t: (t.entry_date, t.instrument))
    for i, t in enumerate(trades, start=1):
        t.trade_id = i
    return trades, diag


def _price_at(adj: pd.Series | None, date: pd.Timestamp) -> float:
    if adj is None or adj.empty:
        return float("nan")
    sub = adj[adj.index <= date]
    return float(sub.iloc[-1]) if len(sub) else float("nan")


def trades_to_df(trades: list[Trade]) -> pd.DataFrame:
    rows = []
    for t in trades:
        rows.append({
            "trade_id": t.trade_id,
            "instrument": t.instrument,
            "direction": t.direction,
            "entry_date": t.entry_date.date(),
            "exit_date": t.exit_date.date(),
            "exit_reason": t.exit_reason,
            "days_held": t.days_held,
            "entry_contracts": t.entry_contracts,
            "avg_contracts": round(t.avg_contracts, 2),
            "max_contracts": t.max_contracts,
            "exit_contracts": t.exit_contracts,
            "entry_price": round(t.entry_price, 4) if pd.notna(t.entry_price) else None,
            "exit_price": round(t.exit_price, 4) if pd.notna(t.exit_price) else None,
            "realized_pnl_pct": round(t.realized_pnl_pct, 5),
            "realized_pnl_usd": round(t.realized_pnl_usd, 2),
            "est_cost_usd": round(t.est_cost_usd, 2),
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════════════════
# 3. Performance metrics  (b3 pure-return functions reused verbatim;
#    assembled on the engine's additive fixed-capital basis)
# ════════════════════════════════════════════════════════════════════════════

def annualize_vol(daily_ret: pd.Series, ppy: int = PPY) -> float:
    return float(daily_ret.dropna().std(ddof=1) * np.sqrt(ppy))


def sharpe(daily_ret: pd.Series, ppy: int = PPY) -> float:
    sd = daily_ret.dropna()
    if sd.empty or sd.std(ddof=1) == 0:
        return float("nan")
    return float(sd.mean() / sd.std(ddof=1) * np.sqrt(ppy))


def sortino(daily_ret: pd.Series, ppy: int = PPY) -> float:
    r = daily_ret.dropna()
    if r.empty:
        return float("nan")
    downside = r[r < 0].std(ddof=1)
    if downside == 0 or pd.isna(downside):
        return float("nan")
    return float(r.mean() / downside * np.sqrt(ppy))


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1.0).min())


def ulcer_index(nav: pd.Series) -> float:
    dd_pct = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt((dd_pct ** 2).mean()))


def additive_nav(daily_ret: pd.Series) -> pd.Series:
    """Engine-native NAV: fixed-capital, non-compounding (1 + cumulative return)."""
    return 1.0 + daily_ret.fillna(0.0).cumsum()


def horizon_skew(daily_ret: pd.Series, horizon_td: int = 20) -> tuple[float, int]:
    r = daily_ret.dropna()
    if len(r) < horizon_td * 2:
        return float("nan"), 0
    blocks = r.groupby(np.arange(len(r)) // horizon_td).sum()
    if len(blocks) < 3:
        return float("nan"), 0
    return float(blocks.skew()), int(blocks.size)


def metrics_block(daily_ret: pd.Series) -> dict:
    """Perf block on the additive fixed-capital basis (matches the engine).

    Annualized return is the ARITHMETIC mean × ppy (the engine's ann_mean
    convention for a non-compounding account curve), not a compounding CAGR.
    """
    r = daily_ret.dropna()
    nav = additive_nav(r)
    ann_ret = float(r.mean() * PPY)
    mdd = max_drawdown(nav)
    sk20, n_sk = horizon_skew(r, 20)
    return {
        "AnnRet_arith": ann_ret,
        "Vol": annualize_vol(r),
        "Sharpe": sharpe(r),
        "Sortino": sortino(r),
        "MDD": mdd,
        "Calmar": (ann_ret / abs(mdd)) if mdd != 0 else float("nan"),
        "Ulcer": ulcer_index(nav),
        "Skew_20TD": sk20,
        "Skew_20TD_n_obs": n_sk,
        "n_days": int(r.size),
        "start": r.index[0].date() if r.size else None,
        "end": r.index[-1].date() if r.size else None,
    }


# ════════════════════════════════════════════════════════════════════════════
# 4. ARS block-bootstrap CI  (D3 = vs zero / absolute)
# ════════════════════════════════════════════════════════════════════════════

def _ret_to_annmean(r: pd.Series, ppy: int = PPY) -> float:
    return float(r.mean() * ppy) if r.size else float("nan")


def _ret_to_sharpe(r: pd.Series, ppy: int = PPY) -> float:
    if r.empty or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(ppy))


def _ret_to_mdd(r: pd.Series) -> float:
    nav = 1.0 + r.cumsum()  # additive, to match the engine basis
    return float((nav / nav.cummax() - 1.0).min())


def block_bootstrap_ci(
    ret: pd.Series, metric_fn, block: int, B: int, seed: int,
) -> tuple[float, float, float, float, float]:
    """Stationary-block bootstrap CI for a single-series metric (vs-zero comparator).

    Returns (point, lo95, hi95, lo99, hi99). The point estimate is the metric on the
    full series; the CI is the [0.5,99.5]/[2.5,97.5] quantiles of the bootstrapped
    metric distribution. Reproducible given `seed`.
    """
    a = ret.dropna().values
    n = len(a)
    point = metric_fn(pd.Series(a)) if n else float("nan")
    if n < block * 4:
        return point, float("nan"), float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts_pool = np.arange(0, n - block + 1)
    vals = np.empty(B)
    for k in range(B):
        starts = rng.choice(starts_pool, size=n_blocks, replace=True)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        vals[k] = metric_fn(pd.Series(a[idx]))
    lo95, hi95 = np.nanquantile(vals, [0.025, 0.975])
    lo99, hi99 = np.nanquantile(vals, [0.005, 0.995])
    return float(point), float(lo95), float(hi95), float(lo99), float(hi99)


def ars_verdict_abs(lo95: float, hi95: float, lo99: float, hi99: float) -> str:
    """Absolute (vs-zero) significance: does the CI exclude 0 on the positive side?"""
    if any(np.isnan(x) for x in (lo95, hi95, lo99, hi99)):
        return "n/a"
    if lo99 > 0:
        return "Strict 99"
    if lo95 > 0:
        return "Strict 95"
    if hi95 < 0:
        return "Negative"
    return "Inconclusive"


# ════════════════════════════════════════════════════════════════════════════
# 5. Price loading (continuous adjusted line + per-contract OHLC via roll calendar)
# ════════════════════════════════════════════════════════════════════════════

def load_adjusted(inst: str) -> pd.Series | None:
    f = ADJ_DIR / f"{inst}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    # header varies across files: first col = DATETIME, last col = price ('price' or '0')
    s = pd.Series(
        pd.to_numeric(df.iloc[:, -1], errors="coerce").values,
        index=pd.to_datetime(df.iloc[:, 0]).dt.normalize(),
    ).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


def load_roll_calendar(inst: str) -> pd.DataFrame | None:
    f = ROLLCAL_DIR / f"{inst}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["DATE_TIME"]).dt.normalize()
    return df.sort_values("date").reset_index(drop=True)


def _contract_path(inst: str, contract) -> Path:
    return CONTRACT_DIR / f"{inst}#{int(contract):08d}.parquet"


def load_contract_ohlc(inst: str, contract) -> pd.DataFrame | None:
    f = _contract_path(inst, contract)
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.rename(columns={"OPEN": "open", "HIGH": "high", "LOW": "low", "FINAL": "close"})
    return df[["open", "high", "low", "close"]].dropna(subset=["close"])


def stitch_contract_ohlc(
    inst: str, start: pd.Timestamp, end: pd.Timestamp, roll: pd.DataFrame,
) -> tuple[pd.DataFrame | None, list[pd.Timestamp]]:
    """Stitch per-contract OHLC over [start, end] using the roll calendar.

    The held contract for a date d is the current_contract of the earliest roll row
    whose roll date >= d (held until that roll); for dates beyond the last roll the
    held contract is the last next_contract. Returns (stitched_ohlc, roll_boundaries)
    or (None, []) if no contract parquet covers the window.
    """
    rdates = roll["date"].values
    segs: list[pd.DataFrame] = []
    boundaries: list[pd.Timestamp] = []
    cur = start
    while cur <= end:
        pos = np.searchsorted(rdates, np.datetime64(cur), side="left")
        if pos < len(roll):
            contract = roll["current_contract"].iloc[pos]
            seg_end = min(end, roll["date"].iloc[pos])
        else:
            contract = roll["next_contract"].iloc[-1]
            seg_end = end
        ohlc = load_contract_ohlc(inst, contract)
        if ohlc is not None:
            seg = ohlc.loc[(ohlc.index >= cur) & (ohlc.index <= seg_end)]
            if not seg.empty:
                if segs:
                    boundaries.append(seg.index[0])
                segs.append(seg)
        nxt = roll["date"].iloc[pos] if pos < len(roll) else seg_end
        cur = (nxt if nxt > cur else seg_end) + pd.Timedelta(days=1)
    if not segs:
        return None, []
    out = pd.concat(segs)
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out, boundaries


# ════════════════════════════════════════════════════════════════════════════
# 6. Candle chart (contract OHLC bars + entry/exit markers + position sub-panel)
# ════════════════════════════════════════════════════════════════════════════

def render_candle(
    trade: Trade, run: RunData, candle_dir: Path, basis: str,
    adj: pd.Series | None, roll: pd.DataFrame | None, pad_td: int = 63,
) -> tuple[str | None, str]:
    """Render one trade's candle chart. Returns (base64_uri | None, status)."""
    pos = run.positions[trade.instrument].fillna(0.0)
    idx = pos.index
    try:
        i0 = idx.get_indexer([trade.entry_date])[0]
        i1 = idx.get_indexer([trade.exit_date])[0]
    except Exception:
        return None, "date_not_in_index"
    lo = idx[max(0, i0 - pad_td)]
    hi = idx[min(len(idx) - 1, i1 + pad_td)]

    # basis selection: contract OHLC where it covers the window, else adjusted line.
    ohlc, boundaries, line, used_basis = None, [], None, None
    if basis == "contract" and roll is not None:
        ohlc, boundaries = stitch_contract_ohlc(trade.instrument, lo, hi, roll)
        if ohlc is not None and not ohlc.empty:
            used_basis = "contract"
    if used_basis is None:  # adjusted-price line (explicit basis, or contract fallback)
        if adj is None:
            return None, "no_price"
        line = adj[(adj.index >= lo) & (adj.index <= hi)]
        if line.empty:
            return None, "no_price_in_window"
        used_basis = "adjusted" if basis == "adjusted" else "adjusted_fallback"

    fig, (ax, axp) = plt.subplots(
        2, 1, figsize=(11, 6.2), dpi=100, sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    if used_basis == "contract":
        win = ohlc
        xpos = {d: i for i, d in enumerate(win.index)}
        for i, (_, row) in enumerate(win.iterrows()):
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            up = c >= o
            col = "#7bc88a" if up else "#e5887e"
            ax.vlines(i, l, h, color=col, linewidth=0.8, alpha=0.85)
            ax.add_patch(Rectangle((i - 0.32, min(o, c)), 0.64,
                                   max(abs(c - o), (h - l) * 0.01) or 1e-9,
                                   facecolor=col, edgecolor=col, linewidth=0.4, alpha=0.85))
        for b in boundaries:
            if b in xpos:
                ax.axvline(xpos[b], color="#8957e5", alpha=0.45, linewidth=0.9, linestyle="--")
        ax.set_ylabel("Price (raw per-contract OHLC)")
        win_index = win.index
    else:
        win_index = line.index
        xpos = {d: i for i, d in enumerate(win_index)}
        ax.plot(np.arange(len(line)), line.values, color="#1f6feb", linewidth=1.0)
        lbl = "Price (continuous back-adjusted"
        ax.set_ylabel(lbl + "; contract OHLC unavailable)" if used_basis == "adjusted_fallback"
                      else lbl + ")")

    # entry / exit markers (place on price at that date; nearest available)
    def _xy(date):
        if date in xpos:
            xi = xpos[date]
        else:
            prior = [d for d in win_index if d <= date]
            if not prior:
                return None
            xi = xpos[prior[-1]]
        if used_basis == "contract":
            y = float(ohlc.iloc[xi]["close"])
        else:
            y = float(line.iloc[xi])
        return xi, y

    e = _xy(trade.entry_date)
    if e:
        entry_marker = "^" if trade.direction == "long" else "v"   # Long ↑, Short ↓
        ax.scatter([e[0]], [e[1]], marker=entry_marker, s=260, facecolor="#00d4ff",
                   edgecolor="black", linewidths=1.6, zorder=10,
                   label=f"ENTRY {trade.entry_date.date()} ({trade.direction.upper()})")
    x = _xy(trade.exit_date)
    if x:
        ax.scatter([x[0]], [x[1]], marker="o", s=200, facecolor="#ff2d75",
                   edgecolor="black", linewidths=1.6, zorder=10,
                   label=f"EXIT {trade.exit_date.date()} ({trade.exit_reason})")

    title = (f"#{trade.trade_id:04d}  {trade.instrument}  {trade.direction.upper()}  "
             f"{trade.entry_date.date()}→{trade.exit_date.date()} ({trade.exit_reason})  "
             f"held={trade.days_held}d  contracts {trade.entry_contracts}→{trade.exit_contracts} "
             f"(max {trade.max_contracts})  P&L={trade.realized_pnl_pct:+.4f}% "
             f"(${trade.realized_pnl_usd:+,.0f})")
    ax.set_title(title, fontsize=9)
    ax.grid(True, alpha=0.25, linewidth=0.4)
    ax.legend(loc="best", fontsize=8, framealpha=0.9)

    # position-size sub-panel (signed contracts over the window)
    win_pos = pos.loc[win_index] if len(win_index) else pos.iloc[0:0]
    color = "#1a7f37" if trade.direction == "long" else "#cf222e"
    axp.fill_between(np.arange(len(win_pos)), win_pos.values, 0,
                     step="post", color=color, alpha=0.35)
    axp.axhline(0, color="#57606a", linewidth=0.6)
    axp.set_ylabel("Contracts\n(signed)")
    axp.grid(True, alpha=0.25, linewidth=0.4)
    step = max(1, len(win_index) // 10)
    axp.set_xticks(np.arange(len(win_index))[::step])
    axp.set_xticklabels([d.strftime("%Y-%m-%d") for d in win_index[::step]],
                        rotation=30, ha="right", fontsize=8)

    fig.tight_layout()
    out_path = candle_dir / f"trade_{trade.trade_id:04d}_{trade.instrument}.png"
    fig.savefig(out_path)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), used_basis


def render_equity_chart(equity_pct: pd.Series) -> str:
    """Native equity curve (cumulative % P&L) + drawdown on the additive NAV."""
    s = equity_pct.dropna()
    nav = 1.0 + s / 100.0
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 6.0), dpi=120, sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    ax.plot(s.index, s.values, color="#1f6feb", linewidth=1.0,
            label="Cumulative P&L (% of capital, native equity_curve.csv)")
    ax.set_ylabel("Cumulative % P&L")
    ax.grid(True, alpha=0.25, linewidth=0.4)
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Portfolio equity curve (engine-native additive basis) & drawdown", fontsize=11)
    dd = (nav / nav.cummax() - 1.0) * 100.0
    ax2.fill_between(dd.index, dd.values, 0, color="#cf222e", alpha=0.35, label="Drawdown")
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(True, alpha=0.25, linewidth=0.4)
    ax2.legend(loc="lower left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ════════════════════════════════════════════════════════════════════════════
# 7. HTML report
# ════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{run_id} — Futures Trade Analysis</title>
<style>
 body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
        color:#1f2328; margin:28px; max-width:1240px; }}
 h1 {{ font-size:22px; border-bottom:1px solid #d0d7de; padding-bottom:6px; }}
 h2 {{ font-size:16px; margin-top:28px; border-bottom:1px solid #eaeef2; padding-bottom:4px; }}
 table {{ border-collapse:collapse; font-size:11px; width:100%; }}
 th,td {{ border:1px solid #d0d7de; padding:4px 6px; text-align:right; }}
 th {{ background:#f6f8fa; }}
 td.txt {{ text-align:left; }}
 .spec-box {{ background:#fff8e1; border:1px solid #d9a441; border-radius:6px; padding:12px 16px; margin:12px 0 20px; }}
 .spec-box .row {{ margin:6px 0; font-size:12px; line-height:1.5; }}
 .meta {{ font-size:11px; color:#57606a; margin-bottom:6px; }}
 code {{ background:#f6f8fa; padding:1px 4px; border-radius:3px; font-size:11px; }}
 .pos {{ color:#1a7f37; }} .neg {{ color:#cf222e; }}
 .trade-block {{ margin:12px 0 22px; padding:8px 10px; border:1px solid #d0d7de; border-radius:6px; }}
 .trade-block h3 {{ margin:0 0 6px; font-size:13px; }}
 .trade-block img {{ width:100%; max-width:1100px; }}
 .equity-chart img {{ width:100%; max-width:1200px; }}
 .v-strict99 {{ color:#1a7f37; font-weight:600; }} .v-strict95 {{ color:#1a7f37; }}
 .v-incon {{ color:#9a6700; }} .v-neg {{ color:#cf222e; }}
</style></head><body>
<h1>{run_id} — Futures Trade Analysis &amp; Performance</h1>
<p class="meta">
Generated {gen_date} · Engine: pysystemtrade (mode <code>{mode}</code>, {n_inst} instruments, capital
<code>${capital:,.0f}</code>, vol target {vol_target}%) · Config <code>{config_file}</code> ·
P&amp;L basis: <strong>native daily_returns.csv</strong> (percent of capital; portfolio = row-sum;
equity_curve.csv = cumulative sum, reconciled to {recon_eps:.1e}) ·
Trade def (D1): <strong>sign-episode</strong> · Candle basis (D2): <strong>{candle_basis}</strong> ·
Benchmark (D3): <strong>vs zero (absolute)</strong>.
</p>

<div class="spec-box">
<div class="row"><strong>Trade (sign-episode):</strong> a maximal run of consecutive days with constant,
non-zero sign in <code>rounded_positions.csv</code>. Opens on 0/opposite→sign; closes on sign→0
(<code>flat</code>), sign→opposite (<code>flip</code>, same-day close+open), or runs to the last available
date (<code>open</code>). Realized P&amp;L = sum of the instrument's native daily returns over the trade
(shift-attributed: the return on day <em>t</em> is earned by the position held into <em>t</em>).</div>
<div class="row"><strong>Performance basis:</strong> the engine account curve is fixed-capital and
NON-compounding, so annualized return is the arithmetic mean × {ppy} (the engine's <code>ann_mean</code>
convention), and drawdown/Ulcer use the additive NAV (1 + cumulative return). The native
<code>stats.yaml</code> is preserved verbatim in §3a. ARS analytics in §3b/§4 are recomputed from
<code>daily_returns.csv</code> on the same additive basis.</div>
<div class="row"><strong>ARS (vs zero):</strong> stationary block bootstrap (block={boot_block} TD,
B={boot_b}, seed={seed}) on the strategy's own daily returns. A metric is significant when its
bootstrap CI excludes 0 on the positive side.</div>
</div>

<h2>1. Summary</h2>
{summary_html}

<h2>2. Portfolio equity curve &amp; drawdown (engine-native)</h2>
<div class="equity-chart"><img src="{eq_chart}" alt="equity curve"/></div>
<p class="meta">Reconciliation — Σ per-trade realized P&amp;L = {sum_pnl:+.4f}% of capital;
equity_curve.csv end = {eq_end:+.4f}%; unattributed flat-day residual (post-exit settlement / costs on
days with no open position) = {resid:+.4f}% ({resid_frac:+.3f}% of end value). The portfolio return
series used for §2–§4 reconciles to equity_curve.csv exactly.</p>

<h2>3a. Native engine stats (<code>stats.yaml</code>, preserved verbatim)</h2>
{native_html}

<h2>3b. ARS-recomputed performance (additive fixed-capital basis)</h2>
{perf_html}

<h2>4. ARS confidence intervals — vs zero (block bootstrap, block={boot_block} TD, B={boot_b})</h2>
{ars_html}

<h2>5. Trade ledger ({n_trades} trades — full ledger in trades.xlsx)</h2>
{table_note}
{table_html}

<h2>6. Per-trade candle charts — top {n_candles} by |realized P&amp;L| ({candle_basis} basis)</h2>
<p class="meta">Cyan ▲ = entry, magenta ▼ = exit. Lower panel = signed contract position over the window
(green long / red short). Purple dashed = contract roll. Realized P&amp;L in the title is the native
(net) account-curve P&amp;L; prices are illustrative.</p>
{skipped_html}
{candles_html}
</body></html>
"""


def build_summary_html(df: pd.DataFrame, run: RunData) -> str:
    n = len(df)
    n_long = int((df["direction"] == "long").sum())
    n_short = int((df["direction"] == "short").sum())
    n_open = int((df["exit_reason"] == "open").sum())
    n_flip = int((df["exit_reason"] == "flip").sum())
    n_flat = int((df["exit_reason"] == "flat").sum())
    r = df["realized_pnl_pct"].dropna()
    win = (r > 0).mean() * 100 if len(r) else float("nan")
    gl = (r[r > 0].mean() / abs(r[r < 0].mean())) if (r < 0).any() and (r > 0).any() else float("nan")
    rows = [
        ("trades total", f"{n}"),
        ("&nbsp;&nbsp;long / short", f"{n_long} / {n_short}"),
        ("&nbsp;&nbsp;closed flat / flip / open", f"{n_flat} / {n_flip} / {n_open}"),
        ("median days held", f"{df['days_held'].median():.0f}"),
        ("mean days held", f"{df['days_held'].mean():.1f}"),
        ("max days held", f"{df['days_held'].max():.0f}"),
        ("realized P&L per trade — mean (%)", f"{r.mean():+.4f}"),
        ("&nbsp;&nbsp;median (%)", f"{r.median():+.4f}"),
        ("&nbsp;&nbsp;std (%)", f"{r.std(ddof=1):.4f}"),
        ("&nbsp;&nbsp;skew", f"{r.skew():+.3f}"),
        ("&nbsp;&nbsp;min / max (%)", f"{r.min():+.4f} / {r.max():+.4f}"),
        ("win rate (%)", f"{win:.1f}"),
        ("gain/loss ratio (mean+ / |mean−|)", f"{gl:.3f}"),
        ("Σ realized P&L (% of capital)", f"{r.sum():+.4f}"),
        ("Σ realized P&L (USD)", f"${df['realized_pnl_usd'].sum():+,.0f}"),
    ]
    body = "".join(f"<tr><td class='txt'>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f"<table><tr><th>metric</th><th>value</th></tr>{body}</table>"


def build_native_html(stats: dict) -> str:
    body = "".join(
        f"<tr><td class='txt'>{k}</td><td>{v}</td></tr>"
        for k, v in stats.get("stats", {}).items()
    )
    extra = (f"<tr><td class='txt'>period</td><td>{stats.get('period','')}</td></tr>"
             f"<tr><td class='txt'>years</td><td>{stats.get('years','')}</td></tr>")
    return ("<p class='meta'>Authoritative engine output — reported exactly as written by the run; "
            "not recomputed.</p>"
            f"<table><tr><th>stat</th><th>value</th></tr>{body}{extra}</table>")


def build_perf_html(rows: list[tuple[str, dict]]) -> str:
    order = ["AnnRet_arith", "Vol", "Sharpe", "Sortino", "MDD", "Calmar", "Ulcer",
             "Skew_20TD", "Skew_20TD_n_obs", "n_days", "start", "end"]
    hdr = "<th>metric</th>" + "".join(f"<th>{name}</th>" for name, _ in rows)
    body = []
    for m in order:
        cells = [f"<td class='txt'>{m}</td>"]
        for _, d in rows:
            v = d[m]
            if isinstance(v, float):
                if m in ("AnnRet_arith", "Vol", "MDD"):
                    cells.append(f"<td>{v*100:+.2f}%</td>" if m != "Vol" else f"<td>{v*100:.2f}%</td>")
                else:
                    cells.append(f"<td>{v:.3f}</td>")
            else:
                cells.append(f"<td>{v}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return "<table><thead><tr>" + hdr + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def build_ars_html(ret: pd.Series, block: int, B: int, seed: int) -> str:
    specs = [
        ("Annualized return (arith)", _ret_to_annmean, True),
        ("Sharpe", _ret_to_sharpe, True),
        ("Max drawdown", _ret_to_mdd, False),
    ]
    cls = {"Strict 99": "v-strict99", "Strict 95": "v-strict95",
           "Inconclusive": "v-incon", "Negative": "v-neg", "n/a": "v-incon"}
    body = []
    for name, fn, higher in specs:
        pt, l95, h95, l99, h99 = block_bootstrap_ci(ret, fn, block, B, seed)
        if name == "Max drawdown":
            verdict = "n/a (absolute)"
            vc = "v-incon"
        else:
            verdict = ars_verdict_abs(l95, h95, l99, h99)
            vc = cls.get(verdict, "")
        body.append(
            f"<tr><td class='txt'>{name}</td><td>{pt:+.4f}</td>"
            f"<td>[{l95:+.4f}, {h95:+.4f}]</td><td>[{l99:+.4f}, {h99:+.4f}]</td>"
            f"<td class='{vc}'>{verdict}</td></tr>")
    return ("<p class='meta'>vs-zero (absolute): point estimate on the full series; CI from the "
            "block-bootstrap distribution. Significant when the CI excludes 0 on the positive side. "
            "Drawdown is reported for information only (no vs-zero test).</p>"
            "<table><thead><tr><th>metric</th><th>point</th><th>95% CI</th><th>99% CI</th>"
            "<th>verdict</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>")


def build_table_html(df: pd.DataFrame, limit: int) -> tuple[str, str]:
    cols = ["trade_id", "instrument", "direction", "entry_date", "exit_date", "exit_reason",
            "days_held", "entry_contracts", "max_contracts", "exit_contracts",
            "realized_pnl_pct", "realized_pnl_usd"]
    show = df.reindex(df["realized_pnl_pct"].abs().sort_values(ascending=False).index).head(limit)
    note = (f"<p class='meta'>Showing the {len(show)} trades with the largest |realized P&amp;L| "
            f"(of {len(df)} total); full ledger in trades.xlsx.</p>") if len(df) > limit else ""
    hdr = "".join(f"<th>{c}</th>" for c in cols)
    rows = []
    for _, r in show.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in ("realized_pnl_pct", "realized_pnl_usd") and pd.notna(v):
                kls = "pos" if v > 0 else ("neg" if v < 0 else "")
                cells.append(f"<td class='{kls}'>{v:+,.2f}</td>" if c == "realized_pnl_usd"
                             else f"<td class='{kls}'>{v:+.4f}</td>")
            elif c in ("instrument", "direction", "exit_reason"):
                cells.append(f"<td class='txt'>{v}</td>")
            else:
                cells.append(f"<td>{v}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return note, "<table><thead><tr>" + hdr + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


# ════════════════════════════════════════════════════════════════════════════
# 8. Main
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(description="Arki futures trade-by-trade analyzer")
    ap.add_argument("run", nargs="?", help="run id under results/runs/ (or use --run-dir)")
    ap.add_argument("--run-dir", help="explicit run directory path")
    ap.add_argument("--out", help="output dir (default: <run_dir>/trade_analysis)")
    ap.add_argument("--top-n", type=int, default=50, help="candles for top-N trades by |P&L| (default 50)")
    ap.add_argument("--candle-basis", choices=["contract", "adjusted"], default="contract",
                    help="candle price basis (default contract OHLC; 'adjusted' = continuous line)")
    ap.add_argument("--benchmark", choices=["zero"], default="zero", help="ARS benchmark (default zero)")
    ap.add_argument("--boot-block", type=int, default=10, help="bootstrap block length (TD)")
    ap.add_argument("--boot-B", type=int, default=2000, help="bootstrap resamples")
    ap.add_argument("--seed", type=int, default=20260527, help="bootstrap RNG seed")
    args = ap.parse_args()

    run_arg = args.run_dir or args.run
    if not run_arg:
        ap.error("provide a run id positionally or via --run-dir")

    print(f"[1/6] loading run artifacts: {run_arg}")
    run = load_run(run_arg)
    out_dir = Path(args.out) if args.out else (run.run_dir / "trade_analysis")
    candle_dir = out_dir / "candles"
    candle_dir.mkdir(parents=True, exist_ok=True)
    print(f"      run_id={run.run_id} capital=${run.capital:,.0f} "
          f"instruments={len(run.instruments)} days={len(run.positions)}")

    # native portfolio return series (exact reconciliation to equity_curve.csv)
    port_pct = run.returns.sum(axis=1)             # percent per day
    port_ret = (port_pct / 100.0).rename("ret")    # fractional daily return
    recon_eps = float((port_pct.cumsum() - run.equity_curve).abs().max())

    print("[2/6] extracting sign-episode trades ...")
    adj_prices = {i: load_adjusted(i) for i in run.positions.columns}
    trades, diag = build_trades(run, adj_prices)
    df = trades_to_df(trades)
    xlsx_path = out_dir / "trades.xlsx"
    df.to_excel(xlsx_path, index=False, sheet_name="trades")
    # acceptance checks
    assert diag["sum_days_held"] == diag["nonzero_cells"], (
        f"days_held mismatch: Σdays={diag['sum_days_held']} nonzero_cells={diag['nonzero_cells']}")
    sum_pnl = diag["sum_pnl_pct"]
    eq_end = float(run.equity_curve.iloc[-1])
    resid = eq_end - sum_pnl
    print(f"      {len(trades)} trades · Σdays_held={diag['sum_days_held']} == nonzero_cells "
          f"(reconciles) · Σpnl={sum_pnl:+.4f}% vs equity_end={eq_end:+.4f}% "
          f"(flat-day residual {resid:+.4f}%)")

    print("[3/6] equity curve CSV + chart ...")
    nav = additive_nav(port_ret)
    eq_df = pd.DataFrame({"cum_pnl_pct": run.equity_curve,
                          "nav_additive": (1.0 + run.equity_curve / 100.0)})
    eq_df.index.name = "date"
    eq_df.to_csv(out_dir / "equity_curve.csv")
    eq_chart = render_equity_chart(run.equity_curve)

    print("[4/6] performance metrics (native + ARS-recomputed) ...")
    native_html = build_native_html(run.stats)
    perf_rows = [("Portfolio (full)", metrics_block(port_ret))]
    perf_html = build_perf_html(perf_rows)

    print("[5/6] ARS bootstrap (vs zero) ...")
    ars_html = build_ars_html(port_ret, args.boot_block, args.boot_B, args.seed)

    print(f"[6/6] rendering top-{args.top_n} candles ({args.candle_basis} basis) ...")
    top = df.reindex(df["realized_pnl_pct"].abs().sort_values(ascending=False).index).head(args.top_n)
    by_id = {t.trade_id: t for t in trades}
    roll_cache: dict[str, pd.DataFrame | None] = {}
    candle_blocks, skipped = [], []
    basis_used = {"contract": 0, "adjusted": 0, "adjusted_fallback": 0}
    for _, r in top.iterrows():
        t = by_id[int(r["trade_id"])]
        if t.instrument not in roll_cache:
            roll_cache[t.instrument] = load_roll_calendar(t.instrument)
        uri, status = render_candle(t, run, candle_dir, args.candle_basis,
                                    adj_prices.get(t.instrument), roll_cache[t.instrument])
        if uri is None:
            skipped.append((t, status))
            continue
        basis_used[status] = basis_used.get(status, 0) + 1
        blabel = {"contract": "contract OHLC", "adjusted": "adjusted line",
                  "adjusted_fallback": "adjusted line (contract OHLC unavailable)"}.get(status, status)
        rc = "pos" if t.realized_pnl_pct >= 0 else "neg"
        candle_blocks.append(
            f"<div class='trade-block'><h3>Trade #{t.trade_id:04d} — {t.instrument} "
            f"({t.direction}, {t.days_held}d, {t.exit_reason})</h3>"
            f"<div class='meta'>{t.entry_date.date()} → {t.exit_date.date()} · contracts "
            f"{t.entry_contracts}→{t.exit_contracts} (max {t.max_contracts}) · realized "
            f"<span class='{rc}'>{t.realized_pnl_pct:+.4f}% (${t.realized_pnl_usd:+,.0f})</span> · "
            f"basis: {blabel}</div>"
            f"<img src='{uri}' alt='trade {t.trade_id}'/></div>")
    cov_note = (f"<p class='meta'>Candle basis used across the {len(candle_blocks)} rendered: "
                f"contract OHLC {basis_used['contract']}, adjusted line {basis_used['adjusted']}, "
                f"adjusted-line fallback {basis_used['adjusted_fallback']}. "
                f"Note: this run's per-contract OHLC parquet holds only recent forward contracts "
                f"(2025–2026) and the roll calendars end 2020–2023, so historical contract bars are "
                f"unavailable — candles use the continuous back-adjusted price (the P&amp;L basis).</p>")
    skipped_html = cov_note
    if skipped:
        items = "".join(
            f"<li>#{t.trade_id:04d} {t.instrument} {t.entry_date.date()}→{t.exit_date.date()} "
            f"(P&amp;L {t.realized_pnl_pct:+.4f}%) — <code>{s}</code></li>" for t, s in skipped)
        skipped_html += (f"<p class='meta'>{len(skipped)} of top {len(top)} trades skipped "
                         f"(no price coverage in window):</p><ul style='font-size:11px'>{items}</ul>")

    note, table_html = build_table_html(df, args.top_n)
    html = HTML_TEMPLATE.format(
        run_id=run.run_id, gen_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        mode=run.config.get("mode", ""), n_inst=len(run.instruments), capital=run.capital,
        vol_target=run.config.get("vol_target", ""), config_file=run.config.get("config_file", ""),
        recon_eps=recon_eps, candle_basis=args.candle_basis, ppy=PPY,
        boot_block=args.boot_block, boot_b=args.boot_B, seed=args.seed,
        summary_html=build_summary_html(df, run), eq_chart=eq_chart,
        sum_pnl=sum_pnl, eq_end=eq_end, resid=resid,
        resid_frac=(resid / eq_end * 100 if eq_end else float("nan")),
        native_html=native_html, perf_html=perf_html, ars_html=ars_html,
        n_trades=len(df), table_note=note, table_html=table_html,
        n_candles=len(candle_blocks), candles_html="\n".join(candle_blocks),
        skipped_html=skipped_html,
    )
    html_path = out_dir / "trade_report.html"
    html_path.write_text(html, encoding="utf-8")

    # reproducibility metadata
    meta = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "run_id": run.run_id, "run_dir": str(run.run_dir),
        "decisions": {"D1": "sign-episode", "D2": f"candle:{args.candle_basis}", "D3": "vs-zero"},
        "pnl_basis": "native daily_returns.csv (percent of capital)",
        "reconcile_equity_max_abs_err": recon_eps,
        "n_trades": len(trades), "sum_pnl_pct": sum_pnl, "equity_end_pct": eq_end,
        "flat_day_residual_pct": resid,
        "bootstrap": {"block": args.boot_block, "B": args.boot_B, "seed": args.seed},
        "top_n_candles": args.top_n, "candles_rendered": len(candle_blocks),
        "candles_skipped": len(skipped),
    }
    (out_dir / "analysis_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"\nWrote: {xlsx_path}")
    print(f"Wrote: {out_dir/'equity_curve.csv'}")
    print(f"Wrote: {html_path}")
    print(f"Wrote: {out_dir/'analysis_meta.json'}")
    print(f"Trades: {len(df)} | candles rendered {len(candle_blocks)} skipped {len(skipped)} "
          f"| reconcile ε={recon_eps:.1e}")


if __name__ == "__main__":
    main()
