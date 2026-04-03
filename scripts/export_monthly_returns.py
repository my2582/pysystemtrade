#!/usr/bin/env python3
"""
Futures Back-Adjusted Monthly Returns Export
=============================================
Reads pysystemtrade back-adjusted daily prices, computes monthly returns,
and exports in ADW-compatible format.

Usage:
    python scripts/export_monthly_returns.py
    python scripts/export_monthly_returns.py --start 2000-01-01
    python scripts/export_monthly_returns.py --output /path/to/output
    python scripts/export_monthly_returns.py --format long
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

print(f"Loading config from {PROJECT_ROOT / 'private' / 'private_config.yaml'}")

CSV_DIR = PROJECT_ROOT / "data" / "futures" / "adjusted_prices_csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "monthly_returns"

# Mapping: pysystemtrade instrument code → ADW Internal ID
INSTRUMENT_MAP = {
    "SP500":   "SP500_ER",
    "DAX":     "DAX_ER",
    "NIKKEI":  "NIKKEI225_ER",
    "FTSE100": "FTSE100_ER",
    "US10":    "US_ULTRA10Y_ER",
    "BUND":    "EUROBUND_ER",
    "JGB":     "JGB10Y_ER",
    "GILT":    "GILT_ER",
    "GOLD":    "GOLD_ER",
}

# Reverse mapping for display
ADW_LABELS = {
    "SP500_ER":       "S&P500 EMINI",
    "DAX_ER":         "DAX Mini",
    "NIKKEI225_ER":   "NIKKEI 225",
    "FTSE100_ER":     "FTSE 100",
    "US_ULTRA10Y_ER": "US 10YR NOTE",
    "EUROBUND_ER":    "EURO-BUND",
    "JGB10Y_ER":      "JPN 10Y BOND",
    "GILT_ER":        "LONG GILT",
    "GOLD_ER":        "GOLD 100 OZ",
}


def load_adjusted_prices(instrument_code: str) -> pd.Series:
    """Load back-adjusted daily prices from CSV."""
    csv_path = CSV_DIR / f"{instrument_code}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No CSV found: {csv_path}")

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    prices = df.iloc[:, 0]
    prices.name = instrument_code

    # pysystemtrade CSVs may have intraday timestamps; keep last per date
    prices.index = prices.index.normalize()
    prices = prices.groupby(prices.index).last()

    return prices


def _find_stable_start(prices: pd.Series, threshold_pct: float = 0.10) -> pd.Timestamp:
    """
    Find the first date where back-adjusted prices become reliably
    large enough for meaningful percentage returns.

    For instruments whose Panama-canal stitching produces negative or
    near-zero prices in early history (e.g., US10, GILT), standard
    pct_change() produces extreme values. This function finds the
    point where prices reach at least `threshold_pct` of the final
    price level and stay there permanently.

    For instruments with always-positive, well-behaved prices (equities,
    gold), returns the original start date immediately.
    """
    clean = prices.dropna()

    if clean.empty:
        return prices.index[0]

    # Fast path: all positive → no Panama stitch issue
    if (clean > 0).all():
        return clean.index[0]

    # Determine a minimum price threshold based on the final price level.
    # E.g., for GILT ending at ~100, threshold = 10 (10%).
    # This skips the near-zero oscillation zone entirely.
    final_price = clean.iloc[-1]
    min_price = abs(final_price) * threshold_pct

    # Find first date where price exceeds threshold AND stays above it
    above = clean > min_price
    # Walk backward from the end to find the earliest contiguous block
    # where above is always True
    above_reversed = above[::-1]
    # Find the first False (going backward = last dip below threshold)
    first_false_rev = above_reversed[~above_reversed]
    if first_false_rev.empty:
        # Always above threshold
        return clean.index[0]

    last_dip_date = first_false_rev.index[0]
    # Start from the day after the last dip
    candidates = clean[clean.index > last_dip_date]
    if candidates.empty:
        return clean.index[-1]

    return candidates.index[0]


def compute_monthly_returns(daily_prices: pd.Series) -> pd.Series:
    """
    Resample daily back-adjusted prices to month-end and compute returns.

    Automatically trims prices from instruments with Panama-canal
    stitching artifacts (negative/near-zero prices in early history).
    """
    # Auto-trim unstable price region
    stable_start = _find_stable_start(daily_prices)
    trimmed = daily_prices[stable_start:].dropna()

    if trimmed.empty or len(trimmed) < 2:
        return pd.Series(dtype=float)

    # Resample to month-end: take the last available price in each month
    monthly_prices = trimmed.resample("BM").last()

    # Drop NaN from resampling gaps
    monthly_prices = monthly_prices.dropna()

    # Standard percentage returns (safe now that all prices are positive)
    monthly_returns = monthly_prices.pct_change()

    # Drop the first NaN return
    monthly_returns = monthly_returns.dropna()

    return monthly_returns


def export_returns(output_dir: Path, start_date: str = None,
                   fmt: str = "wide") -> pd.DataFrame:
    """
    Main export function.

    Returns wide DataFrame of monthly returns (date × ADW instrument IDs).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_returns = {}
    summary_rows = []

    print(f"\n{'='*70}")
    print("  Futures Back-Adjusted Monthly Returns")
    print(f"{'='*70}")
    print(f"  Source:  {CSV_DIR}")
    print(f"  Output:  {output_dir}")
    print(f"  Format:  {fmt}")
    if start_date:
        print(f"  Start:   {start_date}")
    print()

    for pst_code, adw_id in INSTRUMENT_MAP.items():
        try:
            prices = load_adjusted_prices(pst_code)
            returns = compute_monthly_returns(prices)

            if start_date:
                returns = returns[start_date:]

            all_returns[adw_id] = returns

            label = ADW_LABELS[adw_id]
            first = returns.index[0].strftime("%Y-%m")
            last = returns.index[-1].strftime("%Y-%m")
            n_months = len(returns)
            ann_ret = (1 + returns.mean()) ** 12 - 1
            ann_vol = returns.std() * np.sqrt(12)

            summary_rows.append({
                "ADW_ID": adw_id,
                "Asset": label,
                "PST_Code": pst_code,
                "First": first,
                "Last": last,
                "Months": n_months,
                "Ann_Return": f"{ann_ret:.2%}",
                "Ann_Vol": f"{ann_vol:.2%}",
            })

            print(f"  ✅ {adw_id:<18} {first} → {last}  ({n_months:>4} months)  "
                  f"ret={ann_ret:>7.2%}  vol={ann_vol:>7.2%}")

        except Exception as e:
            print(f"  ❌ {pst_code}: {e}")

    if not all_returns:
        print("\n  ❌ No data exported!")
        return pd.DataFrame()

    # Build wide DataFrame
    wide_df = pd.DataFrame(all_returns)
    wide_df.index.name = "date"
    wide_df = wide_df.sort_index()

    # --- Output files ---

    # 1. Wide format CSV (primary)
    wide_path = output_dir / "futures_monthly_returns.csv"
    wide_df.to_csv(wide_path, float_format="%.8f")
    print(f"\n  💾 Wide CSV:  {wide_path}")

    # 2. Long format CSV (optional)
    if fmt == "long" or fmt == "both":
        long_records = []
        for adw_id, returns in all_returns.items():
            for date, ret in returns.items():
                long_records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "instrument_id": adw_id,
                    "monthly_return": ret,
                })
        long_df = pd.DataFrame(long_records)
        long_path = output_dir / "futures_monthly_returns_long.csv"
        long_df.to_csv(long_path, index=False, float_format="%.8f")
        print(f"  💾 Long CSV:  {long_path}")

    # 3. Individual instrument CSVs
    ind_dir = output_dir / "by_instrument"
    ind_dir.mkdir(exist_ok=True)
    for adw_id, returns in all_returns.items():
        ind_path = ind_dir / f"{adw_id}.csv"
        returns.to_csv(ind_path, header=["monthly_return"], float_format="%.8f")
    print(f"  💾 Individual: {ind_dir}/ ({len(all_returns)} files)")

    # 4. Summary
    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_dir / "summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"  💾 Summary:   {summary_path}")

    # Print summary table
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    print(f"  {'ADW ID':<18} {'Asset':<16} {'Range':<19} {'Months':>6} {'Ret':>8} {'Vol':>8}")
    print(f"  {'-'*18} {'-'*16} {'-'*19} {'-'*6} {'-'*8} {'-'*8}")
    for row in summary_rows:
        print(f"  {row['ADW_ID']:<18} {row['Asset']:<16} "
              f"{row['First']}→{row['Last']}  {row['Months']:>5}  "
              f"{row['Ann_Return']:>7}  {row['Ann_Vol']:>7}")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n  Generated: {stamp}")
    print(f"  Total instruments: {len(all_returns)}")
    intersect_start = wide_df.dropna().index[0].strftime("%Y-%m") if not wide_df.dropna().empty else "N/A"
    intersect_end = wide_df.dropna().index[-1].strftime("%Y-%m") if not wide_df.dropna().empty else "N/A"
    print(f"  Common period (all 9): {intersect_start} → {intersect_end}")
    print()

    return wide_df


def main():
    parser = argparse.ArgumentParser(
        description="Export monthly returns from back-adjusted futures prices"
    )
    parser.add_argument("--start", type=str, default=None,
                        help="Start date filter (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (default: results/monthly_returns/)")
    parser.add_argument("--format", choices=["wide", "long", "both"],
                        default="both",
                        help="Output format (default: both)")

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT
    export_returns(output_dir, start_date=args.start, fmt=args.format)


if __name__ == "__main__":
    main()
