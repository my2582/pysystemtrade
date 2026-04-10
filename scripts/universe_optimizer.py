#!/usr/bin/env python3
"""
Arki Universe Optimizer
=======================
Selects the optimal instrument subset for a given capital level
using a 4-stage pipeline:

  Stage 1: Quality Gates (cost, volatility)
  Stage 2: Executability Filter (contract value vs capital)
  Stage 3: Factor SR Scoring (Trend, Carry, CS Momentum)
  Stage 4: Greedy Subset Selection (diversification + SR)

Usage:
  python scripts/universe_optimizer.py --capital 200000 --target 15
  python scripts/universe_optimizer.py --capital 300000 --target 20 --json
"""

import argparse
import json
import os
import sys
import warnings
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# ═══════════════════════════════════════════════════════════════
# Constants (aligned with pysystemtrade defaults)
# ═══════════════════════════════════════════════════════════════

MAX_SR_COST = 0.013           # Slightly relaxed from Carver's 0.01 for broader pool
MIN_ANN_STDEV_PCT = 4.0       # Minimum annual % stdev (avoid "too safe" instruments)
RISK_TARGET = 0.25            # 25% vol target
IDM_ESTIMATE = 2.5            # Instrument diversification multiplier (25 inst)
LOOKBACK_DAYS = 1280          # 5 years of trading days
SR_SHRINKAGE = 0.50           # 50% shrinkage toward cross-sectional mean (Carver)
MIN_HISTORY_DAYS = 750        # Minimum price history required
SQRT_256 = 16.0               # √256 for annualization

# Factor weights (equal weight)
FACTOR_WEIGHTS = {"trend": 0.34, "carry": 0.33, "cs_momentum": 0.33}

# Diversification constraints
MIN_ASSET_CLASSES = 3
MAX_PER_ASSET_CLASS = 5
CORRELATION_PENALTY_THRESHOLD = 0.70
CORRELATION_HARD_EXCLUDE = 0.85     # Hard exclude if corr > this

# Known duplicate groups (only keep the best one from each group)
KNOWN_DUPLICATE_GROUPS = [
    ["COCOA", "COCOA_LDN"],
    ["CRUDE_W", "CRUDE_W_micro", "CRUDE_W_mini"],
    ["GOLD", "GOLD-mini", "GOLD_micro"],
    ["SP500", "SP500_micro"],
    ["NASDAQ", "NASDAQ_micro"],
    ["COPPER", "COPPER-micro", "COPPER-mini"],
    ["CORN", "CORN_mini"],
    ["EUR", "EUR_micro", "EUR_mini"],
    ["AUD", "AUD_micro"],
    ["GBP", "GBP_micro"],
    ["CAD", "CAD_micro"],
    ["JGB", "JGB-mini", "JGB-SGX-mini"],
    ["AEX", "AEX_mini"],
    ["HANG", "HANG_mini", "HANGENT_mini"],
    ["VIX", "VIX_mini"],
    ["SOYBEAN", "SOYBEAN_mini"],
    ["WHEAT", "WHEAT_mini"],
    ["CRUDE_W", "BRENT-LAST"],  # Same underlying exposure
]

# Reclassify certain instruments
ASSET_CLASS_OVERRIDES = {
    "BITCOIN": "Crypto",
    "ETHER-micro": "Crypto",
}

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "futures")
ADJUSTED_PRICES_DIR = os.path.join(DATA_DIR, "adjusted_prices_csv")
MULTIPLE_PRICES_DIR = os.path.join(DATA_DIR, "multiple_prices_csv")
FX_PRICES_DIR = os.path.join(DATA_DIR, "fx_prices_csv")
INSTRUMENT_CONFIG = os.path.join(DATA_DIR, "csvconfig", "instrumentconfig.csv")
SPREAD_COSTS = os.path.join(DATA_DIR, "csvconfig", "spreadcosts.csv")


# ═══════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class InstrumentProfile:
    """Complete profile for one instrument"""
    code: str
    description: str = ""
    asset_class: str = ""
    region: str = ""
    currency: str = "USD"
    pointsize: float = 1.0
    per_block: float = 0.0
    spread_cost: float = 0.0

    # Computed
    price: float = 0.0
    fx_rate: float = 1.0
    contract_value_usd: float = 0.0
    ann_stdev_pct: float = 0.0
    ann_stdev_price: float = 0.0
    sr_cost: float = 0.0
    min_capital_one: float = 0.0
    history_days: int = 0

    # Factor scores (annualized SR)
    trend_sr: float = 0.0
    carry_sr: float = 0.0
    cs_mom_sr: float = 0.0
    composite_sr: float = 0.0
    shrunk_sr: float = 0.0

    # Gates
    passes_quality: bool = False
    passes_executability: bool = False
    quality_reasons: List[str] = field(default_factory=list)
    exec_reasons: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════════

def load_instrument_config() -> pd.DataFrame:
    """Load instrumentconfig.csv"""
    return pd.read_csv(INSTRUMENT_CONFIG)


def load_spread_costs() -> pd.DataFrame:
    """Load spreadcosts.csv"""
    return pd.read_csv(SPREAD_COSTS)


def load_adjusted_prices(instrument: str) -> Optional[pd.Series]:
    """Load adjusted price series for an instrument"""
    path = os.path.join(ADJUSTED_PRICES_DIR, f"{instrument}.csv")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df.iloc[:, 0].dropna()
    except Exception:
        return None


def load_multiple_prices(instrument: str) -> Optional[pd.DataFrame]:
    """Load multiple prices (CARRY, PRICE, FORWARD) for carry calculation"""
    path = os.path.join(MULTIPLE_PRICES_DIR, f"{instrument}.csv")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, parse_dates=["DATETIME"])
        df = df.set_index("DATETIME")
        return df
    except Exception:
        return None


def load_fx_rate(currency: str) -> float:
    """Load latest FX rate to USD"""
    if currency == "USD":
        return 1.0
    pair = f"{currency}USD"
    path = os.path.join(FX_PRICES_DIR, f"{pair}.csv")
    if not os.path.exists(path):
        return 1.0  # Fallback
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return float(df.iloc[:, 0].dropna().iloc[-1])
    except Exception:
        return 1.0


# ═══════════════════════════════════════════════════════════════
# Stage 1: Quality Gates
# ═══════════════════════════════════════════════════════════════

def compute_sr_cost(spread_cost: float, per_block: float,
                    ann_stdev_price: float, pointsize: float) -> float:
    """
    SR cost = SpreadCost/annual_σ + PerBlock/(annual_σ × Pointsize)
    """
    if ann_stdev_price <= 0 or pointsize <= 0:
        return 999.0
    spread_component = spread_cost / ann_stdev_price
    commission_component = per_block / (ann_stdev_price * pointsize)
    return spread_component + commission_component


def apply_quality_gates(profile: InstrumentProfile) -> InstrumentProfile:
    """Apply quality gates: cost, volatility, history"""
    reasons = []

    if profile.history_days < MIN_HISTORY_DAYS:
        reasons.append(f"Short history ({profile.history_days}d < {MIN_HISTORY_DAYS})")

    if profile.sr_cost > MAX_SR_COST:
        reasons.append(f"Expensive (SR cost {profile.sr_cost:.4f} > {MAX_SR_COST})")

    if profile.ann_stdev_pct < MIN_ANN_STDEV_PCT:
        reasons.append(f"Too safe ({profile.ann_stdev_pct:.1f}% < {MIN_ANN_STDEV_PCT}%)")

    if profile.ann_stdev_pct == 0 or profile.price == 0:
        reasons.append("No valid price/stdev data")

    profile.quality_reasons = reasons
    profile.passes_quality = len(reasons) == 0
    return profile


# ═══════════════════════════════════════════════════════════════
# Stage 2: Executability Filter
# ═══════════════════════════════════════════════════════════════

def apply_executability_filter(profile: InstrumentProfile,
                                capital: float, n_target: int) -> InstrumentProfile:
    """Check if instrument is executable at given capital level"""
    reasons = []

    # Contract value in USD
    cv = profile.contract_value_usd
    if cv <= 0:
        reasons.append("Zero contract value")
        profile.exec_reasons = reasons
        profile.passes_executability = False
        return profile

    # Minimum capital for one contract (standalone basis)
    # min_cap = pointsize_base × price × ann_stdev / risk_target
    profile.min_capital_one = cv * (profile.ann_stdev_pct / 100.0) / RISK_TARGET

    # Can we hold ≥ 0.5 contracts on average?
    # notional_pos ≈ capital × IDM × (1/n) × vol_target / (stdev_price × pointsize × √256)
    idm = min(2.5, 1.0 + 0.1 * n_target)  # Scale IDM with instrument count
    weight = 1.0 / n_target
    if profile.ann_stdev_price > 0 and profile.pointsize > 0:
        subsys_pos = (capital * RISK_TARGET) / (profile.ann_stdev_price * profile.pointsize * profile.fx_rate)
        notional_pos = subsys_pos * idm * weight
    else:
        notional_pos = 0

    if notional_pos < 0.5:
        reasons.append(f"Avg position {notional_pos:.2f} < 0.5 contracts (CV=${cv:,.0f})")

    # Hard limit: contract value > 80% of capital
    if cv > capital * 0.80:
        reasons.append(f"Contract too large (${cv:,.0f} > 80% of ${capital:,.0f})")

    profile.exec_reasons = reasons
    profile.passes_executability = len(reasons) == 0
    return profile


# ═══════════════════════════════════════════════════════════════
# Stage 3: Factor SR Scoring
# ═══════════════════════════════════════════════════════════════

def compute_trend_sr(prices: pd.Series, lookback: int = LOOKBACK_DAYS) -> float:
    """
    EWMAC(16, 64) trend signal → SR
    Signal = EMA(16) - EMA(64), normalized by rolling stdev
    """
    recent = prices.tail(lookback + 100)  # Extra for warm-up
    if len(recent) < 200:
        return 0.0

    ema_fast = recent.ewm(span=16, adjust=False).mean()
    ema_slow = recent.ewm(span=64, adjust=False).mean()
    raw_signal = ema_fast - ema_slow

    # Normalize by rolling stdev of price changes
    daily_returns = recent.diff()
    vol = daily_returns.ewm(span=35, adjust=False).std()
    vol = vol.replace(0, np.nan).ffill()

    normalized_signal = raw_signal / vol
    normalized_signal = normalized_signal.clip(-20, 20)

    # Signal returns = signal(t-1) × return(t) / vol(t)
    signal_returns = (normalized_signal.shift(1) * daily_returns / vol).dropna()
    signal_returns = signal_returns.tail(lookback)

    if len(signal_returns) < 500 or signal_returns.std() == 0:
        return 0.0

    sr = signal_returns.mean() / signal_returns.std() * SQRT_256
    return float(np.clip(sr, -2.0, 2.0))


def compute_carry_sr(mp: pd.DataFrame, lookback: int = LOOKBACK_DAYS) -> float:
    """
    Carry signal from multiple prices: (CARRY - PRICE) / price, annualized
    """
    if mp is None or "CARRY" not in mp.columns or "PRICE" not in mp.columns:
        return 0.0

    recent = mp.tail(lookback + 100)
    carry = recent["CARRY"]
    price = recent["PRICE"]

    # Raw carry = (carry_price - price) / price
    # This is roughly the roll yield
    raw_carry = (carry - price) / price.replace(0, np.nan)
    raw_carry = raw_carry.dropna()

    if len(raw_carry) < 200:
        return 0.0

    # Normalize
    vol = raw_carry.ewm(span=35, adjust=False).std().replace(0, np.nan).ffill()
    norm_carry = raw_carry / vol
    norm_carry = norm_carry.clip(-20, 20)

    # Adjusted price returns
    adj_returns = price.diff() / price.shift(1).replace(0, np.nan)
    adj_returns = adj_returns.dropna()

    # Signal returns
    signal_returns = (norm_carry.shift(1) * adj_returns).dropna()
    signal_returns = signal_returns.tail(lookback)

    if len(signal_returns) < 500 or signal_returns.std() == 0:
        return 0.0

    sr = signal_returns.mean() / signal_returns.std() * SQRT_256
    return float(np.clip(sr, -2.0, 2.0))


def compute_cs_momentum_sr(prices: pd.Series, all_prices: Dict[str, pd.Series],
                            asset_class: str, asset_class_map: Dict[str, str],
                            lookback: int = LOOKBACK_DAYS) -> float:
    """
    Cross-sectional momentum: rank instrument's return vs peers in same asset class
    """
    # Find peers
    peers = [k for k, v in asset_class_map.items() if v == asset_class and k in all_prices]
    if len(peers) < 3:
        return 0.0  # Not enough peers for cross-sectional ranking

    # Compute 12-month (252-day) returns for all peers
    horizon = 252
    recent = prices.tail(lookback + horizon)
    if len(recent) < horizon + 100:
        return 0.0

    daily_returns = recent.pct_change().dropna()
    vol = daily_returns.ewm(span=35, adjust=False).std().replace(0, np.nan).ffill()

    # For each date, compute rolling return and rank vs peers
    rolling_ret = recent.pct_change(horizon)

    # Simplified: use the average rank over the lookback period
    # Compute peer returns at each point
    peer_returns = {}
    for p in peers:
        p_prices = all_prices.get(p)
        if p_prices is not None and len(p_prices) > horizon + 100:
            peer_returns[p] = p_prices.tail(lookback + horizon).pct_change(horizon)

    if len(peer_returns) < 3:
        return 0.0

    # Build DataFrame of peer returns
    peer_df = pd.DataFrame(peer_returns)
    # Rank (0 to 1) for our instrument
    instrument_code = prices.name if hasattr(prices, "name") else None
    if instrument_code is None or instrument_code not in peer_df.columns:
        return 0.0

    ranks = peer_df.rank(axis=1, pct=True)
    our_rank = ranks[instrument_code].dropna().tail(lookback)

    if len(our_rank) < 200:
        return 0.0

    # Signal = rank - 0.5 (centered)
    signal = our_rank - 0.5

    # Signal returns
    inst_returns = daily_returns.reindex(signal.index)
    inst_vol = vol.reindex(signal.index)
    signal_returns = (signal.shift(1) * inst_returns / inst_vol).dropna()

    if len(signal_returns) < 200 or signal_returns.std() == 0:
        return 0.0

    sr = signal_returns.mean() / signal_returns.std() * SQRT_256
    return float(np.clip(sr, -2.0, 2.0))


# ═══════════════════════════════════════════════════════════════
# Stage 4: Greedy Subset Selection
# ═══════════════════════════════════════════════════════════════

def greedy_select(candidates: List[InstrumentProfile],
                  target_n: int,
                  all_prices: Dict[str, pd.Series]) -> List[InstrumentProfile]:
    """
    Greedy algorithm to select optimal subset.
    Score = shrunk_SR + diversity_bonus - correlation_penalty
    """
    selected = []
    remaining = sorted(candidates, key=lambda p: p.shrunk_sr, reverse=True)

    # Asset class counts
    class_counts: Dict[str, int] = {}

    for _ in range(target_n):
        if not remaining:
            break

        best_score = -999
        best_idx = -1

        for i, cand in enumerate(remaining):
            score = cand.shrunk_sr

            # Diversity bonus: underrepresented asset class
            ac = cand.asset_class
            current_count = class_counts.get(ac, 0)
            total_selected = len(selected)

            if total_selected > 0:
                # Bonus for adding a new asset class
                if current_count == 0:
                    score += 0.15
                # Penalty for overrepresented class
                elif current_count >= MAX_PER_ASSET_CLASS:
                    score -= 999  # Hard constraint
                elif current_count >= 3:
                    score -= 0.05 * (current_count - 2)

            # Known duplicate check: skip if a duplicate is already selected
            is_duplicate = False
            for group in KNOWN_DUPLICATE_GROUPS:
                if cand.code in group:
                    for sel in selected:
                        if sel.code in group and sel.code != cand.code:
                            is_duplicate = True
                            break
                if is_duplicate:
                    break
            if is_duplicate:
                score -= 999  # Hard block
                if score > best_score:  # won't be, skip correlation calc
                    best_score = score
                    best_idx = i
                continue

            # Correlation penalty: check vs already selected instruments
            if selected and cand.code in all_prices:
                cand_prices = all_prices[cand.code]
                max_corr = 0.0
                for sel in selected:
                    if sel.code in all_prices:
                        sel_prices = all_prices[sel.code]
                        # Use last 2 years of returns correlation
                        common_idx = cand_prices.index.intersection(sel_prices.index)
                        if len(common_idx) > 500:
                            c_ret = cand_prices.reindex(common_idx).pct_change().tail(500)
                            s_ret = sel_prices.reindex(common_idx).pct_change().tail(500)
                            corr = c_ret.corr(s_ret)
                            if not np.isnan(corr):
                                max_corr = max(max_corr, abs(corr))
                # Hard exclude if very high correlation
                if max_corr > CORRELATION_HARD_EXCLUDE:
                    score -= 999
                elif max_corr > CORRELATION_PENALTY_THRESHOLD:
                    score -= 0.30 * (max_corr - CORRELATION_PENALTY_THRESHOLD) / (CORRELATION_HARD_EXCLUDE - CORRELATION_PENALTY_THRESHOLD)

            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0:
            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            class_counts[chosen.asset_class] = class_counts.get(chosen.asset_class, 0) + 1

    # Check minimum asset class constraint
    if len(set(p.asset_class for p in selected)) < MIN_ASSET_CLASSES:
        print(f"  ⚠️ Warning: Only {len(set(p.asset_class for p in selected))} asset classes (min {MIN_ASSET_CLASSES})")

    return selected


# ═══════════════════════════════════════════════════════════════
# Main Pipeline
# ═══════════════════════════════════════════════════════════════

def run_optimizer(capital: float = 200000, target_n: int = 15,
                  output_json: str = None, verbose: bool = True) -> List[InstrumentProfile]:
    """Run the full 4-stage optimization pipeline"""

    if verbose:
        print("═" * 60)
        print(f"  ARKI UNIVERSE OPTIMIZER — ${capital/1000:.0f}K, Target {target_n} instruments")
        print("═" * 60)
        print()

    # Load config data
    ic = load_instrument_config()
    sc = load_spread_costs()
    sc_dict = dict(zip(sc["Instrument"], sc["SpreadCost"]))
    ic_dict = {row["Instrument"]: row for _, row in ic.iterrows()}

    # Find instruments with price data
    price_files = [f.replace(".csv", "") for f in os.listdir(ADJUSTED_PRICES_DIR)
                   if f.endswith(".csv")]
    tradeable = [i for i in price_files if i in ic_dict and i in sc_dict]
    tradeable.sort()

    if verbose:
        print(f"Pool: {len(tradeable)} instruments with price + config + spread data")
        print()

    # ─── Load all prices (for CS momentum and correlation) ───
    if verbose:
        print("Loading price data...", end="", flush=True)

    all_prices: Dict[str, pd.Series] = {}
    asset_class_map: Dict[str, str] = {}
    profiles: List[InstrumentProfile] = []

    for code in tradeable:
        prices = load_adjusted_prices(code)
        if prices is None or len(prices) < 100:
            continue

        prices.name = code
        all_prices[code] = prices

        row = ic_dict[code]
        ac = ASSET_CLASS_OVERRIDES.get(code, row["AssetClass"])
        asset_class_map[code] = ac
        currency = row["Currency"]
        fx_rate = load_fx_rate(currency)
        pointsize = float(row["Pointsize"])
        per_block = float(row.get("PerBlock", 0))
        spread = sc_dict.get(code, 0)
        last_price = float(prices.dropna().iloc[-1])

        # Compute volatility
        daily_ret = prices.pct_change().dropna()
        recent_ret = daily_ret.tail(LOOKBACK_DAYS)
        if len(recent_ret) < 200:
            continue

        daily_stdev_pct = recent_ret.std() * 100
        ann_stdev_pct = daily_stdev_pct * SQRT_256
        ann_stdev_price = recent_ret.std() * last_price * SQRT_256

        # Contract value
        cv = last_price * pointsize * fx_rate

        # SR cost
        sr_cost_val = compute_sr_cost(spread, per_block, ann_stdev_price, pointsize)

        p = InstrumentProfile(
            code=code,
            description=row.get("Description", ""),
            asset_class=ac,
            region=row.get("Region", ""),
            currency=currency,
            pointsize=pointsize,
            per_block=per_block,
            spread_cost=spread,
            price=last_price,
            fx_rate=fx_rate,
            contract_value_usd=cv,
            ann_stdev_pct=ann_stdev_pct,
            ann_stdev_price=ann_stdev_price,
            sr_cost=sr_cost_val,
            history_days=len(prices),
        )
        profiles.append(p)

    if verbose:
        print(f" loaded {len(profiles)} valid instruments")
        print()

    # ─── Stage 1: Quality Gates ───
    if verbose:
        print("─── Stage 1: Quality Gates ───")

    for p in profiles:
        apply_quality_gates(p)

    passed_quality = [p for p in profiles if p.passes_quality]
    failed_quality = [p for p in profiles if not p.passes_quality]

    if verbose:
        print(f"  Passed: {len(passed_quality)} / {len(profiles)}")
        print(f"  Failed: {len(failed_quality)} (expensive={sum(1 for p in failed_quality if any('Expensive' in r for r in p.quality_reasons))}, "
              f"too safe={sum(1 for p in failed_quality if any('Too safe' in r for r in p.quality_reasons))}, "
              f"short history={sum(1 for p in failed_quality if any('Short' in r for r in p.quality_reasons))})")
        print()

    # ─── Stage 2: Executability Filter ───
    if verbose:
        print("─── Stage 2: Executability Filter ───")

    for p in passed_quality:
        apply_executability_filter(p, capital, target_n)

    passed_exec = [p for p in passed_quality if p.passes_executability]
    failed_exec = [p for p in passed_quality if not p.passes_executability]

    if verbose:
        print(f"  Passed: {len(passed_exec)} / {len(passed_quality)}")
        if failed_exec:
            print(f"  Failed: {len(failed_exec)} (too large for ${capital/1000:.0f}K)")
        print()

    # ─── Stage 3: Factor SR Scoring ───
    if verbose:
        print("─── Stage 3: Factor SR Scoring ───")
        print("  Computing Trend SR (EWMAC 16/64)...", end="", flush=True)

    for p in passed_exec:
        prices = all_prices.get(p.code)
        if prices is not None:
            p.trend_sr = compute_trend_sr(prices)

    if verbose:
        print(" done")
        print("  Computing Carry SR...", end="", flush=True)

    for p in passed_exec:
        mp = load_multiple_prices(p.code)
        p.carry_sr = compute_carry_sr(mp)

    if verbose:
        print(" done")
        print("  Computing CS Momentum SR...", end="", flush=True)

    for p in passed_exec:
        prices = all_prices.get(p.code)
        if prices is not None:
            p.cs_mom_sr = compute_cs_momentum_sr(
                prices, all_prices, p.asset_class, asset_class_map
            )

    if verbose:
        print(" done")

    # Composite SR (weighted average)
    for p in passed_exec:
        p.composite_sr = (
            FACTOR_WEIGHTS["trend"] * p.trend_sr
            + FACTOR_WEIGHTS["carry"] * p.carry_sr
            + FACTOR_WEIGHTS["cs_momentum"] * p.cs_mom_sr
        )

    # Shrinkage toward cross-sectional mean
    all_composites = [p.composite_sr for p in passed_exec if p.composite_sr != 0]
    mean_sr = np.mean(all_composites) if all_composites else 0
    for p in passed_exec:
        p.shrunk_sr = (1 - SR_SHRINKAGE) * p.composite_sr + SR_SHRINKAGE * mean_sr

    if verbose:
        top5 = sorted(passed_exec, key=lambda x: x.composite_sr, reverse=True)[:5]
        print(f"\n  Top 5 by composite SR (before shrinkage):")
        for p in top5:
            print(f"    {p.code:<22} T={p.trend_sr:+.3f}  C={p.carry_sr:+.3f}  M={p.cs_mom_sr:+.3f}  → {p.composite_sr:+.3f}")
        print()

    # ─── Stage 4: Greedy Subset Selection ───
    if verbose:
        print("─── Stage 4: Greedy Subset Selection ───")

    selected = greedy_select(passed_exec, target_n, all_prices)

    # ─── Output ───
    if verbose:
        print()
        print("═" * 72)
        print(f"  RECOMMENDED UNIVERSE ({len(selected)} instruments, ${capital/1000:.0f}K)")
        print("═" * 72)
        print()
        print(f"{'#':>2} {'Instrument':<22} {'Class':<10} {'CV($)':>10} {'SR Cost':>8} "
              f"{'Trend':>7} {'Carry':>7} {'CSM':>7} {'Comp':>7} {'Shrunk':>7}")
        print("─" * 100)
        for i, p in enumerate(selected, 1):
            print(f"{i:>2} {p.code:<22} {p.asset_class:<10} "
                  f"${p.contract_value_usd/1000:>7.0f}K "
                  f"{p.sr_cost:>7.4f} "
                  f"{p.trend_sr:>+6.3f} {p.carry_sr:>+6.3f} {p.cs_mom_sr:>+6.3f} "
                  f"{p.composite_sr:>+6.3f} {p.shrunk_sr:>+6.3f}")

        # Asset class summary
        ac_summary = {}
        for p in selected:
            ac_summary[p.asset_class] = ac_summary.get(p.asset_class, 0) + 1
        print()
        print("  Asset Class Balance: " + " | ".join(
            f"{ac}: {n}" for ac, n in sorted(ac_summary.items(), key=lambda x: -x[1])
        ))

        exec_rate = len(selected) / len(selected) * 100 if selected else 0
        print(f"  Executability: {len(selected)}/{len(selected)} = {exec_rate:.0f}% PRODUCTION")
        print()

        # Compare with current v6
        v6_instruments = [
            'AUD_micro', 'BRENT-LAST', 'BUND', 'COCOA_LDN', 'COPPER-micro',
            'COTTON', 'CRUDE_W', 'DAX', 'FTSE100', 'FTSECHINAA', 'GASOIL',
            'GILT', 'GOLD_micro', 'IBEX_mini', 'JGB', 'LEANHOG', 'MXP',
            'NASDAQ_micro', 'NIKKEI', 'SILVER', 'SP500_micro', 'SUGAR11',
            'US10', 'US5', 'YENEUR'
        ]
        selected_codes = {p.code for p in selected}
        kept = selected_codes.intersection(v6_instruments)
        added = selected_codes - set(v6_instruments)
        dropped = set(v6_instruments) - selected_codes

        print("  vs Current v6 (25 instruments):")
        print(f"    Kept:    {len(kept)} — {sorted(kept)}")
        print(f"    Added:   {len(added)} — {sorted(added)}")
        print(f"    Dropped: {len(dropped)} — {sorted(dropped)}")
        print()

    # ─── JSON output ───
    if output_json:
        result = {
            "config": {
                "capital": capital,
                "target_n": target_n,
                "sr_shrinkage": SR_SHRINKAGE,
                "max_sr_cost": MAX_SR_COST,
                "lookback_days": LOOKBACK_DAYS,
                "factor_weights": FACTOR_WEIGHTS,
            },
            "pipeline": {
                "total_pool": len(profiles),
                "passed_quality": len(passed_quality),
                "passed_executability": len(passed_exec),
                "selected": len(selected),
            },
            "selected": [
                {
                    "code": p.code,
                    "asset_class": p.asset_class,
                    "region": p.region,
                    "contract_value_usd": round(p.contract_value_usd),
                    "sr_cost": round(p.sr_cost, 5),
                    "trend_sr": round(p.trend_sr, 4),
                    "carry_sr": round(p.carry_sr, 4),
                    "cs_momentum_sr": round(p.cs_mom_sr, 4),
                    "composite_sr": round(p.composite_sr, 4),
                    "shrunk_sr": round(p.shrunk_sr, 4),
                }
                for p in selected
            ],
            "candidates": [
                {
                    "code": p.code,
                    "asset_class": p.asset_class,
                    "contract_value_usd": round(p.contract_value_usd),
                    "sr_cost": round(p.sr_cost, 5),
                    "composite_sr": round(p.composite_sr, 4),
                    "passes_quality": p.passes_quality,
                    "passes_executability": p.passes_executability,
                }
                for p in sorted(profiles, key=lambda x: x.composite_sr, reverse=True)
            ],
        }

        with open(output_json, "w") as f:
            json.dump(result, f, indent=2)
        if verbose:
            print(f"  Results saved to: {output_json}")

    return selected


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Arki Universe Optimizer")
    parser.add_argument("--capital", type=float, default=200000,
                        help="Trading capital in USD (default: 200000)")
    parser.add_argument("--target", type=int, default=15,
                        help="Target number of instruments (default: 15)")
    parser.add_argument("--json", type=str, default=None,
                        help="Output JSON file path")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output")
    args = parser.parse_args()

    json_path = args.json
    if json_path is None:
        # Default output location
        json_path = os.path.join(
            os.path.dirname(__file__), "..", "results",
            f"optimizer_{int(args.capital/1000)}k_{args.target}inst.json"
        )

    run_optimizer(
        capital=args.capital,
        target_n=args.target,
        output_json=json_path,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
