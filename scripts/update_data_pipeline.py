"""
pysystemtrade Production Data Pipeline — Automated Update
=========================================================
Step 1: Seed CSV → MongoDB (multiple prices, adjusted prices, FX)
Step 2: Update contract prices from IB  
Step 3: Rebuild multiple + adjusted prices
Step 4: Export MongoDB → CSV (back to sim data directory)

Only updates the 46 instruments used in our backtest portfolio.
"""

import sys
import os
import time
import pandas as pd
from pathlib import Path

# Ensure we're in the right directory
sys.path.insert(0, '/Users/msyeom/Developer/pysystemtrade')
os.chdir('/Users/msyeom/Developer/pysystemtrade')

from sysdata.data_blob import dataBlob
from sysdata.csv.csv_multiple_prices import csvFuturesMultiplePricesData
from sysdata.csv.csv_adjusted_prices import csvFuturesAdjustedPricesData
from sysdata.csv.csv_spot_fx import csvFxPricesData
from sysproduction.data.prices import diagPrices, updatePrices
from sysproduction.data.currency_data import dataCurrency

print("Loading config from /Users/msyeom/Developer/pysystemtrade/private/private_config.yaml")

# Our 46 backtest instruments
INSTRUMENTS = [
    'AUD_micro', 'BOBL', 'BONO', 'BRENT-LAST', 'BUND', 'BUTTER', 'CHEESE',
    'CHFJPY', 'CLP', 'COCOA_LDN', 'COFFEE', 'COPPER-micro', 'COTTON',
    'CRUDE_W', 'EU-BANKS', 'EU-DJ-OIL', 'EU-DJ-TELECOM', 'EURIBOR',
    'EURIBOR-ICE', 'FED', 'FEEDCOW', 'FTSECHINAA', 'GASOIL', 'IBEX_mini',
    'INR', 'LEANHOG', 'LIVECOW', 'LUMBER-new', 'MXP', 'NASDAQ_micro',
    'OAT', 'OJ', 'PLN', 'REDWHEAT', 'RICE', 'SILVER', 'SPI200',
    'SUGAR11', 'SUGAR_WHITE', 'TOPIX', 'TWD-mini', 'US-DISCRETE',
    'US-STAPLES', 'US-UTILS', 'US5', 'YENEUR',
]


def step1_seed_csv_to_mongo():
    """Seed existing CSV data into MongoDB as baseline"""
    print("\n" + "=" * 60)
    print("STEP 1: Seeding CSV → MongoDB")
    print("=" * 60)

    data = dataBlob(log_name="seed_csv_to_mongo")
    dp = diagPrices(data)

    # 1a. Seed multiple prices
    print("\n  [1a] Seeding multiple prices...")
    csv_mp = csvFuturesMultiplePricesData()
    db_mp = dp.db_futures_multiple_prices_data
    available_in_csv = csv_mp.get_list_of_instruments()

    seeded_mp = 0
    for inst in INSTRUMENTS:
        if inst in available_in_csv:
            try:
                mp = csv_mp.get_multiple_prices(inst)
                db_mp.add_multiple_prices(inst, mp, ignore_duplication=True)
                seeded_mp += 1
                print(f"    ✅ {inst} ({len(mp)} rows)")
            except Exception as e:
                print(f"    ⚠️  {inst}: {e}")
        else:
            print(f"    ⏭️  {inst}: not in CSV multiple prices")
    print(f"  Multiple prices seeded: {seeded_mp}/{len(INSTRUMENTS)}")

    # 1b. Seed adjusted prices
    print("\n  [1b] Seeding adjusted prices...")
    csv_ap = csvFuturesAdjustedPricesData()
    db_ap = dp.db_futures_adjusted_prices_data
    available_adj = csv_ap.get_list_of_instruments()

    seeded_ap = 0
    for inst in INSTRUMENTS:
        if inst in available_adj:
            try:
                ap = csv_ap.get_adjusted_prices(inst)
                db_ap.add_adjusted_prices(inst, ap, ignore_duplication=True)
                seeded_ap += 1
                print(f"    ✅ {inst} ({len(ap)} rows)")
            except Exception as e:
                print(f"    ⚠️  {inst}: {e}")
        else:
            print(f"    ⏭️  {inst}: not in CSV adjusted prices")
    print(f"  Adjusted prices seeded: {seeded_ap}/{len(INSTRUMENTS)}")

    # 1c. Seed FX prices
    print("\n  [1c] Seeding FX spot prices...")
    csv_fx = csvFxPricesData()
    dc = dataCurrency()
    db_fx = dc.db_fx_prices_data
    all_fx = csv_fx.get_list_of_fxcodes()
    print(f"    Available FX pairs: {len(all_fx)}")

    seeded_fx = 0
    for code in all_fx:
        try:
            fx = csv_fx.get_fx_prices(code)
            db_fx.add_fx_prices(code=code, fx_price_data=fx, ignore_duplication=True)
            seeded_fx += 1
        except Exception as e:
            print(f"    ⚠️  {code}: {e}")
    print(f"  FX prices seeded: {seeded_fx}/{len(all_fx)}")

    data.close()
    print("\n  ✅ Step 1 complete!")
    return seeded_mp, seeded_ap


def step2_update_from_ib():
    """Update contract prices from IB for our instruments"""
    print("\n" + "=" * 60)
    print("STEP 2: Updating prices from IB Gateway")
    print("=" * 60)

    from sysproduction.update_historical_prices import (
        update_historical_prices_for_instrument,
    )
    from sysdata.tools.cleaner import get_config_for_price_filtering

    data = dataBlob(log_name="Update-Historical-Prices")
    cleaning_config = get_config_for_price_filtering(data)

    success_count = 0
    fail_count = 0

    for i, inst in enumerate(INSTRUMENTS):
        print(f"\n  [{i+1}/{len(INSTRUMENTS)}] {inst}...")
        try:
            result = update_historical_prices_for_instrument(
                inst, data,
                cleaning_config=cleaning_config,
                interactive_mode=False,
            )
            if result == 0:  # success constant
                success_count += 1
                print(f"    ✅ OK")
            else:
                print(f"    ⚠️  Result: {result}")
                fail_count += 1
        except Exception as e:
            print(f"    ❌ Error: {e}")
            fail_count += 1
        
        # Brief pause to avoid IB rate limits
        time.sleep(1)

    data.close()
    print(f"\n  ✅ Step 2 complete: {success_count} updated, {fail_count} failed")
    return success_count, fail_count


def step3_update_multiple_adjusted():
    """Rebuild multiple and adjusted prices from contract prices"""
    print("\n" + "=" * 60)
    print("STEP 3: Rebuilding multiple + adjusted prices")
    print("=" * 60)

    from sysproduction.update_multiple_adjusted_prices import (
        update_multiple_adjusted_prices_for_instrument,
    )

    data = dataBlob(log_name="Update-Multiple-Adjusted")
    success_count = 0

    for inst in INSTRUMENTS:
        try:
            update_multiple_adjusted_prices_for_instrument(inst, data)
            success_count += 1
            print(f"    ✅ {inst}")
        except Exception as e:
            print(f"    ⚠️  {inst}: {e}")

    data.close()
    print(f"\n  ✅ Step 3 complete: {success_count}/{len(INSTRUMENTS)}")


def step4_export_mongo_to_csv():
    """Export updated adjusted prices from MongoDB back to CSV for sim"""
    print("\n" + "=" * 60)
    print("STEP 4: Exporting MongoDB → CSV")
    print("=" * 60)

    data = dataBlob(log_name="export_to_csv")
    dp = diagPrices(data)
    db_ap = dp.db_futures_adjusted_prices_data

    csv_dir = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/adjusted_prices_csv')
    
    exported = 0
    for inst in INSTRUMENTS:
        try:
            ap = db_ap.get_adjusted_prices(inst)
            if len(ap) == 0:
                print(f"    ⏭️  {inst}: no data in MongoDB")
                continue

            # Write to CSV
            df = pd.DataFrame(ap)
            df.columns = ['price']
            csv_path = csv_dir / f'{inst}.csv'
            df.to_csv(csv_path, index_label='DATETIME')
            exported += 1
            print(f"    ✅ {inst}: {len(ap)} rows → {ap.index[-1].strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"    ⚠️  {inst}: {e}")

    # Also export FX
    print("\n  Exporting FX prices...")
    dc = dataCurrency(data)
    db_fx = dc.db_fx_prices_data
    fx_dir = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/fx_prices_csv')
    
    fx_exported = 0
    try:
        fx_codes = db_fx.get_list_of_fxcodes()
        for code in fx_codes:
            fx = db_fx.get_fx_prices(code)
            if len(fx) > 0:
                df = pd.DataFrame(fx)
                df.columns = ['price'] if len(df.columns) == 1 else df.columns
                csv_path = fx_dir / f'{code}.csv'
                df.to_csv(csv_path, index_label='DATETIME')
                fx_exported += 1
    except Exception as e:
        print(f"    ⚠️  FX export error: {e}")

    data.close()
    print(f"\n  ✅ Step 4 complete: {exported} instruments, {fx_exported} FX pairs exported to CSV")


def verify_update():
    """Verify the update worked by checking last dates"""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    csv_dir = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/adjusted_prices_csv')
    
    results = []
    for inst in sorted(INSTRUMENTS):
        csv_path = csv_dir / f'{inst}.csv'
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            last = df.index[-1].strftime('%Y-%m-%d')
            results.append((inst, last, len(df)))
    
    print(f"\n  {'Instrument':<20} {'Last Date':<15} {'Rows':>8}")
    print(f"  {'-'*20} {'-'*15} {'-'*8}")
    for inst, last, rows in results:
        marker = "🆕" if "2026" in last or "2025" in last else "  "
        print(f"  {marker} {inst:<20} {last:<15} {rows:>8}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Update pysystemtrade price data from IB')
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4], 
                        help='Run specific step only (1=seed, 2=IB update, 3=rebuild, 4=export)')
    parser.add_argument('--verify', action='store_true', help='Just verify current state')
    args = parser.parse_args()

    if args.verify:
        verify_update()
    elif args.step == 1:
        step1_seed_csv_to_mongo()
    elif args.step == 2:
        step2_update_from_ib()
    elif args.step == 3:
        step3_update_multiple_adjusted()
    elif args.step == 4:
        step4_export_mongo_to_csv()
    else:
        # Full pipeline
        print("🚀 FULL DATA UPDATE PIPELINE")
        print(f"   Instruments: {len(INSTRUMENTS)}")
        print(f"   IB Gateway: 127.0.0.1:4001")
        
        step1_seed_csv_to_mongo()
        step2_update_from_ib()
        step3_update_multiple_adjusted()
        step4_export_mongo_to_csv()
        verify_update()
        
        print("\n\n✅ PIPELINE COMPLETE!")
