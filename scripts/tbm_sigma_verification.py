#!/usr/bin/env python
"""TBM barrier-sigma verification (HANDOFF §2 first step).

Verifies that this repo's ZN panama feed reproduces the raw ZN sigma median
of ~0.39 price points that the TBM barriers (PT=8sigma, SL=4sigma) were
calibrated on in /Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md.

If sigma differs materially, the data pipeline is divergent and the barriers
(defined as sigma-multiples) auto-follow the new sigma but the runner spec
must understand WHY before proceeding.

Two additional sanity checks:
  (1) zero-crossing region 1986-1990 (panama price |close|<5): sigma must
      NOT explode (would indicate pct-returns slipping back in).
  (2) 2024-04 to 2025-04 gap: handling (NaN propagation or smooth interpolation).

Usage:
    venv/bin/python scripts/tbm_sigma_verification.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arki.utils.martin_vol import martin_ema_vol  # noqa: E402

TARGET_SIGMA_MEDIAN = 0.39
SIGMA_TOLERANCE = 0.03


def load_zn_price() -> pd.Series:
    """Load via pysystemtrade rawdata to match what the TBM runner will use."""
    from sysdata.config.configdata import Config
    from systems.provided.futures_chapter15.basesystem import futures_system
    cfg = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    cfg.instruments = ["US10"]
    sys_ = futures_system(config=cfg)
    return sys_.rawdata.get_daily_prices("US10")


def compute_sigma_with_floor(price: pd.Series,
                              N: int = 20,
                              floor_min_periods: int = 20,
                              floor_quantile: float = 0.5,
                              floor_multiplier: float = 0.2) -> tuple[pd.Series, pd.Series]:
    """Martin §2.5 absolute-change EMA-of-squares + HANDOFF §2 no-look-ahead floor.

    floor = sigma.expanding(min_periods=20).median() * 0.2
    sigma_final = sigma.clip(lower=floor)
    """
    dpx = price.diff()
    sigma = martin_ema_vol(dpx, N=N, min_periods=10)
    # Expanding median for no-look-ahead floor
    floor = sigma.expanding(min_periods=floor_min_periods).quantile(floor_quantile) * floor_multiplier
    sigma_final = sigma.clip(lower=floor)
    return sigma_final, sigma


def main() -> int:
    print("=" * 72)
    print(" TBM barrier-sigma verification -- HANDOFF §2 first step")
    print("=" * 72)

    print("[1/5] loading ZN panama price via pysystemtrade rawdata ...")
    price = load_zn_price()
    print(f"      price index: {price.index[0].date()} -> {price.index[-1].date()}  "
          f"({len(price)} rows)")
    print(f"      price range: min={price.min():.3f}, max={price.max():.3f}")
    n_zero_cross = int((np.sign(price).diff().abs() > 0).sum())
    print(f"      sign-crossings of price (panama can go negative): {n_zero_cross}")

    print("\n[2/5] computing Martin §2.5 sigma (absolute-change EMA-of-sq, gamma=0.95) ...")
    sigma_floored, sigma_raw = compute_sigma_with_floor(price)
    sigma_valid = sigma_floored.dropna()
    print(f"      sigma series: {sigma_valid.index[0].date()} -> {sigma_valid.index[-1].date()}  "
          f"({len(sigma_valid)} valid days)")

    print("\n[3/5] PRIMARY GATE: sigma.median() vs HANDOFF target (0.39 ± 0.03)")
    med = float(sigma_valid.median())
    p25 = float(sigma_valid.quantile(0.25))
    p75 = float(sigma_valid.quantile(0.75))
    delta = med - TARGET_SIGMA_MEDIAN
    primary_pass = abs(delta) <= SIGMA_TOLERANCE
    print(f"      median = {med:.4f}  (target {TARGET_SIGMA_MEDIAN:.2f}, tol ±{SIGMA_TOLERANCE:.2f}, "
          f"delta {delta:+.4f})  {'PASS' if primary_pass else 'FAIL'}")
    print(f"      p25    = {p25:.4f}  (HANDOFF reference: 0.32)")
    print(f"      p75    = {p75:.4f}  (HANDOFF reference: 0.48)")

    print("\n[4/5] SANITY 1: zero-crossing region 1986-1990 |close|<5")
    zerox_mask = (price.abs() < 5)
    zerox_dates = price.index[zerox_mask]
    if len(zerox_dates) == 0:
        print("      [info] no |price|<5 days found (data may not include 1986-1990 segment)")
        zerox_ok = True
    else:
        n_near = int(zerox_mask.sum())
        sigma_zerox = sigma_floored.reindex(zerox_dates).dropna()
        sigma_med_zerox = float(sigma_zerox.median()) if len(sigma_zerox) else float("nan")
        sigma_max_zerox = float(sigma_zerox.max()) if len(sigma_zerox) else float("nan")
        # if pct-returns were used, sigma would explode (price -> 0 in denominator).
        # With absolute change, sigma should remain comparable to the global median.
        ratio = sigma_med_zerox / med if med > 0 else float("nan")
        zerox_ok = (ratio < 3.0) and np.isfinite(sigma_med_zerox)
        print(f"      |price|<5 days: {n_near}")
        print(f"      median sigma in that region: {sigma_med_zerox:.4f}")
        print(f"      max    sigma in that region: {sigma_max_zerox:.4f}")
        print(f"      ratio (local_med / global_med) = {ratio:.2f}x  "
              f"{'PASS (no explosion)' if zerox_ok else 'FAIL (sigma explodes; pct slipped in?)'}")

    print("\n[5/5] SANITY 2: 2024-04 to 2025-04 gap window handling")
    gap_start = pd.Timestamp("2024-04-01")
    gap_end = pd.Timestamp("2025-04-01")
    gap_slice = price.loc[gap_start:gap_end]
    if len(gap_slice) == 0:
        print(f"      [info] no rows in 2024-04..2025-04: data series ends before gap")
        gap_ok = True
    else:
        n_in_window = len(gap_slice.dropna())
        n_total_in_window = len(gap_slice)
        biz_days_in_window = pd.date_range(gap_start, gap_end, freq="B").size
        miss_pct = (1 - n_in_window / biz_days_in_window) * 100
        print(f"      window business days expected: {biz_days_in_window}")
        print(f"      window business days observed: {n_in_window} (missing {miss_pct:.1f}%)")
        # If the gap is real, we expect lots of NaNs OR large date jumps in the index.
        gap_ok = (miss_pct > 30) or (n_in_window < 100)
        print(f"      gap visibly present in data: {gap_ok}")
        # Sigma behaviour across gap
        sigma_pre_gap = sigma_floored.loc[:gap_start].dropna().iloc[-5:] if len(sigma_floored.loc[:gap_start].dropna()) else None
        sigma_post_gap = sigma_floored.loc[gap_end:].dropna().iloc[:5] if len(sigma_floored.loc[gap_end:].dropna()) else None
        if sigma_pre_gap is not None and len(sigma_pre_gap):
            print(f"      sigma last 5 days pre-2024-04: median {sigma_pre_gap.median():.4f}")
        if sigma_post_gap is not None and len(sigma_post_gap):
            print(f"      sigma first 5 days post-2025-04: median {sigma_post_gap.median():.4f}")

    # ---- Output verdict ----
    print("\n" + "=" * 72)
    overall_pass = primary_pass and zerox_ok and gap_ok
    print(f" OVERALL: {'PASS — proceed to runner' if overall_pass else 'FAIL — investigate before runner'}")
    print("=" * 72)
    print("Implication for barriers:")
    print(f"  PT = 8 sigma = 8 × {med:.4f} = {8*med:.3f} price points (target ~3.12)")
    print(f"  SL = 4 sigma = 4 × {med:.4f} = {4*med:.3f} price points (target ~1.56)")
    print(f"  These are SCALES used at every event time; the multipliers are the locked spec,")
    print(f"  not the absolute values. If sigma differs from 0.39 at the same multipliers,")
    print(f"  the barriers auto-track -- but the data-pipeline question must still be understood.")

    # Persist a one-line audit record
    out_dir = ROOT / "arki" / "results" / "2026-05-30"
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = pd.DataFrame([{
        "instrument": "US10",
        "sigma_median_target": TARGET_SIGMA_MEDIAN,
        "sigma_median_observed": med,
        "sigma_p25_observed": p25,
        "sigma_p75_observed": p75,
        "primary_pass": primary_pass,
        "zerox_region_pass": zerox_ok,
        "gap_window_pass": gap_ok,
        "overall_pass": overall_pass,
        "PT_8sigma_price_points": 8 * med,
        "SL_4sigma_price_points": 4 * med,
        "n_valid_days": len(sigma_valid),
        "data_start": str(price.index[0].date()),
        "data_end": str(price.index[-1].date()),
    }])
    audit_path = out_dir / "tbm_sigma_verification.csv"
    audit.to_csv(audit_path, index=False)
    print(f"\n[ok] audit row -> {audit_path}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
