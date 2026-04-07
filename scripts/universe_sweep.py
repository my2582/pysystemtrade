#!/usr/bin/env python3
"""
Universe Sweep: systematically test asset class combinations.

Fixed:   Equity (7) + Bond (5) = 12 instruments
Removed: OilGas (3) always excluded
Variable: Ags (4), FX (3), Metals (3) — all 2^3 = 8 combinations

Usage:
    python scripts/universe_sweep.py
    python scripts/universe_sweep.py --dry-run     # preview only
    python scripts/universe_sweep.py --compare     # compare existing results only
"""
import yaml
import subprocess
import sys
import itertools
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_CONFIG = PROJECT_ROOT / "scripts" / "backtest_config" / "arki_production.yaml"
SWEEP_DIR = PROJECT_ROOT / "scripts" / "backtest_config" / "sweep"
RESULTS_DIR = PROJECT_ROOT / "results" / "runs"

# ── Asset class definitions ──────────────────────────────────────────────────
FIXED = {
    "Equity": ["SP500_micro", "NASDAQ_micro", "DAX", "NIKKEI", "FTSE100", "IBEX_mini", "FTSECHINAA"],
    "Bond": ["US10", "US5", "BUND", "GILT", "JGB"],
}

EXCLUDED = {
    "OilGas": ["CRUDE_W", "BRENT-LAST", "GASOIL"],
}

VARIABLE = {
    "Ags": ["COCOA_LDN", "SUGAR11", "COTTON", "LEANHOG"],
    "FX": ["AUD_micro", "MXP", "YENEUR"],
    "Metals": ["GOLD_micro", "SILVER", "COPPER-micro"],
}


def generate_combinations():
    """Generate all 2^N combinations of variable asset classes."""
    variable_names = sorted(VARIABLE.keys())
    combos = []
    for r in range(len(variable_names) + 1):
        for included in itertools.combinations(variable_names, r):
            excluded_var = [v for v in variable_names if v not in included]
            label_parts = list(included) if included else ["base"]
            label = "sweep_" + "_".join(label_parts)
            
            instruments = []
            for cls_instruments in FIXED.values():
                instruments.extend(cls_instruments)
            for cls in included:
                instruments.extend(VARIABLE[cls])
            
            combos.append({
                "label": label,
                "included": list(included),
                "excluded": list(excluded_var) + list(EXCLUDED.keys()),
                "instruments": sorted(instruments),
                "count": len(instruments),
            })
    return combos


def generate_config(combo, base_config_data):
    """Generate a sweep config YAML from the base config."""
    cfg = dict(base_config_data)
    cfg["instruments"] = combo["instruments"]
    
    # Update instrument_weights to equal weight
    n = len(combo["instruments"])
    weight = round(1.0 / n, 6)
    cfg["instrument_weights"] = {inst: weight for inst in combo["instruments"]}
    
    return cfg


def run_backtest(label, config_path):
    """Run a single backtest and return the result."""
    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts" / "backtest_runner.py"),
        "run",
        "--label", label,
        "--capital", "200000",
        "--mode", "dynamic",
        "--config", str(config_path),
    ]
    print(f"\n{'='*70}")
    print(f"  Running: {label}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode == 0


def load_results():
    """Load results from existing sweep runs."""
    results = []
    for run_dir in sorted(RESULTS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        if "sweep_" not in run_dir.name:
            continue
        meta_file = run_dir / "dashboard_meta.json"
        if meta_file.exists():
            import json
            with open(meta_file) as f:
                meta = json.load(f)
            results.append({
                "run_id": run_dir.name,
                "label": "_".join(run_dir.name.split("_")[2:]),  # strip timestamp
                **meta.get("stats", {}),
                "instruments": len(meta.get("instruments", [])),
            })
    return results


def print_comparison(results):
    """Print a formatted comparison table."""
    if not results:
        print("No sweep results found.")
        return
    
    print(f"\n{'='*90}")
    print(f"  UNIVERSE SWEEP COMPARISON")
    print(f"{'='*90}")
    print(f"  {'Label':<30} {'#Inst':>5} {'SR':>7} {'Return':>8} {'Vol':>7} {'MaxDD':>8} {'Sortino':>8}")
    print(f"  {'-'*30} {'-'*5} {'-'*7} {'-'*8} {'-'*7} {'-'*8} {'-'*8}")
    
    # Sort by Sharpe
    results_sorted = sorted(results, key=lambda x: float(x.get("sharpe", 0)), reverse=True)
    
    for r in results_sorted:
        label = r["label"]
        n = r["instruments"]
        sr = float(r.get("sharpe", 0))
        ret = float(r.get("ann_mean", 0))
        vol = float(r.get("ann_std", 0))
        dd = float(r.get("avg_drawdown", 0))
        sortino = float(r.get("sortino", 0))
        
        marker = " ★" if sr == max(float(x.get("sharpe", 0)) for x in results_sorted) else ""
        print(f"  {label:<30} {n:>5} {sr:>7.3f} {ret:>7.1f}% {vol:>6.1f}% {dd:>7.1f}% {sortino:>8.3f}{marker}")
    
    print(f"\n  ★ = Best Sharpe Ratio")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Universe sweep backtest")
    parser.add_argument("--dry-run", action="store_true", help="Preview combinations only")
    parser.add_argument("--compare", action="store_true", help="Compare existing results only")
    args = parser.parse_args()
    
    combos = generate_combinations()
    
    if args.compare:
        results = load_results()
        print_comparison(results)
        return
    
    # Preview
    print(f"\n{'='*70}")
    print(f"  UNIVERSE SWEEP PLAN")
    print(f"{'='*70}")
    print(f"  Fixed:    Equity (7) + Bond (5) = 12 instruments")
    print(f"  Excluded: OilGas (3)")
    print(f"  Variable: Ags (4), FX (3), Metals (3)")
    print(f"  Total combinations: {len(combos)}")
    print(f"{'='*70}")
    
    for i, c in enumerate(combos, 1):
        incl = ", ".join(c["included"]) if c["included"] else "(none)"
        excl = ", ".join(c["excluded"])
        print(f"  {i}. {c['label']:<30} {c['count']:>2} inst  | +{incl}  | -{excl}")
    
    if args.dry_run:
        print(f"\n  (Dry run — no backtests executed)")
        return
    
    # Load base config
    with open(BASE_CONFIG) as f:
        base_cfg = yaml.safe_load(f)
    
    # Create sweep directory
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run all combinations
    start_time = datetime.now()
    succeeded = 0
    failed = 0
    
    for i, combo in enumerate(combos, 1):
        print(f"\n  [{i}/{len(combos)}] Preparing {combo['label']}...")
        
        # Generate config
        cfg = generate_config(combo, base_cfg)
        config_path = SWEEP_DIR / f"{combo['label']}.yaml"
        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        
        # Run backtest
        success = run_backtest(combo["label"], config_path)
        if success:
            succeeded += 1
        else:
            failed += 1
            print(f"  ⚠️ {combo['label']} failed")
    
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n{'='*70}")
    print(f"  SWEEP COMPLETE: {succeeded} succeeded, {failed} failed ({elapsed:.1f} min)")
    print(f"{'='*70}")
    
    # Show comparison
    results = load_results()
    print_comparison(results)


if __name__ == "__main__":
    main()
