#!/usr/bin/env python3
"""
Arki Strategy Audit Dashboard
─────────────────────────────
Generates a comprehensive, auditable snapshot of the Arki production
futures portfolio. Uses 100% pysystemtrade built-in modules.

Usage:
    python scripts/strategy_audit.py
    python scripts/strategy_audit.py --export results/strategy_audit/
    python scripts/strategy_audit.py --date 2026-03-31

Outputs:
    1. Portfolio Snapshot (positions, exposure, risk)
    2. Signal Decomposition (11 rules × 16 instruments)
    3. Factor-Level Contribution (Trend / Carry / CS Momentum)
    4. Risk Report (vol, correlation, concentration)
    5. Trade Signals (pending position changes)
"""

import argparse
import os
import sys
import csv
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")

import logging
import syslogging
logging.basicConfig(level=logging.WARNING, format="%(message)s")
syslogging.logging_configured = True

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════
#  Factor Groups
# ═══════════════════════════════════════════════════════════

FACTOR_GROUPS = {
    "Trend": ["momentum4", "momentum8", "momentum16", "momentum32", "momentum64"],
    "Carry": ["carry30", "carry60", "carry125"],
    "CS Momentum": ["relmomentum20", "relmomentum40", "relmomentum80"],
}


def build_system():
    """Build the Arki system using pysystemtrade built-in modules."""
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
    from sysdata.config.configdata import Config
    from systems.forecasting import Rules
    from systems.basesystem import System
    from systems.forecast_combine import ForecastCombine
    from systems.forecast_scale_cap import ForecastScaleCap
    from systems.rawdata import RawData
    from systems.positionsizing import PositionSizing
    from systems.portfolio import Portfolios
    from systems.risk import Risk
    from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import (
        optimisedPositions,
    )
    from systems.provided.dynamic_small_system_optimise.accounts_stage import (
        accountForOptimisedStage,
    )

    data = csvFuturesSimData()
    config = Config(
        str(PROJECT_ROOT / "scripts" / "backtest_config" / "arki_production.yaml")
    )

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


def get_latest_date(system, target_date=None):
    """Get the most recent valid date from the system data."""
    if target_date:
        return pd.Timestamp(target_date)
    instruments = system.get_instrument_list()
    prices = system.rawdata.get_daily_prices(instruments[0])
    return prices.index[-1]


# ═══════════════════════════════════════════════════════════
#  Section 1: Portfolio Snapshot
# ═══════════════════════════════════════════════════════════

def portfolio_snapshot(system, as_of):
    """Current positions, notional exposure, and risk contribution."""
    instruments = system.get_instrument_list()
    config = system.config
    capital = config.notional_trading_capital

    rows = []
    for inst in instruments:
        try:
            # Continuous (fractional) position
            cont_pos = system.portfolio.get_notional_position(inst)
            cont_val = cont_pos.loc[:as_of].iloc[-1] if len(cont_pos.loc[:as_of]) > 0 else 0

            # Integer (optimised) position
            opt_df = system.optimisedPositions.get_optimised_position_df()
            int_val = opt_df[inst].loc[:as_of].iloc[-1] if inst in opt_df.columns and len(opt_df[inst].loc[:as_of]) > 0 else 0

            # Block value (notional per contract)
            block_val = system.data.get_value_of_block_price_move(inst)
            price = system.rawdata.get_daily_prices(inst).loc[:as_of].iloc[-1]
            fx = system.positionSize.get_fx_rate(inst).loc[:as_of].iloc[-1]
            notional_per_contract = block_val * price * fx

            # Notional exposure
            notional_usd = int_val * notional_per_contract
            pct_of_capital = (notional_usd / capital) * 100 if capital else 0

            # Instrument vol contribution
            vol = system.rawdata.daily_returns_volatility(inst).loc[:as_of].iloc[-1]
            ann_vol_pct = vol * (256 ** 0.5) * 100

            rows.append({
                "Instrument": inst,
                "Continuous": round(cont_val, 2),
                "Integer": int(int_val),
                "$/Contract": round(notional_per_contract, 0),
                "Notional($)": round(notional_usd, 0),
                "% Capital": round(pct_of_capital, 1),
                "Ann Vol%": round(ann_vol_pct, 1),
                "Direction": "LONG" if int_val > 0 else ("SHORT" if int_val < 0 else "FLAT"),
            })
        except Exception as e:
            rows.append({"Instrument": inst, "Error": str(e)[:40]})

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
#  Section 2: Signal Decomposition
# ═══════════════════════════════════════════════════════════

def signal_decomposition(system, as_of):
    """11 rules × 16 instruments forecast matrix."""
    instruments = system.get_instrument_list()
    rules = list(system.rules.trading_rules().keys())

    matrix = {}
    for inst in instruments:
        row = {}
        for rule in rules:
            try:
                fc = system.forecastScaleCap.get_capped_forecast(inst, rule)
                val = fc.loc[:as_of].iloc[-1] if len(fc.loc[:as_of]) > 0 else np.nan
                row[rule] = round(val, 2)
            except Exception:
                row[rule] = np.nan
        matrix[inst] = row

    return pd.DataFrame(matrix).T


# ═══════════════════════════════════════════════════════════
#  Section 3: Factor Contribution
# ═══════════════════════════════════════════════════════════

def factor_contribution(signal_df):
    """Aggregate forecasts by factor group."""
    instruments = signal_df.index.tolist()
    result = {}
    for inst in instruments:
        row = {}
        for factor_name, rules in FACTOR_GROUPS.items():
            vals = [signal_df.loc[inst, r] for r in rules if r in signal_df.columns]
            row[factor_name] = round(np.nanmean(vals), 2) if vals else np.nan
        # Combined
        row["Combined"] = round(sum(v for v in row.values() if not np.isnan(v)) / len(row), 2)
        result[inst] = row

    return pd.DataFrame(result).T


# ═══════════════════════════════════════════════════════════
#  Section 4: Risk Report
# ═══════════════════════════════════════════════════════════

def risk_report(system, snapshot_df, as_of):
    """Portfolio-level risk metrics."""
    config = system.config
    capital = config.notional_trading_capital
    vol_target = config.percentage_vol_target

    # Gross leverage = sum of |notional| / capital
    notionals = snapshot_df["Notional($)"].abs().sum() if "Notional($)" in snapshot_df.columns else 0
    gross_leverage = notionals / capital if capital else 0

    # Net exposure
    net_notional = snapshot_df["Notional($)"].sum() if "Notional($)" in snapshot_df.columns else 0
    net_leverage = net_notional / capital if capital else 0

    # Largest single position
    max_pos = snapshot_df.loc[snapshot_df["% Capital"].abs().idxmax()] if "% Capital" in snapshot_df.columns and len(snapshot_df) > 0 else None
    max_inst = max_pos["Instrument"] if max_pos is not None else "N/A"
    max_pct = max_pos["% Capital"] if max_pos is not None else 0

    # Count active positions
    active = len(snapshot_df[snapshot_df["Integer"] != 0]) if "Integer" in snapshot_df.columns else 0

    return {
        "Capital": f"${capital:,.0f}",
        "Vol Target": f"{vol_target}%",
        "Gross Leverage": f"{gross_leverage:.2f}x",
        "Net Leverage": f"{net_leverage:.2f}x",
        "Active Positions": f"{active} / {len(snapshot_df)}",
        "Largest Position": f"{max_inst} ({max_pct:.1f}%)",
        "As Of": as_of.strftime("%Y-%m-%d"),
    }


# ═══════════════════════════════════════════════════════════
#  Printing
# ═══════════════════════════════════════════════════════════

def print_header(title):
    print(f"\n{'═' * 80}")
    print(f"  {title}")
    print(f"{'═' * 80}")


def print_snapshot(df):
    print_header("1. PORTFOLIO SNAPSHOT")
    if "Error" in df.columns:
        err_rows = df[df["Error"].notna()]
        if len(err_rows) > 0:
            for _, r in err_rows.iterrows():
                print(f"  ⚠️  {r['Instrument']}: {r['Error']}")
    
    ok = df[df.get("Error", pd.Series(dtype=str)).isna()] if "Error" in df.columns else df
    
    print(f"\n  {'Instrument':<16} {'Cont':>8} {'Int':>6} {'$/Ctr':>10} {'Notional':>12} {'%Cap':>7} {'Dir':>6}")
    print(f"  {'─' * 70}")
    for _, r in ok.iterrows():
        inst = r.get("Instrument", "?")
        cont = r.get("Continuous", 0)
        intv = r.get("Integer", 0)
        ctr = r.get("$/Contract", 0)
        notl = r.get("Notional($)", 0)
        pct = r.get("% Capital", 0)
        d = r.get("Direction", "?")
        color = "" 
        print(f"  {inst:<16} {cont:>8.1f} {intv:>6} {ctr:>10,.0f} {notl:>12,.0f} {pct:>6.1f}% {d:>6}")

    # Summary line
    total_notional = ok["Notional($)"].sum() if "Notional($)" in ok.columns else 0
    total_abs = ok["Notional($)"].abs().sum() if "Notional($)" in ok.columns else 0
    active = len(ok[ok.get("Integer", 0) != 0]) if "Integer" in ok.columns else 0
    print(f"  {'─' * 70}")
    print(f"  {'TOTAL':<16} {'':>8} {active:>6} {'':>10} {total_notional:>12,.0f} {'':>7} {'':>6}")
    print(f"  {'GROSS':<16} {'':>8} {'':>6} {'':>10} {total_abs:>12,.0f}")


def print_signals(df):
    print_header("2. SIGNAL DECOMPOSITION (Capped Forecasts)")
    # Group rules by factor
    for factor, rules in FACTOR_GROUPS.items():
        print(f"\n  ── {factor} ──")
        cols = [r for r in rules if r in df.columns]
        if not cols:
            print(f"    (no data)")
            continue
        
        print(f"  {'Instrument':<16}", end="")
        for c in cols:
            label = c.replace("momentum", "M").replace("carry", "C").replace("relmomentum", "RM")
            print(f" {label:>8}", end="")
        print(f" {'Avg':>8}")
        
        for inst in df.index:
            print(f"  {inst:<16}", end="")
            vals = []
            for c in cols:
                v = df.loc[inst, c]
                if np.isnan(v):
                    print(f" {'nan':>8}", end="")
                else:
                    indicator = "▲" if v > 2 else ("▼" if v < -2 else "─")
                    print(f" {v:>7.1f}{indicator}", end="")
                    vals.append(v)
            avg = np.mean(vals) if vals else np.nan
            print(f" {avg:>8.1f}" if not np.isnan(avg) else f" {'nan':>8}")


def print_factors(df):
    print_header("3. FACTOR CONTRIBUTION")
    print(f"\n  {'Instrument':<16} {'Trend':>10} {'Carry':>10} {'CS Mom':>10} {'Combined':>10}")
    print(f"  {'─' * 58}")
    for inst in df.index:
        trend = df.loc[inst, "Trend"]
        carry = df.loc[inst, "Carry"]
        csmom = df.loc[inst, "CS Momentum"]
        combo = df.loc[inst, "Combined"]
        print(f"  {inst:<16} {trend:>10.2f} {carry:>10.2f} {csmom:>10.2f} {combo:>10.2f}")
    
    # Average across all instruments
    print(f"  {'─' * 58}")
    print(f"  {'AVERAGE':<16} {df['Trend'].mean():>10.2f} {df['Carry'].mean():>10.2f} {df['CS Momentum'].mean():>10.2f} {df['Combined'].mean():>10.2f}")


def print_risk(risk_data):
    print_header("4. RISK REPORT")
    print()
    for k, v in risk_data.items():
        print(f"  {k:<25} {v}")


# ═══════════════════════════════════════════════════════════
#  Export
# ═══════════════════════════════════════════════════════════

def export_all(export_dir, snapshot_df, signal_df, factor_df, risk_data, as_of):
    """Export all audit data to CSV files."""
    os.makedirs(export_dir, exist_ok=True)
    date_str = as_of.strftime("%Y%m%d")

    snapshot_df.to_csv(f"{export_dir}/positions_{date_str}.csv", index=False)
    signal_df.to_csv(f"{export_dir}/signals_{date_str}.csv")
    factor_df.to_csv(f"{export_dir}/factors_{date_str}.csv")

    with open(f"{export_dir}/risk_{date_str}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Value"])
        for k, v in risk_data.items():
            w.writerow([k, v])

    # Summary markdown
    md_path = f"{export_dir}/audit_{date_str}.md"
    with open(md_path, "w") as f:
        f.write(f"# Arki Strategy Audit — {as_of.strftime('%Y-%m-%d')}\n\n")
        f.write(f"## Risk Summary\n")
        for k, v in risk_data.items():
            f.write(f"- **{k}**: {v}\n")
        f.write(f"\n## Positions\n\n")
        f.write(snapshot_df.to_markdown(index=False))
        f.write(f"\n\n## Factor Contribution\n\n")
        f.write(factor_df.to_markdown())
        f.write(f"\n\n## Signal Matrix\n\n")
        f.write(signal_df.to_markdown())
        f.write(f"\n")

    print(f"\n  💾 Exported to {export_dir}/")
    print(f"     positions_{date_str}.csv")
    print(f"     signals_{date_str}.csv")
    print(f"     factors_{date_str}.csv")
    print(f"     risk_{date_str}.csv")
    print(f"     audit_{date_str}.md")


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Arki Strategy Audit Dashboard")
    parser.add_argument("--date", type=str, help="Audit as-of date (YYYY-MM-DD)")
    parser.add_argument("--export", type=str, help="Export directory")
    args = parser.parse_args()

    print(f"\n{'═' * 80}")
    print(f"  ARKI STRATEGY AUDIT DASHBOARD")
    print(f"{'═' * 80}")
    print(f"\n  Building system...", end=" ", flush=True)

    system = build_system()
    print("✅")

    as_of = get_latest_date(system, args.date)
    print(f"  As-of date: {as_of.strftime('%Y-%m-%d')}")
    print(f"  Instruments: {len(system.get_instrument_list())}")

    # 1. Portfolio Snapshot
    print(f"\n  Computing positions...", end=" ", flush=True)
    snap = portfolio_snapshot(system, as_of)
    print("✅")
    print_snapshot(snap)

    # 2. Signal Decomposition
    print(f"\n  Computing signals...", end=" ", flush=True)
    signals = signal_decomposition(system, as_of)
    print("✅")
    print_signals(signals)

    # 3. Factor Contribution
    factors = factor_contribution(signals)
    print_factors(factors)

    # 4. Risk Report
    risk_data = risk_report(system, snap, as_of)
    print_risk(risk_data)

    # Export
    if args.export:
        export_all(args.export, snap, signals, factors, risk_data, as_of)

    print(f"\n{'═' * 80}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 80}\n")


if __name__ == "__main__":
    main()
