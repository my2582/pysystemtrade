#!/usr/bin/env python3
"""
Generate arki_macro_summary.json for the dashboard Arki Macro tab.
Produces TWO scenarios:
  1. Original Arki Macro: Mini ($100K) + Multi-Factor 25-inst ($200K) = $300K
  2. Smaller Arki Macro:  Mini ($150K) + Multi-Factor 100K-opt ($100K) = $250K

Also generates universe info with contract specs and nominal values.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "scripts" / "dashboard"

# --- Configuration ---
MINI_FILE = PROJECT_ROOT / "data" / "arki_macro" / "arki_macro_mini_returns.xlsx"
MF200_FILE = PROJECT_ROOT / "results" / "runs" / "20260405_0147_arki_v4_optimized" / "daily_returns.csv"
MF100_FILE = PROJECT_ROOT / "results" / "runs" / "20260409_1028_arki_100k_13inst" / "daily_returns.csv"
INST_CONFIG = PROJECT_ROOT / "data" / "futures" / "csvconfig" / "instrumentconfig.csv"

# Scenario definitions
SCENARIOS = {
    "original": {
        "label": "Arki Macro",
        "mini_capital": 100_000,
        "mf_capital": 200_000,
        "mf_file": MF200_FILE,
        "mf_label": "Multi-Factor ($200K, 25 inst)",
        "mf_inst_count": 25,
    },
    "smaller": {
        "label": "Smaller Arki Macro",
        "mini_capital": 150_000,
        "mf_capital": 100_000,
        "mf_file": MF100_FILE,
        "mf_label": "Multi-Factor ($100K, optimized)",
        "mf_inst_count": 13,
    },
}


def load_macro_mini():
    """Load Arki Macro Mini monthly returns (already 1.6x leveraged)."""
    df = pd.read_excel(MINI_FILE)
    df.columns = ["Date", "return"]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    return df["return"]


def load_multi_factor(filepath):
    """Load Multi-Factor daily returns from CSV and resample to monthly.
    CSV has per-instrument daily returns in PERCENT units.
    """
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    port_daily_pct = df.sum(axis=1)
    daily_ret = port_daily_pct / 100
    monthly = (1 + daily_ret).resample("M").prod() - 1
    return monthly


def compute_stats(returns, label=""):
    """Compute performance stats from monthly return series.

    SR uses pysystemtrade's method (accountCurve.sharpe):
      ann_mean = sum(returns) / number_of_years  (arithmetic, NOT CAGR)
      ann_std  = std(returns) × √(times_per_year)
      sharpe   = ann_mean / ann_std
    """
    n = len(returns)
    if n == 0:
        return {}
    ann_factor = 12
    cumulative = (1 + returns).cumprod()
    total_return = cumulative.iloc[-1] - 1
    years = n / 12

    # pysystemtrade method: arithmetic annualization
    ann_mean = returns.sum() / years if years > 0 else 0
    ann_std = returns.std() * np.sqrt(ann_factor)
    sharpe = ann_mean / ann_std if ann_std > 0 else 0

    downside = returns[returns < 0].std() * np.sqrt(ann_factor)
    sortino = ann_mean / downside if downside > 0 else 0
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

    # CAGR is kept as a separate metric (distinct from ann_mean used for SR)
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    return {
        "label": label,
        "total_return": round(total_return * 100, 2),
        "cagr": round(cagr * 100, 2),
        "ann_mean": round(ann_mean * 100, 2),
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


def compute_period_returns(returns):
    now = returns.index[-1]
    result = {}
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
    cum = (1 + returns).prod() - 1
    ann = (1 + cum) ** (12 / len(returns)) - 1
    result["since_inception"] = round(ann * 100, 2)
    return result


def compute_annual_returns(mini, mf, combined):
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


def compute_monthly_matrix(returns):
    result = {}
    for dt, ret in returns.items():
        y = str(dt.year)
        m = str(dt.month)
        if y not in result:
            result[y] = {}
        result[y][m] = round(ret * 100, 2)
    return result


def series_to_points(series):
    result = []
    for dt, val in series.items():
        ts = int(dt.timestamp() * 1000)
        result.append([ts, round(float(val), 4)])
    return result


def compute_rolling_sharpe(returns, window_months=36):
    rolling_mean = returns.rolling(window_months).mean() * 12
    rolling_std = returns.rolling(window_months).std() * np.sqrt(12)
    rolling_sr = (rolling_mean / rolling_std).dropna()
    return series_to_points(rolling_sr)


def compute_rolling_correlation(mini, mf, window_months=36):
    aligned = pd.DataFrame({"mini": mini, "mf": mf}).dropna()
    if len(aligned) < window_months:
        return []
    rolling_corr = aligned["mini"].rolling(window_months).corr(aligned["mf"]).dropna()
    return series_to_points(rolling_corr)


def compute_drawdown_series(returns):
    cumulative = (1 + returns).cumprod()
    cummax = cumulative.cummax()
    drawdown = (cumulative - cummax) / cummax
    return series_to_points(drawdown)


def build_scenario(mini_ret, mf_file, mini_capital, mf_capital, label):
    """Build a single scenario summary dict."""
    mf_ret = load_multi_factor(mf_file)
    total_capital = mini_capital + mf_capital

    # Align
    common_start = max(mini_ret.index[0], mf_ret.index[0])
    common_end = min(mini_ret.index[-1], mf_ret.index[-1])
    mini_aligned = mini_ret[common_start:common_end]
    mf_aligned = mf_ret[common_start:common_end]
    common_idx = mini_aligned.index.intersection(mf_aligned.index)
    mini_aligned = mini_aligned.reindex(common_idx)
    mf_aligned = mf_aligned.reindex(common_idx)

    # Combine: capital-weighted P&L
    mini_pnl = mini_aligned * mini_capital
    mf_pnl = mf_aligned * mf_capital
    combined_ret = (mini_pnl + mf_pnl) / total_capital

    # Equity
    mini_equity = (1 + mini_aligned).cumprod()
    mf_equity = (1 + mf_aligned).cumprod()
    combined_equity = (1 + combined_ret).cumprod()

    overall_corr = mini_aligned.corr(mf_aligned)
    print(f"  [{label}] Common: {common_idx[0].date()} → {common_idx[-1].date()} ({len(common_idx)} months), ρ={overall_corr:.4f}")

    return {
        "meta": {
            "label": label,
            "total_capital": total_capital,
            "mini_capital": mini_capital,
            "mf_capital": mf_capital,
            "correlation": round(overall_corr, 4),
            "common_start": str(common_idx[0].date()),
            "common_end": str(common_idx[-1].date()),
            "total_months": len(common_idx),
        },
        "combined": {
            "stats": compute_stats(combined_ret, label),
            "equity_monthly": series_to_points(combined_equity),
            "period_returns": compute_period_returns(combined_ret),
        },
        "macro_mini": {
            "stats": compute_stats(mini_aligned, f"Macro Mini (${mini_capital//1000}K)"),
            "equity_monthly": series_to_points(mini_equity),
            "period_returns": compute_period_returns(mini_aligned),
        },
        "multi_factor": {
            "stats": compute_stats(mf_aligned, f"Multi-Factor (${mf_capital//1000}K)"),
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
    }, mini_aligned, mf_aligned, combined_ret


def build_universe_info(instruments_list):
    """Build universe info table with contract specs, IB symbols, and universe membership."""
    cfg = pd.read_csv(INST_CONFIG)
    IB_CONFIG = PROJECT_ROOT / "sysbrokers" / "IB" / "config" / "ib_config_futures.csv"
    ibcfg = pd.read_csv(IB_CONFIG) if IB_CONFIG.exists() else pd.DataFrame()

    INSTS_25 = ['SP500_micro','NASDAQ_micro','DAX','NIKKEI','FTSE100','IBEX_mini','FTSECHINAA',
                'US10','US5','BUND','GILT','JGB','GOLD_micro','SILVER','COPPER-micro',
                'CRUDE_W','BRENT-LAST','GASOIL','AUD_micro','MXP','YENEUR',
                'SUGAR11','COTTON','LEANHOG','COCOA_LDN']
    INSTS_13 = ['GOLD_micro','DAX','EU-DJ-OIL','SILVER','CRUDE_W','BRENT-LAST',
                'COPPER-micro','GILT','SP500_micro','EU-BANKS','TOPIX','EU-DJ-TELECOM','US10']

    universe = []
    for inst in sorted(instruments_list):
        row = cfg[cfg["Instrument"] == inst]
        if len(row) == 0:
            continue
        r = row.iloc[0]
        # IB config
        ib = ibcfg[ibcfg["Instrument"] == inst] if len(ibcfg) > 0 else pd.DataFrame()
        ib_symbol = ib["IBSymbol"].values[0] if len(ib) > 0 else ""
        ib_exchange = ib["IBExchange"].values[0] if len(ib) > 0 else ""
        # Latest price
        price_file = PROJECT_ROOT / "data" / "futures" / "multiple_prices_csv" / f"{inst}.csv"
        latest_price = None
        if price_file.exists():
            try:
                pdf = pd.read_csv(price_file)
                if "PRICE" in pdf.columns:
                    latest_price = pdf["PRICE"].dropna().iloc[-1]
            except Exception:
                pass
        pointsize = float(r["Pointsize"])
        nominal = round(latest_price * pointsize, 0) if latest_price else None
        universe.append({
            "instrument": inst,
            "ib_symbol": ib_symbol,
            "ib_exchange": ib_exchange,
            "description": r.get("Description", ""),
            "asset_class": r.get("AssetClass", ""),
            "currency": r.get("Currency", ""),
            "pointsize": pointsize,
            "latest_price": round(latest_price, 2) if latest_price else None,
            "nominal_value": nominal,
            "in_25": inst in INSTS_25,
            "in_13": inst in INSTS_13,
        })
    return universe


def main():
    print("Loading Arki Macro Mini returns (already 1.6x leveraged)...")
    mini_ret = load_macro_mini()
    print(f"  {len(mini_ret)} months: {mini_ret.index[0].date()} → {mini_ret.index[-1].date()}")

    # Build both scenarios
    results = {}
    for key, cfg in SCENARIOS.items():
        print(f"\nBuilding scenario: {cfg['label']}...")
        scenario, mini_a, mf_a, comb = build_scenario(
            mini_ret, cfg["mf_file"], cfg["mini_capital"], cfg["mf_capital"], cfg["label"]
        )
        results[key] = scenario

    # For backward compat, output the "original" as the main arki_macro_summary.json
    orig = results["original"]
    # Add generated timestamp
    orig["meta"]["generated"] = datetime.now().isoformat()
    orig["meta"]["components"] = [
        {"name": "Arki Macro Mini", "capital": 100_000, "leverage": 1.6},
        {"name": "Arki Multi-Factor", "capital": 200_000, "leverage": None},
    ]

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    # Write original
    path1 = DASHBOARD_DIR / "arki_macro_summary.json"
    with open(path1, "w") as f:
        json.dump(orig, f, separators=(",", ":"))
    print(f"\n✅ Original Macro → {path1} ({path1.stat().st_size/1024:.0f} KB)")

    # Write smaller
    smaller = results["smaller"]
    smaller["meta"]["generated"] = datetime.now().isoformat()
    smaller["meta"]["components"] = [
        {"name": "Arki Macro Mini", "capital": 150_000, "leverage": 1.6},
        {"name": "Arki Multi-Factor", "capital": 100_000, "leverage": None},
    ]
    path2 = DASHBOARD_DIR / "arki_macro_smaller.json"
    with open(path2, "w") as f:
        json.dump(smaller, f, separators=(",", ":"))
    print(f"✅ Smaller Macro → {path2} ({path2.stat().st_size/1024:.0f} KB)")

    # Write comparison summary
    comparison = {
        "generated": datetime.now().isoformat(),
        "scenarios": {},
    }
    for key in ["original", "smaller"]:
        s = results[key]
        comparison["scenarios"][key] = {
            "label": s["meta"]["label"],
            "total_capital": s["meta"]["total_capital"],
            "mini_capital": s["meta"]["mini_capital"],
            "mf_capital": s["meta"]["mf_capital"],
            "correlation": s["meta"]["correlation"],
            "stats": s["combined"]["stats"],
            "period_returns": s["combined"]["period_returns"],
            "equity_monthly": s["combined"]["equity_monthly"],
            "drawdown": s["drawdown"]["combined"],
        }
    path3 = DASHBOARD_DIR / "arki_macro_comparison.json"
    with open(path3, "w") as f:
        json.dump(comparison, f, separators=(",", ":"))
    print(f"✅ Comparison → {path3} ({path3.stat().st_size/1024:.0f} KB)")

    # Universe info
    all_instruments = set()
    for key, cfg in SCENARIOS.items():
        df = pd.read_csv(cfg["mf_file"], index_col=0, nrows=0)
        all_instruments.update(df.columns.tolist())
    universe = build_universe_info(all_instruments)
    path4 = DASHBOARD_DIR / "arki_universe_info.json"
    with open(path4, "w") as f:
        json.dump(universe, f, indent=2)
    print(f"✅ Universe → {path4} ({path4.stat().st_size/1024:.0f} KB)")

    # Print summary table
    print(f"\n{'='*70}")
    print(f"  {'Strategy':<25} {'CAGR':>8} {'SR':>8} {'MaxDD':>10} {'Corr':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*10} {'-'*8}")
    for key in ["original", "smaller"]:
        s = results[key]["combined"]["stats"]
        c = results[key]["meta"]["correlation"]
        print(f"  {s['label']:<25} {s['cagr']:>7}% {s['sharpe']:>8} {s['max_drawdown']:>9}% {c:>8}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
