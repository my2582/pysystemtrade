#!/usr/bin/env python3
"""
Unified data pipeline for back-adjusted futures prices.

Strategies:
    A: Quick Start — Copy shipped CSV data to Parquet/DB for faster backtesting
    B: Hybrid Update — Splice fresh IB data onto shipped CSV base (max depth)
    C: Full IB Build — Seed everything from IB (limited ~1yr history)

Usage:
    python scripts/data_pipeline.py --list-instruments
    python scripts/data_pipeline.py --check-ib
    python scripts/data_pipeline.py --strategy A
    python scripts/data_pipeline.py --strategy A --instruments SP500_micro,CRUDE_W
    python scripts/data_pipeline.py --strategy B --instruments SP500_micro
    python scripts/data_pipeline.py --strategy C --instruments SP500_micro
    python scripts/data_pipeline.py --get-prices SP500_micro
    python scripts/data_pipeline.py --get-prices SP500_micro --start 2000-01-01 --output ./prices/
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")


def list_instruments():
    """Show all available instruments from CSV and IB config."""
    print("\n" + "=" * 70)
    print("  AVAILABLE INSTRUMENTS")
    print("=" * 70)

    # CSV instruments (shipped with repo)
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
    csv_data = csvFuturesSimData()
    csv_instruments = sorted(csv_data.get_instrument_list())
    print(f"\n📦 Shipped CSV data: {len(csv_instruments)} instruments")
    print("   " + ", ".join(csv_instruments[:20]) + "...")
    print(f"   (showing 20 of {len(csv_instruments)})")

    # IB instruments
    import pandas as pd
    ib_config_path = PROJECT_ROOT / "sysbrokers" / "IB" / "config" / "ib_config_futures.csv"
    ib_df = pd.read_csv(ib_config_path)
    ib_instruments = sorted(ib_df["Instrument"].tolist())
    print(f"\n🔌 IB-mapped instruments: {len(ib_instruments)} instruments")
    print("   " + ", ".join(ib_instruments[:20]) + "...")

    # Available for immediate backtesting (have adjusted prices CSV)
    adj_path = PROJECT_ROOT / "data" / "futures" / "adjusted_prices_csv"
    if adj_path.exists():
        adj_files = sorted([f.stem for f in adj_path.glob("*.csv")])
        print(f"\n✅ Ready for backtesting (have adjusted prices): {len(adj_files)} instruments")
        # Print in columns
        cols = 6
        for i in range(0, len(adj_files), cols):
            row = adj_files[i:i + cols]
            print("   " + "  ".join(f"{x:<20}" for x in row))

    print()


def check_ib_connection():
    """Test IB Gateway connectivity."""
    print("\n🔌 Testing IB Gateway connection...")
    try:
        from sysbrokers.IB.ib_connection import connectionIB
        conn = connectionIB(99)
        print(f"  ✅ Connected: {conn}")
        print(f"  Account: {conn.ib.managedAccounts()}")
        conn.close_connection()
        print("  Connection closed.")
        return True
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        print("  Make sure IB Gateway is running on port 4001")
        return False


def strategy_a_csv_to_db(instruments=None):
    """
    Strategy A: Copy shipped CSV data to database.
    Fast, no IB needed, data goes back decades but stale (~March 2024).
    """
    print("\n" + "=" * 70)
    print("  STRATEGY A: CSV → Database (Quick Start)")
    print("=" * 70)

    from sysinit.futures.multiple_and_adjusted_from_csv_to_db import (
        init_db_with_csv_prices_for_code,
    )
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData

    csv_data = csvFuturesSimData()
    all_instruments = csv_data.get_instrument_list()

    if instruments:
        target = [i for i in instruments if i in all_instruments]
        missing = [i for i in instruments if i not in all_instruments]
        if missing:
            print(f"  ⚠️  Not in CSV data: {', '.join(missing)}")
    else:
        target = all_instruments

    print(f"  Processing {len(target)} instruments...")

    for i, code in enumerate(target, 1):
        try:
            print(f"  [{i}/{len(target)}] {code}...", end=" ", flush=True)
            init_db_with_csv_prices_for_code(code)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")

    print(f"\n  ✅ Strategy A complete. {len(target)} instruments loaded to DB.")


def strategy_b_hybrid_update(instruments):
    """
    Strategy B: Hybrid — CSV base + fresh IB data.
    Maximizes historical depth by splicing IB onto shipped data.
    """
    if not instruments:
        print("❌ Strategy B requires --instruments. Example:")
        print("   python scripts/data_pipeline.py --strategy B --instruments SP500_micro,CRUDE_W")
        return

    print("\n" + "=" * 70)
    print("  STRATEGY B: Hybrid Update (CSV base + IB fresh data)")
    print("=" * 70)

    import pandas as pd
    from sysdata.data_blob import dataBlob
    from sysproduction.data.prices import diagPrices, updatePrices
    from sysproduction.data.broker import dataBroker
    from sysinit.futures.seed_price_data_from_IB import seed_price_data_from_IB
    from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
        process_multiple_prices_single_instrument,
    )
    from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
        process_adjusted_prices_single_instrument,
    )
    from sysinit.futures.multiple_and_adjusted_from_csv_to_db import (
        init_db_with_csv_prices_for_code,
    )

    for code in instruments:
        print(f"\n  📊 Processing {code}...")

        # Step 1: Load shipped CSV base into DB
        print(f"    Step 1: Loading CSV base data...", end=" ", flush=True)
        try:
            init_db_with_csv_prices_for_code(code)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            continue

        # Step 2: Seed fresh contract prices from IB
        print(f"    Step 2: Downloading fresh data from IB...", end=" ", flush=True)
        try:
            seed_price_data_from_IB(code)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            print(f"    ⚠️  Continuing with CSV-only data for {code}")

        # Step 3: Regenerate adjusted prices
        print(f"    Step 3: Regenerating back-adjusted prices...", end=" ", flush=True)
        try:
            process_adjusted_prices_single_instrument(code, ADD_TO_DB=True, ADD_TO_CSV=False)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")

    print(f"\n  ✅ Strategy B complete.")

    # Auto-sync parquet → CSV so backtesting picks up fresh data
    parquet_to_csv(instruments)


def strategy_c_full_ib_build(instruments):
    """
    Strategy C: Full IB build from scratch.
    Limited to ~1 year of history but fully fresh.
    """
    if not instruments:
        print("❌ Strategy C requires --instruments. Example:")
        print("   python scripts/data_pipeline.py --strategy C --instruments SP500_micro")
        return

    print("\n" + "=" * 70)
    print("  STRATEGY C: Full IB Build (fresh data only)")
    print("=" * 70)

    from sysinit.futures.seed_price_data_from_IB import seed_price_data_from_IB
    from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
        build_and_write_roll_calendar,
    )
    from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
        process_multiple_prices_single_instrument,
    )
    from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
        process_adjusted_prices_single_instrument,
    )

    roll_cal_path = str(PROJECT_ROOT / "data" / "futures" / "roll_calendars_from_ib")
    os.makedirs(roll_cal_path, exist_ok=True)

    for code in instruments:
        print(f"\n  📊 Processing {code}...")

        # Step 1: Seed contract prices from IB
        print(f"    Step 1: Downloading contract prices from IB...", end=" ", flush=True)
        try:
            seed_price_data_from_IB(code)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            continue

        # Step 2: Build roll calendar
        print(f"    Step 2: Building roll calendar...", end=" ", flush=True)
        try:
            build_and_write_roll_calendar(code, output_datapath=roll_cal_path)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            continue

        # Step 3: Create multiple prices
        print(f"    Step 3: Creating multiple prices...", end=" ", flush=True)
        try:
            process_multiple_prices_single_instrument(
                code,
                csv_roll_data_path=roll_cal_path,
                ADD_TO_DB=True,
                ADD_TO_CSV=False,
            )
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            continue

        # Step 4: Create adjusted prices
        print(f"    Step 4: Creating back-adjusted prices...", end=" ", flush=True)
        try:
            process_adjusted_prices_single_instrument(code, ADD_TO_DB=True, ADD_TO_CSV=False)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")

    print(f"\n  ✅ Strategy C complete.")


def parquet_to_csv(instruments=None):
    """Convert parquet adjusted prices to CSV for backtesting."""
    import pandas as pd

    parquet_dir = PROJECT_ROOT / "data" / "parquet_store" / "futures_adjusted_prices"
    csv_dir = PROJECT_ROOT / "data" / "futures" / "adjusted_prices_csv"

    if not parquet_dir.exists():
        print(f"  ❌ No parquet data found at {parquet_dir}")
        return

    all_files = sorted(parquet_dir.glob("*.parquet"))
    if instruments:
        files = [f for f in all_files if f.stem in instruments]
    else:
        files = all_files

    if not files:
        print(f"  ⚠️  No parquet files found{' for ' + ','.join(instruments) if instruments else ''}")
        return

    print(f"\n  📦 Converting {len(files)} parquet file(s) → CSV...")
    for f in files:
        df = pd.read_parquet(f)
        out = csv_dir / f"{f.stem}.csv"
        df.index.name = "DATETIME"
        df.to_csv(out)
        print(f"    ✅ {f.stem}: {len(df):,} rows → {out.name}")

    print(f"  ✅ Parquet → CSV sync complete.\n")


def get_prices(instrument, start_date=None, output_dir=None):
    """Retrieve back-adjusted prices for an instrument."""
    from sysdata.sim.csv_futures_sim_data import csvFuturesSimData

    print(f"\n📊 Retrieving back-adjusted prices for {instrument}...")

    data = csvFuturesSimData()

    if instrument not in data.get_instrument_list():
        print(f"  ❌ Instrument '{instrument}' not found in CSV data.")
        print(f"  Available: {', '.join(sorted(data.get_instrument_list())[:20])}...")
        return None

    prices = data.get_raw_price(instrument)

    if start_date:
        prices = prices[start_date:]

    # Get metadata
    meta = data.get_instrument_object_with_meta_data(instrument)

    print(f"\n  Instrument: {instrument}")
    print(f"  Metadata: {meta}")
    print(f"  Date range: {prices.index[0].strftime('%Y-%m-%d')} → {prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"  Total days: {len(prices):,}")
    print(f"  Last price: {prices.iloc[-1]:.4f}")
    print(f"\n  Last 10 prices:")
    print(prices.tail(10).to_string())

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{instrument}_adjusted.csv")
        prices.to_csv(output_path, header=["price"])
        print(f"\n  💾 Exported to: {output_path}")

    return prices


def main():
    parser = argparse.ArgumentParser(
        description="pysystemtrade Data Pipeline — Back-Adjusted Futures Prices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list-instruments                          Show all available instruments
  %(prog)s --check-ib                                  Test IB Gateway connection
  %(prog)s --strategy A                                Quick: copy all CSV → DB
  %(prog)s --strategy A --instruments SP500_micro,GOLD  Quick: specific instruments
  %(prog)s --strategy B --instruments SP500_micro       Hybrid: CSV base + IB fresh
  %(prog)s --strategy C --instruments SP500_micro       Full IB build
  %(prog)s --get-prices SP500_micro                     Retrieve adjusted prices
  %(prog)s --get-prices SP500_micro --start 2000-01-01 --output ./prices/
        """,
    )

    parser.add_argument("--list-instruments", action="store_true", help="Show available instruments")
    parser.add_argument("--check-ib", action="store_true", help="Test IB Gateway connection")
    parser.add_argument("--strategy", choices=["A", "B", "C"], help="Data pipeline strategy")
    parser.add_argument("--instruments", type=str, help="Comma-separated instrument codes")
    parser.add_argument("--parquet-to-csv", action="store_true",
                        help="Convert parquet adjusted prices to CSV")
    parser.add_argument("--get-prices", type=str, metavar="INSTRUMENT", help="Get adjusted prices")
    parser.add_argument("--start", type=str, help="Start date filter (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, help="Output directory for CSV export")

    args = parser.parse_args()

    instruments = args.instruments.split(",") if args.instruments else None

    if args.list_instruments:
        list_instruments()
    elif args.check_ib:
        check_ib_connection()
    elif args.strategy == "A":
        strategy_a_csv_to_db(instruments)
    elif args.strategy == "B":
        strategy_b_hybrid_update(instruments)
    elif args.strategy == "C":
        strategy_c_full_ib_build(instruments)
    elif args.parquet_to_csv:
        parquet_to_csv(instruments)
    elif args.get_prices:
        get_prices(args.get_prices, start_date=args.start, output_dir=args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
