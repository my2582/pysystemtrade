#!/usr/bin/env python3
"""
Generate a pure, static reference dictionary for all available instruments.
This script produces `arki_universe_info.json`, which acts solely as a lookup table
for immutable instrument specifications (Pointsize, AssetClass, Currency, Description).

It deliberately excludes runtime-dependent values like latest_price and nominal_value.
Those are calculated at backtest time via system.data and exported per-run by
backtest_runner.py (see position_snapshot.csv, spread_costs.csv).
"""

import json
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "scripts" / "dashboard"
INST_CONFIG = PROJECT_ROOT / "data" / "futures" / "csvconfig" / "instrumentconfig.csv"
IB_CONFIG = PROJECT_ROOT / "sysbrokers" / "IB" / "config" / "ib_config_futures.csv"

def build_pure_universe_dict():
    """Builds a static dictionary of instrument metadata."""
    print(f"Loading configurations...")
    cfg = pd.read_csv(INST_CONFIG)
    ibcfg = pd.read_csv(IB_CONFIG) if IB_CONFIG.exists() else pd.DataFrame()
    
    # We want to build the dictionary for all instruments that exist in config
    all_instruments = sorted(cfg["Instrument"].tolist())
    
    universe = []
    print(f"Building dictionary for {len(all_instruments)} instruments...")
    
    for inst in all_instruments:
        row = cfg[cfg["Instrument"] == inst]
        if len(row) == 0:
            continue
        r = row.iloc[0]
        
        # Determine IB details
        ib = ibcfg[ibcfg["Instrument"] == inst] if len(ibcfg) > 0 else pd.DataFrame()
        ib_symbol = ib["IBSymbol"].values[0] if len(ib) > 0 else ""
        ib_exchange = ib["IBExchange"].values[0] if len(ib) > 0 else ""

        pointsize = float(r.get("Pointsize", 1))

        # Immutable specs only. No latest_price / nominal_value.
        universe.append({
            "instrument": inst,
            "ib_symbol": ib_symbol,
            "ib_exchange": ib_exchange,
            "description": r.get("Description", ""),
            "asset_class": r.get("AssetClass", ""),
            "currency": r.get("Currency", ""),
            "pointsize": pointsize,
        })
        
    return universe

def main():
    universe = build_pure_universe_dict()
    
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DASHBOARD_DIR / "arki_universe_info.json"
    
    with open(out_path, "w") as f:
        json.dump(universe, f, indent=2)
        
    print(f"\n✅ Pure Reference Dictionary Generated: {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
    print(f"   Total instruments captured: {len(universe)}")

if __name__ == "__main__":
    main()
