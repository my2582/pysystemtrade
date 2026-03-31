#!/usr/bin/env python3
"""
Static Instrument Selection for Small Accounts

Uses pysystemtrade's find_best_ordered_set_of_instruments() to find
the optimal instrument subset for a given capital level.

IMPORTANT: Uses FIXED forecast weights (not estimated) for speed.
The static optimizer only needs subsystem P&L to compute instrument
correlations and net SR. Estimated forecast weights make this O(n²)
and take hours. Fixed equal weights give the same instrument ranking.

Usage:
    python scripts/static_instrument_selection.py --capital 200000
"""

import argparse
import os
import sys
import time
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")

import logging
import syslogging

logging.basicConfig(level=logging.WARNING, format="%(message)s")
syslogging.logging_configured = True


def build_3factor_system_fixed():
    """Build a system with FIXED forecast weights for fast static optimization."""
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
    from sysdata.config.configdata import Config
    from systems.forecasting import Rules
    from systems.basesystem import System
    from systems.forecast_combine import ForecastCombine
    from systems.forecast_scale_cap import ForecastScaleCap
    from systems.rawdata import RawData
    from systems.positionsizing import PositionSizing
    from systems.portfolio import Portfolios
    from systems.accounts.accounts_stage import Account

    data = csvFuturesSimData()

    # Use pre-computed forecast scalars from Rob's system (no estimation needed)
    config_dict = {
        "trading_rules": {
            # --- Trend-Following (EWMAC) ---
            "momentum4": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": [
                    "rawdata.get_daily_prices",
                    "rawdata.daily_returns_volatility",
                ],
                "other_args": {"Lfast": 4, "Lslow": 16},
            },
            "momentum8": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": [
                    "rawdata.get_daily_prices",
                    "rawdata.daily_returns_volatility",
                ],
                "other_args": {"Lfast": 8, "Lslow": 32},
            },
            "momentum16": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": [
                    "rawdata.get_daily_prices",
                    "rawdata.daily_returns_volatility",
                ],
                "other_args": {"Lfast": 16, "Lslow": 64},
            },
            "momentum32": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": [
                    "rawdata.get_daily_prices",
                    "rawdata.daily_returns_volatility",
                ],
                "other_args": {"Lfast": 32, "Lslow": 128},
            },
            "momentum64": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": [
                    "rawdata.get_daily_prices",
                    "rawdata.daily_returns_volatility",
                ],
                "other_args": {"Lfast": 64, "Lslow": 256},
            },
            # --- Carry ---
            "carry30": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 30},
            },
            "carry60": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 60},
            },
            "carry125": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 125},
            },
            # --- Cross-Sectional Momentum ---
            "relmomentum20": {
                "function": "systems.provided.rules.rel_mom.relative_momentum",
                "data": [
                    "rawdata.get_cumulative_daily_vol_normalised_returns",
                    "rawdata.normalised_price_for_asset_class",
                ],
                "other_args": {"horizon": 20},
            },
            "relmomentum40": {
                "function": "systems.provided.rules.rel_mom.relative_momentum",
                "data": [
                    "rawdata.get_cumulative_daily_vol_normalised_returns",
                    "rawdata.normalised_price_for_asset_class",
                ],
                "other_args": {"horizon": 40},
            },
            "relmomentum80": {
                "function": "systems.provided.rules.rel_mom.relative_momentum",
                "data": [
                    "rawdata.get_cumulative_daily_vol_normalised_returns",
                    "rawdata.normalised_price_for_asset_class",
                ],
                "other_args": {"horizon": 80},
            },
            # --- Cross-Sectional Carry ---
            "relcarry": {
                "function": "systems.provided.rules.carry.relative_carry",
                "data": [
                    "rawdata.smoothed_carry",
                    "rawdata.median_carry_for_asset_class",
                ],
            },
        },
        # FIXED scalars and weights for SPEED
        # (Rob's production scalars for these rule types)
        "forecast_scalars": {
            "momentum4": 12.1,
            "momentum8": 8.53,
            "momentum16": 5.95,
            "momentum32": 4.1,
            "momentum64": 2.72,
            "carry30": 14.0,
            "carry60": 11.0,
            "carry125": 7.5,
            "relmomentum20": 12.2,
            "relmomentum40": 8.3,
            "relmomentum80": 5.5,
            "relcarry": 30.0,
        },
        # FIXED equal weights across all factors
        "forecast_weights": {
            "momentum4": 0.05,
            "momentum8": 0.10,
            "momentum16": 0.10,
            "momentum32": 0.10,
            "momentum64": 0.10,
            "carry30": 0.10,
            "carry60": 0.10,
            "carry125": 0.10,
            "relmomentum20": 0.05,
            "relmomentum40": 0.05,
            "relmomentum80": 0.05,
            "relcarry": 0.10,
        },
        "forecast_div_multiplier": 1.35,
        # DO NOT estimate anything for Phase 1
        "use_forecast_scale_estimates": False,
        "use_forecast_weight_estimates": False,
        "use_forecast_div_mult_estimates": False,
        "use_instrument_weight_estimates": True,  # needed for correlation matrix
        "use_instrument_div_mult_estimates": True,
        # Sizing
        "percentage_vol_target": 25.0,
        "base_currency": "USD",
    }

    config = Config(config_dict)

    system = System(
        [
            Account(),
            Portfolios(),
            PositionSizing(),
            RawData(),
            ForecastCombine(),
            ForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )

    return system


def run_static_selection(capital, output_path=None):
    """Run the static instrument selection optimizer."""
    from systems.provided.static_small_system_optimise.optimise_small_system import (
        find_best_ordered_set_of_instruments,
    )

    print(f"\n{'='*70}")
    print(f"  STATIC INSTRUMENT SELECTION")
    print(f"  Capital: ${capital:,.0f}")
    print(f"  Mode: FIXED forecast weights (fast)")
    print(f"{'='*70}\n")

    print("Building 3-factor system...")
    t0 = time.time()
    system = build_3factor_system_fixed()
    print(f"  System built in {time.time() - t0:.1f}s")
    print(f"  Available instruments: {len(system.data.get_instrument_list())}")

    print(f"\nPre-caching subsystem P&L for instrument selection...")
    t1 = time.time()
    # Pre-cache combined forecasts for all instruments
    # This is the expensive step, but only done ONCE
    all_instruments = system.portfolio.get_instrument_list(
        for_instrument_weights=True, auto_remove_bad_instruments=True
    )
    print(f"  Valid instruments: {len(all_instruments)}")

    print(f"\nRunning greedy instrument selection (capital=${capital:,.0f})...")
    print(f"  Adding instruments one-by-one, tracking portfolio SR.\n")

    optimal_set = find_best_ordered_set_of_instruments(
        system,
        capital=capital,
        max_instrument_weight=0.05,
        notional_starting_IDM=1.0,
    )
    elapsed = time.time() - t0

    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}")
    print(f"  Optimal instrument count: {len(optimal_set)}")
    print(f"  Selection time: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"\n  Instruments (in selection order):")
    for i, inst in enumerate(optimal_set, 1):
        print(f"    {i:3d}. {inst}")

    # Save results
    result = {
        "capital": capital,
        "vol_target_pct": 25.0,
        "instrument_count": len(optimal_set),
        "instruments": optimal_set,
        "factors": ["trend_following", "carry", "cross_sectional_momentum", "relative_carry"],
    }

    default_path = PROJECT_ROOT / "results" / "optimal_instruments_200k.yaml"
    os.makedirs(default_path.parent, exist_ok=True)
    with open(default_path, "w") as f:
        yaml.dump(result, f, default_flow_style=False, sort_keys=False)
    print(f"\n  💾 Saved to: {default_path}")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(result, f, default_flow_style=False, sort_keys=False)
        print(f"  💾 Also saved to: {output_path}")

    print(f"\n{'='*70}\n")
    return optimal_set


def main():
    parser = argparse.ArgumentParser(
        description="Static Instrument Selection for Small Accounts",
    )
    parser.add_argument("--capital", type=float, default=200000)
    parser.add_argument("--output", type=str, help="Output YAML file path")
    args = parser.parse_args()
    run_static_selection(args.capital, args.output)


if __name__ == "__main__":
    main()
