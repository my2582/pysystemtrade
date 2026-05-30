#!/usr/bin/env python
"""execution_friction_us10 -- regime + non-stationarity diagnostics.

Consumes the 6 run dirs (equity_curves.csv + trades_US10.csv + summary.csv)
plus raw US10/ZN price from pysystemtrade rawdata. Emits:

  Sec 1  Full-history performance per cell (Sharpe, MaxDD, skew, hit-rate)
  Sec 2  Decade decomposition (1980s..2020s)
  Sec 3  Rolling 252d Sharpe / hit-rate / MaxDD (plots + sample table)
  Sec 4  Event windows (GFC 2007-09, COVID 2020Q1, 2022 hike 2022-2023)
  Sec 5  CUSUM-of-returns structural break per cell -- candidate break dates
  Sec 6  Rolling 252d beta of strategy returns to ZN return
  Sec 7  ZN-specific regime conditional performance
           - Kaufman Efficiency Ratio terciles (20d, 60d)
           - Realized-vol terciles (20d, 60d)
           - Sign-agreement across the 3 specs at $1M
           - 20d ZN-return autocorr sign buckets
           - Rolling 60d ZN-return terciles (rate-cycle phase proxy)
  Sec 8  Per-trade analysis (martin_primary): holding distribution +
         in-trade MFE/MAE proxy from daily-return path

Output:
  arki/results/<date>/execution_friction_us10_regime_analysis.html
  ..._full_history.csv  ..._decade.csv  ..._events.csv  ..._breaks.csv
  ..._regime_buckets.csv  ..._per_trade_mfe_mae.csv
  ..._rolling_sharpe.png  ..._event_windows.png  ..._regime_buckets.png

Also delivers the above to the Obsidian inbox at
~/Library/.../_Inbox/<date>/pysystemtrade_execution_friction_us10/.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "ars" / "runs"

SPEC_ORDER = ["carver_6speed_us10", "martin_baseline_us10", "martin_primary_ema2_us10"]
CAP_ORDER = [50_000, 1_000_000]
CAP_TAGS = {50_000: "50k", 1_000_000: "1m"}
TRADING_DAYS = 256
ZN = "US10"

SLUG_RE = re.compile(r"^\d{8}T\d{6}Z_(?P<spec>[a-z0-9_]+?)_(?P<cap>50k|1m)$")

EVENT_WINDOWS = {
    "GFC 2007-09":          ("2007-07-01", "2009-06-30"),
    "GFC core 2008-09→09-03": ("2008-09-01", "2009-03-31"),
    "COVID 2020Q1":         ("2020-02-15", "2020-05-01"),
    "Fed hike 2022-2023":   ("2022-03-15", "2023-10-31"),
}

DECADE_EDGES = [
    ("1980s", "1982-08-30", "1989-12-31"),
    ("1990s", "1990-01-01", "1999-12-31"),
    ("2000s", "2000-01-01", "2009-12-31"),
    ("2010s", "2010-01-01", "2019-12-31"),
    ("2020s", "2020-01-01", "2026-04-03"),
]

OBSIDIAN_INBOX = Path.home() / (
    "Library/Mobile Documents/iCloud~md~obsidian/Documents/MainVault/_Inbox"
)


# =====================================================================
# 1. Discovery + load
# =====================================================================

def _find_latest_cells() -> dict[tuple[str, int], Path]:
    cells: dict[tuple[str, int], Path] = {}
    for d in sorted(RUNS.iterdir()):
        if not d.is_dir():
            continue
        m = SLUG_RE.match(d.name)
        if not m:
            continue
        spec = m.group("spec")
        cap_int = 50_000 if m.group("cap") == "50k" else 1_000_000
        key = (spec, cap_int)
        if key not in cells or d.name > cells[key].name:
            cells[key] = d
    return cells


def _load_cell(d: Path) -> dict:
    s = pd.read_csv(d / "summary.csv").iloc[0].to_dict()
    eq = pd.read_csv(d / "equity_curves.csv", index_col=0, parse_dates=True)
    equity = eq.iloc[:, 0]
    eq_frac = 1.0 + equity / 100.0
    daily_pct = (eq_frac.pct_change().fillna(0.0) * 100.0)
    trades = pd.read_csv(d / f"trades_{ZN}.csv", parse_dates=["start", "end"])
    side = _reconstruct_side_series(trades, daily_pct.index)
    return {"summary": s, "equity": equity, "daily_pct": daily_pct,
            "trades": trades, "side": side, "run_dir": d}


def _reconstruct_side_series(trades: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.Series:
    """Build a daily signed-sign series from the trade ledger (1, -1, or 0)."""
    s = pd.Series(0, index=idx, dtype=int)
    for _, row in trades.iterrows():
        rng = pd.date_range(row["start"], row["end"], freq="B")
        rng = rng.intersection(idx)
        s.loc[rng] = int(row["sign"])
    return s


def _load_zn_price() -> pd.Series:
    from sysdata.config.configdata import Config
    from systems.provided.futures_chapter15.basesystem import futures_system
    config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    config.instruments = [ZN]
    sys = futures_system(config=config)
    return sys.rawdata.get_daily_prices(ZN)


# =====================================================================
# 2. Stats helpers
# =====================================================================

def _ann_sharpe(daily_pct: pd.Series) -> float:
    s = daily_pct.dropna()
    if len(s) < 30 or s.std() < 1e-12:
        return float("nan")
    return float(s.mean() / s.std() * np.sqrt(TRADING_DAYS))


def _ann_ret(daily_pct: pd.Series) -> float:
    return float(daily_pct.dropna().mean() * TRADING_DAYS)


def _ann_vol(daily_pct: pd.Series) -> float:
    return float(daily_pct.dropna().std() * np.sqrt(TRADING_DAYS))


def _maxdd_geom(daily_pct: pd.Series) -> float:
    eq = (1.0 + daily_pct.fillna(0) / 100.0).cumprod().clip(lower=1e-9)
    dd = (eq / eq.cummax() - 1.0) * 100
    return float(dd.min())


def _hit_rate(daily_pct: pd.Series) -> float:
    s = daily_pct.dropna()
    s = s[s != 0]
    if len(s) == 0:
        return float("nan")
    return float((s > 0).mean() * 100.0)


def _skew(daily_pct: pd.Series) -> float:
    return float(daily_pct.dropna().skew())


def _kurt(daily_pct: pd.Series) -> float:
    return float(daily_pct.dropna().kurtosis())


def _summary_row(label: str, daily_pct: pd.Series, n_trades_full: int | None = None) -> dict:
    return {
        "cell": label,
        "n_days": int(daily_pct.dropna().shape[0]),
        "start": str(daily_pct.dropna().index[0].date()) if len(daily_pct.dropna()) else "",
        "end": str(daily_pct.dropna().index[-1].date()) if len(daily_pct.dropna()) else "",
        "sharpe": round(_ann_sharpe(daily_pct), 3),
        "ann_ret_pct": round(_ann_ret(daily_pct), 3),
        "ann_vol_pct": round(_ann_vol(daily_pct), 3),
        "maxdd_geom_pct": round(_maxdd_geom(daily_pct), 2),
        "skew_daily": round(_skew(daily_pct), 3),
        "kurt_daily": round(_kurt(daily_pct), 3),
        "hit_rate_pct": round(_hit_rate(daily_pct), 2),
        "n_trades_full": n_trades_full,
    }


# =====================================================================
# Sec 1 Full-history table
# =====================================================================

def section_1_full_history(cells: dict) -> pd.DataFrame:
    rows = []
    for spec in SPEC_ORDER:
        for cap in CAP_ORDER:
            key = (spec, cap)
            if key not in cells:
                continue
            label = f"{spec}_{CAP_TAGS[cap]}"
            r = _summary_row(label, cells[key]["daily_pct"], int(cells[key]["summary"]["n_trades"]))
            rows.append(r)
    return pd.DataFrame(rows)


# =====================================================================
# Sec 2 Decade decomposition
# =====================================================================

def section_2_decade(cells: dict) -> pd.DataFrame:
    rows = []
    for spec in SPEC_ORDER:
        for cap in CAP_ORDER:
            key = (spec, cap)
            if key not in cells:
                continue
            d = cells[key]["daily_pct"]
            for name, lo, hi in DECADE_EDGES:
                slc = d.loc[lo:hi].dropna()
                if len(slc) < 60:
                    continue
                rows.append({
                    "cell": f"{spec}_{CAP_TAGS[cap]}",
                    "decade": name,
                    "n_days": int(len(slc)),
                    "sharpe": round(_ann_sharpe(slc), 3),
                    "ann_ret_pct": round(_ann_ret(slc), 2),
                    "ann_vol_pct": round(_ann_vol(slc), 2),
                    "maxdd_geom_pct": round(_maxdd_geom(slc), 2),
                    "hit_rate_pct": round(_hit_rate(slc), 2),
                    "skew_daily": round(_skew(slc), 3),
                })
    return pd.DataFrame(rows)


# =====================================================================
# Sec 3 Rolling 252d Sharpe / hit-rate / MaxDD
# =====================================================================

def _rolling_sharpe(daily_pct: pd.Series, window: int = 252) -> pd.Series:
    r = daily_pct.fillna(0)
    mu = r.rolling(window).mean()
    sd = r.rolling(window).std()
    return (mu / sd * np.sqrt(TRADING_DAYS)).rename(f"sharpe_{window}d")


def _rolling_hit(daily_pct: pd.Series, window: int = 252) -> pd.Series:
    r = daily_pct.fillna(0)
    nz = r != 0
    pos = (r > 0).astype(int)
    pos_roll = pos.rolling(window).sum()
    nz_roll = nz.rolling(window).sum()
    return ((pos_roll / nz_roll.replace(0, np.nan)) * 100).rename(f"hit_{window}d")


def _rolling_maxdd(daily_pct: pd.Series, window: int = 252) -> pd.Series:
    eq = (1.0 + daily_pct.fillna(0) / 100.0).cumprod()
    roll_peak = eq.rolling(window).max()
    dd = (eq / roll_peak - 1.0) * 100
    return dd.rename(f"dd_{window}d")


def section_3_rolling_plot(cells: dict, out_png: Path) -> pd.DataFrame:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(12, 9.5), sharex=True)
    sample_rows = []
    sample_dates = ["1995-01-03", "2005-01-03", "2015-01-02", "2020-12-31", "2026-04-03"]
    for spec in SPEC_ORDER:
        for cap in [1_000_000]:                    # plot at $1M to reduce clutter
            key = (spec, cap)
            if key not in cells:
                continue
            d = cells[key]["daily_pct"]
            label = f"{spec}_{CAP_TAGS[cap]}"
            sh = _rolling_sharpe(d)
            hr = _rolling_hit(d)
            md = _rolling_maxdd(d)
            axes[0].plot(sh.index, sh.values, label=label, lw=0.9)
            axes[1].plot(hr.index, hr.values, label=label, lw=0.9)
            axes[2].plot(md.index, md.values, label=label, lw=0.9)
            for dt in sample_dates:
                try:
                    sample_rows.append({
                        "cell": label, "date": dt,
                        "rolling_sharpe_252d": round(float(sh.loc[:dt].iloc[-1]), 3)
                            if len(sh.loc[:dt]) else None,
                        "rolling_hit_252d_pct": round(float(hr.loc[:dt].iloc[-1]), 2)
                            if len(hr.loc[:dt]) else None,
                        "rolling_dd_252d_pct": round(float(md.loc[:dt].iloc[-1]), 2)
                            if len(md.loc[:dt]) else None,
                    })
                except Exception:
                    pass
    axes[0].axhline(0, color="k", lw=0.5)
    axes[0].set_ylabel("Rolling Sharpe (252d)")
    axes[1].axhline(50, color="k", lw=0.5)
    axes[1].set_ylabel("Rolling hit-rate % (252d)")
    axes[2].axhline(0, color="k", lw=0.5)
    axes[2].set_ylabel("Rolling drawdown % (252d window)")
    for ax in axes:
        ax.grid(True, alpha=0.3); ax.legend(loc="upper left", fontsize=8)
    # event-window shading
    for lbl, (lo, hi) in EVENT_WINDOWS.items():
        for ax in axes:
            ax.axvspan(pd.to_datetime(lo), pd.to_datetime(hi), color="grey", alpha=0.08)
    fig.suptitle("Rolling 252d performance (3 specs @ $1M) -- grey shading: GFC / COVID / 2022 hike")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    return pd.DataFrame(sample_rows)


# =====================================================================
# Sec 4 Event windows
# =====================================================================

def section_4_events(cells: dict) -> pd.DataFrame:
    rows = []
    for label_e, (lo, hi) in EVENT_WINDOWS.items():
        for spec in SPEC_ORDER:
            for cap in CAP_ORDER:
                key = (spec, cap)
                if key not in cells:
                    continue
                slc = cells[key]["daily_pct"].loc[lo:hi].dropna()
                if len(slc) < 5:
                    continue
                rows.append({
                    "event": label_e,
                    "cell": f"{spec}_{CAP_TAGS[cap]}",
                    "n_days": int(len(slc)),
                    "cum_pct": round(float((1 + slc/100).prod() - 1) * 100, 2),
                    "sharpe": round(_ann_sharpe(slc), 3),
                    "maxdd_geom_pct": round(_maxdd_geom(slc), 2),
                    "hit_rate_pct": round(_hit_rate(slc), 2),
                })
    return pd.DataFrame(rows)


# =====================================================================
# Sec 5 CUSUM-of-returns structural break candidate
# =====================================================================

def _cusum_break(daily_pct: pd.Series) -> dict:
    """Find max-absolute CUSUM deviation date (single-break heuristic)."""
    r = daily_pct.fillna(0).values
    n = len(r)
    if n < 200:
        return {"break_date": None, "cusum_max_abs": float("nan")}
    cum = np.cumsum(r - r.mean())
    # Pre-break and post-break Sharpe to characterise
    idx_max = int(np.argmax(np.abs(cum)))
    dates = daily_pct.index
    br_date = dates[idx_max]
    pre = daily_pct.loc[:br_date]
    post = daily_pct.loc[br_date:]
    return {
        "break_date": str(br_date.date()),
        "cusum_max_abs": round(float(np.abs(cum).max()), 3),
        "pre_sharpe": round(_ann_sharpe(pre), 3),
        "post_sharpe": round(_ann_sharpe(post), 3),
        "pre_n_days": int(len(pre.dropna())),
        "post_n_days": int(len(post.dropna())),
        "delta_sharpe_post_pre": round(_ann_sharpe(post) - _ann_sharpe(pre), 3),
    }


def section_5_breaks(cells: dict) -> pd.DataFrame:
    rows = []
    for spec in SPEC_ORDER:
        for cap in CAP_ORDER:
            key = (spec, cap)
            if key not in cells:
                continue
            br = _cusum_break(cells[key]["daily_pct"])
            br["cell"] = f"{spec}_{CAP_TAGS[cap]}"
            rows.append(br)
    cols = ["cell", "break_date", "pre_sharpe", "post_sharpe",
            "delta_sharpe_post_pre", "pre_n_days", "post_n_days", "cusum_max_abs"]
    return pd.DataFrame(rows)[cols]


# =====================================================================
# Sec 6 Rolling beta to ZN underlying
# =====================================================================

def section_6_beta(cells: dict, zn_price: pd.Series, window: int = 252) -> pd.DataFrame:
    rows = []
    zn_ret = zn_price.diff()
    zn_ret_pct = (zn_ret / zn_price.shift(1)) * 100   # percent return (for beta to be unitless)
    for spec in SPEC_ORDER:
        cap = 1_000_000
        key = (spec, cap)
        if key not in cells:
            continue
        d = cells[key]["daily_pct"].reindex(zn_ret_pct.index).fillna(0)
        z = zn_ret_pct.fillna(0)
        cov = d.rolling(window).cov(z)
        var = z.rolling(window).var()
        beta = (cov / var).rename("beta")
        # sample dates
        for dt in ["1995-01-03", "2005-01-03", "2015-01-02", "2022-12-30", "2026-04-03"]:
            try:
                v = beta.loc[:dt].dropna().iloc[-1]
                rows.append({
                    "cell": f"{spec}_1m",
                    "date": dt,
                    f"beta_to_ZN_{window}d": round(float(v), 4),
                })
            except Exception:
                pass
    return pd.DataFrame(rows)


# =====================================================================
# Sec 7 ZN-specific regime conditional performance
# =====================================================================

def _kaufman_er(price: pd.Series, N: int) -> pd.Series:
    direction = (price - price.shift(N)).abs()
    volatility = price.diff().abs().rolling(N).sum()
    return (direction / volatility.replace(0, np.nan)).rename(f"ER_{N}d")


def _bucket_terciles(s: pd.Series) -> pd.Series:
    return pd.qcut(s.dropna(), q=3, labels=["low", "mid", "high"]).reindex(s.index)


def _bucket_stats(daily_pct: pd.Series, bucket: pd.Series, bucket_name: str) -> list[dict]:
    rows = []
    for lvl in ["low", "mid", "high"]:
        mask = (bucket == lvl)
        s = daily_pct[mask]
        if len(s.dropna()) < 30:
            continue
        rows.append({
            "axis": bucket_name,
            "bucket": lvl,
            "n_days": int(len(s.dropna())),
            "mean_pct": round(float(s.mean()), 4),
            "sharpe": round(_ann_sharpe(s), 3),
            "hit_rate_pct": round(_hit_rate(s), 2),
        })
    return rows


def section_7_regime_buckets(cells: dict, zn_price: pd.Series) -> tuple[pd.DataFrame, Path]:
    # Subject: martin_primary_ema2_us10 at $1M (continuous strict Martin)
    # plus sign-agreement uses all 3 specs at $1M.
    key = ("martin_primary_ema2_us10", 1_000_000)
    if key not in cells:
        return pd.DataFrame(), None
    d_mp = cells[key]["daily_pct"]
    rows = []

    # Trend strength: Kaufman ER 20 & 60
    er20 = _kaufman_er(zn_price, 20).reindex(d_mp.index)
    er60 = _kaufman_er(zn_price, 60).reindex(d_mp.index)
    rows += _bucket_stats(d_mp, _bucket_terciles(er20), "ER_20d")
    rows += _bucket_stats(d_mp, _bucket_terciles(er60), "ER_60d")

    # Realized vol terciles 20 & 60 (ZN price std)
    rv20 = zn_price.diff().rolling(20).std().reindex(d_mp.index)
    rv60 = zn_price.diff().rolling(60).std().reindex(d_mp.index)
    rows += _bucket_stats(d_mp, _bucket_terciles(rv20), "realised_vol_20d")
    rows += _bucket_stats(d_mp, _bucket_terciles(rv60), "realised_vol_60d")

    # Sign agreement: count agreeing signs across 3 specs at $1M
    sides = {}
    for spec in SPEC_ORDER:
        k = (spec, 1_000_000)
        if k in cells:
            sides[spec] = cells[k]["side"].reindex(d_mp.index).fillna(0).astype(int)
    if len(sides) == 3:
        df = pd.DataFrame(sides)
        # count how many agree (non-zero sign) -- group by majority sign / agreement count
        nz = df.replace(0, np.nan)
        # agreement = number of non-NaN that share the row mode sign
        def _agree(row):
            vals = row.dropna().values
            if len(vals) == 0:
                return "all_flat"
            pos = int((vals == 1).sum())
            neg = int((vals == -1).sum())
            if pos == 3 or neg == 3:
                return "all3_agree"
            if pos == 2 or neg == 2:
                return "2of3_agree"
            return "split_1_1_1"
        agree_bucket = nz.apply(_agree, axis=1)
        # custom bucket-stats since labels are non-tercile
        for lvl in ["all3_agree", "2of3_agree", "split_1_1_1", "all_flat"]:
            mask = (agree_bucket == lvl)
            s = d_mp[mask]
            if len(s.dropna()) < 20:
                continue
            rows.append({
                "axis": "sign_agreement_3specs",
                "bucket": lvl,
                "n_days": int(len(s.dropna())),
                "mean_pct": round(float(s.mean()), 4),
                "sharpe": round(_ann_sharpe(s), 3),
                "hit_rate_pct": round(_hit_rate(s), 2),
            })

    # 20d ZN-return autocorr buckets (lag-1 over rolling 20d)
    zret = zn_price.diff()
    ac20 = zret.rolling(20).apply(lambda x: pd.Series(x).autocorr(lag=1), raw=False).reindex(d_mp.index)
    # bucket by sign
    ac_bucket = ac20.apply(lambda v: "pos" if v > 0.05 else ("neg" if v < -0.05 else "near0"))
    for lvl in ["pos", "near0", "neg"]:
        mask = (ac_bucket == lvl)
        s = d_mp[mask]
        if len(s.dropna()) < 30:
            continue
        rows.append({
            "axis": "ZN_20d_autocorr",
            "bucket": lvl,
            "n_days": int(len(s.dropna())),
            "mean_pct": round(float(s.mean()), 4),
            "sharpe": round(_ann_sharpe(s), 3),
            "hit_rate_pct": round(_hit_rate(s), 2),
        })

    # Rate cycle phase proxy: rolling 60d ZN return terciles
    # ZN up = rates down (price up = yield down). Sign of 60d return = cycle direction.
    zn_60d_ret = (zn_price - zn_price.shift(60)).reindex(d_mp.index)
    rows += _bucket_stats(d_mp, _bucket_terciles(zn_60d_ret), "ZN_60d_return")

    df_out = pd.DataFrame(rows)

    # plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pivot = df_out.pivot_table(index="bucket", columns="axis", values="sharpe", aggfunc="first")
    fig, ax = plt.subplots(figsize=(11, 5.0))
    pivot.plot.bar(ax=ax, edgecolor="white")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("Sharpe per bucket"); ax.set_xlabel("bucket")
    ax.set_title("martin_primary_ema2_us10 @ $1M -- Sharpe by regime bucket")
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    out_png = None
    return df_out, out_png


# =====================================================================
# Sec 8 Per-trade MFE/MAE (martin_primary)
# =====================================================================

def section_8_per_trade_mfe_mae(cells: dict) -> pd.DataFrame:
    """In-trade max-favourable-excursion + max-adverse-excursion proxy.

    For each trade row (start..end, sign), compute cumulative strategy daily
    return path from `start+1` to `end` inclusive, then MFE = max(path),
    MAE = min(path). Reported in % of capital."""
    key = ("martin_primary_ema2_us10", 1_000_000)
    if key not in cells:
        return pd.DataFrame()
    d = cells[key]["daily_pct"]
    trades = cells[key]["trades"]
    rows = []
    for _, t in trades.iterrows():
        slc = d.loc[t["start"]:t["end"]].dropna()
        if len(slc) < 1:
            continue
        path = slc.cumsum()
        rows.append({
            "start": str(t["start"].date()),
            "end": str(t["end"].date()),
            "days": int(t["days"]),
            "sign": int(t["sign"]),
            "trade_return_pct": float(t["trade_return_pct"]),
            "mfe_pct": round(float(path.max()), 4),
            "mae_pct": round(float(path.min()), 4),
        })
    df = pd.DataFrame(rows)
    return df


# =====================================================================
# Event-window plot (Sec 4 visual)
# =====================================================================

def render_event_windows_plot(cells: dict, out_png: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(EVENT_WINDOWS), figsize=(16, 4.0), sharey=False)
    for ax, (name, (lo, hi)) in zip(axes, EVENT_WINDOWS.items()):
        for spec in SPEC_ORDER:
            cap = 1_000_000
            key = (spec, cap)
            if key not in cells:
                continue
            slc = cells[key]["daily_pct"].loc[lo:hi].dropna()
            if len(slc) < 5:
                continue
            cum = ((1 + slc/100).cumprod() - 1) * 100
            ax.plot(cum.index, cum.values, label=spec, lw=1.1)
        ax.axhline(0, color="k", lw=0.5)
        ax.set_title(name); ax.grid(True, alpha=0.3); ax.legend(fontsize=7)
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle("Cumulative return % within event windows (3 specs @ $1M)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def render_regime_bucket_plot(df: pd.DataFrame, out_png: Path) -> None:
    if df.empty:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pivot = df.pivot_table(index="bucket", columns="axis", values="sharpe", aggfunc="first")
    fig, ax = plt.subplots(figsize=(12, 5.0))
    pivot.plot.bar(ax=ax, edgecolor="white")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("Sharpe per bucket"); ax.set_xlabel("bucket")
    ax.set_title("martin_primary_ema2_us10 @ $1M -- Sharpe by regime bucket")
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


# =====================================================================
# HTML report
# =====================================================================

def _df_to_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p><i>no data</i></p>"
    return df.to_html(index=False, classes="tbl", border=0,
                      float_format=lambda x: f"{x:.4f}"
                          if isinstance(x, float) else x)


def render_html(out: Path,
                full_hist: pd.DataFrame,
                decade: pd.DataFrame,
                rolling_sample: pd.DataFrame,
                events: pd.DataFrame,
                breaks: pd.DataFrame,
                beta_table: pd.DataFrame,
                regime: pd.DataFrame,
                mfe_mae: pd.DataFrame,
                imgs: dict[str, str],
                run_utc: str,
                git_sha: str) -> None:
    mfe_summary = ""
    if not mfe_mae.empty:
        mfe_summary = pd.DataFrame([{
            "n_trades": len(mfe_mae),
            "median_days": int(mfe_mae["days"].median()),
            "pct_days_le_20": round(float((mfe_mae["days"] <= 20).mean() * 100), 1),
            "pct_days_le_60": round(float((mfe_mae["days"] <= 60).mean() * 100), 1),
            "median_trade_return_pct": round(float(mfe_mae["trade_return_pct"].median()), 3),
            "skew_trade_return": round(float(mfe_mae["trade_return_pct"].skew()), 3),
            "kurt_trade_return": round(float(mfe_mae["trade_return_pct"].kurtosis()), 3),
            "median_mfe_pct": round(float(mfe_mae["mfe_pct"].median()), 3),
            "median_mae_pct": round(float(mfe_mae["mae_pct"].median()), 3),
            "median_mfe_over_mae_ratio": round(float((mfe_mae["mfe_pct"] /
                                                     mfe_mae["mae_pct"].replace(0, np.nan)
                                                     ).abs().median()), 3),
        }]).to_html(index=False, classes="tbl", border=0,
                    float_format=lambda x: f"{x:.4f}" if isinstance(x, float) else x)

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>execution_friction_us10 -- regime + non-stationarity diagnostics</title>
<style>
 body {{ font-family: 'Inter', -apple-system, system-ui, sans-serif; max-width: 1240px;
        margin: 32px auto; color:#1a1f2c; padding: 0 24px; }}
 h1, h2, h3 {{ color:#0d4f3f; }}
 .meta {{ color:#5b6470; font-size: 13px; margin-bottom: 24px; }}
 .tbl {{ border-collapse: collapse; margin: 8px 0 24px; font-size: 12px; }}
 .tbl th, .tbl td {{ border-bottom: 1px solid #e3e8ee; padding: 4px 10px; text-align: right; }}
 .tbl th {{ background:#0d4f3f; color:white; text-align:center; }}
 .tbl td:first-child, .tbl th:first-child {{ text-align: left; }}
 .note {{ background:#f8f9fb; border-left:4px solid #0d4f3f; padding: 10px 16px;
          margin: 14px 0; font-size: 13px; }}
 img {{ max-width: 100%; height: auto; margin: 8px 0; }}
</style></head><body>
<h1>execution_friction_us10 — regime + non-stationarity diagnostics</h1>
<p class="meta">Generated {run_utc} UTC · git {git_sha[:8]} · subjects = 6 cells from
<code>execution_friction_us10</code> measurement (3 specs × $50K/$1M). Regime sub-analysis (Sec 7-8)
narrows to <code>martin_primary_ema2_us10 @ $1M</code> = strict Martin §1+§2.1 EMA2 continuous on ZN.</p>

<h2>Sec 1 — Full-history performance</h2>
{_df_to_html(full_hist)}

<h2>Sec 2 — Decade decomposition</h2>
<p class="note">ZN went through a ~40-year secular bull (rates falling). The 2010s/2020s should
reveal whether trend edge survived once the secular tailwind weakened.</p>
{_df_to_html(decade)}

<h2>Sec 3 — Rolling 252-day metrics (plot + select-date sample)</h2>
<p><img src="{imgs['rolling']}" alt="rolling 252d"></p>
{_df_to_html(rolling_sample)}

<h2>Sec 4 — Event-window stats</h2>
{_df_to_html(events)}
<p><img src="{imgs['events']}" alt="event windows"></p>

<h2>Sec 5 — CUSUM structural break candidates</h2>
<p class="note">Single-break heuristic: date of max-|CUSUM| of returns. Pre/post Sharpe
contrast quantifies the regime gap. NOT a formal Bai-Perron test, but a useful
direction-of-regime-change locator.</p>
{_df_to_html(breaks)}

<h2>Sec 6 — Rolling beta of strategy to ZN underlying (252d, select dates)</h2>
{_df_to_html(beta_table)}

<h2>Sec 7 — ZN regime conditional performance (martin_primary @ $1M)</h2>
<p class="note">All rows are the strict-Martin continuous cell only. Sharpe is annualised
on the bucket-conditional daily return distribution. These are the empirical inputs
to ④ feature design (TBM meta-labeler) and τ-range.</p>
{_df_to_html(regime)}
<p><img src="{imgs['regime']}" alt="regime buckets"></p>

<h2>Sec 8 — Per-trade MFE / MAE + holding distribution (martin_primary @ $1M)</h2>
<p class="note">Aggregated summary of in-trade max-favourable-excursion (MFE) and
max-adverse-excursion (MAE). Median MFE / |MAE| ratio approximates the natural
π/ℓ barrier ratio for TBM; the days percentiles inform T_max choice.</p>
{mfe_summary}
<details><summary>Full per-trade ledger ({len(mfe_mae)} trades) — collapsed</summary>
{_df_to_html(mfe_mae.head(50))}
<p><i>showing first 50 rows of {len(mfe_mae)}; full CSV in this folder.</i></p></details>

</body></html>"""
    out.write_text(html)


# =====================================================================
# Main
# =====================================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--no-deliver-obsidian", dest="deliver_obsidian",
                    action="store_false", default=True)
    args = ap.parse_args()

    print("[load] discovering cells ...")
    cells_paths = _find_latest_cells()
    cells = {k: _load_cell(p) for k, p in cells_paths.items()}
    print(f"[load] {len(cells)} cells")
    print("[load] ZN price ...")
    zn_price = _load_zn_price()
    print(f"[load] ZN price {zn_price.index[0].date()}->{zn_price.index[-1].date()} "
          f"({len(zn_price)} rows)")

    out_dir = ROOT / "arki" / "results" / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    base = "execution_friction_us10_regime_analysis"

    print("[sec1] full history ...")
    full = section_1_full_history(cells)
    full.to_csv(out_dir / f"{base}_full_history.csv", index=False)
    print("[sec2] decade ...")
    dec = section_2_decade(cells)
    dec.to_csv(out_dir / f"{base}_decade.csv", index=False)
    print("[sec3] rolling ...")
    rolling_png = out_dir / f"{base}_rolling.png"
    sample = section_3_rolling_plot(cells, rolling_png)
    sample.to_csv(out_dir / f"{base}_rolling_sample.csv", index=False)
    print("[sec4] events ...")
    events = section_4_events(cells)
    events.to_csv(out_dir / f"{base}_events.csv", index=False)
    events_png = out_dir / f"{base}_events.png"
    render_event_windows_plot(cells, events_png)
    print("[sec5] CUSUM breaks ...")
    breaks = section_5_breaks(cells)
    breaks.to_csv(out_dir / f"{base}_breaks.csv", index=False)
    print("[sec6] rolling beta ...")
    beta = section_6_beta(cells, zn_price)
    beta.to_csv(out_dir / f"{base}_beta.csv", index=False)
    print("[sec7] regime buckets ...")
    regime, _ = section_7_regime_buckets(cells, zn_price)
    regime.to_csv(out_dir / f"{base}_regime_buckets.csv", index=False)
    regime_png = out_dir / f"{base}_regime_buckets.png"
    render_regime_bucket_plot(regime, regime_png)
    print("[sec8] per-trade MFE/MAE ...")
    mfe_mae = section_8_per_trade_mfe_mae(cells)
    mfe_mae.to_csv(out_dir / f"{base}_per_trade_mfe_mae.csv", index=False)

    git_sha = "unknown"
    try:
        import subprocess
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        pass

    html_path = out_dir / f"{base}.html"
    render_html(html_path, full, dec, sample, events, breaks, beta, regime, mfe_mae,
                imgs={"rolling": rolling_png.name, "events": events_png.name,
                      "regime": regime_png.name},
                run_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                git_sha=git_sha)
    print(f"[ok] wrote {html_path}")

    if args.deliver_obsidian and OBSIDIAN_INBOX.exists():
        ob_dir = OBSIDIAN_INBOX / args.date / "pysystemtrade_execution_friction_us10"
        ob_dir.mkdir(parents=True, exist_ok=True)
        for f in out_dir.glob(f"{base}*"):
            shutil.copy(f, ob_dir / f.name)
        print(f"[ok] delivered regime files to {ob_dir}")

    print("\n=== SUMMARY ===")
    print("Full-history Sharpe by cell:")
    print(full[["cell", "sharpe", "ann_ret_pct", "maxdd_geom_pct",
                "skew_daily", "hit_rate_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
