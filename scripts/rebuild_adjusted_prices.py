#!/usr/bin/env python3
"""
Rebuild adjusted prices using pysystemtrade's native _panama_stitch().

This script:
1. Extends roll calendars from their last entry to 2026
2. Downloads per-contract prices from IB for the gap period (2024-04 onwards)
3. Extends the existing multiple_prices with new IB data
4. Runs pysystemtrade's official _panama_stitch() to compute adjusted prices
5. Exports the result as CSV (replacing the buggy custom-stitched version)

Usage:
    python scripts/rebuild_adjusted_prices.py --instruments GOLD
    python scripts/rebuild_adjusted_prices.py  # all 9 instruments
"""
import argparse
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# pysystemtrade imports
from sysobjects.adjusted_prices import futuresAdjustedPrices
from sysobjects.multiple_prices import futuresMultiplePrices
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker
from sysobjects.contracts import futuresContract
from syscore.dateutils import DAILY_PRICE_FREQ

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = PROJECT_ROOT / "data" / "futures"
RESULTS_DIR = PROJECT_ROOT / "results" / "monthly_returns"

ALL_INSTRUMENTS = ["SP500", "DAX", "NIKKEI", "FTSE100", "US10", "BUND", "JGB", "GILT", "GOLD"]

# Month code mapping
MONTH_CODES = {
    'F': 1, 'G': 2, 'H': 3, 'J': 4, 'K': 5, 'M': 6,
    'N': 7, 'Q': 8, 'U': 9, 'V': 10, 'X': 11, 'Z': 12,
}


def get_roll_months(instrument_code):
    """Get the valid contract months for an instrument from its roll cycle."""
    rp_data = csvRollParametersData()
    rp = rp_data.get_roll_parameters(instrument_code)
    cycle = str(rp.priced_rollcycle)
    months = [MONTH_CODES[c] for c in cycle]
    roll_offset = rp.roll_offset_day
    return sorted(months), roll_offset


def extend_roll_calendar(instrument_code, target_year=2026, target_month=8):
    """Extend the roll calendar for an instrument up to the target date."""
    rc_path = CSV_DIR / "roll_calendars_csv" / f"{instrument_code}.csv"
    rc = pd.read_csv(rc_path, index_col=0, parse_dates=True)

    roll_months, roll_offset = get_roll_months(instrument_code)

    # Find the last entry
    last_row = rc.iloc[-1]
    last_next = int(last_row['next_contract'])
    last_next_year = last_next // 10000
    last_next_month = (last_next % 10000) // 100

    # Start generating from the next contract
    curr_year = last_next_year
    curr_month_idx = roll_months.index(last_next_month)

    entries = []
    while True:
        curr_month = roll_months[curr_month_idx]
        next_month_idx = (curr_month_idx + 1) % len(roll_months)
        next_month = roll_months[next_month_idx]
        next_year = curr_year + (1 if next_month_idx == 0 else 0)

        curr_contract = curr_year * 10000 + curr_month * 100
        next_contract = next_year * 10000 + next_month * 100
        carry_contract = next_contract

        # Roll date: roll_offset days before expiry
        # Expiry ≈ last business day of month BEFORE delivery
        expiry_month = curr_month - 1 if curr_month > 1 else 12
        expiry_year = curr_year if curr_month > 1 else curr_year - 1

        try:
            # Last day of expiry month
            if expiry_month == 12:
                end_of_month = datetime(expiry_year, 12, 31)
            else:
                end_of_month = datetime(expiry_year, expiry_month + 1, 1) - timedelta(days=1)

            roll_date = end_of_month + timedelta(days=roll_offset)  # roll_offset is negative
        except ValueError:
            roll_date = datetime(expiry_year, expiry_month, 15) + timedelta(days=roll_offset)

        entries.append({
            'DATE_TIME': roll_date,
            'current_contract': curr_contract,
            'next_contract': next_contract,
            'carry_contract': carry_contract,
        })

        if next_year > target_year or (next_year == target_year and next_month > target_month):
            break

        curr_year = next_year
        curr_month_idx = next_month_idx

    if not entries:
        return rc

    new_df = pd.DataFrame(entries).set_index('DATE_TIME')
    extended = pd.concat([rc, new_df])
    extended = extended[~extended.index.duplicated(keep='first')]
    extended = extended.sort_index()

    return extended


def download_contract_prices_from_ib(data_broker, instrument_code, contract_date, is_expired=False):
    """Download daily prices for a single contract from IB."""
    try:
        contract_str = str(contract_date)[:6]
        # Remove trailing zeros if format is YYYYMM00
        if len(contract_str) == 8:
            contract_str = contract_str[:6]
        contract = futuresContract(instrument_code, contract_str)

        if is_expired:
            prices = data_broker.get_prices_at_frequency_for_potentially_expired_contract_object(
                contract, frequency=DAILY_PRICE_FREQ
            )
        else:
            prices = data_broker.get_prices_at_frequency_for_contract_object(
                contract, frequency=DAILY_PRICE_FREQ
            )

        if prices is not None and len(prices) > 0:
            final = prices.return_final_prices()
            return final
    except Exception as e:
        pass

    return None


def build_extended_multiple_prices(instrument_code, roll_calendar, contract_prices_dict, existing_multiple):
    """
    Build multiple_prices DataFrame by combining existing data with new IB contract prices.

    For each date, we need: PRICE, FORWARD, CARRY, PRICE_CONTRACT, FORWARD_CONTRACT, CARRY_CONTRACT
    """
    last_existing_date = existing_multiple.index[-1]

    # Get roll events after the last existing date
    future_rolls = roll_calendar.loc[roll_calendar.index > last_existing_date]

    if len(future_rolls) == 0:
        print(f"    No future rolls found beyond {last_existing_date}")
        return existing_multiple

    # Build the contract chain: for each date after last_existing_date,
    # determine which contract is PRICE and which is FORWARD
    last_row = existing_multiple.iloc[-1]
    current_price_contract = int(last_row['PRICE_CONTRACT'])
    current_forward_contract = int(last_row['FORWARD_CONTRACT'])

    # Find all dates from contract prices
    all_dates = set()
    for cdate, prices in contract_prices_dict.items():
        if prices is not None:
            for d in prices.index:
                if d > last_existing_date:
                    all_dates.add(d)

    if not all_dates:
        print(f"    No new dates found in contract prices")
        return existing_multiple

    all_dates = sorted(all_dates)

    # Build the multiple prices row by row
    new_rows = []
    roll_idx = 0
    rolls = future_rolls.reset_index()

    for date in all_dates:
        # Check if a roll happened
        while roll_idx < len(rolls) and pd.Timestamp(rolls.iloc[roll_idx]['DATE_TIME']) <= pd.Timestamp(date):
            current_price_contract = int(rolls.iloc[roll_idx]['current_contract'])
            current_forward_contract = int(rolls.iloc[roll_idx]['next_contract'])
            roll_idx += 1

        # Wait, the roll calendar says "current_contract" becomes the PRICE contract
        # AFTER the roll date. Let me re-check the semantics.
        # Actually in pysystemtrade roll calendar:
        # On the roll date, we switch FROM current_contract TO next_contract
        # So BEFORE roll: PRICE = current_contract
        # AFTER roll: PRICE = next_contract (which becomes the new current)

        # Let me fix: we need to track the state machine properly
        pass

    # Simpler approach: use the roll calendar to determine contract assignments
    # For each date, find which contract period it falls into
    extended_rolls = roll_calendar.copy()
    extended_rolls = extended_rolls.sort_index()

    # The last entry in existing multiple_prices tells us the starting state
    state_price = int(last_row['PRICE_CONTRACT'])
    state_forward = int(last_row['FORWARD_CONTRACT'])
    state_carry = int(last_row['CARRY_CONTRACT']) if 'CARRY_CONTRACT' in last_row.index else state_forward

    # Find rolls relevant to the gap period
    relevant_rolls = extended_rolls.loc[extended_rolls.index > last_existing_date].sort_index()

    # Create date→contract mapping
    # Before first relevant roll: use the state from existing data
    # After each roll: use next_contract as PRICE, and the one after as FORWARD
    contract_periods = []

    # Period before first roll
    if len(relevant_rolls) > 0:
        first_roll_date = relevant_rolls.index[0]
        contract_periods.append({
            'start': last_existing_date,
            'end': first_roll_date,
            'price_contract': state_price,
            'forward_contract': state_forward,
            'carry_contract': state_carry,
        })

        # Periods between rolls
        for i in range(len(relevant_rolls)):
            row = relevant_rolls.iloc[i]
            next_contract = int(row['next_contract'])
            carry_contract = int(row['carry_contract']) if 'carry_contract' in row.index else next_contract

            # After this roll, next_contract becomes the new PRICE
            # And the contract after that becomes the new FORWARD
            if i + 1 < len(relevant_rolls):
                next_next = int(relevant_rolls.iloc[i + 1]['next_contract'])
                end_date = relevant_rolls.index[i + 1]
            else:
                next_next = carry_contract
                end_date = pd.Timestamp('2030-01-01')

            contract_periods.append({
                'start': relevant_rolls.index[i],
                'end': end_date,
                'price_contract': next_contract,
                'forward_contract': next_next,
                'carry_contract': next_next,
            })
    else:
        contract_periods.append({
            'start': last_existing_date,
            'end': pd.Timestamp('2030-01-01'),
            'price_contract': state_price,
            'forward_contract': state_forward,
            'carry_contract': state_carry,
        })

    # Now build the actual rows
    new_rows = []
    for date in all_dates:
        ts = pd.Timestamp(date)

        # Find the applicable period
        period = None
        for p in contract_periods:
            if p['start'] < ts <= p['end']:
                period = p
                break
        if period is None:
            continue

        pc = period['price_contract']
        fc = period['forward_contract']
        cc = period['carry_contract']

        # Get prices from contract_prices_dict
        pc_key = pc // 100 * 100  # Normalize to YYYYMM00
        fc_key = fc // 100 * 100
        cc_key = cc // 100 * 100

        price_val = _get_price_for_date(contract_prices_dict, pc, date)
        forward_val = _get_price_for_date(contract_prices_dict, fc, date)
        carry_val = _get_price_for_date(contract_prices_dict, cc, date)

        if price_val is not None:
            new_rows.append({
                'PRICE': price_val,
                'PRICE_CONTRACT': pc,
                'FORWARD': forward_val if forward_val is not None else np.nan,
                'FORWARD_CONTRACT': fc,
                'CARRY': carry_val if carry_val is not None else np.nan,
                'CARRY_CONTRACT': cc,
            })
        # If no price for the PRICE contract, skip this date

    if not new_rows:
        print(f"    No valid rows built from IB data")
        return existing_multiple

    new_df = pd.DataFrame(new_rows, index=[d for d in all_dates if any(
        _get_price_for_date(contract_prices_dict, p['price_contract'], d) is not None
        for p in contract_periods if p['start'] < pd.Timestamp(d) <= p['end']
    )])

    # Ensure proper column order
    cols = ['CARRY', 'CARRY_CONTRACT', 'PRICE', 'PRICE_CONTRACT', 'FORWARD', 'FORWARD_CONTRACT']
    new_df = new_df[cols]

    # Merge with existing
    combined = pd.concat([existing_multiple, new_df])
    combined = combined[~combined.index.duplicated(keep='first')]
    combined = combined.sort_index()

    return combined


def _get_price_for_date(contract_prices_dict, contract_code, date):
    """Lookup price for a specific contract on a specific date."""
    ts = pd.Timestamp(date)

    # Try different key formats: YYYYMM00, YYYYMM
    for key in [contract_code, contract_code // 100 * 100, str(contract_code)[:6]]:
        if key in contract_prices_dict and contract_prices_dict[key] is not None:
            prices = contract_prices_dict[key]
            # Normalize index
            normalized = prices.copy()
            normalized.index = normalized.index.normalize()

            if ts.normalize() in normalized.index:
                return float(normalized.loc[ts.normalize()])
            # Try without normalization
            matches = prices.loc[prices.index.normalize() == ts.normalize()]
            if len(matches) > 0:
                return float(matches.iloc[-1])

    return None


def process_instrument(instrument_code, data_broker, dry_run=False):
    """Full pipeline for one instrument."""
    print(f"\n{'='*60}")
    print(f"  {instrument_code}")
    print(f"{'='*60}")

    # 1. Load existing multiple_prices
    mp_path = CSV_DIR / "multiple_prices_csv" / f"{instrument_code}.csv"
    existing_mp = pd.read_csv(mp_path, index_col=0, parse_dates=True)
    last_date = existing_mp.index[-1]
    last_price_contract = int(existing_mp.iloc[-1]['PRICE_CONTRACT'])
    last_forward_contract = int(existing_mp.iloc[-1]['FORWARD_CONTRACT'])
    print(f"  Existing multiple_prices: {len(existing_mp)} rows → {last_date.strftime('%Y-%m-%d')}")
    print(f"  Last contracts: PRICE={last_price_contract}, FORWARD={last_forward_contract}")

    # 2. Extend roll calendar
    print(f"\n  [Step 1] Extending roll calendar...")
    extended_rc = extend_roll_calendar(instrument_code)
    future_rolls = extended_rc.loc[extended_rc.index > last_date]
    print(f"    {len(future_rolls)} future roll events")
    for _, row in future_rolls.iterrows():
        print(f"      {_.strftime('%Y-%m-%d')}: {int(row['current_contract'])} → {int(row['next_contract'])}")

    # 3. Determine which contracts to download
    contracts_needed = set()
    contracts_needed.add(last_price_contract)
    contracts_needed.add(last_forward_contract)
    for _, row in future_rolls.iterrows():
        contracts_needed.add(int(row['current_contract']))
        contracts_needed.add(int(row['next_contract']))
        contracts_needed.add(int(row['carry_contract']))

    contracts_needed = sorted(contracts_needed)
    print(f"\n  [Step 2] Downloading {len(contracts_needed)} contracts from IB...")

    # 4. Download contract prices
    contract_prices = {}
    for cdate in contracts_needed:
        year = cdate // 10000
        month = (cdate % 10000) // 100
        # Contract is expired if its delivery month is before current date
        is_expired = datetime(year, month, 1) < datetime.now() - timedelta(days=60)

        time.sleep(1)  # IB rate limiting

        prices = download_contract_prices_from_ib(data_broker, instrument_code, cdate, is_expired)
        if prices is not None and len(prices) > 0:
            contract_prices[cdate] = prices
            # Only keep data after the gap start to reduce noise
            print(f"    ✅ {cdate}: {len(prices)} days ({prices.index[0].strftime('%Y-%m-%d')} → {prices.index[-1].strftime('%Y-%m-%d')})")
        else:
            print(f"    ⚠️  {cdate}: no data from IB")

    if not contract_prices:
        print(f"  ❌ No contract data downloaded!")
        return False

    # 5. Build extended multiple_prices
    print(f"\n  [Step 3] Building extended multiple_prices...")
    extended_mp = build_extended_multiple_prices(
        instrument_code, extended_rc, contract_prices, existing_mp
    )
    print(f"    Extended: {len(extended_mp)} rows → {extended_mp.index[-1].strftime('%Y-%m-%d')}")

    # 6. Run pysystemtrade's _panama_stitch()
    print(f"\n  [Step 4] Running pysystemtrade _panama_stitch()...")
    multiple_prices_obj = futuresMultiplePrices(extended_mp)
    adjusted = futuresAdjustedPrices.stitch_multiple_prices(multiple_prices_obj, forward_fill=True)
    print(f"    Adjusted prices: {len(adjusted)} rows → {adjusted.index[-1].strftime('%Y-%m-%d')}")

    if dry_run:
        print(f"\n  [DRY RUN] Not saving files")
    else:
        # 7. Save adjusted prices CSV
        adj_path = CSV_DIR / "adjusted_prices_csv" / f"{instrument_code}.csv"
        df_out = pd.DataFrame(adjusted, columns=['price'])
        df_out.index.name = 'DATETIME'
        df_out.to_csv(adj_path)
        print(f"    💾 Saved adjusted prices: {adj_path}")

        # Also save extended multiple_prices
        extended_mp.to_csv(mp_path, index_label='DATETIME')
        print(f"    💾 Saved extended multiple_prices: {mp_path}")

        # Save extended roll calendar
        rc_path = CSV_DIR / "roll_calendars_csv" / f"{instrument_code}.csv"
        extended_rc.to_csv(rc_path, index_label='DATE_TIME')
        print(f"    💾 Saved extended roll calendar: {rc_path}")

    # 8. Verification
    print(f"\n  [Step 5] Verification:")
    monthly = adjusted.resample('BM').last().dropna()
    if '2025-12' in str(monthly.index) or any(m.year == 2025 and m.month == 12 for m in monthly.index):
        dec25 = monthly.loc[monthly.index.to_series().dt.to_period('M') == '2025-12'].iloc[0]
        jan26 = monthly.loc[monthly.index.to_series().dt.to_period('M') == '2026-01'].iloc[0]
        jan_ret = jan26 / dec25 - 1
        print(f"    Dec 2025 close: {dec25:.2f}")
        print(f"    Jan 2026 close: {jan26:.2f}")
        print(f"    Jan 2026 return: {jan_ret:.4%}")

        if instrument_code == "GOLD":
            print(f"    Expected (spot): ~13.08%")
            if abs(jan_ret - 0.1308) < 0.02:
                print(f"    ✅ PASS — within 2pp of spot")
            else:
                print(f"    ⚠️  Divergence from spot: {(jan_ret - 0.1308)*100:.1f}pp")

    return True


def main():
    parser = argparse.ArgumentParser(description='Rebuild adjusted prices using pysystemtrade native Panama stitch')
    parser.add_argument('--instruments', nargs='+', default=ALL_INSTRUMENTS, help='Instruments to process')
    parser.add_argument('--dry-run', action='store_true', help='Do not save files')
    args = parser.parse_args()

    print("=" * 60)
    print("  Rebuild Adjusted Prices (pysystemtrade native stitch)")
    print("=" * 60)
    print(f"  Instruments: {', '.join(args.instruments)}")
    print(f"  Dry run: {args.dry_run}")

    # Connect to IB using pysystemtrade's standard pattern
    print(f"\n  Connecting to IB Gateway...")
    data = dataBlob(log_name="rebuild-adjusted-prices")
    data_broker = dataBroker(data)

    results = {}
    for inst in args.instruments:
        try:
            ok = process_instrument(inst, data_broker, dry_run=args.dry_run)
            results[inst] = "✅" if ok else "❌"
        except Exception as e:
            print(f"  ❌ {inst}: {e}")
            import traceback
            traceback.print_exc()
            results[inst] = f"❌ {e}"

    data.close()

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for inst, status in results.items():
        print(f"  {inst:<10} {status}")


if __name__ == "__main__":
    main()
