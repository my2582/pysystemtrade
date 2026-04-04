#!/usr/bin/env python3
"""
pysystemtrade Backtesting CLI

Supports pre-built systems and custom configurations.

Usage:
    # Pre-built systems
    python scripts/backtest.py --system chapter15
    python scripts/backtest.py --system chapter15 --report full
    python scripts/backtest.py --system estimated --instruments SP500_micro,CRUDE_W,GOLD,US10
    python scripts/backtest.py --system rob

    # Custom configurations
    python scripts/backtest.py --capital 500000 --instruments SP500_micro,CRUDE_W,GOLD,US10 --strategy trend_and_carry
    python scripts/backtest.py --capital 1000000 --instruments SP500_micro,NASDAQ_micro --strategy trend_following --vol-target 25
    python scripts/backtest.py --config scripts/backtest_config/trend_only.yaml

    # Output options
    python scripts/backtest.py --system chapter15 --report full --export ./results/
    python scripts/backtest.py --system chapter15 --instruments SP500_micro --rule-detail
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")

# Suppress noisy DEBUG logging from pysystemtrade
import logging
import syslogging
logging.basicConfig(level=logging.WARNING, format="%(message)s")
syslogging.logging_configured = True

# === STRATEGY PRESETS ===

STRATEGY_PRESETS = {
    "trend_following": {
        "description": "Pure trend following (EWMAC at 6 speeds)",
        "trading_rules": {
            "ewmac2_8": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 2, "Lslow": 8},
                "forecast_scalar": 10.6,
            },
            "ewmac4_16": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 4, "Lslow": 16},
                "forecast_scalar": 7.5,
            },
            "ewmac8_32": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 8, "Lslow": 32},
                "forecast_scalar": 5.3,
            },
            "ewmac16_64": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 16, "Lslow": 64},
                "forecast_scalar": 3.75,
            },
            "ewmac32_128": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 32, "Lslow": 128},
                "forecast_scalar": 2.65,
            },
            "ewmac64_256": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 64, "Lslow": 256},
                "forecast_scalar": 1.87,
            },
        },
        "forecast_weights": {
            "ewmac2_8": 1 / 6,
            "ewmac4_16": 1 / 6,
            "ewmac8_32": 1 / 6,
            "ewmac16_64": 1 / 6,
            "ewmac32_128": 1 / 6,
            "ewmac64_256": 1 / 6,
        },
        "forecast_div_multiplier": 1.4,
    },
    "carry": {
        "description": "Pure carry strategy",
        "trading_rules": {
            "carry": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 90},
                "forecast_scalar": 30,
            },
        },
        "forecast_weights": {"carry": 1.0},
        "forecast_div_multiplier": 1.0,
    },
    "trend_carry_csmom": {
        "description": "Trend-Following + Carry + Cross-Sectional Momentum (3-factor)",
        "trading_rules": {
            "momentum8": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 8, "Lslow": 32},
                "forecast_scalar": 5.95,
            },
            "momentum16": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 16, "Lslow": 64},
                "forecast_scalar": 4.10,
            },
            "momentum32": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 32, "Lslow": 128},
                "forecast_scalar": 2.79,
            },
            "momentum64": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 64, "Lslow": 256},
                "forecast_scalar": 1.91,
            },
            "carry30": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 30},
                "forecast_scalar": 28.38,
            },
            "carry60": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 60},
                "forecast_scalar": 28.40,
            },
            "carry125": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 125},
                "forecast_scalar": 29.37,
            },
            "relmomentum20": {
                "function": "systems.provided.rules.rel_mom.relative_momentum",
                "data": ["rawdata.get_cumulative_daily_vol_normalised_returns", "rawdata.normalised_price_for_asset_class"],
                "other_args": {"horizon": 20},
                "forecast_scalar": 86.51,
            },
            "relmomentum40": {
                "function": "systems.provided.rules.rel_mom.relative_momentum",
                "data": ["rawdata.get_cumulative_daily_vol_normalised_returns", "rawdata.normalised_price_for_asset_class"],
                "other_args": {"horizon": 40},
                "forecast_scalar": 117.78,
            },
            "relmomentum80": {
                "function": "systems.provided.rules.rel_mom.relative_momentum",
                "data": ["rawdata.get_cumulative_daily_vol_normalised_returns", "rawdata.normalised_price_for_asset_class"],
                "other_args": {"horizon": 80},
                "forecast_scalar": 159.88,
            },
        },
        "forecast_weights": {
            "momentum8": 0.083,
            "momentum16": 0.083,
            "momentum32": 0.083,
            "momentum64": 0.083,
            "carry30": 0.111,
            "carry60": 0.111,
            "carry125": 0.111,
            "relmomentum20": 0.111,
            "relmomentum40": 0.111,
            "relmomentum80": 0.111,
        },
        "forecast_div_multiplier": 1.35,
    },
    "trend_and_carry": {
        "description": "Blended trend + carry (Chapter 15 style)",
        "trading_rules": {
            "ewmac16_64": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 16, "Lslow": 64},
                "forecast_scalar": 3.75,
            },
            "ewmac32_128": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 32, "Lslow": 128},
                "forecast_scalar": 2.65,
            },
            "ewmac64_256": {
                "function": "systems.provided.rules.ewmac.ewmac",
                "data": ["rawdata.get_daily_prices", "rawdata.daily_returns_volatility"],
                "other_args": {"Lfast": 64, "Lslow": 256},
                "forecast_scalar": 1.87,
            },
            "carry": {
                "function": "systems.provided.rules.carry.carry",
                "data": ["rawdata.raw_carry"],
                "other_args": {"smooth_days": 90},
                "forecast_scalar": 30,
            },
        },
        "forecast_weights": {
            "ewmac16_64": 0.21,
            "ewmac32_128": 0.08,
            "ewmac64_256": 0.21,
            "carry": 0.50,
        },
        "forecast_div_multiplier": 1.31,
    },
}


def build_system(args):
    """Build a System object from CLI arguments."""
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

    # Pre-built systems
    if args.system == "chapter15":
        from systems.provided.futures_chapter15.basesystem import futures_system
        config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
        if args.capital:
            config.notional_trading_capital = args.capital
        if args.currency:
            config.base_currency = args.currency
        if args.vol_target:
            config.percentage_vol_target = args.vol_target
        if args.instruments:
            instruments = args.instruments.split(",")
            n = len(instruments)
            config.instrument_weights = {i: 1.0 / n for i in instruments}
            config.instrument_div_multiplier = min(1.0 + 0.3 * (n - 1), 2.5)
            config.instruments = instruments
        return futures_system(data=data, config=config)

    elif args.system == "estimated":
        from systems.provided.futures_chapter15.estimatedsystem import (
            futures_system as estimated_system,
        )
        config = Config("systems.provided.futures_chapter15.futuresestimateconfig.yaml")
        if args.capital:
            config.notional_trading_capital = args.capital
        if args.currency:
            config.base_currency = args.currency
        if args.vol_target:
            config.percentage_vol_target = args.vol_target
        if args.instruments:
            instruments = args.instruments.split(",")
            config.instruments = instruments
        return estimated_system(data=data, config=config)

    elif args.system == "rob":
        config = Config("systems.provided.rob_system.config.yaml")
        if args.capital:
            config.notional_trading_capital = args.capital
        if args.currency:
            config.base_currency = args.currency
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

    elif args.system == "arki":
        # Arki production system: 3-factor (Trend+Carry+CS Mom) with
        # dynamic_small_system_optimise for integer position sizing
        from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import optimisedPositions
        from systems.provided.dynamic_small_system_optimise.accounts_stage import accountForOptimisedStage
        from systems.risk import Risk

        config = Config(str(PROJECT_ROOT / "scripts" / "backtest_config" / "arki_production.yaml"))
        if args.capital:
            config.notional_trading_capital = args.capital
        if args.currency:
            config.base_currency = args.currency
        if args.vol_target:
            config.percentage_vol_target = args.vol_target

        system = System(
            [
                Risk(),
                accountForOptimisedStage(),
                optimisedPositions(),
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

    elif args.config:
        config = Config(args.config)
        if args.capital:
            config.notional_trading_capital = args.capital
        if args.currency:
            config.base_currency = args.currency
        if args.vol_target:
            config.percentage_vol_target = args.vol_target
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

    # Custom strategy from presets
    strategy_name = args.strategy or "trend_and_carry"
    if strategy_name not in STRATEGY_PRESETS:
        print(f"❌ Unknown strategy: {strategy_name}")
        print(f"Available: {', '.join(STRATEGY_PRESETS.keys())}")
        sys.exit(1)

    preset = STRATEGY_PRESETS[strategy_name]
    instruments = args.instruments.split(",") if args.instruments else ["SP500_micro", "US10", "CORN", "EUROSTX"]

    config_dict = {
        "trading_rules": preset["trading_rules"],
        "forecast_weights": preset["forecast_weights"],
        "forecast_div_multiplier": preset["forecast_div_multiplier"],
        "percentage_vol_target": args.vol_target or 20.0,
        "notional_trading_capital": args.capital or 250000,
        "base_currency": args.currency or "USD",
        "instrument_weights": {i: 1.0 / len(instruments) for i in instruments},
        "instrument_div_multiplier": min(1.0 + 0.3 * (len(instruments) - 1), 2.5),
    }

    config = Config(config_dict)
    config.instruments = instruments

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


def print_report(system, args, elapsed):
    """Print comprehensive backtest results."""
    report_level = args.report or "summary"

    instruments = system.get_instrument_list()
    config = system.config

    capital = getattr(config, "notional_trading_capital", 250000)
    vol_target = getattr(config, "percentage_vol_target", 20.0)
    currency = getattr(config, "base_currency", "USD")
    strategy = args.strategy or args.system or "custom"

    print(f"\n{'='*80}")
    print(f"  BACKTEST RESULTS: {strategy.upper()}")
    print(f"{'='*80}")
    print(f"  Account Size: ${capital:,.0f} | Vol Target: {vol_target}% | Currency: {currency}")
    print(f"  Instruments: {', '.join(instruments)}")

    # Portfolio P&L
    print(f"\n  Computing portfolio P&L...", end=" ", flush=True)
    try:
        portfolio_pnl = system.accounts.portfolio()
        stats = portfolio_pnl.percent.stats()
        print("✅")
    except Exception as e:
        print(f"\n  ❌ Error computing portfolio P&L: {e}")
        return

    # Extract date range
    curve = portfolio_pnl.percent
    start_date = curve.index[0].strftime("%Y-%m-%d")
    end_date = curve.index[-1].strftime("%Y-%m-%d")
    years = (curve.index[-1] - curve.index[0]).days / 365.25

    print(f"  Period: {start_date} → {end_date} ({years:.1f} years)")
    print(f"  Computation time: {elapsed:.1f}s")
    print(f"{'='*80}")

    # Parse stats
    stats_dict = {item[0]: item[1] for item in stats[0]}

    print(f"\n  PORTFOLIO PERFORMANCE")
    print(f"  {'─'*40}")
    print(f"    Annualized Return:    {float(stats_dict.get('ann_mean', 0)):>10.2f}%")
    print(f"    Annualized Volatility:{float(stats_dict.get('ann_std', 0)):>10.2f}%")
    print(f"    Sharpe Ratio:         {float(stats_dict.get('sharpe', 0)):>10.4f}")
    print(f"    Sortino Ratio:        {float(stats_dict.get('sortino', 0)):>10.4f}")
    print(f"    Max Drawdown:         {float(stats_dict.get('min', 0)):>10.4f}%")
    print(f"    Avg Drawdown:         {float(stats_dict.get('avg_drawdown', 0)):>10.2f}%")
    print(f"    Calmar Ratio:         {float(stats_dict.get('calmar', 0)):>10.4f}")
    print(f"    Hit Rate:             {float(stats_dict.get('hitrate', 0)):>10.4f}")
    print(f"    Profit Factor:        {float(stats_dict.get('profitfactor', 0)):>10.4f}")
    print(f"    t-statistic:          {float(stats_dict.get('t_stat', 0)):>10.4f}")
    print(f"    p-value:              {float(stats_dict.get('p_value', 1)):>10.6f}")
    print(f"    Skewness:             {float(stats_dict.get('skew', 0)):>10.4f}")

    if report_level == "full":
        # Cost analysis
        try:
            gross_sharpe = portfolio_pnl.gross.sharpe()
            net_sharpe = portfolio_pnl.sharpe()
            print(f"\n  COST ANALYSIS")
            print(f"  {'─'*40}")
            print(f"    Gross Sharpe:     {gross_sharpe:>10.4f}")
            print(f"    Net Sharpe:       {net_sharpe:>10.4f}")
            print(f"    Cost Impact:      {net_sharpe - gross_sharpe:>10.4f} SR units")
        except Exception:
            pass

        # Instrument breakdown
        print(f"\n  INSTRUMENT BREAKDOWN")
        print(f"  {'─'*40}")
        print(f"    {'Instrument':<20} {'Sharpe':>8} {'Avg Position':>14}")

        for code in instruments:
            try:
                inst_pnl = system.accounts.pandl_for_subsystem(code)
                inst_sharpe = inst_pnl.sharpe()
                avg_pos = system.portfolio.get_notional_position(code).abs().mean()
                print(f"    {code:<20} {inst_sharpe:>8.4f} {avg_pos:>14.1f}")
            except Exception as e:
                print(f"    {code:<20} {'N/A':>8} {'N/A':>14}  ({e})")

        # Rule breakdown
        try:
            rules = system.rules.trading_rules().keys()
            if rules:
                print(f"\n  RULE BREAKDOWN")
                print(f"  {'─'*40}")
                print(f"    {'Rule':<20} {'Avg |Forecast|':>16}")
                for rule in rules:
                    try:
                        # Average absolute forecast across instruments
                        forecasts = []
                        for code in instruments[:4]:  # limit for speed
                            try:
                                fc = system.forecastScaleCap.get_capped_forecast(code, rule)
                                forecasts.append(fc.abs().mean())
                            except Exception:
                                pass
                        if forecasts:
                            avg_fc = sum(forecasts) / len(forecasts)
                            print(f"    {rule:<20} {avg_fc:>16.2f}")
                    except Exception:
                        pass
        except Exception:
            pass

    # Export
    export_dir = args.export
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)

        # Export equity curve
        curve_path = os.path.join(export_dir, "equity_curve.csv")
        portfolio_pnl.percent.cumsum().to_csv(curve_path)
        print(f"\n  💾 Equity curve: {curve_path}")

        # Export daily returns
        returns_path = os.path.join(export_dir, "daily_returns.csv")
        portfolio_pnl.percent.to_csv(returns_path)
        print(f"  💾 Daily returns: {returns_path}")

        # Export stats
        stats_path = os.path.join(export_dir, "stats.txt")
        with open(stats_path, "w") as f:
            f.write(f"Strategy: {strategy}\n")
            f.write(f"Capital: {capital}\n")
            f.write(f"Period: {start_date} - {end_date}\n")
            f.write(f"Instruments: {', '.join(instruments)}\n\n")
            for k, v in stats_dict.items():
                f.write(f"{k}: {v}\n")
        print(f"  💾 Stats: {stats_path}")

    print(f"\n{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="pysystemtrade Backtest CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pre-built systems:
  chapter15     Staunch Systems Trader (6 instruments, trend+carry)
  estimated     Same as chapter15 but with estimated weights/scalars
  rob           Rob Carver's full personal system

Strategy presets:
  trend_following      Pure EWMAC at 6 speeds
  carry                Pure carry
  trend_carry_csmom    Trend + Carry + Cross-Sectional Momentum (3-factor)
  trend_and_carry      Blended trend + carry (default)

Examples:
  %(prog)s --system chapter15
  %(prog)s --system chapter15 --report full
  %(prog)s --capital 500000 --instruments SP500_micro,CRUDE_W,GOLD,US10
  %(prog)s --strategy trend_following --capital 1000000 --instruments SP500_micro,EUR,GOLD
  %(prog)s --system chapter15 --export ./results/
        """,
    )

    parser.add_argument("--system", choices=["chapter15", "estimated", "rob", "arki"],
                        help="Pre-built system to use")
    parser.add_argument("--strategy", choices=list(STRATEGY_PRESETS.keys()),
                        help="Strategy preset")
    parser.add_argument("--config", type=str, help="Path to custom YAML config")
    parser.add_argument("--capital", type=float, help="Notional trading capital")
    parser.add_argument("--currency", type=str, default="USD", help="Base currency (default: USD)")
    parser.add_argument("--vol-target", type=float, help="Annualized vol target %% (default: 20)")
    parser.add_argument("--instruments", type=str,
                        help="Comma-separated instrument codes")
    parser.add_argument("--report", choices=["summary", "full"], default="summary",
                        help="Report detail level")
    parser.add_argument("--export", type=str, help="Export results to directory")
    parser.add_argument("--rule-detail", action="store_true",
                        help="Show per-rule forecast details")

    args = parser.parse_args()

    if not args.system and not args.strategy and not args.config and not args.instruments:
        parser.print_help()
        print("\n💡 Quick start: python scripts/backtest.py --system chapter15 --report full")
        return

    # If only instruments given with no system/strategy, default to trend_and_carry
    if not args.system and not args.strategy and not args.config:
        args.strategy = "trend_and_carry"

    print(f"\n🚀 Building system...", flush=True)
    t0 = time.time()
    system = build_system(args)
    print(f"   System: {system}")
    print(f"   Instruments: {system.get_instrument_list()}")

    print(f"\n📊 Running backtest...", flush=True)
    elapsed = time.time() - t0
    print_report(system, args, elapsed)


if __name__ == "__main__":
    main()
