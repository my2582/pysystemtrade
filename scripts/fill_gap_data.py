"""
Fill Gap Data Pipeline
======================
Merges user-provided gap period CSV files (2024-04 ~ 2025-03)
into the existing adjusted_prices_csv using Panama canal stitching.

Pipeline:
1. Read existing adjusted prices (ends 2024-03-28)
2. Read gap CSV (raw unadjusted front-month prices, 2024-04 ~ 2025-03)
3. Read IB-updated prices (starts ~2025-03-31, already stitched)
4. Panama stitch: old → gap → IB segment to create seamless series
5. Write final adjusted prices CSV

Usage:
  python scripts/fill_gap_data.py --gap-dir data/futures/gap_prices/
  python scripts/fill_gap_data.py --gap-dir data/futures/gap_prices/ --instruments BUND CRUDE_W
  python scripts/fill_gap_data.py --verify  # just verify gap coverage
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, '/Users/msyeom/Developer/pysystemtrade')
os.chdir('/Users/msyeom/Developer/pysystemtrade')

print("Loading config from /Users/msyeom/Developer/pysystemtrade/private/private_config.yaml")

BACKUP_DIR = Path('data/futures/adjusted_prices_csv_backup_20240328')
CURRENT_DIR = Path('data/futures/adjusted_prices_csv')
DEFAULT_GAP_DIR = Path('data/futures/gap_prices')

INSTRUMENTS = sorted([
    'AUD_micro', 'BOBL', 'BONO', 'BRENT-LAST', 'BUND', 'BUTTER', 'CHEESE',
    'CHFJPY', 'CLP', 'COCOA_LDN', 'COFFEE', 'COPPER-micro', 'COTTON',
    'CRUDE_W', 'EU-BANKS', 'EU-DJ-OIL', 'EU-DJ-TELECOM', 'EURIBOR',
    'EURIBOR-ICE', 'FED', 'FEEDCOW', 'FTSECHINAA', 'GASOIL', 'IBEX_mini',
    'INR', 'LEANHOG', 'LIVECOW', 'LUMBER-new', 'MXP', 'NASDAQ_micro',
    'OAT', 'OJ', 'PLN', 'REDWHEAT', 'RICE', 'SILVER', 'SPI200',
    'SUGAR11', 'SUGAR_WHITE', 'TOPIX', 'TWD-mini', 'US-DISCRETE',
    'US-STAPLES', 'US-UTILS', 'US5', 'YENEUR',
])

# These 3 need full gap (IB had no data at all)
FULL_GAP = ['COTTON', 'SUGAR11', 'SUGAR_WHITE']


def load_gap_csv(gap_dir, instrument_code):
    """
    Load gap period CSV. Supports multiple formats:
    - DATETIME,CLOSE
    - DATETIME,OPEN,HIGH,LOW,CLOSE
    - DATETIME,price
    - Date,Close (Barchart format)
    """
    gap_path = gap_dir / f'{instrument_code}.csv'
    if not gap_path.exists():
        return None

    df = pd.read_csv(gap_path)
    
    # Detect date column
    date_col = None
    for col in ['DATETIME', 'Date', 'date', 'DATE', 'Datetime', 'datetime', 'Time']:
        if col in df.columns:
            date_col = col
            break
    
    if date_col is None:
        # Assume first column is date
        date_col = df.columns[0]
    
    # Detect price column
    price_col = None
    for col in ['CLOSE', 'Close', 'close', 'price', 'Price', 'PRICE', 'Last', 'last',
                'Settle', 'settle', 'SETTLE', 'Adj Close', 'adj_close']:
        if col in df.columns:
            price_col = col
            break
    
    if price_col is None:
        # Use last column
        price_col = df.columns[-1]
    
    # Parse
    df[date_col] = pd.to_datetime(df[date_col])
    series = pd.Series(df[price_col].values, index=df[date_col])
    series = series.sort_index()
    series = series.dropna()
    
    # Remove duplicate dates
    series = series[~series.index.duplicated(keep='last')]
    
    return series


def panama_stitch_three_segments(original_adj, gap_raw, ib_segment):
    """
    Three-segment Panama canal stitching:
    
    Segment A: original adjusted prices (1969 ~ 2024-03-28) — KEEP AS IS
    Segment B: gap raw prices (2024-04 ~ 2025-03) — stitch to A
    Segment C: IB-updated prices (2025-03/04 ~ 2026-03) — stitch to B
    
    Panama method: compute offset at overlap/junction to maintain
    price continuity while preserving the returns of each segment.
    """
    # --- Stitch A → B ---
    a_last_date = original_adj.index[-1]
    a_last_price = original_adj.iloc[-1]
    
    # Gap data after where original ends
    gap_after_a = gap_raw.loc[gap_raw.index > a_last_date]
    
    if len(gap_after_a) == 0:
        print(f"    ⚠️  No gap data after {a_last_date.strftime('%Y-%m-%d')}")
        return None
    
    # Compute Panama offset: match first gap price to last adjusted price
    # Check for overlap first
    overlap_dates = original_adj.index.intersection(gap_raw.index)
    if len(overlap_dates) >= 5:
        # Use average offset over overlap for more stable estimate
        offset_ab = (original_adj.loc[overlap_dates] - gap_raw.loc[overlap_dates]).median()
        print(f"    📐 A→B offset: {offset_ab:.4f} (from {len(overlap_dates)} overlap days)")
    else:
        # No overlap — use boundary matching
        gap_first_price = gap_after_a.iloc[0]
        offset_ab = a_last_price - gap_first_price
        print(f"    📐 A→B offset: {offset_ab:.4f} (boundary match)")
    
    # Adjusted gap segment
    gap_adjusted = gap_after_a + offset_ab
    
    # --- Stitch (A+B) → C ---
    if ib_segment is not None and len(ib_segment) > 0:
        ab_combined = pd.concat([original_adj, gap_adjusted])
        ab_combined = ab_combined[~ab_combined.index.duplicated(keep='first')]
        ab_last_date = ab_combined.index[-1]
        ab_last_price = ab_combined.iloc[-1]
        
        ib_after = ib_segment.loc[ib_segment.index > ab_last_date]
        
        if len(ib_after) > 0:
            # Check overlap between gap and IB
            overlap_bc = gap_adjusted.index.intersection(ib_segment.index)
            if len(overlap_bc) >= 5:
                # Both are in adjusted space now, so compare gap_adjusted vs ib_segment
                offset_bc = (gap_adjusted.loc[overlap_bc] - ib_segment.loc[overlap_bc]).median()
                print(f"    📐 B→C offset: {offset_bc:.4f} (from {len(overlap_bc)} overlap days)")
            else:
                ib_first_price = ib_after.iloc[0]
                offset_bc = ab_last_price - ib_first_price
                print(f"    📐 B→C offset: {offset_bc:.4f} (boundary match)")
            
            ib_adjusted = ib_after + offset_bc
            final = pd.concat([original_adj, gap_adjusted, ib_adjusted])
        else:
            print(f"    ⚠️  No IB data after gap ends ({ab_last_date.strftime('%Y-%m-%d')})")
            final = pd.concat([original_adj, gap_adjusted])
    else:
        # No IB segment (COTTON, SUGAR11, SUGAR_WHITE)
        final = pd.concat([original_adj, gap_adjusted])
    
    # Deduplicate and sort
    final = final[~final.index.duplicated(keep='first')]
    final = final.sort_index()
    
    return final


def process_instrument(instrument_code, gap_dir):
    """Process one instrument: load 3 segments, stitch, save."""
    
    # Segment A: Original backup (clean, ends 2024-03-28)
    backup_path = BACKUP_DIR / f'{instrument_code}.csv'
    if not backup_path.exists():
        print(f"    ❌ No backup file (original data)")
        return False
    
    backup_df = pd.read_csv(backup_path, index_col=0, parse_dates=True)
    original_adj = backup_df.iloc[:, 0]
    
    # Segment B: Gap data (user-provided)
    gap_raw = load_gap_csv(gap_dir, instrument_code)
    if gap_raw is None:
        print(f"    ❌ No gap CSV found in {gap_dir}/")
        return False
    
    print(f"    Segment A (original): {original_adj.index[0].strftime('%Y-%m-%d')} → {original_adj.index[-1].strftime('%Y-%m-%d')} ({len(original_adj)} rows)")
    print(f"    Segment B (gap):      {gap_raw.index[0].strftime('%Y-%m-%d')} → {gap_raw.index[-1].strftime('%Y-%m-%d')} ({len(gap_raw)} rows)")
    
    # Segment C: IB-updated data (from current adjusted_prices, contains only the IB portion)
    current_path = CURRENT_DIR / f'{instrument_code}.csv'
    ib_segment = None
    
    if instrument_code not in FULL_GAP and current_path.exists():
        current_df = pd.read_csv(current_path, index_col=0, parse_dates=True)
        current_prices = current_df.iloc[:, 0]
        
        # Extract only the IB-added portion (after original data ends)
        ib_portion = current_prices.loc[current_prices.index > original_adj.index[-1]]
        if len(ib_portion) > 0:
            ib_segment = ib_portion
            print(f"    Segment C (IB):       {ib_segment.index[0].strftime('%Y-%m-%d')} → {ib_segment.index[-1].strftime('%Y-%m-%d')} ({len(ib_segment)} rows)")
    
    # Panama stitch
    final = panama_stitch_three_segments(original_adj, gap_raw, ib_segment)
    if final is None:
        return False
    
    # Validate: no NaN in the middle
    nan_count = final.isna().sum()
    if nan_count > 0:
        print(f"    ⚠️  {nan_count} NaN values found — filling forward")
        final = final.fillna(method='ffill')
    
    # Check for unreasonable jumps (>20% in one day)
    returns = final.pct_change().dropna()
    big_jumps = returns[returns.abs() > 0.20]
    if len(big_jumps) > 0:
        print(f"    ⚠️  {len(big_jumps)} days with >20% jump detected (may indicate stitching issue):")
        for date, ret in big_jumps.head(5).items():
            print(f"       {date.strftime('%Y-%m-%d')}: {ret:+.1%}")
    
    # Save
    df_out = pd.DataFrame(final)
    df_out.columns = ['price']
    df_out.to_csv(current_path, index_label='DATETIME')
    
    print(f"    ✅ Final: {final.index[0].strftime('%Y-%m-%d')} → {final.index[-1].strftime('%Y-%m-%d')} ({len(final)} rows)")
    return True


def verify_gap_coverage(gap_dir):
    """Check which gap CSVs are present and their coverage."""
    print("\n" + "=" * 70)
    print("GAP DATA COVERAGE CHECK")
    print("=" * 70)
    print(f"\nGap directory: {gap_dir}")
    print(f"{'Instrument':<20} {'Status':<10} {'Rows':>6} {'Start':>12} {'End':>12}")
    print("-" * 70)
    
    found = 0
    missing = 0
    for inst in INSTRUMENTS:
        gap = load_gap_csv(gap_dir, inst)
        if gap is not None:
            found += 1
            print(f"{inst:<20} {'✅ Found':<10} {len(gap):>6} {gap.index[0].strftime('%Y-%m-%d'):>12} {gap.index[-1].strftime('%Y-%m-%d'):>12}")
        else:
            missing += 1
            print(f"{inst:<20} {'❌ Missing':<10}")
    
    print("-" * 70)
    print(f"Found: {found}/{len(INSTRUMENTS)}  Missing: {missing}")
    
    if missing > 0:
        print(f"\n⚠️  {missing} instruments still missing. Cannot proceed with full pipeline.")
    else:
        print(f"\n✅ All {found} instruments present! Ready to run: python scripts/fill_gap_data.py --gap-dir {gap_dir}")


def main():
    parser = argparse.ArgumentParser(description='Fill gap period data with Panama canal stitching')
    parser.add_argument('--gap-dir', type=str, default=str(DEFAULT_GAP_DIR),
                        help='Directory containing gap period CSV files')
    parser.add_argument('--instruments', nargs='+', help='Specific instruments to process')
    parser.add_argument('--verify', action='store_true', help='Only verify gap data coverage')
    args = parser.parse_args()
    
    gap_dir = Path(args.gap_dir)
    
    if args.verify:
        verify_gap_coverage(gap_dir)
        return
    
    if not gap_dir.exists():
        print(f"❌ Gap directory not found: {gap_dir}")
        print(f"   Create it and place CSV files there:")
        print(f"   mkdir -p {gap_dir}")
        return
    
    instruments = args.instruments or INSTRUMENTS
    
    print("🚀 GAP DATA FILL PIPELINE")
    print(f"   Gap directory: {gap_dir}")
    print(f"   Instruments: {len(instruments)}")
    print(f"   Method: 3-segment Panama canal stitching")
    print(f"   A (original 1969~2024-03) → B (gap 2024-04~2025-03) → C (IB 2025-04~2026-03)")
    print()
    
    # First verify all gap files exist
    missing = [inst for inst in instruments if not (gap_dir / f'{inst}.csv').exists()]
    if missing:
        print(f"⚠️  Missing {len(missing)} gap CSV files: {', '.join(missing[:10]})")
        proceed = input("Continue with available files? [y/N] ").strip().lower()
        if proceed != 'y':
            print("Aborted.")
            return
        instruments = [inst for inst in instruments if inst not in missing]
    
    results = {'success': [], 'error': []}
    
    for i, inst in enumerate(instruments):
        print(f"\n[{i+1}/{len(instruments)}] {inst}")
        try:
            ok = process_instrument(inst, gap_dir)
            if ok:
                results['success'].append(inst)
            else:
                results['error'].append(inst)
        except Exception as e:
            print(f"    ❌ Error: {e}")
            results['error'].append(inst)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  ✅ Success: {len(results['success'])}/{len(instruments)}")
    print(f"  ❌ Error: {len(results['error'])}")
    
    if results['error']:
        print(f"     Failed: {', '.join(results['error'])}")
    
    # Final verification
    print("\n[Final Verification]")
    print(f"{'Instrument':<20} {'Start':>12} {'End':>12} {'Rows':>8} {'Gap?':>6}")
    print("-" * 65)
    
    for inst in sorted(instruments):
        csv_path = CURRENT_DIR / f'{inst}.csv'
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            prices = df.iloc[:, 0]
            
            # Check for gaps > 5 business days
            date_diffs = prices.index.to_series().diff().dt.days
            max_gap = date_diffs.max()
            has_gap = "⚠️" if max_gap > 5 else "✅"
            
            print(f"{inst:<20} {prices.index[0].strftime('%Y-%m-%d'):>12} {prices.index[-1].strftime('%Y-%m-%d'):>12} {len(prices):>8} {has_gap:>6}")


if __name__ == '__main__':
    main()
