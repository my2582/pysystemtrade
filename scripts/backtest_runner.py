#!/usr/bin/env python3
"""
Multi-Run Backtest Framework

Wraps run_dynamic_backtest.py with:
  - Run registry (results/runs/registry.yaml)
  - Versioned output (results/runs/{run_id}/)
  - Enhanced data export (factor returns, forecast weights, turnover, rolling stats)
  - Comparison CLI (--compare run1 run2)

Usage:
    # Run a new backtest with label
    python scripts/backtest_runner.py run --label "baseline" --capital 200000

    # Run with custom vol target
    python scripts/backtest_runner.py run --label "vol20" --capital 200000 --vol-target 20

    # List all runs
    python scripts/backtest_runner.py list

    # Compare two runs
    python scripts/backtest_runner.py compare baseline vol20

    # Re-export enhanced data for existing run
    python scripts/backtest_runner.py export --run-id 20260331_1845_baseline

    # Serve dashboard
    python scripts/backtest_runner.py dashboard [--run-id ...]
"""
import argparse
import os
import sys
import time
import shutil
import yaml
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")

RUNS_DIR = PROJECT_ROOT / "results" / "runs"
REGISTRY_PATH = RUNS_DIR / "registry.yaml"


def load_registry():
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return yaml.safe_load(f) or {"runs": []}
    return {"runs": []}


def save_registry(registry):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False)


def generate_run_id(label):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    safe_label = label.replace(" ", "_").replace("/", "-")[:30]
    return f"{ts}_{safe_label}"


def find_run(registry, identifier):
    """Find run by id or label (partial match)."""
    for run in registry["runs"]:
        if run["id"] == identifier or run.get("label") == identifier:
            return run
    # Partial match
    for run in registry["runs"]:
        if identifier in run["id"] or identifier in run.get("label", ""):
            return run
    return None


# ──────────────────────────────────────────────────────────────────
# Enhanced Data Export
# ──────────────────────────────────────────────────────────────────

def export_enhanced_data(system, instruments, run_dir):
    """Export extended CSVs for dashboard consumption."""
    import pandas as pd
    import numpy as np
    import warnings
    warnings.filterwarnings("ignore")

    print("  Exporting enhanced data...")

    # 1. Factor returns (per trading rule P&L)
    print("    Factor returns...", end=" ", flush=True)
    try:
        rule_names = list(system.rules.trading_rules().keys())
        factor_dict = {}
        for rule in rule_names:
            try:
                pnl = system.accounts.pandl_for_trading_rule(rule)
                factor_dict[rule] = pnl.percent
            except Exception:
                pass
        if factor_dict:
            factor_df = pd.DataFrame(factor_dict)
            factor_df.to_csv(run_dir / "factor_returns.csv")
            print(f"✅ ({len(factor_dict)} rules)")
        else:
            print("⚠️ no data")
    except Exception as e:
        print(f"❌ {e}")

    # 2. All forecast weights
    print("    Forecast weights...", end=" ", flush=True)
    try:
        fw_all = {}
        for code in instruments:
            try:
                fw = system.combForecast.get_forecast_weights(code)
                fw_last = fw.iloc[-1]
                fw_all[code] = fw_last.to_dict()
            except Exception:
                pass
        if fw_all:
            fw_df = pd.DataFrame(fw_all).T
            fw_df.index.name = "instrument"
            fw_df.to_csv(run_dir / "forecast_weights.csv")
            print(f"✅ ({len(fw_all)} instruments)")
        else:
            print("⚠️ no data")
    except Exception as e:
        print(f"❌ {e}")

    # 3. Turnover
    print("    Turnover...", end=" ", flush=True)
    try:
        turnover_data = []
        for code in instruments:
            try:
                t = system.accounts.instrument_turnover(code)
                turnover_data.append({"instrument": code, "annualized_turnover": round(float(t), 4)})
            except Exception:
                pass
        if turnover_data:
            pd.DataFrame(turnover_data).to_csv(run_dir / "turnover.csv", index=False)
            print(f"✅ ({len(turnover_data)} instruments)")
        else:
            print("⚠️ no data")
    except Exception as e:
        print(f"❌ {e}")

    # 4. Rolling stats
    print("    Rolling stats...", end=" ", flush=True)
    try:
        ret = pd.read_csv(run_dir / "daily_returns.csv", index_col=0, parse_dates=True)
        port_ret = ret.sum(axis=1)

        rolling = pd.DataFrame(index=port_ret.index)
        for window_days, label in [(256, "1Y"), (256 * 3, "3Y"), (256 * 5, "5Y")]:
            roll_mean = port_ret.rolling(window_days, min_periods=window_days // 2).mean() * 256
            roll_std = port_ret.rolling(window_days, min_periods=window_days // 2).std() * (256 ** 0.5)
            rolling[f"ann_return_{label}"] = roll_mean
            rolling[f"ann_vol_{label}"] = roll_std
            rolling[f"sharpe_{label}"] = roll_mean / roll_std

        # Portfolio equity curve (cumulative)
        rolling["cumulative_return"] = (1 + port_ret / 100).cumprod() - 1
        rolling["cumulative_return_pct"] = rolling["cumulative_return"] * 100

        # Drawdown
        wealth = (1 + port_ret / 100).cumprod()
        running_max = wealth.cummax()
        rolling["drawdown_pct"] = (wealth / running_max - 1) * 100

        rolling.to_csv(run_dir / "rolling_stats.csv")
        print(f"✅")
    except Exception as e:
        print(f"❌ {e}")

    # 5. Subsystem positions
    print("    Subsystem positions...", end=" ", flush=True)
    try:
        subsys = {}
        for code in instruments:
            try:
                pos = system.positionSize.get_subsystem_position(code)
                subsys[code] = pos
            except Exception:
                pass
        if subsys:
            pd.DataFrame(subsys).to_csv(run_dir / "subsystem_positions.csv")
            print(f"✅ ({len(subsys)} instruments)")
        else:
            print("⚠️ no data")
    except Exception as e:
        print(f"❌ {e}")

    # 6. Config snapshot as JSON (for dashboard)
    print("    Config JSON...", end=" ", flush=True)
    try:
        with open(run_dir / "stats.yaml") as f:
            stats = yaml.safe_load(f)

        # Build dashboard-ready JSON
        dashboard_data = {
            "meta": {
                "capital": stats.get("capital", 200000),
                "mode": stats.get("mode", "dynamic"),
                "period": stats.get("period", ""),
                "years": stats.get("years", 0),
                "instrument_count": len(instruments),
            },
            "stats": stats.get("stats", {}),
            "instruments": instruments,
        }
        with open(run_dir / "dashboard_meta.json", "w") as f:
            json.dump(dashboard_data, f, indent=2)
        print("✅")
    except Exception as e:
        print(f"❌ {e}")


# ──────────────────────────────────────────────────────────────────
# Core Commands
# ──────────────────────────────────────────────────────────────────

def cmd_run(args):
    """Execute a new backtest run."""
    import logging
    import syslogging
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    syslogging.logging_configured = True

    from scripts.run_dynamic_backtest import build_estimated_system, build_dynamic_system, print_report

    run_id = generate_run_id(args.label)
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  BACKTEST RUN: {run_id}")
    print(f"{'='*70}")

    # Load instruments
    instruments = None
    instruments_file = args.instruments_from or "results/optimal_instruments_200k.yaml"
    if os.path.exists(instruments_file):
        with open(instruments_file) as f:
            data = yaml.safe_load(f)
        instruments = data.get("instruments", [])
        print(f"  Instruments: {len(instruments)} from {instruments_file}")

    config_path = args.config or "scripts/backtest_config/trend_carry_csmom_estimated.yaml"
    capital = args.capital
    mode = args.mode
    vol_target = args.vol_target

    # Build system
    t0 = time.time()
    if mode == "dynamic":
        system = build_dynamic_system(config_path, capital, instruments)
    else:
        system = build_estimated_system(config_path, capital, instruments)

    # Override vol target if specified
    if vol_target != 25.0:
        system.config.percentage_vol_target = vol_target

    actual_instruments = system.get_instrument_list()

    # Run and export standard data
    print_report(
        system, mode=mode, capital=capital,
        instruments=actual_instruments,
        elapsed=time.time() - t0,
        report_level="full",
        export_dir=str(run_dir),
    )

    # Enhanced export
    export_enhanced_data(system, actual_instruments, run_dir)

    # Save run config
    config_snapshot = {
        "capital": capital,
        "vol_target": vol_target,
        "mode": mode,
        "config_file": config_path,
        "instruments_file": instruments_file,
        "instruments": actual_instruments,
        "run_id": run_id,
        "label": args.label,
        "timestamp": datetime.now().isoformat(),
    }
    with open(run_dir / "config.yaml", "w") as f:
        yaml.dump(config_snapshot, f, default_flow_style=False, sort_keys=False)

    # Register run
    registry = load_registry()
    with open(run_dir / "stats.yaml") as f:
        stats = yaml.safe_load(f)

    registry["runs"].append({
        "id": run_id,
        "label": args.label,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "capital": capital,
            "vol_target": vol_target,
            "mode": mode,
            "instruments": len(actual_instruments),
            "config_file": config_path,
        },
        "results": {
            "net_sharpe": float(stats["stats"]["sharpe"]),
            "ann_return": float(stats["stats"]["ann_mean"]),
            "ann_vol": float(stats["stats"]["ann_std"]),
            "max_dd": float(stats["stats"]["min"]),
            "sortino": float(stats["stats"]["sortino"]),
            "period": stats["period"],
        },
        "path": str(run_dir.relative_to(PROJECT_ROOT)),
    })
    save_registry(registry)

    print(f"\n  ✅ Run {run_id} complete")
    print(f"  📁 {run_dir}")
    print(f"  📋 Registry updated: {REGISTRY_PATH}")


def cmd_list(args):
    """List all registered runs."""
    registry = load_registry()
    if not registry["runs"]:
        print("No runs registered.")
        return

    print(f"\n{'='*100}")
    print(f"  {'ID':<35} {'Label':<20} {'SR':>6} {'Return%':>8} {'Vol%':>6} {'DD%':>7} {'#Inst':>5} {'Mode':<10}")
    print(f"  {'-'*35} {'-'*20} {'-'*6} {'-'*8} {'-'*6} {'-'*7} {'-'*5} {'-'*10}")

    for run in registry["runs"]:
        r = run.get("results", {})
        c = run.get("config", {})
        print(
            f"  {run['id']:<35} {run.get('label',''):<20} "
            f"{r.get('net_sharpe',0):>6.3f} {r.get('ann_return',0):>7.1f}% "
            f"{r.get('ann_vol',0):>5.1f}% {r.get('max_dd',0):>6.1f}% "
            f"{c.get('instruments',0):>5} {c.get('mode',''):>10}"
        )
    print(f"{'='*100}\n")


def cmd_compare(args):
    """Compare two runs side by side."""
    registry = load_registry()
    run_a = find_run(registry, args.run_a)
    run_b = find_run(registry, args.run_b)

    if not run_a:
        print(f"❌ Run not found: {args.run_a}")
        return
    if not run_b:
        print(f"❌ Run not found: {args.run_b}")
        return

    ra = run_a.get("results", {})
    rb = run_b.get("results", {})
    ca = run_a.get("config", {})
    cb = run_b.get("config", {})

    print(f"\n{'='*70}")
    print(f"  RUN COMPARISON")
    print(f"{'='*70}")
    print(f"  {'Metric':<25} {'Run A':>20} {'Run B':>20} {'Delta':>10}")
    print(f"  {'-'*25} {'-'*20} {'-'*20} {'-'*10}")
    print(f"  {'ID':<25} {run_a['id']:>20} {run_b['id']:>20}")
    print(f"  {'Label':<25} {run_a.get('label',''):>20} {run_b.get('label',''):>20}")
    print(f"  {'Capital':<25} {ca.get('capital',0):>20,.0f} {cb.get('capital',0):>20,.0f}")
    print(f"  {'Vol Target':<25} {ca.get('vol_target',0):>19.0f}% {cb.get('vol_target',0):>19.0f}%")
    print(f"  {'Mode':<25} {ca.get('mode',''):>20} {cb.get('mode',''):>20}")
    print(f"  {'Instruments':<25} {ca.get('instruments',0):>20} {cb.get('instruments',0):>20}")
    print()

    metrics = [
        ("Net Sharpe", "net_sharpe", ".4f"),
        ("Ann Return %", "ann_return", ".2f"),
        ("Ann Vol %", "ann_vol", ".2f"),
        ("Max Drawdown %", "max_dd", ".2f"),
        ("Sortino", "sortino", ".4f"),
    ]
    for label, key, fmt in metrics:
        va = ra.get(key, 0)
        vb = rb.get(key, 0)
        delta = vb - va
        print(f"  {label:<25} {va:>20{fmt}} {vb:>20{fmt}} {delta:>+10{fmt}}")

    print(f"\n{'='*70}\n")


def cmd_dashboard(args):
    """Serve the dashboard."""
    import http.server
    import functools

    dashboard_dir = PROJECT_ROOT / "scripts" / "dashboard"
    if not dashboard_dir.exists():
        print(f"❌ Dashboard not found at {dashboard_dir}")
        return

    # Symlink latest run data
    if args.run_id:
        registry = load_registry()
        run = find_run(registry, args.run_id)
        if run:
            data_link = dashboard_dir / "data"
            target = PROJECT_ROOT / run["path"]
            if data_link.exists() or data_link.is_symlink():
                data_link.unlink()
            data_link.symlink_to(target)
            print(f"  Linked data → {target}")
    else:
        # Use latest run
        registry = load_registry()
        if registry["runs"]:
            latest = registry["runs"][-1]
            data_link = dashboard_dir / "data"
            target = PROJECT_ROOT / latest["path"]
            if data_link.exists() or data_link.is_symlink():
                data_link.unlink()
            data_link.symlink_to(target)
            print(f"  Linked data → {target} (latest)")

    port = args.port or 8080
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(dashboard_dir))
    print(f"\n  🌐 Dashboard: http://127.0.0.1:{port}")
    print(f"  Press Ctrl+C to stop\n")
    with http.server.HTTPServer(("127.0.0.1", port), handler) as httpd:
        httpd.serve_forever()


def cmd_export(args):
    """Re-export enhanced data for an existing run."""
    import logging
    import syslogging
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    syslogging.logging_configured = True

    registry = load_registry()
    run = find_run(registry, args.run_id)
    if not run:
        print(f"❌ Run not found: {args.run_id}")
        return

    run_dir = PROJECT_ROOT / run["path"]
    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        return

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    from scripts.run_dynamic_backtest import build_estimated_system, build_dynamic_system
    instruments = cfg.get("instruments", [])
    mode = cfg.get("mode", "estimated")
    capital = cfg.get("capital", 200000)
    config_file = cfg.get("config_file", "scripts/backtest_config/trend_carry_csmom_estimated.yaml")

    if mode == "dynamic":
        system = build_dynamic_system(config_file, capital, instruments)
    else:
        system = build_estimated_system(config_file, capital, instruments)

    export_enhanced_data(system, instruments, run_dir)
    print(f"\n  ✅ Enhanced data exported to {run_dir}")


def cmd_migrate(args):
    """Migrate existing results/phase3 to the runs structure."""
    phase3_dir = PROJECT_ROOT / "results" / "phase3"
    if not phase3_dir.exists():
        print("No results/phase3 found.")
        return

    run_id = "20260331_1500_baseline_phase3"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for f in phase3_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, run_dir / f.name)

    # Create config
    with open(run_dir / "stats.yaml") as f:
        stats = yaml.safe_load(f)

    config = {
        "capital": 200000,
        "vol_target": 25.0,
        "mode": "dynamic",
        "config_file": "scripts/backtest_config/trend_carry_csmom_estimated.yaml",
        "instruments_file": "results/optimal_instruments_200k.yaml",
        "instruments": stats.get("instruments", []),
        "run_id": run_id,
        "label": "baseline_phase3",
        "timestamp": "2026-03-31T15:00:00+08:00",
    }
    with open(run_dir / "config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Register
    registry = load_registry()
    registry["runs"].append({
        "id": run_id,
        "label": "baseline_phase3",
        "timestamp": "2026-03-31T15:00:00+08:00",
        "config": {
            "capital": 200000,
            "vol_target": 25.0,
            "mode": "dynamic",
            "instruments": len(stats.get("instruments", [])),
            "config_file": "scripts/backtest_config/trend_carry_csmom_estimated.yaml",
        },
        "results": {
            "net_sharpe": float(stats["stats"]["sharpe"]),
            "ann_return": float(stats["stats"]["ann_mean"]),
            "ann_vol": float(stats["stats"]["ann_std"]),
            "max_dd": float(stats["stats"]["min"]),
            "sortino": float(stats["stats"]["sortino"]),
            "period": stats["period"],
        },
        "path": str(run_dir.relative_to(PROJECT_ROOT)),
    })
    save_registry(registry)
    print(f"  ✅ Migrated to {run_dir}")
    print(f"  📋 Registered as {run_id}")


def main():
    parser = argparse.ArgumentParser(description="Multi-Run Backtest Framework")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # run
    p_run = subparsers.add_parser("run", help="Execute a new backtest")
    p_run.add_argument("--label", required=True, help="Human-readable label")
    p_run.add_argument("--capital", type=float, default=200000)
    p_run.add_argument("--vol-target", type=float, default=25.0)
    p_run.add_argument("--mode", choices=["estimated", "dynamic"], default="estimated")
    p_run.add_argument("--config", type=str)
    p_run.add_argument("--instruments-from", type=str)

    # list
    subparsers.add_parser("list", help="List all runs")

    # compare
    p_cmp = subparsers.add_parser("compare", help="Compare two runs")
    p_cmp.add_argument("run_a", help="Run ID or label")
    p_cmp.add_argument("run_b", help="Run ID or label")

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Serve dashboard")
    p_dash.add_argument("--run-id", type=str, help="Run to display")
    p_dash.add_argument("--port", type=int, default=8080)

    # export
    p_exp = subparsers.add_parser("export", help="Re-export enhanced data")
    p_exp.add_argument("--run-id", required=True)

    # migrate
    subparsers.add_parser("migrate", help="Migrate results/phase3 to runs")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "migrate":
        cmd_migrate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
