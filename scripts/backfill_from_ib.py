"""
Backfill Gap Data from IBKR → pysystemtrade CSV
================================================
Uses pysystemtrade native modules:
  - seed_price_data_from_IB: downloads all available contract data from IBKR
  - update_multiple_adjusted_prices: rebuilds multiple + adjusted prices
  - Export: dumps MongoDB → CSV for backtest consumption

Gap period: ~2024-03-28 to ~2025-03-31 across all 25 production instruments.
"""

import sys
import os
import time
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/Users/msyeom/Developer/pysystemtrade')
os.chdir('/Users/msyeom/Developer/pysystemtrade')

print("Loading config from /Users/msyeom/Developer/pysystemtrade/private/private_config.yaml")

# Production 25-instrument universe
PRODUCTION_INSTRUMENTS = [
    'SP500_micro', 'NASDAQ_micro', 'DAX', 'NIKKEI', 'FTSE100',
    'IBEX_mini', 'FTSECHINAA', 'US10', 'US5', 'BUND',
    'GILT', 'JGB', 'GOLD_micro', 'SILVER', 'COPPER-micro',
    'CRUDE_W', 'BRENT-LAST', 'GASOIL', 'AUD_micro', 'MXP',
    'YENEUR', 'SUGAR11', 'COTTON', 'LEANHOG', 'COCOA_LDN',
]

# Also seed the extended universe used in sweeps
EXTENDED_INSTRUMENTS = [
    'SP500', 'BOBL', 'BONO', 'BUTTER', 'CHEESE', 'CHFJPY', 'CLP',
    'COFFEE', 'EU-BANKS', 'EU-DJ-OIL', 'EU-DJ-TELECOM', 'EURIBOR',
    'EURIBOR-ICE', 'FED', 'FEEDCOW', 'GASOIL', 'GOLD',
    'INR', 'LIVECOW', 'LUMBER-new', 'NIKKEI', 'OAT', 'OJ', 'PLN',
    'REDWHEAT', 'RICE', 'SPI200', 'TOPIX', 'TWD-mini',
    'US-DISCRETE', 'US-STAPLES', 'US-UTILS',
]


def step0_check_connectivity():
    """Verify IBKR Gateway is reachable"""
    print("\n" + "=" * 60)
    print("STEP 0: Connectivity Check")
    print("=" * 60)

    try:
        from ib_insync import IB
        ib = IB()
        ib.connect('127.0.0.1', 4001, clientId=99)
        connected = ib.isConnected()
        ib.disconnect()
        if connected:
            print("  ✅ IBKR Gateway connected")
            return True
        else:
            print("  ❌ IBKR Gateway not connected")
            return False
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False


def step1_seed_from_ib(instruments, skip_existing=True):
    """
    Download all available contract prices from IBKR using native
    pysystemtrade seed_price_data_from_IB.
    This handles expired contracts automatically.
    """
    print("\n" + "=" * 60)
    print("STEP 1: Seed contract prices from IBKR")
    print(f"  Instruments: {len(instruments)}")
    print("=" * 60)

    from sysinit.futures.seed_price_data_from_IB import seed_price_data_from_IB

    results = {'success': [], 'failed': [], 'skipped': []}

    for i, inst in enumerate(instruments):
        print(f"\n  [{i+1}/{len(instruments)}] {inst}...")

        try:
            seed_price_data_from_IB(inst)
            results['success'].append(inst)
            print(f"    ✅ Seeded successfully")
        except Exception as e:
            results['failed'].append((inst, str(e)))
            print(f"    ❌ Failed: {e}")

        # IBKR rate limit protection
        time.sleep(5)

    print(f"\n  Summary:")
    print(f"    ✅ Success: {len(results['success'])}")
    print(f"    ❌ Failed:  {len(results['failed'])}")
    if results['failed']:
        for inst, err in results['failed']:
            print(f"       - {inst}: {err}")

    return results


def step2_seed_csv_baseline(instruments):
    """
    Seed existing CSV multiple/adjusted prices into MongoDB
    so the rebuild step has a baseline to work from.
    """
    print("\n" + "=" * 60)
    print("STEP 2: Seed CSV baseline → MongoDB")
    print("=" * 60)

    from sysdata.data_blob import dataBlob
    from sysdata.csv.csv_multiple_prices import csvFuturesMultiplePricesData
    from sysdata.csv.csv_adjusted_prices import csvFuturesAdjustedPricesData
    from sysproduction.data.prices import diagPrices

    data = dataBlob(log_name="backfill_csv_seed")
    dp = diagPrices(data)

    # Multiple prices
    csv_mp = csvFuturesMultiplePricesData()
    db_mp = dp.db_futures_multiple_prices_data
    available = csv_mp.get_list_of_instruments()

    seeded = 0
    for inst in instruments:
        if inst in available:
            try:
                mp = csv_mp.get_multiple_prices(inst)
                db_mp.add_multiple_prices(inst, mp, ignore_duplication=True)
                seeded += 1
                print(f"    ✅ {inst} multiple_prices ({len(mp)} rows)")
            except Exception as e:
                print(f"    ⚠️  {inst}: {e}")

    # Adjusted prices
    csv_ap = csvFuturesAdjustedPricesData()
    db_ap = dp.db_futures_adjusted_prices_data
    available_adj = csv_ap.get_list_of_instruments()

    seeded_ap = 0
    for inst in instruments:
        if inst in available_adj:
            try:
                ap = csv_ap.get_adjusted_prices(inst)
                db_ap.add_adjusted_prices(inst, ap, ignore_duplication=True)
                seeded_ap += 1
            except Exception as e:
                print(f"    ⚠️  {inst} adjusted: {e}")

    # FX prices
    print("  Seeding FX prices...")
    from sysdata.csv.csv_spot_fx import csvFxPricesData
    from sysproduction.data.currency_data import dataCurrency
    csv_fx = csvFxPricesData()
    dc = dataCurrency(data)
    db_fx = dc.db_fx_prices_data
    for code in csv_fx.get_list_of_fxcodes():
        try:
            fx = csv_fx.get_fx_prices(code)
            db_fx.add_fx_prices(code=code, fx_price_data=fx, ignore_duplication=True)
        except:
            pass

    data.close()
    print(f"  ✅ Seeded {seeded} multiple, {seeded_ap} adjusted prices")


def step3_rebuild_multiple_adjusted(instruments):
    """Rebuild multiple and adjusted prices from contract data"""
    print("\n" + "=" * 60)
    print("STEP 3: Rebuild multiple + adjusted prices")
    print("=" * 60)

    from sysdata.data_blob import dataBlob
    from sysproduction.update_multiple_adjusted_prices import (
        update_multiple_adjusted_prices_for_instrument,
    )

    data = dataBlob(log_name="backfill_rebuild")
    success = 0

    for inst in instruments:
        try:
            update_multiple_adjusted_prices_for_instrument(inst, data)
            success += 1
            print(f"    ✅ {inst}")
        except Exception as e:
            print(f"    ⚠️  {inst}: {e}")

    data.close()
    print(f"  ✅ Rebuilt {success}/{len(instruments)}")


def step4_export_to_csv(instruments):
    """Export updated data from MongoDB back to CSV"""
    print("\n" + "=" * 60)
    print("STEP 4: Export MongoDB → CSV")
    print("=" * 60)

    from sysdata.data_blob import dataBlob
    from sysproduction.data.prices import diagPrices

    data = dataBlob(log_name="backfill_export")
    dp = diagPrices(data)

    # Export multiple prices
    mp_dir = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/multiple_prices_csv')
    ap_dir = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/adjusted_prices_csv')

    db_mp = dp.db_futures_multiple_prices_data
    db_ap = dp.db_futures_adjusted_prices_data

    exported_mp = 0
    exported_ap = 0

    for inst in instruments:
        # Multiple prices
        try:
            mp = db_mp.get_multiple_prices(inst)
            if len(mp) > 0:
                mp.to_csv(mp_dir / f'{inst}.csv', index_label='DATETIME')
                exported_mp += 1
                last_date = mp.index[-1].strftime('%Y-%m-%d')
                print(f"    ✅ {inst} multiple: {len(mp)} rows → {last_date}")
        except Exception as e:
            print(f"    ⚠️  {inst} multiple: {e}")

        # Adjusted prices
        try:
            ap = db_ap.get_adjusted_prices(inst)
            if len(ap) > 0:
                df = pd.DataFrame(ap)
                df.columns = ['price']
                df.to_csv(ap_dir / f'{inst}.csv', index_label='DATETIME')
                exported_ap += 1
                last_date = ap.index[-1].strftime('%Y-%m-%d')
                print(f"    ✅ {inst} adjusted: {len(ap)} rows → {last_date}")
        except Exception as e:
            print(f"    ⚠️  {inst} adjusted: {e}")

    data.close()
    print(f"\n  ✅ Exported {exported_mp} multiple, {exported_ap} adjusted prices")


def step5_verify(instruments):
    """Verify gap has been filled"""
    print("\n" + "=" * 60)
    print("VERIFICATION: Gap Analysis")
    print("=" * 60)

    ap_dir = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/adjusted_prices_csv')

    for inst in sorted(instruments):
        csv_path = ap_dir / f'{inst}.csv'
        if not csv_path.exists():
            print(f"  ❌ {inst}: CSV missing")
            continue

        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        dates = df.index.sort_values()

        # Check for gaps > 7 calendar days in 2024-2026
        recent = dates[dates >= '2024-01-01']
        gaps = []
        for i in range(1, len(recent)):
            gap_days = (recent[i] - recent[i-1]).days
            if gap_days > 7:
                gaps.append((recent[i-1], recent[i], gap_days))

        last_date = dates[-1].strftime('%Y-%m-%d')
        if gaps:
            gap_str = '; '.join([f"{g[0].strftime('%m/%d')}-{g[1].strftime('%m/%d')}({g[2]}d)" for g in gaps])
            print(f"  ⚠️  {inst:20s} last={last_date}  gaps: {gap_str}")
        else:
            print(f"  ✅ {inst:20s} last={last_date}  continuous ✓")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill futures data gaps from IBKR')
    parser.add_argument('--step', type=int, choices=[0, 1, 2, 3, 4, 5],
                        help='Run specific step (0=check, 1=seed IB, 2=seed CSV, 3=rebuild, 4=export, 5=verify)')
    parser.add_argument('--instruments', nargs='+',
                        help='Override instrument list')
    parser.add_argument('--extended', action='store_true',
                        help='Include extended universe beyond production 25')
    parser.add_argument('--verify-only', action='store_true',
                        help='Just run verification')
    args = parser.parse_args()

    instruments = args.instruments if args.instruments else PRODUCTION_INSTRUMENTS
    if args.extended:
        instruments = list(set(PRODUCTION_INSTRUMENTS + EXTENDED_INSTRUMENTS))

    if args.verify_only:
        step5_verify(instruments)
        sys.exit(0)

    if args.step is not None:
        if args.step == 0:
            step0_check_connectivity()
        elif args.step == 1:
            step1_seed_from_ib(instruments)
        elif args.step == 2:
            step2_seed_csv_baseline(instruments)
        elif args.step == 3:
            step3_rebuild_multiple_adjusted(instruments)
        elif args.step == 4:
            step4_export_to_csv(instruments)
        elif args.step == 5:
            step5_verify(instruments)
    else:
        # Full pipeline
        print("🚀 FULL BACKFILL PIPELINE")
        print(f"   Instruments: {len(instruments)}")
        print(f"   IB Gateway: 127.0.0.1:4001")
        start_time = datetime.now()

        if not step0_check_connectivity():
            print("❌ Cannot proceed without IBKR connection")
            sys.exit(1)

        step2_seed_csv_baseline(instruments)
        step1_seed_from_ib(instruments)
        step3_rebuild_multiple_adjusted(instruments)
        step4_export_to_csv(instruments)
        step5_verify(instruments)

        elapsed = (datetime.now() - start_time).total_seconds() / 60
        print(f"\n\n✅ BACKFILL COMPLETE! ({elapsed:.1f} minutes)")
