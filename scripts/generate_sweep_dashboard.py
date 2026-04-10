#!/usr/bin/env python3
"""
Generate sweep_summary.json for the dashboard Universe Sweep tab.
Consolidates equity curves (weekly sampled) + metrics from all sweep runs + v6 baseline.
"""
import json
import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "results" / "runs"
DASHBOARD_DATA = PROJECT_ROOT / "scripts" / "dashboard" / "data"

# Define asset class composition for labeling
CLASS_MAP = {
    "sweep_base": {"label": "Equity + Bond", "classes": ["Equity", "Bond"]},
    "sweep_Ags": {"label": "+ Ags", "classes": ["Equity", "Bond", "Ags"]},
    "sweep_FX": {"label": "+ FX", "classes": ["Equity", "Bond", "FX"]},
    "sweep_Metals": {"label": "+ Metals", "classes": ["Equity", "Bond", "Metals"]},
    "sweep_Ags_FX": {"label": "+ Ags + FX", "classes": ["Equity", "Bond", "Ags", "FX"]},
    "sweep_Ags_Metals": {"label": "+ Ags + Metals", "classes": ["Equity", "Bond", "Ags", "Metals"]},
    "sweep_FX_Metals": {"label": "+ FX + Metals", "classes": ["Equity", "Bond", "FX", "Metals"]},
    "sweep_Ags_FX_Metals": {"label": "+ Ags + FX + Metals", "classes": ["Equity", "Bond", "Ags", "FX", "Metals"]},
    "arki_v4_optimized": {"label": "Full 25 ($200K)", "classes": ["Equity", "Bond", "Ags", "FX", "Metals", "Energy"]},
    "full25_250k": {"label": "Full 25 ($250K)", "classes": ["Equity", "Bond", "Ags", "FX", "Metals", "Energy"]},
    "arki_100k_13inst": {"label": "$100K Macro Mini (13 inst)", "classes": ["Equity", "Bond", "Metals", "OilGas", "Ags"]},
}

VOL_TARGET_DEFAULT = 25.0  # annual % vol target
EXEC_LOOKBACK = 1280  # 5 years of trading days for executability scoring
EXEC_THRESHOLD = 0.5  # same as backtest_runner.py position_snapshot threshold


def compute_capital_efficiency(run_dir):
    """
    Compute capital efficiency metrics from actual backtest notional positions.

    Uses the SAME method as backtest_runner.py's executability scoring
    (avg |notional_position| >= 0.5 = tradeable) but bounded to the last
    5 years (1280 trading days) to avoid historical inflation bias from
    decades of cheaper contract prices.

    The dashboard header's 84% score uses the full 50-year history where
    instruments like GOLD_micro averaged 12+ contracts (due to $200/oz in
    1975) even though they average <1 contract at today's $3,000/oz.
    Using a 5-year window eliminates this survivorship bias while still
    being stable across runs.

    Returns: dict with efficiency metrics, or None if data missing.
    """
    run_dir = Path(run_dir)

    np_file = run_dir / "notional_positions.csv"
    if not np_file.exists():
        return None

    np_df = pd.read_csv(np_file, index_col=0, parse_dates=True)
    n_inst = len(np_df.columns)
    if n_inst == 0:
        return None

    # Use last 5 years of notional positions
    recent = np_df.tail(EXEC_LOOKBACK)
    avg_abs = recent.abs().mean()

    # Per-instrument executability (same metric as backtest_runner.py:339)
    per_inst = {}
    tradeable_count = 0

    for inst in np_df.columns:
        avg_pos = float(avg_abs.get(inst, 0))
        is_tradeable = avg_pos >= EXEC_THRESHOLD
        if is_tradeable:
            tradeable_count += 1
        per_inst[inst] = {
            "avg_pos": round(avg_pos, 4),
            "tradeable": is_tradeable,
        }

    exec_pct = round(tradeable_count / n_inst * 100, 1) if n_inst > 0 else 0
    avg_pos_all = round(float(avg_abs.mean()), 2)

    # Untradeable instruments list (for explainer card)
    untradeable = sorted(
        [inst for inst, d in per_inst.items() if not d["tradeable"]],
        key=lambda x: per_inst[x]["avg_pos"],
    )

    return {
        "n_instruments": n_inst,
        "tradeable_count": tradeable_count,
        "exec_pct": exec_pct,
        "avg_position": avg_pos_all,
        "untradeable": untradeable,
        "lookback_days": min(EXEC_LOOKBACK, len(recent)),
        "per_instrument": per_inst,
    }


def find_latest_sweep_runs():
    """Find the latest run directory for each sweep label."""
    runs = {}
    for d in sorted(RUNS_DIR.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        # Extract label (everything after timestamp)
        parts = name.split("_", 2)
        if len(parts) < 3:
            continue
        label = parts[2]

        # Include sweep runs
        if label in CLASS_MAP:
            meta_file = d / "dashboard_meta.json"
            if meta_file.exists():
                runs[label] = d  # latest wins (sorted order)

        # Include arki_v4_optimized
        if label == "arki_v4_optimized":
            meta_file = d / "dashboard_meta.json"
            if meta_file.exists():
                runs["arki_v4_optimized"] = d

        # Include full25_250k
        if label == "full25_250k":
            meta_file = d / "dashboard_meta.json"
            if meta_file.exists():
                runs["full25_250k"] = d

    # Include $100K 13-instrument Macro Mini run
    for d in sorted(RUNS_DIR.iterdir()):
        if "100k_13inst" in d.name:
            meta_file = d / "dashboard_meta.json"
            if meta_file.exists():
                runs["arki_100k_13inst"] = d

    return runs


def load_equity_curve_weekly(run_dir):
    """Load equity curve and resample to weekly."""
    eq_file = run_dir / "equity_curve.csv"
    if not eq_file.exists():
        return []

    df = pd.read_csv(eq_file, index_col=0, parse_dates=True)
    col = df.columns[0]

    # Cumulative sum to get equity level
    cumulative = df[col].cumsum()

    # Resample to weekly (Friday close)
    weekly = cumulative.resample("W-FRI").last().dropna()

    # Convert to [timestamp_ms, value] pairs
    result = []
    for dt, val in weekly.items():
        ts = int(dt.timestamp() * 1000)
        result.append([ts, round(float(val), 2)])

    return result


def load_rolling_sharpe(run_dir, window_years=3):
    """Compute rolling Sharpe ratio from daily returns.
    Handles both single-column (portfolio P&L) and multi-column (per-instrument) CSVs.
    """
    ret_file = run_dir / "daily_returns.csv"
    if not ret_file.exists():
        return []

    df = pd.read_csv(ret_file, index_col=0, parse_dates=True)

    # If multi-column (per-instrument), sum to get portfolio daily P&L
    if len(df.columns) > 1:
        returns = df.sum(axis=1)
    else:
        returns = df.iloc[:, 0]
    returns = returns.dropna()

    # Need enough data for the rolling window
    window = int(window_years * 252)
    if len(returns) < window + 60:
        return []

    rolling_mean = returns.rolling(window).mean() * 252
    rolling_std = returns.rolling(window).std() * (252 ** 0.5)
    rolling_sr = (rolling_mean / rolling_std).dropna()

    # Resample to monthly
    monthly = rolling_sr.resample("M").last().dropna()

    result = []
    for dt, val in monthly.items():
        ts = int(dt.timestamp() * 1000)
        result.append([ts, round(float(val), 3)])

    return result


def main():
    runs = find_latest_sweep_runs()
    print(f"Found {len(runs)} runs to process")

    summary = {"runs": [], "generated": datetime.now().isoformat()}

    # Process sweep runs in a logical order
    order = [
        "arki_100k_13inst",
        "sweep_base", "sweep_Ags", "sweep_FX", "sweep_Metals",
        "sweep_Ags_FX", "sweep_Ags_Metals", "sweep_FX_Metals",
        "sweep_Ags_FX_Metals", "arki_v4_optimized", "full25_250k",
    ]

    for label in order:
        if label not in runs:
            print(f"  ⚠️ Missing: {label}")
            continue

        run_dir = runs[label]
        meta_file = run_dir / "dashboard_meta.json"
        with open(meta_file) as f:
            meta = json.load(f)

        stats = meta.get("stats", {})
        instruments = meta.get("instruments", [])

        # Get display info
        if label == "arki_100k_13inst":
            display_label = CLASS_MAP[label]["label"]
            classes = CLASS_MAP[label]["classes"]
            is_baseline = False
        else:
            display_label = CLASS_MAP[label]["label"]
            classes = CLASS_MAP[label]["classes"]
            is_baseline = False

        print(f"  Processing {label} ({run_dir.name})...")

        # Load equity curve (weekly)
        equity = load_equity_curve_weekly(run_dir)
        print(f"    Equity: {len(equity)} weekly points")

        # Load rolling Sharpe
        rolling_sr = load_rolling_sharpe(run_dir)
        print(f"    Rolling SR: {len(rolling_sr)} monthly points")

        run_data = {
            "id": label,
            "label": display_label,
            "classes": classes,
            "is_baseline": is_baseline,
            "n_instruments": len(instruments),
            "capital": float(meta.get("meta", {}).get("capital", 0)),
            "sharpe": float(stats.get("sharpe", 0)),
            "ann_return": float(stats.get("ann_mean", 0)),
            "ann_vol": float(stats.get("ann_std", 0)),
            "sortino": float(stats.get("sortino", 0)),
            "avg_drawdown": float(stats.get("avg_drawdown", 0)),
            "max_drawdown": float(stats["min"]) if "min" in stats else None,
            "skew": float(stats.get("skew", 0)),
            "calmar": float(stats.get("calmar", 0)),
            "equity_weekly": equity,
            "rolling_sharpe_3y": rolling_sr,
        }

        # Compute capital efficiency from actual positions
        eff = compute_capital_efficiency(run_dir)
        if eff:
            run_data["tradeable_count"] = eff["tradeable_count"]
            run_data["exec_pct"] = eff["exec_pct"]
            run_data["avg_position"] = eff["avg_position"]
            run_data["untradeable"] = eff["untradeable"]
            run_data["exec_lookback"] = eff["lookback_days"]
            print(f"    Executability: {eff['tradeable_count']}/{eff['n_instruments']} tradeable ({eff['exec_pct']}%, 5Y avg|pos|≥0.5)")
        else:
            print(f"    Executability: N/A (missing data)")

        summary["runs"].append(run_data)

    # Compute marginal contributions
    base_sr = next((r["sharpe"] for r in summary["runs"] if r["id"] == "sweep_base"), 0)
    no_energy_sr = next((r["sharpe"] for r in summary["runs"] if r["id"] == "sweep_Ags_FX_Metals"), 0)
    full_sr = next((r["sharpe"] for r in summary["runs"] if r["id"] == "arki_v4_optimized"), 0)
    marginal = []
    for cls_name, single_label in [("Ags", "sweep_Ags"), ("FX", "sweep_FX"), ("Metals", "sweep_Metals")]:
        single_sr = next((r["sharpe"] for r in summary["runs"] if r["id"] == single_label), 0)
        marginal.append({
            "class": cls_name,
            "contribution": round(single_sr - base_sr, 4),
        })
    # Energy marginal = Full25 SR - (Ags+FX+Metals without Energy)
    marginal.append({
        "class": "Energy",
        "contribution": round(full_sr - no_energy_sr, 4),
    })
    summary["marginal_contributions"] = sorted(marginal, key=lambda x: x["contribution"], reverse=True)

    # Sort runs by Sharpe (descending)
    summary["runs"].sort(key=lambda x: x["sharpe"], reverse=True)

    # Write output
    output_path = DASHBOARD_DATA / "sweep_summary.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, separators=(",", ":"))

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\n✅ Written to {output_path} ({size_mb:.1f} MB)")
    print(f"   {len(summary['runs'])} runs, {sum(len(r['equity_weekly']) for r in summary['runs'])} total equity points")


if __name__ == "__main__":
    main()
