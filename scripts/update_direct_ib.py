"""
Practical IB Price Update for Simulation
========================================
Approach: For each instrument, download prices from IB for the nearest
active contract, then append to the existing adjusted_prices_csv.

The back-adjustment is maintained by computing the panama-canal stitch
using the overlap between the old and new front-month contracts.

Key insight: pysystemtrade sim data only needs adjusted_prices_csv.
We don't need the full production pipeline.
"""

import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/msyeom/Developer/pysystemtrade')
os.chdir('/Users/msyeom/Developer/pysystemtrade')

print("Loading config from /Users/msyeom/Developer/pysystemtrade/private/private_config.yaml")

from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker
from sysobjects.contracts import futuresContract
from syscore.dateutils import DAILY_PRICE_FREQ

CSV_DIR = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/adjusted_prices_csv')
BACKUP_DIR = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/adjusted_prices_csv_backup_20240328')
MULTI_CSV_DIR = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/multiple_prices_csv')

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

# FX pairs needed for pysystemtrade (mapping instrument currency → XXXUSD)
FX_CSV_DIR = Path('/Users/msyeom/Developer/pysystemtrade/data/futures/fx_prices_csv')


def backup_existing_csv():
    """Backup existing CSV files before modification"""
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True)
        import shutil
        for f in CSV_DIR.glob('*.csv'):
            shutil.copy2(f, BACKUP_DIR / f.name)
        print(f"  ✅ Backed up {len(list(BACKUP_DIR.glob('*.csv')))} CSV files to {BACKUP_DIR.name}/")
    else:
        print(f"  ⏭️  Backup already exists at {BACKUP_DIR.name}/")


def get_multiple_prices_contracts(instrument_code):
    """
    Read the multiple_prices_csv to find which contracts were used 
    at the end of the data (2024-03-28)
    """
    mp_path = MULTI_CSV_DIR / f'{instrument_code}.csv'
    if not mp_path.exists():
        return None, None, None
    
    df = pd.read_csv(mp_path, index_col=0, parse_dates=True)
    last_row = df.iloc[-1]
    
    price_contract = str(int(last_row.get('PRICE_CONTRACT', 0)))
    carry_contract = str(int(last_row.get('CARRY_CONTRACT', 0)))
    forward_contract = str(int(last_row.get('FORWARD_CONTRACT', 0)))
    
    return price_contract, carry_contract, forward_contract


def download_front_month_prices(data_broker, instrument_code, num_contracts=3):
    """
    Download prices for the nearest N contracts from IB.
    Returns dict of {contract_date: pd.DataFrame}
    """
    try:
        contracts = data_broker.get_list_of_contract_dates_for_instrument_code(
            instrument_code, allow_expired=False  
        )
        contracts.sort()
    except Exception as e:
        print(f"    ❌ Can't get contract chain: {e}")
        return None
    
    if len(contracts) == 0:
        print(f"    ❌ No contracts available")
        return None
    
    print(f"    IB contracts: {contracts[:5]}...")
    
    result = {}
    for cdate in contracts[:num_contracts]:
        try:
            contract = futuresContract(instrument_code, cdate[:6])
            prices = data_broker.get_prices_at_frequency_for_potentially_expired_contract_object(
                contract, frequency=DAILY_PRICE_FREQ
            )
            if prices is not None and len(prices) > 0:
                # Extract FINAL (close) price
                final = prices.return_final_prices()
                result[cdate[:6]] = final
                print(f"    ✅ {cdate[:6]}: {len(final)} days ({final.index[0].strftime('%Y-%m-%d')} → {final.index[-1].strftime('%Y-%m-%d')})")
            time.sleep(0.5)  # pacing
        except Exception as e:
            print(f"    ⚠️  {cdate[:6]}: {e}")
    
    # Also try to get recently expired contracts (for stitching)
    try:
        expired = data_broker.get_list_of_contract_dates_for_instrument_code(
            instrument_code, allow_expired=True
        )
        expired.sort()
        # Find contracts that expired recently (within last 2 years)
        recent_expired = [c for c in expired 
                         if c not in [x[:len(c)] for x in contracts] 
                         and c[:4] >= '2023']
        
        for cdate in recent_expired[-3:]:  # last 3 expired
            if cdate[:6] not in result:
                try:
                    contract = futuresContract(instrument_code, cdate[:6])
                    prices = data_broker.get_prices_at_frequency_for_potentially_expired_contract_object(
                        contract, frequency=DAILY_PRICE_FREQ
                    )
                    if prices is not None and len(prices) > 0:
                        final = prices.return_final_prices()
                        result[cdate[:6]] = final
                        print(f"    ✅ {cdate[:6]} (expired): {len(final)} days ({final.index[-1].strftime('%Y-%m-%d')})")
                    time.sleep(0.5)
                except Exception:
                    pass
    except Exception:
        pass
    
    return result


def stitch_adjusted_prices(existing_adj, new_front_prices, old_contract, new_contract):
    """
    Panama canal stitching: compute offset from overlapping period
    and apply to new prices to splice smoothly.
    
    existing_adj: existing back-adjusted price series
    new_front_prices: raw prices for new front-month contract
    old_contract / new_contract: contract identifiers
    """
    last_existing_date = existing_adj.index[-1]
    
    # Find overlap: dates where both old adjusted and new raw exist
    overlap_start = max(new_front_prices.index[0], existing_adj.index[0])
    overlap_end = last_existing_date
    
    if overlap_start > overlap_end:
        # No overlap — use level matching at the boundary
        # Just find the closest dates
        new_at_boundary = new_front_prices.loc[new_front_prices.index > last_existing_date]
        if len(new_at_boundary) == 0:
            return existing_adj  # nothing to add
        
        # Compute offset from last known adjusted vs first new raw price
        last_adj_val = existing_adj.iloc[-1]
        first_new_val = new_at_boundary.iloc[0]
        offset = last_adj_val - first_new_val
        
        new_adjusted = new_at_boundary + offset
    else:
        # Has overlap — compute average offset during overlap
        overlap_adj = existing_adj.loc[overlap_start:overlap_end]
        overlap_new = new_front_prices.loc[overlap_start:overlap_end]
        
        # Align by date
        common_dates = overlap_adj.index.intersection(overlap_new.index)
        if len(common_dates) > 0:
            offset = (overlap_adj.loc[common_dates] - overlap_new.loc[common_dates]).mean()
        else:
            offset = existing_adj.iloc[-1] - new_front_prices.loc[new_front_prices.index <= last_existing_date].iloc[-1]
        
        # Apply offset to new prices beyond existing data
        new_prices_after = new_front_prices.loc[new_front_prices.index > last_existing_date]
        if len(new_prices_after) == 0:
            return existing_adj
        
        new_adjusted = new_prices_after + offset
    
    # Concatenate
    combined = pd.concat([existing_adj, new_adjusted])
    combined = combined[~combined.index.duplicated(keep='first')]
    combined = combined.sort_index()
    
    return combined


def update_fx_prices(data_broker):
    """Update FX spot prices from IB"""
    print("\n" + "=" * 60)
    print("UPDATING FX PRICES")
    print("=" * 60)
    
    from sysbrokers.IB.ib_spot_FX_data import ibFxPricesData
    
    fx_codes_map = {
        'EURUSD': ('EUR', 'USD'),
        'GBPUSD': ('GBP', 'USD'),
        'AUDUSD': ('AUD', 'USD'),
        'JPYUSD': ('JPY', 'USD'),
        'CHFUSD': ('CHF', 'USD'),
        'CADUSD': ('CAD', 'USD'),
        'MXPUSD': ('MXN', 'USD'),
        'HKDUSD': ('HKD', 'USD'),
        'CNHUSD': ('CNH', 'USD'),
        'KRWUSD': ('KRW', 'USD'),
    }
    
    updated = 0
    for code, (base, quote) in fx_codes_map.items():
        csv_path = FX_CSV_DIR / f'{code}.csv'
        if not csv_path.exists():
            continue
        
        existing = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        last_date = existing.index[-1]
        
        if last_date.year >= 2026:
            print(f"  ⏭️  {code}: already up to date ({last_date.strftime('%Y-%m-%d')})")
            continue
        
        # We can't easily get FX history from IB without the full broker setup
        # For now, mark as needing update
        print(f"  ⚠️  {code}: last date {last_date.strftime('%Y-%m-%d')} — needs manual update")
    
    return updated


def update_instrument(data_broker, instrument_code):
    """Full update for one instrument"""
    csv_path = CSV_DIR / f'{instrument_code}.csv'
    if not csv_path.exists():
        print(f"    ❌ No existing CSV file")
        return False
    
    # Load existing adjusted prices
    existing = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    existing_prices = existing.iloc[:, 0]  # First column = price
    last_date = existing_prices.index[-1]
    print(f"    Existing data: {len(existing_prices)} rows → {last_date.strftime('%Y-%m-%d')}")
    
    if last_date.year >= 2026 and last_date.month >= 3:
        print(f"    ⏭️  Already up to date!")
        return True
    
    # Download front-month prices from IB
    contract_prices = download_front_month_prices(data_broker, instrument_code)
    if not contract_prices:
        return False
    
    # Find the contract whose price overlaps most with our existing data
    best_contract = None
    best_overlap = 0
    best_extension = 0
    
    for cdate, prices in sorted(contract_prices.items()):
        # Count overlap days with existing
        overlap = len(prices.index.intersection(existing_prices.index))
        # Count new days
        new_days = len(prices.loc[prices.index > last_date])
        
        if new_days > best_extension or (new_days == best_extension and overlap > best_overlap):
            best_contract = cdate
            best_overlap = overlap
            best_extension = new_days
    
    if best_contract is None or best_extension == 0:
        print(f"    ⏭️  No new data to add")
        return True
    
    print(f"    → Best contract for stitching: {best_contract} (overlap={best_overlap}, new_days={best_extension})")
    
    # If there are intermediate contracts (gap between old PRICE contract and best_contract),
    # chain-stitch through them
    old_price_contract, _, _ = get_multiple_prices_contracts(instrument_code)
    
    # Build chain of contracts to stitch
    sorted_contracts = sorted(contract_prices.keys())
    
    # Start stitching
    current_adj = existing_prices.copy()
    
    for cdate in sorted_contracts:
        prices = contract_prices[cdate]
        new_days = len(prices.loc[prices.index > current_adj.index[-1]])
        if new_days > 0:
            current_adj = stitch_adjusted_prices(current_adj, prices, None, cdate)
            print(f"    🔗 Stitched {cdate}: +{new_days} days → {current_adj.index[-1].strftime('%Y-%m-%d')}")
    
    # Save
    df_out = pd.DataFrame(current_adj)
    df_out.columns = ['price']
    df_out.to_csv(csv_path, index_label='DATETIME')
    print(f"    ✅ Saved: {len(current_adj)} rows → {current_adj.index[-1].strftime('%Y-%m-%d')}")
    
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Update adjusted prices from IB')
    parser.add_argument('--instruments', nargs='+', help='Specific instruments to update')
    parser.add_argument('--dry-run', action='store_true', help='Only check, do not write')
    args = parser.parse_args()

    instruments = args.instruments or INSTRUMENTS

    print("🚀 PRACTICAL IB PRICE UPDATE")
    print(f"   Instruments: {len(instruments)}")
    print(f"   CSV dir: {CSV_DIR}")
    print()

    # Step 0: Backup
    print("[Step 0] Backing up existing CSV files...")
    backup_existing_csv()

    # Step 1: Connect to IB
    print("\n[Step 1] Connecting to IB Gateway...")
    data = dataBlob(log_name="Practical-IB-Update")
    data_broker = dataBroker(data)
    print(f"  ✅ Connected")

    # Step 2: Update each instrument
    print(f"\n[Step 2] Updating {len(instruments)} instruments...")
    results = {'success': [], 'no_data': [], 'error': [], 'skipped': []}

    for i, inst in enumerate(instruments):
        print(f"\n[{i+1}/{len(instruments)}] {inst}")
        try:
            result = update_instrument(data_broker, inst)
            if result:
                results['success'].append(inst)
            else:
                results['no_data'].append(inst)
        except Exception as e:
            print(f"    ❌ {e}")
            results['error'].append(inst)
        
        time.sleep(1)  # IB pacing

    data.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  ✅ Updated: {len(results['success'])} — {', '.join(results['success'][:10])}{'...' if len(results['success']) > 10 else ''}")
    print(f"  ⏭️  No IB data: {len(results['no_data'])} — {', '.join(results['no_data'])}")
    print(f"  ❌ Error: {len(results['error'])} — {', '.join(results['error'])}")

    # Verify
    print("\n[Verification] Last dates:")
    for inst in sorted(instruments):
        csv_path = CSV_DIR / f'{inst}.csv'
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            last = df.index[-1].strftime('%Y-%m-%d')
            tag = "🆕" if "2026" in last or "2025" in last else "⬜"
            print(f"  {tag} {inst:<20} → {last}")


if __name__ == '__main__':
    main()
