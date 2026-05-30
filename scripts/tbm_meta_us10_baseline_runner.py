#!/usr/bin/env python
"""TBM Stage-1 meta-labeling runner for US10/ZN.

Pre-registration (Path A, locked 2026-05-30):
  ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md

This is queue item #1 of the futures_momentum family:
  ars/families/futures_momentum/queue.md

Integration posture (HANDOFF §3 "Option B" -- label-only attachment):
  * SIDE = sign of single-EMA2(N=20,40) on ZN, derived internally with
    Martin §2.5 absolute-change form (NOT pct-returns; ZN panama crosses zero).
  * SIZE = learned meta-classifier on CUSUM-day events labeled by TBM.
  * Engine (pysystemtrade) is NOT modified -- this is a standalone numpy +
    sklearn attachment that consumes the same ZN price data the engine uses.

Skeleton source: /Users/msyeom/Downloads/stage1_meta_labeling.py
  * Functions LIFTED: average_uniqueness, sample_weights, MetaSizer,
                       size_from_meta, build_features (with pct->abs fix),
                       perf_metrics, kaufman_efficiency_ratio.
  * Functions REPLACED (3 -- ZN panama sign-crossing fixes):
      daily_vol            -> daily_vol_absolute        (pct -> abs price points)
      cusum_events         -> cusum_events_abs_with_reset (pct -> abs + Rule 5.2.a)
      triple_barrier_labels -> triple_barrier_labels_abs  (pct -> abs price points)
  * Functions ADDED (gap-handling + CPCV):
      gap_aware_event_filter (Rules 5.2.b + 5.2.c)
      combinatorial_purged_cv_indices (extends skeleton's purged_kfold to CPCV)
  * DSR / PBO -- NOT lifted; imported from arki.utils.dsr (single SOT, bug-fixed
    per-period vs annualised consistency). The skeleton's local copies are
    NOT used.

Output schema matches futures_momentum family conventions (ars/families/...).
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# ---- Single SOT DSR / PBO (NO local copies; bug ③ fix from arki/utils/dsr) ----
from arki.utils.dsr import (             # noqa: E402
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    expected_max_sharpe,
)
from arki.utils.martin_vol import martin_ema_vol  # noqa: E402

INSTRUMENT = "US10"
TRADING_DAYS = 256                       # ann_factor (pysystemtrade BUSINESS_DAYS_IN_YEAR)
OUT_BASE = ROOT / "ars" / "runs"
PRE_REG = "ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md"

# Family-scope DSR context (carried into the runner so it can flag absolute promotion claims)
FAMILY_DSR_THRESHOLD_AT_N_50 = 0.325     # annualised; from family.yaml multiple_testing block
FAMILY_N_CONFIGS_SEARCHED = 50           # post-lock of this pre-reg
FAMILY_SR_TRIALS_STD_ANN = 0.1426        # std of {SR_n: 12 family cells}; from family DSR computation
                                          # NOT the within-cell trial-grid std (that would be daily-return
                                          # std of the single strategy, a different statistic).


# =====================================================================
# Stage1Config -- locked per HANDOFF §0-§2 + pre-reg §3
# =====================================================================

@dataclass
class Stage1Config:
    # vol estimator (Martin §2.5 absolute-change form)
    vol_span: int = 20
    vol_floor_min_periods: int = 20
    vol_floor_quantile: float = 0.5
    vol_floor_multiplier: float = 0.2
    # CUSUM event sampling
    cusum_kappa: float = 1.0
    gap_threshold_days: int = 5                 # Rule 5.2.a trigger threshold
    # Triple barrier (raw-σ calibrated per HANDOFF §2)
    pt_mult: float = 8.0
    sl_mult: float = 4.0
    t_max: int = 120                            # business days (vertical barrier)
    use_high_low: bool = True
    # Martin momentum speeds for the 6-speed pseudo-cross-section pool
    # (pandas span for Martin α: span = 2/(1-α) - 1; Martin N=20,40 -> span=39,79)
    speeds: tuple = (
        (39, 79),   # Martin EMA2(N=20, 40)  -- the primary side
        (9, 17),    # ewmac4_16-like
        (5, 9),     # ewmac2_8-like
        (17, 35),   # ewmac8_32-like
        (35, 71),   # ewmac16_64-like
        (71, 143),  # ewmac32_128-like
    )
    primary_speed_idx: int = 0
    # Sample weights
    time_decay: float = 0.75
    # Sizing -- LOCKED g_min=0.30, g_max=1.0 (preserves Martin §4 Eq.(20))
    g_min: float = 0.30
    g_max: float = 1.0
    # FIRST RUN: single config to eliminate within-cell selection bias.
    # Internal grid expansion (tau / feature-subset sweep) is queued for a
    # SEPARATE pre-reg + run -- adding more configs raises family DSR
    # threshold self-correcting (per family.yaml multiple_testing block).
    tau_grid: tuple = (0.50,)                    # single tau (no sweep this run)
    feature_subsets: tuple = ("ER_plus_rest",)   # single feature set (no sweep this run)
    # Classification threshold (for F1) -- DECOUPLED from tau (sizing != classification).
    classify_threshold: float = 0.50
    target_vol: float = 0.20                     # ann -- matches family vol_target_pct
    vol_target_span: int = 63
    # Meta-model
    n_estimators: int = 100                      # reduced from skeleton 200 for tractability
    max_depth: int = 3
    random_state: int = 0
    # CPCV (combinatorial purged + embargo)
    n_cv_groups: int = 6                         # -> C(6,3)=20 pairings
    embargo_frac: float = 0.01
    # Annualisation -- locked to 256 (matches family.yaml)
    ann_factor: float = float(TRADING_DAYS)


# =====================================================================
# (REPLACED) daily_vol -- absolute-change form (HANDOFF §3 code-fix)
# =====================================================================

def daily_vol_absolute(close: pd.Series, span: int = 20,
                       floor_min_periods: int = 20,
                       floor_quantile: float = 0.5,
                       floor_multiplier: float = 0.2) -> pd.Series:
    """Martin §2.5 sigma_hat on RAW absolute price changes (PRICE-POINT units).

    Replaces skeleton.daily_vol which used pct_change and explodes on ZN panama
    sign-crossings. Verified 2026-05-30: this form reproduces HANDOFF sigma
    median 0.39 (observed 0.3871) on the repo's ZN feed; see
    scripts/tbm_sigma_verification.py.
    """
    sigma = martin_ema_vol(close.diff(), N=span, min_periods=floor_min_periods // 2)
    floor = sigma.expanding(min_periods=floor_min_periods).quantile(floor_quantile) * floor_multiplier
    return sigma.clip(lower=floor)


# =====================================================================
# (NEW) Gap detection helper -- identifies all gaps in the index of more
# than `gap_threshold_days` calendar days (per Rule 5.2.a, with the same
# threshold reused for Rule 5.2.b post-gap re-warmup masking)
# =====================================================================

def detect_gaps(index: pd.DatetimeIndex, gap_threshold_days: int = 5) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return list of (last_pre_gap_ts, first_post_gap_ts) for each gap of
    > gap_threshold_days calendar days in `index`."""
    deltas = index.to_series().diff().dt.days
    gap_mask = deltas > gap_threshold_days
    gaps = []
    for ts in index[gap_mask]:
        i = index.get_loc(ts)
        if i > 0:
            gaps.append((index[i - 1], ts))
    return gaps


# =====================================================================
# (REPLACED) cusum_events -- absolute-change drift + Rule 5.2.a reset
# =====================================================================

def cusum_events_abs_with_reset(close: pd.Series, vol: pd.Series,
                                  kappa: float = 1.0,
                                  gap_threshold_days: int = 5) -> pd.DatetimeIndex:
    """Symmetric CUSUM on ABSOLUTE price changes (NOT log returns).

    Replaces skeleton.cusum_events which used np.log(close).diff() and breaks
    on ZN panama sign-crossings. The drift is now `close.diff()` in PRICE
    POINT units; the threshold `kappa * sigma` is also in price-point units
    (sigma from daily_vol_absolute). HANDOFF §3 code-fix.

    Rule 5.2.a applied: when consecutive index timestamps are more than
    `gap_threshold_days` calendar days apart, reset `s_pos = s_neg = 0`
    before processing the new observation. Prevents pre-gap drift firing
    a spurious event on the first post-gap bar.

    Also emits diagnostics tuple via `cusum_events_abs_with_reset.last_diag`
    so the runner can record Rule 5.2.a actuation counts.
    """
    diff = close.diff().fillna(0.0).values
    h = (kappa * vol).bfill().fillna(np.inf).values
    idx = close.index
    deltas = idx.to_series().diff().dt.days.fillna(0).values
    s_pos = s_neg = 0.0
    events: list[pd.Timestamp] = []
    n_resets = 0
    for t in range(len(idx)):
        if deltas[t] > gap_threshold_days:            # Rule 5.2.a
            s_pos = s_neg = 0.0
            n_resets += 1
        s_pos = max(0.0, s_pos + diff[t])
        s_neg = min(0.0, s_neg + diff[t])
        if s_neg < -h[t]:
            s_neg = 0.0
            events.append(idx[t])
        elif s_pos > h[t]:
            s_pos = 0.0
            events.append(idx[t])
    cusum_events_abs_with_reset.last_diag = {       # type: ignore[attr-defined]
        "n_resets_rule_5_2_a": n_resets,
        "n_events_raw_after_reset": len(events),
    }
    return pd.DatetimeIndex(events)


# =====================================================================
# (NEW) gap_aware_event_filter -- applies Rules 5.2.b + 5.2.c
# =====================================================================

def gap_aware_event_filter(events: pd.DatetimeIndex,
                            price_index: pd.DatetimeIndex,
                            cfg: Stage1Config) -> tuple[pd.DatetimeIndex, dict]:
    """Apply gap-handling Rules 5.2.b (sigma re-warmup mask) and 5.2.c
    (cross-gap label window drop) to the raw CUSUM event set BEFORE
    triple_barrier_labels is invoked.

    Returns (filtered_events, diagnostics_dict).
    """
    gaps = detect_gaps(price_index, cfg.gap_threshold_days)
    n_rewarmup_drop = 0
    n_cross_gap_drop = 0
    kept: list[pd.Timestamp] = []
    for ts in events:
        drop_b = False    # Rule 5.2.b -- post-gap re-warmup mask
        drop_c = False    # Rule 5.2.c -- cross-gap label-window drop
        i_event = price_index.get_loc(ts)
        # Window [t_event, t_event + t_max] in business-day positions.
        i_window_end = min(i_event + cfg.t_max, len(price_index) - 1)
        for (last_pre, first_post) in gaps:
            # Rule 5.2.b -- event lies within vol_span business days AFTER gap end
            if ts >= first_post:
                i_post = price_index.get_loc(first_post)
                if i_event - i_post < cfg.vol_span:
                    drop_b = True
            # Rule 5.2.c -- event's [t_event, t_event + t_max] window overlaps gap
            #   case (i): t_event < last_pre AND t_event + t_max >= last_pre
            #   case (ii): last_pre <= t_event <= first_post (event inside gap)
            #   case (iii): t_event in [first_post, first_post + vol_span) -- redundant with (b)
            window_end_ts = price_index[i_window_end]
            if ts < last_pre and window_end_ts >= last_pre:
                drop_c = True                          # event before gap whose window crosses it
            if last_pre <= ts <= first_post:
                drop_c = True                          # event inside gap region
            if first_post <= ts < price_index[min(price_index.get_loc(first_post) + cfg.vol_span,
                                                   len(price_index) - 1)]:
                drop_c = True                          # event in post-gap warm-up (redundant 5.2.b)
        if drop_b:
            n_rewarmup_drop += 1
            continue
        if drop_c:
            n_cross_gap_drop += 1
            continue
        kept.append(ts)
    diag = {
        "n_gaps_detected":                len(gaps),
        "n_events_dropped_rewarmup":      n_rewarmup_drop,
        "n_events_dropped_cross_gap":     n_cross_gap_drop,
        "n_events_kept_after_gap_filter": len(kept),
        "gaps_summary": [{"last_pre": str(a.date()), "first_post": str(b.date()),
                          "gap_days": int((b - a).days)} for a, b in gaps],
    }
    return pd.DatetimeIndex(kept), diag


# =====================================================================
# (REPLACED) triple_barrier_labels -- absolute price-point form
# =====================================================================

def triple_barrier_labels_abs(close: pd.Series, high: pd.Series, low: pd.Series,
                                vol: pd.Series, side: pd.Series,
                                events: pd.DatetimeIndex,
                                cfg: Stage1Config) -> pd.DataFrame:
    """Triple-barrier labeling in ABSOLUTE PRICE-POINT units.

    Replaces skeleton.triple_barrier_labels which used pct return
    `close[i]/p0 - 1.0` and breaks on ZN panama sign-crossings (p0 -> 0 or
    negative). Now: `close[i] - p0` (price-point units) with barriers
    `pt_mult * sigma`, `sl_mult * sigma` also in price-point units.

    Tie-break (PT & SL hit same day): SL first (conservative).

    Returns DataFrame indexed by t0 with columns: t1, ret_pp (absolute
    price-point return, side-adjusted), bin (1 if winning trade, else 0),
    side.
    """
    idx = close.index
    close_v = close.values
    high_v = (high if cfg.use_high_low else close).values
    low_v = (low if cfg.use_high_low else close).values
    pos = {ts: i for i, ts in enumerate(idx)}
    rows = []
    for ts in events:
        i0 = pos[ts]
        s = float(side.loc[ts])
        sig = float(vol.loc[ts])
        if not np.isfinite(sig) or sig <= 0:
            continue
        pt_pp = cfg.pt_mult * sig                 # price-point units
        sl_pp = cfg.sl_mult * sig
        i_end = min(i0 + cfg.t_max, len(idx) - 1)
        p0 = close_v[i0]
        # Default = vertical-barrier outcome (absolute change at t_max)
        t1_ts = idx[i_end]
        ret_pp = s * (close_v[i_end] - p0)
        for j in range(i0 + 1, i_end + 1):
            up_pp = high_v[j] - p0                # absolute change at high
            dn_pp = low_v[j] - p0                 # absolute change at low
            fav = (s * up_pp) if s > 0 else (s * dn_pp)
            adv = (s * dn_pp) if s > 0 else (s * up_pp)
            hit_sl = adv <= -sl_pp
            hit_pt = fav >= pt_pp
            if hit_sl:
                t1_ts, ret_pp = idx[j], -sl_pp
                break
            if hit_pt:
                t1_ts, ret_pp = idx[j], pt_pp
                break
        rows.append((ts, t1_ts, float(ret_pp), int(ret_pp > 0), int(s)))
    return pd.DataFrame(rows, columns=["t0", "t1", "ret_pp", "bin", "side"]).set_index("t0")


# =====================================================================
# (LIFTED, fixed) Side from internal Martin EMA2 -- abs price-EMA, sign only
# =====================================================================

def compute_side_and_sig_df(close: pd.Series, vol: pd.Series,
                             cfg: Stage1Config) -> tuple[pd.Series, pd.DataFrame]:
    """Side = sign(fast_EMA(price) - slow_EMA(price)) on the primary speed.
    sig_df = the same fast-minus-slow oscillator across all configured speeds,
    normalised to vol-units (price_diff / sigma_pp) for use in features.

    HANDOFF integrity: the primary side is from Martin §2.1 EMA2 on price
    (Appendix A Eq.(35)), single instrument. Side is consumed sign-only.
    The 6-speed pseudo-cross-section is for LABEL/FEATURE data-thickness,
    NOT for side redefinition.
    """
    sig_df = pd.DataFrame(index=close.index)
    for i, (s_fast, s_slow) in enumerate(cfg.speeds):
        ema_fast = close.ewm(span=s_fast, adjust=False).mean()
        ema_slow = close.ewm(span=s_slow, adjust=False).mean()
        diff_price = ema_fast - ema_slow           # price-point units
        sig_df[i] = (diff_price / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    primary = sig_df[cfg.primary_speed_idx]
    side = np.sign(primary).replace(0, np.nan).ffill().fillna(1.0).astype(int)
    return side, sig_df


# =====================================================================
# (LIFTED, with internal pct->abs swap) build_features
# =====================================================================

def kaufman_efficiency_ratio(close: pd.Series, window: int) -> pd.Series:
    direction = (close - close.shift(window)).abs()
    volatility = close.diff().abs().rolling(window).sum()
    return (direction / volatility).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_features_abs(close: pd.Series, sig_df: pd.DataFrame, vol: pd.Series,
                        cfg: Stage1Config, feature_subset: str) -> pd.DataFrame:
    """Features in absolute-change form (NOT pct-return). Matches HANDOFF
    feature list with ER_20d and ER_60d as Tier-1 inputs per pre-reg §1.
    """
    # Use ABSOLUTE price change as "ret" feature so ZN panama sign-crossings
    # don't blow up vol-of-vol or autocorr_1.
    dprice = close.diff()
    signs = np.sign(sig_df)
    f = pd.DataFrame(index=close.index)
    f["ER_20d"] = kaufman_efficiency_ratio(close, 20)        # Tier-1 primary (HANDOFF §1B)
    f["ER_60d"] = kaufman_efficiency_ratio(close, 60)        # Tier-1 primary
    if feature_subset == "ER_only":
        return f.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    # ER_plus_rest
    f["sign_agreement"] = signs.mean(axis=1).abs()
    f["signal_dispersion"] = sig_df.std(axis=1)
    f["primary_strength"] = sig_df[cfg.primary_speed_idx].abs()
    f["vol"] = vol
    f["vol_of_vol"] = vol.diff().rolling(cfg.vol_span).std()  # abs diff, not pct
    f["autocorr_1"] = dprice.rolling(cfg.vol_span).apply(
        lambda x: pd.Series(x).autocorr(lag=1) if pd.Series(x).notna().sum() > 2 else 0.0,
        raw=False)
    # Drawdown of an always-on primary baseline (absolute-change P&L proxy)
    base_pnl_pp = (np.sign(sig_df[cfg.primary_speed_idx]).shift(1) * dprice).fillna(0.0)
    cum = base_pnl_pp.cumsum()                                # additive cumsum (abs units)
    f["drawdown"] = (cum - cum.cummax())                      # in price-point units
    return f.replace([np.inf, -np.inf], np.nan).fillna(0.0)


# =====================================================================
# (LIFTED) average_uniqueness, sample_weights -- skeleton verbatim
# =====================================================================

def average_uniqueness(labels: pd.DataFrame, close_index: pd.Index) -> pd.Series:
    conc = pd.Series(0.0, index=close_index)
    spans = []
    for t0, row in labels.iterrows():
        seg = close_index[(close_index >= t0) & (close_index <= row["t1"])]
        spans.append((t0, seg))
        conc.loc[seg] += 1.0
    u = {t0: (1.0 / conc.loc[seg]).mean() if len(seg) else 0.0 for t0, seg in spans}
    return pd.Series(u).reindex(labels.index).fillna(0.0)


def sample_weights(labels: pd.DataFrame, close_index: pd.Index, time_decay: float) -> pd.Series:
    u = average_uniqueness(labels, close_index)
    if len(u) == 0:
        return u
    decay = np.linspace(time_decay, 1.0, len(u))
    w = u.values * decay
    w = w / w.mean() if w.mean() > 0 else w
    return pd.Series(w, index=u.index)


# =====================================================================
# (LIFTED) MetaSizer -- skeleton verbatim except n_estimators default
# =====================================================================

class MetaSizer:
    def __init__(self, cfg: Stage1Config):
        self.cfg = cfg
        self.model = None
        self.cols = None

    def fit(self, X: pd.DataFrame, y: pd.Series, w: pd.Series, avg_uniq: float):
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.ensemble import BaggingClassifier
        self.cols = list(X.columns)
        max_samples = float(np.clip(avg_uniq, 0.05, 1.0))
        base = DecisionTreeClassifier(
            max_depth=self.cfg.max_depth, class_weight="balanced",
            random_state=self.cfg.random_state)
        kw = dict(n_estimators=self.cfg.n_estimators, max_samples=max_samples,
                  max_features=1.0, bootstrap=True, n_jobs=-1,
                  random_state=self.cfg.random_state)
        try:
            self.model = BaggingClassifier(estimator=base, **kw)
        except TypeError:
            self.model = BaggingClassifier(base_estimator=base, **kw)
        self.model.fit(X[self.cols].values, y.values,
                       sample_weight=w.reindex(y.index).fillna(0.0).values)
        return self

    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        p = self.model.predict_proba(X[self.cols].values)[:, 1]
        return pd.Series(p, index=X.index)


def size_from_meta(m: pd.Series, tau: float, g_min: float, g_max: float = 1.0) -> pd.Series:
    """g(m) = g_min + (g_max - g_min) * clip((m - tau) / (1 - tau), 0, 1)."""
    ramp = np.clip((m - tau) / (1.0 - tau), 0.0, 1.0)
    return g_min + (g_max - g_min) * ramp


# =====================================================================
# (NEW) Combinatorial Purged CV indices  (extends skeleton's k-fold purged)
# =====================================================================

def combinatorial_purged_cv_indices(labels: pd.DataFrame, n_groups: int,
                                     embargo_frac: float = 0.01):
    """CPCV per LdP 2018 ch.12 §12.4: yield C(n_groups, n_groups/2) (train, test)
    splits. Each split has `n_groups/2` test groups and `n_groups/2` train
    groups. Train labels whose [t0,t1] overlaps test span are purged, plus
    embargo at the boundaries."""
    t0_arr = labels.index.values
    t1_arr = labels["t1"].values
    n = len(labels)
    embargo = int(n * embargo_frac)
    groups = np.array_split(np.arange(n), n_groups)
    half = n_groups // 2
    for combo in combinations(range(n_groups), half):
        test_groups = [groups[i] for i in combo]
        test_idx = np.concatenate(test_groups)
        test_t0 = t0_arr[test_idx.min()]
        test_t1 = t1_arr[test_idx.max()]
        keep = ~((t1_arr >= test_t0) & (t0_arr <= test_t1))     # purge overlaps
        train_idx = np.where(keep)[0]
        train_idx = train_idx[
            (train_idx < test_idx.min() - embargo) |
            (train_idx > test_idx.max() + embargo)
        ]
        yield train_idx, test_idx


# =====================================================================
# Position + strategy returns -- absolute-change form
# =====================================================================

def strategy_returns_abs(side: pd.Series, g: pd.Series, vol: pd.Series,
                          dprice: pd.Series, cfg: Stage1Config) -> tuple[pd.Series, pd.Series]:
    """Strategy daily returns and position series (absolute-change form).

    Position theta = side * g / sigma_pp (dimensionless "1/price" per signal-sigma).
    Daily P&L per unit-of-(theta) = theta_{t-1} * dprice_t. Scaled ex-post to
    target annualised vol via the rolling-vol scaler (skeleton convention).
    Returns (daily_pct, position_normalised).
    """
    raw_theta = (side * g / vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    raw_pnl = (raw_theta.shift(1) * dprice).fillna(0.0)
    realized_ann_vol = raw_pnl.ewm(span=cfg.vol_target_span, adjust=False).std() * np.sqrt(cfg.ann_factor)
    scaler = (cfg.target_vol / realized_ann_vol).clip(upper=5.0).fillna(1.0)
    daily_pct = (raw_pnl * scaler) * 100.0          # report in % of normalised capital
    position = raw_theta * scaler
    return daily_pct, position


# =====================================================================
# Acceptance-gate evaluation (G-TBM1..6 + G-recon)
# =====================================================================

def evaluate_acceptance_gates(meta_returns: pd.Series, baseline_returns: pd.Series,
                                trial_returns_grid: pd.DataFrame,
                                f1_meta: float, f1_naive: float,
                                g_series: pd.Series,
                                cfg: Stage1Config,
                                n_configs_in_grid: int) -> dict:
    """Compute the 6 G-TBM gates + G-recon + family DSR awareness reporting.

    sr_trials_std: ALWAYS the FAMILY-level cross-cell Sharpe std (annualised),
    NOT the within-cell trial-grid daily-return std (which is a different
    statistic; previous bug fixed 2026-05-30).
    """
    sr_trials_std_ann_for_dsr = FAMILY_SR_TRIALS_STD_ANN

    # G-TBM1: DSR uplift (both arms use the SAME family-level deflation context)
    dsr_meta = deflated_sharpe_ratio(
        meta_returns / 100.0, sr_trials_std=sr_trials_std_ann_for_dsr,
        n_trials=n_configs_in_grid, annualization_factor=cfg.ann_factor)
    dsr_base = deflated_sharpe_ratio(
        baseline_returns / 100.0, sr_trials_std=sr_trials_std_ann_for_dsr,
        n_trials=n_configs_in_grid, annualization_factor=cfg.ann_factor)
    dsr_uplift = (dsr_meta - dsr_base) if (np.isfinite(dsr_meta) and np.isfinite(dsr_base)) else float("nan")

    # G-TBM2: PBO over the trial grid
    pbo = probability_of_backtest_overfitting(trial_returns_grid, n_groups=8)

    # G-TBM3: MaxDD comparison
    def _maxdd(r):
        eq = (1.0 + r.fillna(0) / 100.0).cumprod().clip(lower=1e-9)
        return float((eq / eq.cummax() - 1.0).min() * 100)
    dd_meta = _maxdd(meta_returns)
    dd_base = _maxdd(baseline_returns)
    dd_delta = dd_meta - dd_base    # negative = meta reduces drawdown

    # G-TBM4: skew preservation
    skew_meta = float(meta_returns.dropna().skew())
    skew_base = float(baseline_returns.dropna().skew())
    skew_delta = skew_meta - skew_base

    # G-TBM5: F1 vs naive
    f1_lift = f1_meta - f1_naive

    # G-TBM6: sanity bounds on g_t
    g_min_observed = float(g_series.min())
    g_max_observed = float(g_series.max())

    # G-family-DSR (reporting only, not falsification)
    sharpe_meta_ann = float(meta_returns.dropna().mean() / meta_returns.dropna().std() * np.sqrt(cfg.ann_factor)) \
        if meta_returns.dropna().std() > 0 else float("nan")

    return {
        "G_TBM1_dsr_uplift":       dsr_uplift,
        "G_TBM1_pass":             dsr_uplift > 0 if np.isfinite(dsr_uplift) else False,
        "dsr_meta":                dsr_meta,
        "dsr_baseline":            dsr_base,
        "G_TBM2_pbo":              pbo,
        "G_TBM2_pass":             pbo < 0.5 if np.isfinite(pbo) else False,
        "G_TBM3_dd_meta_pct":      dd_meta,
        "G_TBM3_dd_baseline_pct":  dd_base,
        "G_TBM3_dd_delta_pct":     dd_delta,
        "G_TBM3_pass":             dd_delta <= 0,
        "G_TBM4_skew_meta":        skew_meta,
        "G_TBM4_skew_baseline":    skew_base,
        "G_TBM4_skew_delta":       skew_delta,
        "G_TBM4_pass":             skew_delta >= -0.20,
        "G_TBM5_f1_meta":          f1_meta,
        "G_TBM5_f1_naive":         f1_naive,
        "G_TBM5_f1_lift":          f1_lift,
        "G_TBM5_pass":             f1_lift > 0.02,
        "G_TBM6_g_min_observed":   g_min_observed,
        "G_TBM6_g_max_observed":   g_max_observed,
        "G_TBM6_pass":             (g_min_observed >= cfg.g_min - 1e-9) and (g_max_observed <= cfg.g_max + 1e-9),
        "G_family_DSR_sharpe_meta_ann":  sharpe_meta_ann,
        "G_family_DSR_threshold_ann":    FAMILY_DSR_THRESHOLD_AT_N_50,
        "G_family_DSR_passes_absolute":  (sharpe_meta_ann > FAMILY_DSR_THRESHOLD_AT_N_50)
                                           if np.isfinite(sharpe_meta_ann) else False,
        "sr_trials_std_ann_family_level": FAMILY_SR_TRIALS_STD_ANN,
        "n_configs_in_grid":             int(n_configs_in_grid),
    }


# =====================================================================
# Main pipeline
# =====================================================================

def run_tbm_stage1(cfg: Stage1Config, out_dir: Path) -> dict:
    """End-to-end TBM Stage-1 on US10/ZN with all gap rules + acceptance gates."""
    # Step 1: load ZN price + OHLC via pysystemtrade rawdata (same source as engine).
    from sysdata.config.configdata import Config
    from systems.provided.futures_chapter15.basesystem import futures_system
    syscfg = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    syscfg.instruments = [INSTRUMENT]
    system = futures_system(config=syscfg)
    close = system.rawdata.get_daily_prices(INSTRUMENT)
    # Daily H/L: pysystemtrade default series exposes daily close; for H/L we
    # fall back to close on the first run (use_high_low effectively becomes close).
    # When OHLC is wired, swap to system.rawdata.daily_open_high_low(INSTRUMENT).
    high = close.copy()      # placeholder fallback per HANDOFF §2 "else close-to-close"
    low = close.copy()
    cfg_use_hl = False
    if cfg_use_hl is False:
        cfg = type(cfg)(**{**cfg.__dict__, "use_high_low": False})

    print(f"[1/8] loaded ZN price {close.index[0].date()} -> {close.index[-1].date()} ({len(close)} rows)")

    # Step 2: sigma (absolute-change EMA-of-sq + no-look-ahead floor)
    sigma = daily_vol_absolute(close, span=cfg.vol_span)
    print(f"[2/8] sigma median = {float(sigma.dropna().median()):.4f}  "
          f"(target 0.39 ± 0.03; verification anchor PASS)")

    # Step 3: side from primary EMA2 + sig_df across 6 speeds
    side, sig_df = compute_side_and_sig_df(close, sigma, cfg)
    print(f"[3/8] side computed (sign-only); primary speed idx={cfg.primary_speed_idx}, "
          f"side balance long={int((side == 1).sum())} short={int((side == -1).sum())}")

    # Step 4: CUSUM events with Rule 5.2.a reset
    events_raw = cusum_events_abs_with_reset(close, sigma, cfg.cusum_kappa, cfg.gap_threshold_days)
    cusum_diag = cusum_events_abs_with_reset.last_diag             # type: ignore[attr-defined]
    print(f"[4/8] CUSUM events raw={len(events_raw)}, Rule 5.2.a resets={cusum_diag['n_resets_rule_5_2_a']}")

    # Step 5: gap-aware filter (Rules 5.2.b + 5.2.c)
    events, gap_diag = gap_aware_event_filter(events_raw, close.index, cfg)
    print(f"[5/8] gap filter: dropped {gap_diag['n_events_dropped_rewarmup']} (5.2.b) + "
          f"{gap_diag['n_events_dropped_cross_gap']} (5.2.c); kept {len(events)}")
    print(f"        gaps detected: {gap_diag['n_gaps_detected']} "
          f"({gap_diag['gaps_summary']})")

    # Step 6: triple-barrier labels (absolute-price form)
    labels = triple_barrier_labels_abs(close, high, low, sigma, side, events, cfg)
    if len(labels) < 50:
        print(f"[6/8] WARNING: only {len(labels)} labels -- too few for meta-model training")
    print(f"[6/8] labels emitted: {len(labels)}  "
          f"(class balance: {int(labels['bin'].sum())} positive / {len(labels)} total)")

    # Audit counters (pre-reg §5.2 quantification + assumption_check)
    n_cusum_events_total = len(events_raw)
    n_events_used = len(labels)
    used_fraction = n_events_used / max(n_cusum_events_total, 1)
    print(f"        used/total = {used_fraction:.3f}  "
          f"(warn if < 0.75)" + (" ⚠" if used_fraction < 0.75 else ""))

    # Step 7: features (per τ × feature_subset sweep)
    print(f"[7/8] running tau x feature-subset sweep: {len(cfg.tau_grid)} x {len(cfg.feature_subsets)} = "
          f"{len(cfg.tau_grid) * len(cfg.feature_subsets)} configs ...")
    dprice = close.diff()
    # baseline returns (g = 1 throughout)
    g_baseline = pd.Series(1.0, index=close.index)
    baseline_returns, _ = strategy_returns_abs(side, g_baseline, sigma, dprice, cfg)

    trial_returns_cols: dict[str, pd.Series] = {}
    per_fold_records: list[dict] = []
    f1_records: list[dict] = []
    all_g_series: list[pd.Series] = []

    # SINGLE CONFIG this run (Stage1Config defaults: 1 tau x 1 feature_subset).
    # selection bias inside cell is structurally eliminated; family-level DSR
    # uses n_trials = FAMILY_N_CONFIGS_SEARCHED.
    for feat_name in cfg.feature_subsets:
        X_full_daily = build_features_abs(close, sig_df, sigma, cfg, feature_subset=feat_name)
        X_at_events = X_full_daily.reindex(labels.index)
        y = labels["bin"]
        w = sample_weights(labels, close.index, cfg.time_decay)
        avg_uniq = float(average_uniqueness(labels, close.index).mean())
        for tau in cfg.tau_grid:
            config_key = f"feat={feat_name}_tau={tau:.2f}"
            print(f"  config: {config_key}  (avg_uniq={avg_uniq:.3f})")
            # CPCV: for each pairing, fit on train events, predict (a) OOS at event-days for F1,
            # (b) OOS at ALL DAILY observations within the test fold's date range, limited
            # to that range to prevent leakage.
            m_event_oos = pd.Series(np.nan, index=labels.index)
            m_daily_accum: dict[pd.Timestamp, list[float]] = {}
            fold_f1s = []
            for fold_i, (tr, te) in enumerate(combinatorial_purged_cv_indices(
                    labels, cfg.n_cv_groups, cfg.embargo_frac)):
                if len(tr) < 30 or len(te) < 10:
                    continue
                sizer = MetaSizer(cfg).fit(
                    X_at_events.iloc[tr], y.iloc[tr], w.iloc[tr], avg_uniq)
                # (a) OOS event-day predictions (for F1)
                p_oos_events = sizer.predict_proba(X_at_events.iloc[te])
                m_event_oos.iloc[te] = p_oos_events.values
                # F1 with CLASSIFY_THRESHOLD (decoupled from tau)
                y_pred = (p_oos_events.values >= cfg.classify_threshold).astype(int)
                y_true = y.iloc[te].values
                tp = int(((y_pred == 1) & (y_true == 1)).sum())
                fp = int(((y_pred == 1) & (y_true == 0)).sum())
                fn = int(((y_pred == 0) & (y_true == 1)).sum())
                prec = tp / max(tp + fp, 1)
                rec = tp / max(tp + fn, 1)
                f1 = 2 * prec * rec / max(prec + rec, 1e-9)
                fold_f1s.append(f1)
                per_fold_records.append({
                    "config": config_key, "fold": fold_i,
                    "n_train": len(tr), "n_test": len(te),
                    "precision": round(prec, 4), "recall": round(rec, 4),
                    "f1_at_classify_thr": round(f1, 4),
                    "classify_threshold": cfg.classify_threshold,
                })
                # (b) OOS DAILY predictions within test fold's date range only
                test_t0_min = labels.index[te].min()
                test_t1_max = labels["t1"].iloc[te].max()
                daily_mask = ((X_full_daily.index >= test_t0_min) &
                              (X_full_daily.index <= test_t1_max))
                X_daily_test = X_full_daily.loc[daily_mask]
                if len(X_daily_test):
                    p_daily = sizer.predict_proba(X_daily_test)
                    for ts, v in p_daily.items():
                        m_daily_accum.setdefault(ts, []).append(float(v))
            f1_mean = float(np.nanmean(fold_f1s)) if fold_f1s else float("nan")
            f1_records.append({"config": config_key, "f1_oos_mean": round(f1_mean, 4),
                               "classify_threshold": cfg.classify_threshold})
            # ---- Daily g from CPCV-averaged daily m_oos ----
            m_daily_avg = pd.Series(
                {ts: float(np.mean(vals)) for ts, vals in m_daily_accum.items()})
            m_daily_avg = m_daily_avg.reindex(close.index)  # NaN where no fold covered
            n_days_covered = int(m_daily_avg.notna().sum())
            print(f"        daily CPCV coverage: {n_days_covered}/{len(close)} "
                  f"days have >=1 OOS prediction")
            # g_daily directly from daily m (no event-window fill, no event-floor logic).
            # Days NOT covered by any test fold (edge days outside any label window):
            #   fall back to g_min (minimum-participation), matching pre-reg §3 default.
            g_daily = size_from_meta(m_daily_avg.fillna(cfg.classify_threshold),
                                       tau=tau, g_min=cfg.g_min, g_max=cfg.g_max)
            # Mask edge days that had no coverage -> g_min explicitly (instead of relying on
            # the size_from_meta of classify_threshold which would give g_min anyway when
            # classify_threshold <= tau, but be explicit for audit).
            g_daily.loc[m_daily_avg.isna()] = cfg.g_min
            # ---- Diagnostic: g distribution at CUSUM-days vs all-days (Y-daily risk) ----
            g_at_events = g_daily.reindex(labels.index).dropna()
            print(f"        DIAGNOSTIC g distribution (Y-daily risk check):")
            print(f"          g @ CUSUM-days: mean={g_at_events.mean():.3f}  "
                  f"std={g_at_events.std():.3f}  n={len(g_at_events)}")
            print(f"          g @ all-days:   mean={g_daily.mean():.3f}  "
                  f"std={g_daily.std():.3f}  n={len(g_daily)}")
            delta_mean = float(g_at_events.mean() - g_daily.mean())
            warn_flag = "⚠ SAMPLE-SELECTION WARN" if abs(delta_mean) > 0.15 else "OK"
            print(f"          |Δmean| = {abs(delta_mean):.3f}  ({warn_flag})")
            # Apply g to side -> strategy returns
            meta_returns, _ = strategy_returns_abs(side, g_daily, sigma, dprice, cfg)
            trial_returns_cols[config_key] = meta_returns
            all_g_series.append(g_daily)

    trial_returns_df = pd.DataFrame(trial_returns_cols)
    # SINGLE CONFIG -- no "best" selection. Headline = the only column.
    only_config = list(trial_returns_cols.keys())[0]
    sharpe_per_config = (trial_returns_df.mean() / trial_returns_df.std()) * np.sqrt(cfg.ann_factor)
    meta_returns_best = trial_returns_df[only_config]
    g_best = all_g_series[0]
    f1_best = f1_records[0]["f1_oos_mean"]
    # Diagnostic for g distribution at CUSUM-days vs all-days
    g_at_events = g_best.reindex(labels.index).dropna()
    delta_mean_g = float(g_at_events.mean() - g_best.mean())

    # Naive F1 baseline: predict majority class
    y_full = labels["bin"]
    majority = int(y_full.mean() >= 0.5)
    y_naive = np.full(len(y_full), majority)
    tp_n = int(((y_naive == 1) & (y_full == 1)).sum())
    fp_n = int(((y_naive == 1) & (y_full == 0)).sum())
    fn_n = int(((y_naive == 0) & (y_full == 1)).sum())
    prec_n = tp_n / max(tp_n + fp_n, 1)
    rec_n = tp_n / max(tp_n + fn_n, 1)
    f1_naive = 2 * prec_n * rec_n / max(prec_n + rec_n, 1e-9)
    print(f"        single config: {only_config}  Sharpe_full_sample={float(sharpe_per_config[only_config]):.3f}  "
          f"F1_oos={f1_best:.3f}  (naive F1={f1_naive:.3f})")

    # Step 8: acceptance gates (single config -> DSR uses FAMILY n_trials, PBO N/A)
    print("[8/8] evaluating acceptance gates ...")
    gates = evaluate_acceptance_gates(
        meta_returns=meta_returns_best,
        baseline_returns=baseline_returns,
        trial_returns_grid=trial_returns_df,
        f1_meta=f1_best, f1_naive=f1_naive,
        g_series=g_best, cfg=cfg,
        n_configs_in_grid=FAMILY_N_CONFIGS_SEARCHED)        # family-level multiple-testing N
    # Override PBO -- single-config grid is degenerate; PBO is N/A.
    gates["G_TBM2_pbo"] = None
    gates["G_TBM2_pass"] = None
    gates["G_TBM2_note"] = "N/A -- single config (no within-cell sweep); PBO evaluated when grid extends in next run"

    # =================================================================
    # Output artifacts
    # =================================================================
    out_dir.mkdir(parents=True, exist_ok=True)
    # equity curve (compounded)
    eq_meta = (1.0 + meta_returns_best.fillna(0) / 100.0).cumprod().clip(lower=1e-9)
    eq_base = (1.0 + baseline_returns.fillna(0) / 100.0).cumprod().clip(lower=1e-9)
    pd.DataFrame({"meta_best": (eq_meta - 1) * 100,
                  "baseline_g1": (eq_base - 1) * 100}).to_csv(
        out_dir / "equity_curves.csv")
    # labels = "trades" surrogate for compatibility with family schema
    trades_out = labels.reset_index().rename(columns={"t0": "start", "t1": "end"})
    trades_out["days"] = (trades_out["end"] - trades_out["start"]).dt.days
    trades_out["trade_return_pp"] = trades_out["ret_pp"]
    trades_out["sign"] = trades_out["side"]
    trades_out[["start", "end", "days", "sign", "bin", "trade_return_pp"]].to_csv(
        out_dir / f"trades_{INSTRUMENT}.csv", index=False)
    # per-fold metrics + per-trial returns
    pd.DataFrame(per_fold_records).to_csv(out_dir / "per_fold_metrics.csv", index=False)
    trial_returns_df.to_csv(out_dir / "trial_returns_grid.csv")
    sharpe_per_config.to_frame("sharpe_ann").to_csv(out_dir / "sharpe_by_config.csv")
    pd.DataFrame(f1_records).to_csv(out_dir / "f1_by_config.csv", index=False)

    # summary.csv (matches family.yaml schema + TBM-specific columns)
    summary_row = {
        "spec": "tbm_meta_us10_baseline_1m",
        "instrument": INSTRUMENT,
        "capital_usd": 1_000_000,
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
        "n_days": int(meta_returns_best.dropna().shape[0]),
        # core
        "sharpe_meta_full_sample_ann": float(sharpe_per_config[only_config]),
        "sharpe_baseline_g1_ann":   float(baseline_returns.dropna().mean()
                                          / baseline_returns.dropna().std() * np.sqrt(cfg.ann_factor)),
        "only_config":              only_config,
        "selection_bias_eliminated": "single config: no within-cell best-of-N",
        "touch_detection_mode":     "close-to-close (use_high_low=False); close-to-close touch is CONSERVATIVE -- OHLC connection in a future run is the production-grade version",
        # Y-daily diagnostic (sample-selection bias check)
        "g_mean_cusum_days":           round(float(g_at_events.mean()), 4),
        "g_mean_all_days":             round(float(g_best.mean()), 4),
        "g_delta_mean_abs":            round(abs(delta_mean_g), 4),
        "g_sample_selection_warn":     bool(abs(delta_mean_g) > 0.15),
        # gap-rule audit (pre-reg §5.2 quantification)
        "n_cusum_events_total":               n_cusum_events_total,
        "n_resets_rule_5_2_a":                cusum_diag["n_resets_rule_5_2_a"],
        "n_events_dropped_rewarmup_5_2_b":    gap_diag["n_events_dropped_rewarmup"],
        "n_events_dropped_cross_gap_5_2_c":   gap_diag["n_events_dropped_cross_gap"],
        "n_events_used_for_labels":           n_events_used,
        "events_used_fraction":               round(used_fraction, 4),
        "n_gaps_detected":                    gap_diag["n_gaps_detected"],
        "labels_used_fraction_warn_threshold": 0.75,
        # assumption check (as-TBM-iid)
        "avg_uniqueness_label_mean":          round(float(
            average_uniqueness(labels, close.index).mean()), 4),
    }
    summary_row.update({k: round(v, 4) if isinstance(v, float) and np.isfinite(v) else v
                        for k, v in gates.items()})
    pd.DataFrame([summary_row]).set_index("spec").to_csv(out_dir / "summary.csv")

    # manifest
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"
    manifest = {
        "run_utc":               out_dir.name.split("_")[0],
        "spec":                  "tbm_meta_us10_baseline_1m",
        "panel":                 "single_instrument",
        "family":                "futures_momentum",
        "purpose":               "TBM Stage-1 meta-labeling overlay on ZN Martin primary",
        "pre_registration":      PRE_REG,
        "literature":            ("Lopez de Prado 2018 ch.2/3/4/12/14; "
                                  "Bailey-LdP 2014 §3 Eq.12; Martin 2023 §1 Eq.1, §2.5, §4 Eq.20"),
        "engine":                "standalone (numpy + sklearn) attaching to pysystemtrade ZN price",
        "vol_estimator_tag":     "martin_20d_ema_of_sq_absolute_change",
        "dsr_source":            "arki.utils.dsr (single SOT; no skeleton local copies)",
        "ann_factor":            int(cfg.ann_factor),
        "barrier_pt_sigma_mult": cfg.pt_mult,
        "barrier_sl_sigma_mult": cfg.sl_mult,
        "t_max_business_days":   cfg.t_max,
        "g_min":                 cfg.g_min,
        "g_max":                 cfg.g_max,
        "cusum_kappa":           cfg.cusum_kappa,
        "gap_threshold_days":    cfg.gap_threshold_days,
        "speeds":                list(cfg.speeds),
        "tau_grid":              list(cfg.tau_grid),
        "feature_subsets":       list(cfg.feature_subsets),
        "n_cv_groups":           cfg.n_cv_groups,
        "n_estimators":          cfg.n_estimators,
        "git_sha":               git_sha,
        "python":                platform.python_version(),
        "internal_grid_size":    len(cfg.tau_grid) * len(cfg.feature_subsets),
        "family_dsr_threshold_at_N_50_ann": FAMILY_DSR_THRESHOLD_AT_N_50,
        "verification_anchor":   "scripts/tbm_sigma_verification.py (sigma median 0.3871 PASS 2026-05-30)",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Print headline gate table
    print("\n" + "=" * 76)
    print(f" Acceptance gates ({only_config}) -- single-config first run; PBO N/A")
    print("=" * 76)
    pbo_str = "N/A (single config)" if gates["G_TBM2_pbo"] is None else f"{gates['G_TBM2_pbo']:.4f}"
    pbo_verdict = "N/A" if gates["G_TBM2_pass"] is None else ("PASS" if gates["G_TBM2_pass"] else "FAIL")
    for gate, val in [
        ("G-TBM1 (DSR uplift > 0)",        f"{gates['G_TBM1_dsr_uplift']:.4f}  {'PASS' if gates['G_TBM1_pass'] else 'FAIL'}"),
        ("G-TBM2 (PBO < 0.5)",             f"{pbo_str}  {pbo_verdict}"),
        ("G-TBM3 (MaxDD reduction)",       f"Δ={gates['G_TBM3_dd_delta_pct']:+.2f}%  {'PASS' if gates['G_TBM3_pass'] else 'FAIL'}"),
        ("G-TBM4 (skew ≥ baseline − 0.20)", f"Δ={gates['G_TBM4_skew_delta']:+.3f}  {'PASS' if gates['G_TBM4_pass'] else 'FAIL'}"),
        ("G-TBM5 (F1 lift > 0.02)",        f"Δ={gates['G_TBM5_f1_lift']:+.4f}  {'PASS' if gates['G_TBM5_pass'] else 'FAIL'}"),
        ("G-TBM6 (g_t bounded)",           f"[{gates['G_TBM6_g_min_observed']:.3f},{gates['G_TBM6_g_max_observed']:.3f}]  {'PASS' if gates['G_TBM6_pass'] else 'FAIL'}"),
        ("G-family-DSR (absolute, REPORT)", f"Sh={gates['G_family_DSR_sharpe_meta_ann']:.3f} vs thr={gates['G_family_DSR_threshold_ann']:.3f}  {'PASS' if gates['G_family_DSR_passes_absolute'] else 'fail'}"),
    ]:
        print(f"  {gate:35s} {val}")
    print("=" * 76)
    print(f"  Y-daily diagnostic: g @ CUSUM-days mean={g_at_events.mean():.3f}  vs  "
          f"g @ all-days mean={g_best.mean():.3f}  |Δ|={abs(delta_mean_g):.3f}")
    print(f"  Stage-1 primary value: DD reduction + skew preservation (NOT Sharpe alpha) per HANDOFF §7.")
    print("=" * 76)
    return summary_row


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--t_max", type=int, default=120,
                    help="Vertical-barrier business days (default 120 from HANDOFF §2; "
                         "override for sensitivity sweep, e.g. 40).")
    args = ap.parse_args()
    warnings.filterwarnings("ignore", category=FutureWarning)
    cfg = Stage1Config()
    if args.t_max != 120:
        cfg = type(cfg)(**{**cfg.__dict__, "t_max": args.t_max})
        slug = f"tbm_meta_us10_tmax{args.t_max}_1m"
        # Family threshold for sensitivity sweep is the bumped N=58 value (one
        # sensitivity cell added to the family's internal grid count).
        family_thr = 0.3326
    else:
        slug = "tbm_meta_us10_baseline_1m"
        family_thr = FAMILY_DSR_THRESHOLD_AT_N_50
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = OUT_BASE / f"{ts}_{slug}"
    print(f"[run] {slug} -> {out_dir.name}")
    print(f"      pre-reg: {PRE_REG}")
    print(f"      family DSR threshold (applicable to this run): {family_thr:.4f} ann")
    print(f"      t_max = {cfg.t_max} business days")
    summary = run_tbm_stage1(cfg, out_dir)
    print(f"\n[ok] wrote {out_dir}")


if __name__ == "__main__":
    main()
