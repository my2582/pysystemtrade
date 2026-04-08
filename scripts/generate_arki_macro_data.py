#!/usr/bin/env python3
"""
Generate arki_macro_summary.json for the dashboard Arki Macro tab.
Combines:
  - Arki Macro Mini ($100K, 1.6x leverage, monthly returns from Excel)
  - Arki Multi-Factor ($200K, daily returns from arki_v4_optimized)
Total capital: $300K
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DATA = PROJECT_ROOT / "scripts" / "dashboard" / "data"

# --- Configuration ---
MINI_CAPITAL = 100_000
MF_CAPITAL = 200_000
TOTAL_CAPITAL = MINI_CAPITAL + MF_CAPITAL
MINI_FILE = PROJECT_ROOT / "data" / "arki_macro" / "arki_macro_mini_returns.xlsx"
MF_FILE = PROJECT_ROOT / "results" / "runs" / "20260405_0147_arki_v4_optimized" / "daily_returns.csv"


def load_macro_mini():
    """Load Arki Macro Mini monthly returns."""
    df = pd.read_excel(MINI_FILE)
    df.columns = ["Date", "return"]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    return df["return"]


def load_multi_factor():
    """Load Multi-Factor daily returns and resample to monthly.
    
    The CSV has per-instrument daily returns in PERCENT units.
    We sum across instruments for total portfolio return, then divide by 100.
    """
    df = pd.read_csv(MF_FILE, index_col=0, parse_dates=True)
    # Sum all instruments for total portfolio daily return (in %)
    port_daily_pct = df.sum(axis=1)
    # Convert percent to fractional
    daily_ret = port_daily_pct / 100

    # Compound to monthly
    monthly = (1 + daily_ret).resample("M").prod() - 1
    return monthly


def compute_stats(returns: pd.Series, label: str = "") -> dict:
    """Compute comprehensive statistics from a monthly return series."""
    n = len(returns)
    if n == 0:
        return {}

    ann_factor = 12
    cumulative = (1 + returns).cumprod()
    total_return = cumulative.iloc[-1] - 1
    years = n / 12

    ann_mean = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    ann_std = returns.std() * np.sqrt(ann_factor)

    sharpe = ann_mean / ann_std if ann_std > 0 else 0

    downside = returns[returns < 0].std() * np.sqrt(ann_factor)
    sortino = ann_mean / downside if downside > 0 else 0

    # Drawdown
    cummax = cumulative.cummax()
    drawdown = (cumulative - cummax) / cummax
    max_dd = drawdown.min()
    avg_dd = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0

    calmar = ann_mean / abs(max_dd) if max_dd != 0 else 0

    hit_rate = (returns > 0).sum() / n
    avg_gain = returns[returns > 0].mean() if (returns > 0).any() else 0
    avg_loss = returns[returns < 0].mean() if (returns < 0).any() else 0
    gain_loss_ratio = abs(avg_gain / avg_loss) if avg_loss != 0 else 0

    profit_factor = abs(returns[returns > 0].sum() / returns[returns < 0].sum()) if returns[returns < 0].sum() != 0 else 0

    return {
        "label": label,
        "total_return": round(total_return * 100, 2),
        "cagr": round(ann_mean * 100, 2),
        "ann_vol": round(ann_std * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "avg_drawdown": round(avg_dd * 100, 2),
        "calmar": round(calmar, 3),
        "skew": round(float(returns.skew()), 3),
        "kurtosis": round(float(returns.kurtosis()), 3),
        "hit_rate": round(hit_rate * 100, 1),
        "avg_gain": round(avg_gain * 100, 3),
        "avg_loss": round(avg_loss * 100, 3),
        "gain_loss_ratio": round(gain_loss_ratio, 3),
        "profit_factor": round(profit_factor, 3),
        "best_month": round(returns.max() * 100, 2),
        "worst_month": round(returns.min() * 100, 2),
        "months": n,
        "years": round(years, 1),
    }


def compute_period_returns(returns: pd.Series) -> dict:
    """Compute returns over standard periods: YTD, 1Y, 3Y, 5Y, 10Y, SI."""
    now = returns.index[-1]
    result = {}

    # YTD
    ytd = returns[returns.index >= pd.Timestamp(now.year, 1, 1)]
    result["ytd"] = round(((1 + ytd).prod() - 1) * 100, 2) if len(ytd) > 0 else None

    for label, months in [("1y", 12), ("3y", 36), ("5y", 60), ("10y", 120), ("20y", 240)]:
        cutoff = now - pd.DateOffset(months=months)
        sub = returns[returns.index >= cutoff]
        if len(sub) >= months * 0.8:
            cum = (1 + sub).prod() - 1
            ann = (1 + cum) ** (12 / len(sub)) - 1
            result[label] = round(ann * 100, 2)
        else:
            result[label] = None

    # Since inception
    cum = (1 + returns).prod() - 1
    ann = (1 + cum) ** (12 / len(returns)) - 1
    result["since_inception"] = round(ann * 100, 2)

    return result


def compute_annual_returns(mini: pd.Series, mf: pd.Series, combined: pd.Series) -> list:
    """Compute annual returns for each strategy."""
    years = sorted(set(combined.index.year))
    result = []
    for y in years:
        row = {"year": int(y)}
        for label, series in [("combined", combined), ("mini", mini), ("mf", mf)]:
            sub = series[series.index.year == y]
            if len(sub) > 0:
                row[label] = round(((1 + sub).prod() - 1) * 100, 2)
            else:
                row[label] = None
        result.append(row)
    return result


def compute_monthly_matrix(returns: pd.Series) -> dict:
    """Create year x month return matrix for heatmap."""
    result = {}
    for dt, ret in returns.items():
        y = str(dt.year)
        m = str(dt.month)
        if y not in result:
            result[y] = {}
        result[y][m] = round(ret * 100, 2)
    return result


def series_to_points(series: pd.Series) -> list:
    """Convert pandas Series to [[timestamp_ms, value], ...] for Highcharts."""
    result = []
    for dt, val in series.items():
        ts = int(dt.timestamp() * 1000)
        result.append([ts, round(float(val), 4)])
    return result


def compute_rolling_sharpe(returns: pd.Series, window_months=36) -> list:
    """Compute rolling Sharpe ratio."""
    rolling_mean = returns.rolling(window_months).mean() * 12
    rolling_std = returns.rolling(window_months).std() * np.sqrt(12)
    rolling_sr = (rolling_mean / rolling_std).dropna()
    return series_to_points(rolling_sr)


def compute_rolling_correlation(mini: pd.Series, mf: pd.Series, window_months=36) -> list:
    """Compute rolling correlation between two return series."""
    aligned = pd.DataFrame({"mini": mini, "mf": mf}).dropna()
    if len(aligned) < window_months:
        return []
    rolling_corr = aligned["mini"].rolling(window_months).corr(aligned["mf"]).dropna()
    return series_to_points(rolling_corr)


def compute_drawdown_series(returns: pd.Series) -> list:
    """Compute drawdown series for charting."""
    cumulative = (1 + returns).cumprod()
    cummax = cumulative.cummax()
    drawdown = (cumulative - cummax) / cummax
    return series_to_points(drawdown)


def main():
    print("Loading Arki Macro Mini returns...")
    mini_ret = load_macro_mini()
    print(f"  {len(mini_ret)} months: {mini_ret.index[0].date()} → {mini_ret.index[-1].date()}")

    print("Loading Arki Multi-Factor returns...")
    mf_ret = load_multi_factor()
    print(f"  {len(mf_ret)} months: {mf_ret.index[0].date()} → {mf_ret.index[-1].date()}")

    # Align to common date range
    common_start = max(mini_ret.index[0], mf_ret.index[0])
    common_end = min(mini_ret.index[-1], mf_ret.index[-1])
    mini_aligned = mini_ret[common_start:common_end]
    mf_aligned = mf_ret[common_start:common_end]

    # Ensure same index
    common_idx = mini_aligned.index.intersection(mf_aligned.index)
    mini_aligned = mini_aligned.reindex(common_idx)
    mf_aligned = mf_aligned.reindex(common_idx)

    print(f"  Common period: {common_idx[0].date()} → {common_idx[-1].date()} ({len(common_idx)} months)")

    # Combine: capital-weighted P&L
    mini_pnl = mini_aligned * MINI_CAPITAL
    mf_pnl = mf_aligned * MF_CAPITAL
    combined_pnl = mini_pnl + mf_pnl
    combined_ret = combined_pnl / TOTAL_CAPITAL

    # Equity curves (cumulative)
    mini_equity = (1 + mini_aligned).cumprod()
    mf_equity = (1 + mf_aligned).cumprod()
    combined_equity = (1 + combined_ret).cumprod()

    # Overall correlation
    overall_corr = mini_aligned.corr(mf_aligned)
    print(f"  Correlation: {overall_corr:.4f}")

    # Compute all analytics
    print("Computing statistics...")

    summary = {
        "meta": {
            "total_capital": TOTAL_CAPITAL,
            "components": [
                {"name": "Arki Macro Mini", "capital": MINI_CAPITAL, "leverage": 1.6},
                {"name": "Arki Multi-Factor", "capital": MF_CAPITAL, "leverage": None},
            ],
            "common_start": str(common_idx[0].date()),
            "common_end": str(common_idx[-1].date()),
            "total_months": len(common_idx),
            "correlation": round(overall_corr, 4),
            "generated": datetime.now().isoformat(),
        },
        "combined": {
            "stats": compute_stats(combined_ret, "Arki Macro"),
            "equity_monthly": series_to_points(combined_equity),
            "period_returns": compute_period_returns(combined_ret),
        },
        "macro_mini": {
            "stats": compute_stats(mini_aligned, "Arki Macro Mini"),
            "equity_monthly": series_to_points(mini_equity),
            "period_returns": compute_period_returns(mini_aligned),
        },
        "multi_factor": {
            "stats": compute_stats(mf_aligned, "Arki Multi-Factor"),
            "equity_monthly": series_to_points(mf_equity),
            "period_returns": compute_period_returns(mf_aligned),
        },
        "annual_returns": compute_annual_returns(mini_aligned, mf_aligned, combined_ret),
        "monthly_returns": compute_monthly_matrix(combined_ret),
        "rolling_sharpe_3y": {
            "combined": compute_rolling_sharpe(combined_ret),
            "mini": compute_rolling_sharpe(mini_aligned),
            "mf": compute_rolling_sharpe(mf_aligned),
        },
        "rolling_correlation": compute_rolling_correlation(mini_aligned, mf_aligned),
        "drawdown": {
            "combined": compute_drawdown_series(combined_ret),
            "mini": compute_drawdown_series(mini_aligned),
            "mf": compute_drawdown_series(mf_aligned),
        },
    }

    # Write output
    DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)
    output_path = DASHBOARD_DATA / "arki_macro_summary.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, separators=(",", ":"))

    size_kb = output_path.stat().st_size / 1024
    print(f"\n✅ Written to {output_path} ({size_kb:.0f} KB)")

    # Print summary
    for key in ["combined", "macro_mini", "multi_factor"]:
        s = summary[key]["stats"]
        print(f"  {s['label']:<22} CAGR={s['cagr']:>6}%  SR={s['sharpe']:>6}  MaxDD={s['max_drawdown']:>7}%")


if __name__ == "__main__":
    main()
