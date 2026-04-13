#!/usr/bin/env python3
"""
Generate a pure, static reference dictionary for all available instruments.
This script produces `arki_universe_info.json`, which acts merely as a lookup table
for instrument metadata (Pointsize, AssetClass, Currency, etc.).

It does not contain any stateful flags (e.g., `in_mf`, `in_13`) like the old implementation did.
The dashboard frontend will join this static dictionary with the active run's metadata 
(`state.meta.instruments`) to render the Universe tab contextually.
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
        
        # Best effort to fetch latest price for nominal calculation
        price_file = PROJECT_ROOT / "data" / "futures" / "multiple_prices_csv" / f"{inst}.csv"
        latest_price = None
        if price_file.exists():
            try:
                pdf = pd.read_csv(price_file)
                if "PRICE" in pdf.columns:
                    latest_price = pdf["PRICE"].dropna().iloc[-1]
            except Exception:
                pass
                
        pointsize = float(r.get("Pointsize", 1))
        nominal = round(latest_price * pointsize, 0) if latest_price else None
        
        # Append pure metadata. Note: NO 'in_mf' or run-specific flags here.
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
