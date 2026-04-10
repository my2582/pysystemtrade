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
    "arki_v4_optimized": {"label": "Full 25 (+ Energy)", "classes": ["Equity", "Bond", "Ags", "FX", "Metals", "Energy"]},
    "arki_100k_13inst": {"label": "$100K Macro Mini (13 inst)", "classes": ["Equity", "Bond", "Metals", "OilGas", "Ags"]},
}

VOL_TARGET_DEFAULT = 25.0  # annual % vol target
POSITION_LOOKBACK = 256  # trading days for position analysis


def compute_capital_efficiency(run_dir):
    """
    Compute capital efficiency metrics from actual backtest positions.

    Instead of a theoretical formula, we measure how efficiently the
    capital is being used by analyzing the actual rounded (integer)
    positions from the backtest. This gives a ground-truth answer to
    "can this universe be traded with this capital?"

    Metrics:
    - active_count: instruments actively traded (>50% of days non-zero)
    - active_pct: active_count / total instruments
    - avg_position: average absolute position across all instruments
    - min_capital_est: estimated min capital via subsystem position scaling

    Returns: dict with efficiency metrics, or None if data missing.
    """
    run_dir = Path(run_dir)

    rp_file = run_dir / "rounded_positions.csv"
    sp_file = run_dir / "subsystem_positions.csv"
    np_file = run_dir / "notional_positions.csv"
    iw_file = run_dir / "instrument_weights.csv"

    if not rp_file.exists():
        return None

    rp = pd.read_csv(rp_file, index_col=0, parse_dates=True)
    recent = rp.tail(POSITION_LOOKBACK)
    n_inst = len(rp.columns)

    if n_inst == 0:
        return None

    # Read config for capital
    config_file = run_dir / "config.yaml"
    capital = 200000
    if config_file.exists():
        try:
            with open(config_file) as f:
                cfg = yaml.safe_load(f)
            capital = float(cfg.get("capital", 200000))
        except Exception:
            pass

    # Per-instrument activity analysis from actual positions
    per_inst = {}
    active_count = 0
    total_avg_pos = 0.0

    for inst in rp.columns:
        col = recent[inst].dropna()
        if len(col) == 0:
            per_inst[inst] = {"active_pct": 0, "avg_pos": 0}
            continue

        pct_active = (col != 0).mean()
        avg_pos = col.abs().mean()

        per_inst[inst] = {
            "active_pct": round(pct_active * 100, 1),
            "avg_pos": round(avg_pos, 2),
        }

        if pct_active > 0.50:
            active_count += 1
        total_avg_pos += avg_pos

    active_pct = round(active_count / n_inst * 100, 1) if n_inst > 0 else 0
    avg_pos = round(total_avg_pos / n_inst, 2) if n_inst > 0 else 0

    # Estimate minimum capital using subsystem position scaling
    # vol_scalar ∝ capital, so min_capital = capital × (0.5 / avg_notional_pos)
    # where avg_notional_pos is from the actual backtest
    min_capital_est = None
    if all(f.exists() for f in [sp_file, np_file, iw_file]):
        try:
            sp = pd.read_csv(sp_file, index_col=0, parse_dates=True)
            np_df = pd.read_csv(np_file, index_col=0, parse_dates=True)
            iw = pd.read_csv(iw_file, index_col=0, parse_dates=True)

            last_w = iw.dropna(how="all").iloc[-1]

            # Derive IDM × risk_overlay
            thresh_sp = max(1, int(len(sp.columns) * 0.5))
            thresh_np = max(1, int(len(np_df.columns) * 0.5))
            sp_recent_df = sp.dropna(thresh=thresh_sp)
            np_recent_df = np_df.dropna(thresh=thresh_np)

            if len(sp_recent_df) > 0 and len(np_recent_df) > 0:
                sp_row = sp_recent_df.iloc[-1]
                np_row = np_recent_df.iloc[-1]

                idm_ro = None
                for inst_name in sp.columns:
                    s_val = sp_row.get(inst_name, np.nan)
                    n_val = np_row.get(inst_name, np.nan)
                    w_val = last_w.get(inst_name, np.nan)
                    if (
                        pd.notna(s_val) and pd.notna(n_val) and pd.notna(w_val)
                        and s_val != 0 and w_val != 0
                    ):
                        idm_ro = n_val / (s_val * w_val)
                        break

                if idm_ro and idm_ro > 0:
                    # avg |subsys_pos| over lookback ≈ vol_scalar (at avg forecast)
                    avg_subsys = sp.abs().tail(POSITION_LOOKBACK).mean()

                    # For each instrument, min_capital = capital × (0.5/(IDM×w)) / avg|subsys|
                    inst_min_caps = {}
                    for inst_name in sp.columns:
                        w_val = last_w.get(inst_name, np.nan)
                        avg_s = avg_subsys.get(inst_name, 0)
                        if pd.isna(w_val) or w_val == 0 or avg_s == 0:
                            continue
                        vs_needed = 0.5 / (idm_ro * w_val)
                        inst_min_caps[inst_name] = round(capital * vs_needed / avg_s)

                    if inst_min_caps:
                        # Use the P75 percentile as "practical min capital"
                        # (not all instruments need to be active simultaneously)
                        vals = sorted(inst_min_caps.values())
                        p75_idx = int(len(vals) * 0.75)
                        min_capital_est = vals[p75_idx] if p75_idx < len(vals) else vals[-1]
        except Exception:
            pass

    return {
        "n_instruments": n_inst,
        "active_count": active_count,
        "active_pct": active_pct,
        "avg_position": avg_pos,
        "min_capital_est": min_capital_est,
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

    # Also include v6 handcraft as baseline
    for d in sorted(RUNS_DIR.iterdir()):
        if "v6_handcraft" in d.name:
            meta_file = d / "dashboard_meta.json"
            if meta_file.exists():
                runs["v6_handcraft"] = d

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
        "sweep_Ags_FX_Metals", "arki_v4_optimized", "v6_handcraft",
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
        if label == "v6_handcraft":
            display_label = "Production (25, Handcraft)"
            classes = ["Equity", "Bond", "Ags", "FX", "Metals", "OilGas"]
            is_baseline = True
        elif label == "arki_100k_13inst":
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
            run_data["active_count"] = eff["active_count"]
            run_data["active_pct"] = eff["active_pct"]
            run_data["avg_position"] = eff["avg_position"]
            run_data["min_capital_est"] = eff["min_capital_est"]
            print(f"    Executability: {eff['active_count']}/{eff['n_instruments']} active ({eff['active_pct']}%), avg|pos|={eff['avg_position']}")
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
