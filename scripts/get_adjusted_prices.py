#!/usr/bin/env python3
"""
Quick accessor for back-adjusted futures prices.

Usage:
    python scripts/get_adjusted_prices.py SP500_micro
    python scripts/get_adjusted_prices.py SP500_micro --start 2000-01-01
    python scripts/get_adjusted_prices.py SP500_micro --start 2000-01-01 --output ./prices/
    python scripts/get_adjusted_prices.py --list
    python scripts/get_adjusted_prices.py SP500_micro,CRUDE_W,GOLD --output ./prices/
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")


def main():
    parser = argparse.ArgumentParser(description="Get back-adjusted futures prices")
    parser.add_argument("instruments", nargs="?", help="Comma-separated instrument codes")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, help="Output directory for CSV")
    parser.add_argument("--list", action="store_true", help="List available instruments")
    parser.add_argument("--source", choices=["csv", "db"], default="csv",
                        help="Data source (default: csv)")

    args = parser.parse_args()

    if args.source == "csv":
        from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
        data = csvFuturesSimData()
    else:
        from sysdata.sim.db_futures_sim_data import dbFuturesSimData
        data = dbFuturesSimData()

    if args.list:
        instruments = sorted(data.get_instrument_list())
        print(f"\n📦 Available instruments ({len(instruments)}):\n")
        cols = 5
        for i in range(0, len(instruments), cols):
            row = instruments[i:i + cols]
            print("  " + "  ".join(f"{x:<22}" for x in row))
        return

    if not args.instruments:
        parser.print_help()
        return

    codes = args.instruments.split(",")

    for code in codes:
        code = code.strip()
        if code not in data.get_instrument_list():
            print(f"\n❌ '{code}' not found. Use --list to see available instruments.")
            continue

        prices = data.get_raw_price(code)

        if args.start:
            prices = prices[args.start:]
        if args.end:
            prices = prices[:args.end]

        meta = data.get_instrument_object_with_meta_data(code)

        print(f"\n{'='*60}")
        print(f"  {code} — Back-Adjusted Prices")
        print(f"{'='*60}")
        print(f"  Description: {meta.meta_data.Description}")
        print(f"  Currency:    {meta.meta_data.Currency}")
        print(f"  Asset Class: {meta.meta_data.AssetClass}")
        print(f"  Point Size:  {meta.meta_data.Pointsize}")
        print(f"  Date Range:  {prices.index[0].strftime('%Y-%m-%d')} → {prices.index[-1].strftime('%Y-%m-%d')}")
        print(f"  Total Days:  {len(prices):,}")
        print(f"  Last Price:  {prices.iloc[-1]:.4f}")
        print(f"\n  Last 5 prices:")
        for date, price in prices.tail(5).items():
            print(f"    {date.strftime('%Y-%m-%d')}  {price:.4f}")

        if args.output:
            os.makedirs(args.output, exist_ok=True)
            out = os.path.join(args.output, f"{code}_adjusted.csv")
            prices.to_csv(out, header=["price"])
            print(f"\n  💾 Saved to: {out}")

    print()


if __name__ == "__main__":
    main()
