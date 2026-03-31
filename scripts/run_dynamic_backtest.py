#!/usr/bin/env python3
"""
Dynamic Optimised Backtest (Phase 2 & 3)

Runs the full pysystemtrade production stack:
  - Vol Attenuation (volAttenForecastScaleCap)
  - myFuturesRawData (extended rawdata with skew/kurtosis)
  - Dynamic Optimizer (optimisedPositions / Mr. Greedy)
  - Integer-position P&L (accountForOptimisedStage)
  - Risk stage

Phase 2 mode (--mode estimated):
    Runs estimated system WITHOUT dynamic optimizer.
    Uses auto-estimated weights/scalars for quick validation.

Phase 3 mode (--mode dynamic):
    Full dynamic optimizer with integer-position optimization.
    Much slower but most accurate for small accounts.

Usage:
    # Phase 2: Estimated system (fast, ~30 min)
    python scripts/run_dynamic_backtest.py --mode estimated --capital 200000 --report full

    # Phase 2 with specific instruments from Phase 1
    python scripts/run_dynamic_backtest.py --mode estimated --capital 200000 --instruments-from results/optimal_instruments_200k.yaml

    # Phase 3: Dynamic optimizer (slow, 1-8 hours)
    python scripts/run_dynamic_backtest.py --mode dynamic --capital 200000

    # Export results
    python scripts/run_dynamic_backtest.py --mode estimated --capital 200000 --export results/phase2/
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


def build_estimated_system(config_path, capital, instruments=None):
    """Build an estimated system (Phase 2) — no dynamic optimizer."""
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
    from sysdata.config.configdata import Config
    from systems.forecasting import Rules
    from systems.basesystem import System
    from systems.forecast_combine import ForecastCombine
    from systems.rawdata import RawData
    from systems.positionsizing import PositionSizing
    from systems.portfolio import Portfolios
    from systems.accounts.accounts_stage import Account
    from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import (
        volAttenForecastScaleCap,
    )

    data = csvFuturesSimData()
    config = Config(config_path)
    config.notional_trading_capital = capital

    if instruments:
        config.instruments = instruments

    system = System(
        [
            Account(),
            Portfolios(),
            PositionSizing(),
            RawData(),
            ForecastCombine(),
            volAttenForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )
    return system


def build_dynamic_system(config_path, capital, instruments=None):
    """Build a dynamic optimised system (Phase 3) — with Mr. Greedy."""
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
    from sysdata.config.configdata import Config
    from systems.forecasting import Rules
    from systems.basesystem import System
    from systems.forecast_combine import ForecastCombine
    from systems.rawdata import RawData
    from systems.positionsizing import PositionSizing
    from systems.portfolio import Portfolios
    from systems.risk import Risk
    from systems.provided.attenuate_vol.vol_attenuation_forecast_scale_cap import (
        volAttenForecastScaleCap,
    )
    from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import (
        optimisedPositions,
    )
    from systems.provided.dynamic_small_system_optimise.accounts_stage import (
        accountForOptimisedStage,
    )

    data = csvFuturesSimData()
    config = Config(config_path)
    config.notional_trading_capital = capital

    if instruments:
        config.instruments = instruments

    system = System(
        [
            Risk(),
            accountForOptimisedStage(),
            optimisedPositions(),
            Portfolios(),
            PositionSizing(),
            RawData(),
            ForecastCombine(),
            volAttenForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )
    return system


def print_report(system, mode, capital, instruments, elapsed, report_level="summary", export_dir=None):
    """Print comprehensive backtest results."""
    print(f"\n{'='*80}")
    print(f"  BACKTEST RESULTS: 3-Factor {'Dynamic' if mode == 'dynamic' else 'Estimated'}")
    print(f"{'='*80}")
    print(f"  Capital: ${capital:,.0f} | Vol Target: 25% | Currency: USD")
    print(f"  Mode: {mode.upper()}")
    print(f"  Instruments: {len(instruments)} [{', '.join(instruments[:5])}{'...' if len(instruments) > 5 else ''}]")
    print(f"  Computation: {elapsed:.1f}s ({elapsed/60:.1f}min)")

    # --- Standard Portfolio P&L ---
    print(f"\n  Computing standard portfolio P&L...", end=" ", flush=True)
    try:
        portfolio_pnl = system.accounts.portfolio()
        pct = portfolio_pnl.percent
        stats = pct.stats()
        stats_dict = {item[0]: item[1] for item in stats[0]}
        print("✅")
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        return

    start_date = pct.index[0].strftime("%Y-%m-%d")
    end_date = pct.index[-1].strftime("%Y-%m-%d")
    years = (pct.index[-1] - pct.index[0]).days / 365.25

    print(f"  Period: {start_date} → {end_date} ({years:.1f} years)")

    print(f"\n  STANDARD PORTFOLIO (Rounded Positions)")
    print(f"  {'─'*50}")
    print(f"    Annualized Return:    {float(stats_dict.get('ann_mean', 0)):>10.2f}%")
    print(f"    Annualized Volatility:{float(stats_dict.get('ann_std', 0)):>10.2f}%")
    print(f"    Sharpe Ratio:         {float(stats_dict.get('sharpe', 0)):>10.4f}")
    print(f"    Sortino Ratio:        {float(stats_dict.get('sortino', 0)):>10.4f}")
    print(f"    Max Drawdown:         {float(stats_dict.get('min', 0)):>10.2f}%")
    print(f"    Avg Drawdown:         {float(stats_dict.get('avg_drawdown', 0)):>10.2f}%")
    print(f"    Skewness:             {float(stats_dict.get('skew', 0)):>10.4f}")
    print(f"    t-stat:               {float(stats_dict.get('t_stat', 0)):>10.4f}")
    print(f"    p-value:              {float(stats_dict.get('p_value', 1)):>10.6f}")

    # --- Unrounded P&L ---
    print(f"\n  Computing unrounded P&L...", end=" ", flush=True)
    try:
        unrounded_pnl = system.accounts.portfolio(roundpositions=False)
        unrounded_stats = unrounded_pnl.percent.stats()
        ur_dict = {item[0]: item[1] for item in unrounded_stats[0]}
        print("✅")
        print(f"\n  UNROUNDED PORTFOLIO (Theoretical Optimal)")
        print(f"  {'─'*50}")
        print(f"    Sharpe Ratio:         {float(ur_dict.get('sharpe', 0)):>10.4f}")
        print(f"    Ann. Return:          {float(ur_dict.get('ann_mean', 0)):>10.2f}%")
        sr_penalty = float(ur_dict.get('sharpe', 0)) - float(stats_dict.get('sharpe', 0))
        print(f"    SR Gap (rounding):    {sr_penalty:>10.4f}")
    except Exception as e:
        print(f"❌ {e}")

    # --- Dynamic Optimised P&L (Phase 3 only) ---
    if mode == "dynamic":
        print(f"\n  Computing OPTIMISED P&L (Mr. Greedy)...", end=" ", flush=True)
        try:
            opt_pnl = system.accounts.optimised_portfolio()
            opt_stats = opt_pnl.percent.stats()
            opt_dict = {item[0]: item[1] for item in opt_stats[0]}
            print("✅")

            print(f"\n  DYNAMIC OPTIMISED PORTFOLIO (Integer Positions)")
            print(f"  {'─'*50}")
            print(f"    Sharpe Ratio:         {float(opt_dict.get('sharpe', 0)):>10.4f}")
            print(f"    Ann. Return:          {float(opt_dict.get('ann_mean', 0)):>10.2f}%")
            opt_penalty = float(ur_dict.get('sharpe', 0)) - float(opt_dict.get('sharpe', 0))
            rnd_penalty = float(ur_dict.get('sharpe', 0)) - float(stats_dict.get('sharpe', 0))
            print(f"    SR Penalty vs Ideal:  {opt_penalty:>10.4f}")
            print(f"    Improvement vs Round: {rnd_penalty - opt_penalty:>10.4f}")
        except Exception as e:
            print(f"❌ {e}")

    # --- Cost Analysis ---
    if report_level == "full":
        try:
            gross_sharpe = portfolio_pnl.gross.sharpe()
            net_sharpe = portfolio_pnl.sharpe()
            print(f"\n  COST ANALYSIS")
            print(f"  {'─'*50}")
            print(f"    Gross Sharpe:         {gross_sharpe:>10.4f}")
            print(f"    Net Sharpe:           {net_sharpe:>10.4f}")
            print(f"    Cost Impact:          {net_sharpe - gross_sharpe:>10.4f} SR units")
        except Exception:
            pass

        # Instrument breakdown (top 10 by abs position)
        print(f"\n  INSTRUMENT BREAKDOWN (top 10)")
        print(f"  {'─'*50}")
        print(f"    {'Instrument':<20} {'Sharpe':>8} {'Avg |Pos|':>12}")

        inst_data = []
        for code in instruments:
            try:
                sr = system.accounts.pandl_for_subsystem(code).sharpe()
                avg_pos = system.portfolio.get_notional_position(code).abs().mean()
                inst_data.append((code, sr, avg_pos))
            except Exception:
                pass

        inst_data.sort(key=lambda x: x[2], reverse=True)
        for code, sr, avg_pos in inst_data[:10]:
            print(f"    {code:<20} {sr:>8.4f} {avg_pos:>12.1f}")

    # --- Export ---
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)

        # Equity curve
        eq_path = os.path.join(export_dir, "equity_curve.csv")
        portfolio_pnl.percent.cumsum().to_csv(eq_path)

        # Daily returns
        ret_path = os.path.join(export_dir, "daily_returns.csv")
        portfolio_pnl.percent.to_csv(ret_path)

        # Stats summary
        stats_path = os.path.join(export_dir, "stats.yaml")
        with open(stats_path, "w") as f:
            yaml.dump(
                {
                    "mode": mode,
                    "capital": capital,
                    "instruments": instruments,
                    "period": f"{start_date} to {end_date}",
                    "years": round(years, 1),
                    "stats": {k: str(v) for k, v in stats_dict.items()},
                },
                f,
                default_flow_style=False,
            )
        print(f"\n  💾 Results saved to: {export_dir}")

    print(f"\n{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Dynamic Optimised 3-Factor Backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  estimated   Phase 2: auto-estimated weights, no dynamic optimizer (faster)
  dynamic     Phase 3: full Mr. Greedy integer-position optimization (slower)

Examples:
  %(prog)s --mode estimated --capital 200000
  %(prog)s --mode estimated --capital 200000 --instruments-from results/optimal_instruments_200k.yaml
  %(prog)s --mode dynamic --capital 200000 --report full --export results/phase3/
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["estimated", "dynamic"],
        default="estimated",
        help="Backtest mode (default: estimated)",
    )
    parser.add_argument(
        "--config",
        default="scripts/backtest_config/trend_carry_csmom_estimated.yaml",
        help="Path to YAML config",
    )
    parser.add_argument("--capital", type=float, default=200000, help="Capital (default: 200000)")
    parser.add_argument(
        "--instruments-from",
        type=str,
        help="Load instrument list from YAML (Phase 1 output)",
    )
    parser.add_argument(
        "--instruments",
        type=str,
        help="Comma-separated instrument codes",
    )
    parser.add_argument(
        "--report",
        choices=["summary", "full"],
        default="summary",
        help="Report detail level",
    )
    parser.add_argument("--export", type=str, help="Export results directory")

    args = parser.parse_args()

    # Resolve instruments
    instruments = None
    if args.instruments_from:
        with open(args.instruments_from) as f:
            data = yaml.safe_load(f)
        instruments = data.get("instruments", [])
        print(f"  Loaded {len(instruments)} instruments from {args.instruments_from}")
    elif args.instruments:
        instruments = args.instruments.split(",")

    # Build system
    print(f"\n🚀 Building {'dynamic' if args.mode == 'dynamic' else 'estimated'} system...")
    t0 = time.time()

    if args.mode == "dynamic":
        system = build_dynamic_system(args.config, args.capital, instruments)
    else:
        system = build_estimated_system(args.config, args.capital, instruments)

    actual_instruments = system.get_instrument_list()
    print(f"   Config: {args.config}")
    print(f"   Instruments: {len(actual_instruments)}")
    print(f"   Capital: ${args.capital:,.0f}")

    print(f"\n📊 Running backtest...")
    elapsed = time.time() - t0

    print_report(
        system,
        mode=args.mode,
        capital=args.capital,
        instruments=actual_instruments,
        elapsed=elapsed,
        report_level=args.report,
        export_dir=args.export,
    )


if __name__ == "__main__":
    main()
