#!/usr/bin/env python3
"""
Build recent-only (OOS) Panama back-adjusted price series from the per-contract
parquet that was downloaded from IB (2025-05+), using ONLY native pysystemtrade
builders. NOT a hand-stitch.

Pipeline per instrument (all native):
  1. rollCalendar.create_from_prices         (build_and_write_roll_calendar)
  2. futuresMultiplePrices.create_from_raw_data (process_multiple_prices_single_instrument)
  3. futuresAdjustedPrices.stitch_multiple_prices  (native panama)

Outputs to a SEPARATE location so the historical IS series stays untouched:
  data/futures/oos_recent/{roll_calendars_csv,multiple_prices_csv,adjusted_prices_csv}/

Reads per-contract prices from the parquet store (read-only). Does NOT write to
the MongoDB/parquet multiple/adjusted stores (ADD_TO_DB=False).
"""
import sys, os, argparse, datetime
sys.path.insert(0, "/Users/msyeom/Developer/pysystemtrade")
os.chdir("/Users/msyeom/Developer/pysystemtrade")

from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
    build_and_write_roll_calendar,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysobjects.adjusted_prices import futuresAdjustedPrices
from sysdata.csv.csv_adjusted_prices import csvFuturesAdjustedPricesData

OOS = "data/futures/oos_recent"
ROLLCAL = f"{OOS}/roll_calendars_csv"
MULTIPLE = f"{OOS}/multiple_prices_csv"
ADJ = f"{OOS}/adjusted_prices_csv"
for d in (ROLLCAL, MULTIPLE, ADJ):
    os.makedirs(d, exist_ok=True)

STALE17 = [
    "ETHER-micro", "VIX_mini", "CORN_mini", "JGB-SGX-mini", "WHEAT_mini",
    "KOSPI_mini", "SOYBEAN_mini", "AEX_mini", "HANGENT_mini", "JGB-mini",
    "HANG_mini", "ALUMINIUM_LME", "COPPER-mini", "ALUMINIUM", "GOLD-mini",
    "RUSSELL_mini", "DOW_mini",
]


def build_one(inst):
    # 1. native roll calendar from the downloaded per-contract prices
    build_and_write_roll_calendar(
        inst, output_datapath=ROLLCAL, write=True, check_before_writing=False
    )
    # 2. native multiple prices -> OOS CSV (DB untouched)
    mp = process_multiple_prices_single_instrument(
        inst,
        csv_multiple_data_path=MULTIPLE,
        csv_roll_data_path=ROLLCAL,
        ADD_TO_DB=False,
        ADD_TO_CSV=True,
    )
    # 3. native panama back-adjusted from the multiple-prices object
    adj = futuresAdjustedPrices.stitch_multiple_prices(mp)
    csvFuturesAdjustedPricesData(ADJ).add_adjusted_prices(
        inst, adj, ignore_duplication=True
    )
    return mp, adj


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--instruments", nargs="+", default=STALE17)
    args = ap.parse_args()

    ok, fail = [], []
    for i, inst in enumerate(args.instruments):
        print(f"\n{'='*60}\n[{i+1}/{len(args.instruments)}] {inst}\n{'='*60}")
        try:
            mp, adj = build_one(inst)
            s = adj.index
            ok.append((inst, str(s.min())[:10], str(s.max())[:10], len(adj)))
            print(f"  OK  {inst}: adjusted {str(s.min())[:10]} -> {str(s.max())[:10]} ({len(adj)} rows)")
        except Exception as e:
            fail.append((inst, repr(e)))
            print(f"  FAIL {inst}: {e}")

    print(f"\n\n{'='*60}\nSUMMARY  ok={len(ok)} fail={len(fail)}\n{'='*60}")
    for inst, a, b, n in ok:
        print(f"  OK   {inst:<15} {a} -> {b}  ({n} rows)")
    for inst, e in fail:
        print(f"  FAIL {inst:<15} {e}")
