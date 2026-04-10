#!/usr/bin/env python3
"""
Generate arki_macro_universe_compare.json for the Macro Compare tab.

For each sweep universe, computes:
  Combined Arki Macro = Mini ($100K, 1.6x leveraged) + Multi-Factor ($200K, universe variant)

This isolates the universe effect at the combined portfolio level while keeping
the Mini component and capital allocation fixed.

Also embeds full provenance metadata (source config, trading rules, instrument
weights method, run_id) so the dashboard can display traceability.
"""
import json
import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "results" / "runs"
DASHBOARD_DIR = PROJECT_ROOT / "scripts" / "dashboard"
DATA_DIR = DASHBOARD_DIR / "data"
MINI_FILE = PROJECT_ROOT / "data" / "arki_macro" / "arki_macro_mini_returns.xlsx"

# Fixed capital allocation
MINI_CAPITAL = 100_000      # Macro Mini (same for all)
MF_CAPITAL_DEFAULT = 200_000  # Multi-Factor default


def find_latest_run(label):
    """Find latest run dir matching a label."""
    matches = []
    for d in sorted(RUNS_DIR.iterdir()):
        if not d.is_dir():
            continue
        parts = d.name.split("_", 2)
        if len(parts) >= 3 and parts[2] == label:
            matches.append(d)
    return matches[-1] if matches else None


# Universe configs: (run_label, mf_capital, display_name, n_instruments)
UNIVERSE_CONFIGS = [
    # Full 25 variants (capital scaling)
    ("arki_v4_optimized",   200_000, "Full 25 ($200K)",     25),
    ("full25_250k",         250_000, "Full 25 ($250K)",     25),
    # Asset class building blocks (all at $200K MF)
    ("sweep_Ags_FX_Metals", 200_000, "+ Ags+FX+Metals (22)", 22),
    ("sweep_Ags_Metals",    200_000, "+ Ags+Metals (19)",   19),
    ("sweep_Ags_FX",        200_000, "+ Ags+FX (19)",       19),
    ("sweep_FX_Metals",     200_000, "+ FX+Metals (18)",    18),
    ("sweep_Ags",           200_000, "+ Ags (16)",          16),
    ("sweep_FX",            200_000, "+ FX (15)",           15),
    ("sweep_Metals",        200_000, "+ Metals (15)",       15),
    ("sweep_base",          200_000, "Equity+Bond (12)",    12),
    # Special
    ("arki_100k_13inst",    100_000, "$100K Mini (13)",     13),
]


def load_macro_mini():
    """Load Arki Macro Mini monthly returns (already 1.6x leveraged)."""
    df = pd.read_excel(MINI_FILE)
    df.columns = ["Date", "return"]
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    return df["return"]


def load_multi_factor_monthly(filepath):
    """Load Multi-Factor daily returns from CSV and resample to monthly."""
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    port_daily_pct = df.sum(axis=1)
    daily_ret = port_daily_pct / 100
    monthly = (1 + daily_ret).resample("M").prod() - 1
    return monthly


def compute_daily_sr(filepath):
    """Compute annualized SR from daily returns (pysystemtrade method, √256)."""
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    port = df.sum(axis=1) / 100
    return round(float(port.mean() / port.std() * np.sqrt(256)), 3)


def compute_stats(returns):
    """Compute performance stats from monthly return series."""
    n = len(returns)
    if n == 0:
        return {}
    cumulative = (1 + returns).cumprod()
    total_return = cumulative.iloc[-1] - 1
    years = n / 12
    ann_mean = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    ann_std = returns.std() * np.sqrt(12)
    sharpe = ann_mean / ann_std if ann_std > 0 else 0
    downside = returns[returns < 0].std() * np.sqrt(12)
    sortino = ann_mean / downside if downside > 0 else 0
    cummax = cumulative.cummax()
    drawdown = (cumulative - cummax) / cummax
    max_dd = drawdown.min()
    avg_dd = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0
    calmar = ann_mean / abs(max_dd) if max_dd != 0 else 0
    hit_rate = (returns > 0).sum() / n
    return {
        "cagr": round(ann_mean * 100, 2),
        "ann_vol": round(ann_std * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "avg_drawdown": round(avg_dd * 100, 2),
        "calmar": round(calmar, 3),
        "hit_rate": round(hit_rate * 100, 1),
        "skew": round(float(returns.skew()), 3),
        "best_month": round(returns.max() * 100, 2),
        "worst_month": round(returns.min() * 100, 2),
        "months": n,
        "years": round(years, 1),
    }


def extract_provenance(run_dir):
    """Extract full provenance from a run directory for traceability."""
    provenance = {
        "run_id": run_dir.name,
        "run_dir": str(run_dir.relative_to(PROJECT_ROOT)),
    }

    # config.yaml — run-level metadata
    cfg_file = run_dir / "config.yaml"
    if cfg_file.exists():
        with open(cfg_file) as f:
            cfg = yaml.safe_load(f) or {}
        provenance["config_file"] = cfg.get("config_file", "unknown")
        provenance["instruments_file"] = cfg.get("instruments_file", "unknown")
        provenance["instruments"] = cfg.get("instruments", [])
        provenance["capital"] = cfg.get("capital", cfg.get("notional_trading_capital"))
        provenance["vol_target"] = cfg.get("vol_target")
        provenance["mode"] = cfg.get("mode")
        provenance["timestamp"] = cfg.get("timestamp")

    # methodology.json — trading rules with exact parameters
    meth_file = run_dir / "methodology.json"
    if meth_file.exists():
        with open(meth_file) as f:
            meth = json.load(f)
        rules = meth.get("trading_rules", {})
        provenance["trading_rules"] = {}
        for name, info in sorted(rules.items()):
            family = "unknown"
            func = info.get("function", "")
            if "ewmac" in func:
                family = "Trend"
            elif "carry" in func:
                family = "Carry"
            elif "rel_mom" in func or "relative_momentum" in func:
                family = "CS Momentum"
            provenance["trading_rules"][name] = {
                "family": family,
                "function": func.split(".")[-1],
                "params": info.get("params", info.get("other_args", {})),
            }
        provenance["forecast_cap"] = meth.get("forecast_cap")
        provenance["shadow_cost"] = meth.get("shadow_cost")
        provenance["tracking_error_buffer"] = meth.get("tracking_error_buffer")
        provenance["cost_multiplier"] = meth.get("cost_multiplier")
        provenance["vol_calc"] = meth.get("volatility_calculation", {})

    # Source config file — forecast/instrument weight methods
    src_cfg_path = provenance.get("config_file")
    if src_cfg_path:
        full_src = PROJECT_ROOT / src_cfg_path
        # Fallback chain: original path → arki_production.yaml → archive
        if not full_src.exists():
            full_src = PROJECT_ROOT / "scripts" / "backtest_config" / "arki_production.yaml"
        if not full_src.exists():
            archive_name = Path(src_cfg_path).name
            full_src = PROJECT_ROOT / "scripts" / "backtest_config" / "archive" / archive_name
        if full_src.exists():
            with open(full_src) as f:
                src = yaml.safe_load(f) or {}
            provenance["forecast_weight_method"] = (
                "handcraft" if src.get("forecast_weight_estimate", {}).get("method") == "handcraft"
                else ("estimated" if src.get("use_forecast_weight_estimates") else "fixed")
            )
            provenance["instrument_weight_method"] = (
                "estimated" if src.get("use_instrument_weight_estimates")
                else "fixed"
            )
            # Extract forecast scalars if available
            provenance["forecast_scalars"] = src.get("forecast_scalars", {})
        else:
            provenance["forecast_weight_method"] = "unknown"
            provenance["instrument_weight_method"] = "unknown"

    # stats.yaml — native daily SR from pysystemtrade
    stats_file = run_dir / "stats.yaml"
    if stats_file.exists():
        with open(stats_file) as f:
            st = yaml.safe_load(f) or {}
        native_stats = st.get("stats", {})
        provenance["daily_sr"] = float(native_stats.get("sharpe", 0))
        provenance["period"] = st.get("period")
        provenance["years"] = st.get("years")

    return provenance


def series_to_points(series):
    return [[int(dt.timestamp() * 1000), round(float(val), 4)] for dt, val in series.items()]


def main():
    print("Loading Arki Macro Mini returns (1.6x leveraged)...")
    mini_ret = load_macro_mini()
    print(f"  {len(mini_ret)} months: {mini_ret.index[0].date()} → {mini_ret.index[-1].date()}")

    scenarios = []
    for run_label, mf_capital, display_name, n_inst in UNIVERSE_CONFIGS:
        run_dir = find_latest_run(run_label)
        if not run_dir:
            print(f"  ⚠️ No run found for {run_label}")
            continue

        dr_file = run_dir / "daily_returns.csv"
        if not dr_file.exists():
            print(f"  ⚠️ No daily_returns.csv in {run_dir.name}")
            continue

        print(f"\n  📊 {display_name} ({run_dir.name})...")

        # Extract provenance
        provenance = extract_provenance(run_dir)

        # Load MF returns
        mf_ret = load_multi_factor_monthly(dr_file)
        total_capital = MINI_CAPITAL + mf_capital

        # Also compute native daily SR for MF
        mf_daily_sr = compute_daily_sr(dr_file)

        # Align dates
        common_start = max(mini_ret.index[0], mf_ret.index[0])
        common_end = min(mini_ret.index[-1], mf_ret.index[-1])
        mini_a = mini_ret[common_start:common_end]
        mf_a = mf_ret[common_start:common_end]
        common_idx = mini_a.index.intersection(mf_a.index)
        mini_a = mini_a.reindex(common_idx)
        mf_a = mf_a.reindex(common_idx)

        # Capital-weighted combination
        combined_ret = (mini_a * MINI_CAPITAL + mf_a * mf_capital) / total_capital
        combined_equity = (1 + combined_ret).cumprod()
        corr = mini_a.corr(mf_a)

        # Drawdown series
        cummax = combined_equity.cummax()
        drawdown = (combined_equity - cummax) / cummax

        stats = compute_stats(combined_ret)
        mf_stats = compute_stats(mf_a)

        print(f"    Common: {common_idx[0].date()} → {common_idx[-1].date()} ({len(common_idx)} months)")
        print(f"    Combined SR: {stats['sharpe']:.3f}, MF Monthly SR: {mf_stats['sharpe']:.3f}, MF Daily SR: {mf_daily_sr:.3f}, ρ={corr:.3f}")

        # Build scenario with provenance
        scenario = {
            "id": run_label,
            "label": display_name,
            "n_instruments": n_inst,
            "mini_capital": MINI_CAPITAL,
            "mf_capital": mf_capital,
            "total_capital": total_capital,
            "correlation": round(corr, 4),
            "combined_stats": stats,
            "mf_stats": mf_stats,
            "mf_daily_sr": mf_daily_sr,
            "equity_monthly": series_to_points(combined_equity),
            "drawdown": series_to_points(drawdown),
            "provenance": provenance,
        }
        scenarios.append(scenario)

    # Sort by combined SR descending
    scenarios.sort(key=lambda s: s["combined_stats"]["sharpe"], reverse=True)

    # SR methodology note
    sr_note = {
        "mf_daily_sr": "Annualized from daily returns (√256). Same as pysystemtrade stats and Universe Sweep.",
        "mf_monthly_sr": "CAGR ÷ monthly vol (√12). Lower due to compounding, volatility drag, and monthly resampling.",
        "combined_sr": "Same methodology as Monthly SR, applied to the capital-weighted Mini+MF blend.",
        "why_different": "Daily SR ≈ monthly_mean × √256/std ≈ 1.08. Monthly SR uses CAGR/(std×√12) ≈ 0.75. "
                        "The gap (~0.3) is expected: CAGR < arithmetic mean (due to vol drag) and monthly vol > daily vol × √21 (due to autocorrelation of trend strategies).",
    }

    output = {
        "generated": datetime.now().isoformat(),
        "mini_capital": MINI_CAPITAL,
        "mini_description": "Macro Mini ($100K, 1.6× leveraged trend)",
        "sr_methodology": sr_note,
        "scenarios": scenarios,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "arki_macro_universe_compare.json"
    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\n✅ Written to {out_path} ({size_kb:.0f} KB)")
    print(f"   {len(scenarios)} universe scenarios compared\n")

    # Summary table
    print(f"  {'#':>2}  {'Universe':<25} {'Total$':>7}  {'Comb SR':>8}  {'MF DailySR':>10}  {'MF MonSR':>8}  {'MaxDD':>8}  {'CAGR':>7}  {'ρ':>6}")
    print(f"  {'—'*2}  {'—'*25} {'—'*7}  {'—'*8}  {'—'*10}  {'—'*8}  {'—'*8}  {'—'*7}  {'—'*6}")
    for i, s in enumerate(scenarios, 1):
        cs = s["combined_stats"]
        ms = s["mf_stats"]
        print(f"  {i:2d}  {s['label']:<25} ${s['total_capital']/1000:>5.0f}K  {cs['sharpe']:>8.3f}  {s['mf_daily_sr']:>10.3f}  {ms['sharpe']:>8.3f}  {cs['max_drawdown']:>7.1f}%  {cs['cagr']:>6.1f}%  {s['correlation']:>6.3f}")


if __name__ == "__main__":
    main()
