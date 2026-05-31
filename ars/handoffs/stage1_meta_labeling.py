"""
Arki Monthly Commentary - Trading Engine
Stage-1: Size-only Meta-Labeling overlay on Martin (2023) momentum.

DESIGN (locked):
  - PRIMARY (side)   : Martin EMA2 momentum sign            -> FIXED, not learned.
  - SECONDARY (size) : meta-model P(primary is right | X_t) -> position size g(.).
  - Skew guardrail   : g(.) >= g_min >= 0  =>  effective momentum weight is never
                       negative, so Martin's positive-skew style constraint (eq.20)
                       is preserved BY CONSTRUCTION. Engine untouched; only the
                       throttle (participation/size) is learned.
  - Data             : DAILY OHLC ONLY. No intraday.

References: Lopez de Prado, "Advances in Financial Machine Learning" (2018):
  ch.2 (CUSUM), ch.3 (triple barrier / meta-labeling), ch.4 (sample weights,
  average uniqueness, sequential bootstrap), ch.7 (purged CV); Bailey & Lopez de
  Prado, "The Deflated Sharpe Ratio" (2016); Bailey et al., PBO/CSCV (2017).

Stage-2 hooks (NOT in scope here): speed-tilt lambda(s_t), activation
  aggressiveness, causal/DAG confounder adjustment, conformal OOD guardrail.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.ensemble import BaggingClassifier
from sklearn.tree import DecisionTreeClassifier


# ======================================================================
# CONFIG  (locked Stage-1 defaults)
# ======================================================================
@dataclass
class Stage1Config:
    # volatility estimate (Martin: 20-day EMA of squared daily returns)
    vol_span: int = 20
    # (1) CUSUM event sampling
    cusum_kappa: float = 1.0
    # (2) triple barrier
    pt_mult: float = 2.0          # profit-taking, in sigma units
    sl_mult: float = 2.0          # stop-loss, in sigma units
    t_max: int = 20               # vertical barrier (trading days)
    use_high_low: bool = True     # touch detection via daily H/L (daily data, not intraday)
    # Martin momentum speeds: EMA2 (fast, slow) effective periods N
    speeds: tuple = ((20, 40), (40, 80), (80, 160))
    primary_speed_idx: int = 0    # which speed defines the PRIMARY side (Martin uses 20,40)
    # (3) sample weights
    time_decay: float = 0.75      # weight of OLDEST obs (1.0 = no decay), newest = 1.0
    # (6) sizing  -- LOCKED: g_min = 0.30 (floor preserved)
    g_min: float = 0.30
    tau: float = 0.50             # participation threshold (to be CPCV-tuned)
    target_vol: float = 0.10      # annualized portfolio vol target (outer scaler)
    vol_target_span: int = 63     # slow window for outer vol-target
    # (5) meta-model
    n_estimators: int = 200
    max_depth: int = 3
    random_state: int = 0
    # (7) validation
    n_cv_groups: int = 6
    embargo_frac: float = 0.01
    ann_factor: float = 252.0


# ======================================================================
# MOMENTUM + VOLATILITY  (Martin engine, daily)  -- side is taken from here
# ======================================================================
def _ema(x: pd.Series, span: int) -> pd.Series:
    return x.ewm(span=span, adjust=False).mean()


def daily_vol(close: pd.Series, span: int) -> pd.Series:
    """Martin sigma_hat: sqrt of EMA of squared daily returns (floored for stability)."""
    ret = close.pct_change(fill_method=None)
    vol = np.sqrt((ret ** 2).ewm(span=span, adjust=False).mean())
    floor = vol.expanding(min_periods=span).median() * 0.2     # no look-ahead floor
    return vol.clip(lower=floor)


def ema2_signal(close: pd.Series, n_fast: int, n_slow: int, vol: pd.Series) -> pd.Series:
    """EMA2 oscillator (fast EMA - slow EMA of price), made dimensionless by close*vol."""
    raw = _ema(close, n_fast) - _ema(close, n_slow)
    scale = (close * vol).replace(0, np.nan)
    return (raw / scale).fillna(0.0)


def martin_signals(close: pd.Series, cfg: Stage1Config):
    """Return (side, signal_df_over_speeds, vol).  side in {-1,+1}, FIXED primary."""
    vol = daily_vol(close, cfg.vol_span)
    sig_df = pd.DataFrame(
        {i: ema2_signal(close, nf, ns, vol) for i, (nf, ns) in enumerate(cfg.speeds)}
    )
    primary = sig_df[cfg.primary_speed_idx]
    side = np.sign(primary).replace(0, np.nan).ffill().fillna(1.0)
    return side, sig_df, vol


# ======================================================================
# (1) EVENT SAMPLING - symmetric CUSUM filter  (AFML 2.5.2)
# ======================================================================
def cusum_events(close: pd.Series, vol: pd.Series, kappa: float) -> pd.DatetimeIndex:
    """Sample events when cumulative log-return drift breaches +/- kappa*sigma_t."""
    diff = np.log(close).diff().fillna(0.0).values
    h = (kappa * vol).bfill().fillna(0.0).values
    idx = close.index
    s_pos = s_neg = 0.0
    events = []
    for t in range(len(idx)):
        s_pos = max(0.0, s_pos + diff[t])
        s_neg = min(0.0, s_neg + diff[t])
        if s_neg < -h[t]:
            s_neg = 0.0
            events.append(idx[t])
        elif s_pos > h[t]:
            s_pos = 0.0
            events.append(idx[t])
    return pd.DatetimeIndex(events)


# ======================================================================
# (2) TRIPLE BARRIER + META-LABEL  (AFML 3.x)
# ======================================================================
def triple_barrier_labels(close, high, low, vol, side, events, cfg: Stage1Config) -> pd.DataFrame:
    """
    For each event, take Martin's side and hold until the FIRST of:
        PT (+pt_mult*sigma), SL (-sl_mult*sigma, side-adjusted), vertical (t_max days).
    Touch detection uses daily H/L excursions (daily data) when cfg.use_high_low.
    If PT and SL are touched on the SAME day, SL is assumed first (conservative).

    Returns DataFrame indexed by event t0 with columns:
        t1  : first-touch time
        ret : side-adjusted first-touch return
        bin : META-LABEL  -> 1 if primary made money (ret > 0) else 0
        side: primary side at entry
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
        pt, sl = cfg.pt_mult * sig, cfg.sl_mult * sig
        i_end = min(i0 + cfg.t_max, len(idx) - 1)
        p0 = close_v[i0]
        t1, ret = idx[i_end], s * (close_v[i_end] / p0 - 1.0)   # default = vertical
        for j in range(i0 + 1, i_end + 1):
            up = high_v[j] / p0 - 1.0
            dn = low_v[j] / p0 - 1.0
            fav = (s * up) if s > 0 else (s * dn)   # most favorable side-adjusted move
            adv = (s * dn) if s > 0 else (s * up)   # most adverse side-adjusted move
            hit_sl, hit_pt = (adv <= -sl), (fav >= pt)
            if hit_sl:                               # SL first (also covers same-day tie)
                t1, ret = idx[j], -sl
                break
            if hit_pt:
                t1, ret = idx[j], pt
                break
        rows.append((ts, t1, ret, int(ret > 0), s))

    return pd.DataFrame(rows, columns=["t0", "t1", "ret", "bin", "side"]).set_index("t0")


# ======================================================================
# (3) SAMPLE WEIGHTS - average uniqueness + time decay  (AFML 4.x)
# ======================================================================
def average_uniqueness(labels: pd.DataFrame, close_index: pd.Index) -> pd.Series:
    """Concurrency-based average uniqueness for overlapping labels."""
    conc = pd.Series(0.0, index=close_index)
    spans = []
    for t0, row in labels.iterrows():
        seg = close_index[(close_index >= t0) & (close_index <= row["t1"])]
        spans.append((t0, seg))
        conc.loc[seg] += 1.0
    u = {t0: (1.0 / conc.loc[seg]).mean() if len(seg) else 0.0 for t0, seg in spans}
    return pd.Series(u).reindex(labels.index).fillna(0.0)


def sample_weights(labels: pd.DataFrame, close_index: pd.Index, time_decay: float) -> pd.Series:
    """uniqueness * linear time-decay, normalized to mean 1.
    NOTE: sequential bootstrap (AFML 4.5) is an upgrade path; here we combine
    uniqueness sample_weight with max_samples=avg_uniqueness in the bagger."""
    u = average_uniqueness(labels, close_index)
    if len(u) == 0:
        return u
    decay = np.linspace(time_decay, 1.0, len(u))
    w = u.values * decay
    w = w / w.mean() if w.mean() > 0 else w
    return pd.Series(w, index=u.index)


# ======================================================================
# (4) FEATURES X_t - daily conditioning state ("trust the signal now?")
# ======================================================================
def kaufman_efficiency_ratio(close: pd.Series, window: int) -> pd.Series:
    direction = (close - close.shift(window)).abs()
    volatility = close.diff().abs().rolling(window).sum()
    return (direction / volatility).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_features(close, sig_df, vol, cfg: Stage1Config, asset_id: str | None = None) -> pd.DataFrame:
    ret = close.pct_change(fill_method=None)
    f = pd.DataFrame(index=close.index)
    signs = np.sign(sig_df)
    f["sign_agreement"] = signs.mean(axis=1).abs()          # 1.0 = all speeds agree (turning-pt proxy)
    f["signal_dispersion"] = sig_df.std(axis=1)
    f["primary_strength"] = sig_df[cfg.primary_speed_idx].abs()
    f["vol"] = vol
    f["vol_of_vol"] = vol.pct_change(fill_method=None).rolling(cfg.vol_span).std()
    f["efficiency_ratio"] = kaufman_efficiency_ratio(close, cfg.vol_span)
    f["autocorr_1"] = ret.rolling(cfg.vol_span).apply(
        lambda x: pd.Series(x).autocorr(lag=1) if pd.Series(x).notna().sum() > 2 else 0.0, raw=False
    )
    base_pnl = (np.sign(sig_df[cfg.primary_speed_idx]).shift(1) * ret).fillna(0.0)
    eq = (1 + base_pnl).cumprod()
    f["drawdown"] = eq / eq.cummax() - 1.0                  # baseline (always-on) drawdown state
    if asset_id is not None:
        f["asset_id"] = asset_id
    return f.replace([np.inf, -np.inf], np.nan).fillna(0.0)


# ======================================================================
# (5) META-MODEL - bagged trees, cross-sectional pooling -> m_t
# ======================================================================
class MetaSizer:
    """Bagged decision trees, sample-weighted by uniqueness, with max_samples set to
    the average uniqueness to mitigate overlap-induced overfitting (AFML 4.5).
    Trained POOLED across the asset cross-section (breadth as data augmentation)."""

    def __init__(self, cfg: Stage1Config):
        self.cfg = cfg
        self.model = None
        self.cols = None

    def fit(self, X: pd.DataFrame, y: pd.Series, w: pd.Series, avg_uniqueness: float):
        self.cols = [c for c in X.columns if c != "asset_id"]
        max_samples = float(np.clip(avg_uniqueness, 0.05, 1.0))
        base = DecisionTreeClassifier(
            max_depth=self.cfg.max_depth, class_weight="balanced",
            random_state=self.cfg.random_state,
        )
        kw = dict(n_estimators=self.cfg.n_estimators, max_samples=max_samples,
                  max_features=1.0, bootstrap=True, n_jobs=-1,
                  random_state=self.cfg.random_state)
        try:
            self.model = BaggingClassifier(estimator=base, **kw)          # sklearn >= 1.2
        except TypeError:
            self.model = BaggingClassifier(base_estimator=base, **kw)     # older sklearn
        self.model.fit(
            X[self.cols].values, y.values,
            sample_weight=w.reindex(y.index).fillna(0.0).values,
        )
        return self

    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        p = self.model.predict_proba(X[self.cols].values)[:, 1]
        return pd.Series(p, index=X.index)


# ======================================================================
# (6) SIZE MAP - skew-preserving (g >= g_min) + outer vol-target
# ======================================================================
def size_from_meta(m: pd.Series, cfg: Stage1Config) -> pd.Series:
    """g(m) = g_min + (1-g_min) * clip((m - tau)/(1 - tau), 0, 1)  in [g_min, 1]."""
    ramp = np.clip((m - cfg.tau) / (1.0 - cfg.tau), 0.0, 1.0)
    return cfg.g_min + (1.0 - cfg.g_min) * ramp


def position(side: pd.Series, g: pd.Series, vol: pd.Series, ret: pd.Series, cfg: Stage1Config) -> pd.Series:
    """theta = side * g / sigma, then scaled to target annualized vol (slow window)."""
    raw = (side * g / vol.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    strat_ret = (raw.shift(1) * ret).fillna(0.0)
    realized = strat_ret.ewm(span=cfg.vol_target_span, adjust=False).std() * np.sqrt(cfg.ann_factor)
    scaler = (cfg.target_vol / realized).clip(upper=5.0).fillna(1.0)
    return raw * scaler


# ======================================================================
# (7) VALIDATION RAIL - purged CV, Deflated Sharpe, PBO  (NON-NEGOTIABLE)
# ======================================================================
def purged_kfold_indices(labels: pd.DataFrame, n_splits: int, embargo_frac: float):
    """Yield (train_idx, test_idx) over event rows; purge train labels whose
    [t0,t1] overlaps the test span, plus an embargo. (AFML 7.x)"""
    t0 = labels.index
    t1 = labels["t1"]
    n = len(labels)
    embargo = int(n * embargo_frac)
    for f in np.array_split(np.arange(n), n_splits):
        test_t0, test_t1 = t0[f[0]], t1.iloc[f[-1]]
        keep = ~((t1.values >= test_t0) & (t0.values <= test_t1))   # purge overlaps
        train = np.where(keep)[0]
        train = train[(train < f[0] - embargo) | (train > f[-1] + embargo)]
        yield train, f


def deflated_sharpe_ratio(returns: pd.Series, sr_trials_std: float, n_trials: int) -> float:
    """DSR (Bailey & Lopez de Prado, 2016). Accounts for skew/kurtosis of returns
    and for the expected MAX Sharpe under n_trials selection.  returns: per-period."""
    r = returns.dropna().values
    if len(r) < 10 or r.std() == 0 or n_trials < 2 or sr_trials_std <= 0:
        return np.nan
    sr = r.mean() / r.std()                       # per-period Sharpe
    T = len(r)
    g3 = pd.Series(r).skew()
    g4 = pd.Series(r).kurt() + 3.0                # non-excess kurtosis
    gamma, e = 0.5772156649, np.e
    sr0 = sr_trials_std * (
        (1 - gamma) * norm.ppf(1 - 1.0 / n_trials)
        + gamma * norm.ppf(1 - 1.0 / (n_trials * e))
    )                                             # expected max Sharpe (benchmark)
    denom = 1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2
    if denom <= 0:
        return np.nan
    return float(norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(denom)))


def probability_of_backtest_overfitting(trial_returns: pd.DataFrame, n_groups: int = 8) -> float:
    """PBO via CSCV (Bailey et al., 2017). trial_returns: T x N (one col per config).
    Probability that the IS-best config is OOS BELOW median (logit <= 0)."""
    M = trial_returns.dropna()
    T, N = M.shape
    if N < 2 or T < n_groups:
        return np.nan
    grp = np.array_split(np.arange(T), n_groups)
    half = n_groups // 2
    logits = []
    for combo in combinations(range(n_groups), half):
        is_rows = np.concatenate([grp[i] for i in combo])
        oos_rows = np.concatenate([grp[i] for i in range(n_groups) if i not in combo])
        is_sr = M.iloc[is_rows].mean() / M.iloc[is_rows].std()
        oos_sr = M.iloc[oos_rows].mean() / M.iloc[oos_rows].std()
        n_star = int(np.nanargmax(is_sr.values))
        rank = oos_sr.rank().values[n_star] / (N + 1)
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(np.log(rank / (1 - rank)))
    return float((np.array(logits) <= 0).mean())


def perf_metrics(strat_ret: pd.Series, ann: float) -> dict:
    r = strat_ret.dropna()
    sr = (r.mean() / r.std() * np.sqrt(ann)) if r.std() > 0 else np.nan
    eq = (1 + r).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    return {"sharpe": round(float(sr), 3) if np.isfinite(sr) else np.nan,
            "max_dd": round(dd, 3),
            "calmar": round(float(r.mean() * ann / abs(dd)), 3) if dd < 0 else np.nan,
            "skew": round(float(r.skew()), 3)}


# ======================================================================
# PIPELINE - wire it together (side fixed -> label -> train -> size -> validate)
# ======================================================================
def run_stage1(panel: dict, cfg: Stage1Config) -> dict:
    """
    panel: {asset: DataFrame[open, high, low, close]} indexed by date (DAILY).
    Cross-sectional pooling: features/labels stacked across assets -> one meta-model.

    INTEGRATION SEAMS for the live Arki system:
      * replace `panel` with your real daily OHLC feed;
      * replace `martin_signals(...)` with the production Martin signal if it
        already exists upstream (only the SIDE = sign is consumed here).
    """
    XS, YS, WS, per_asset = [], [], [], {}
    for asset, df in panel.items():
        close, high, low = df["close"], df["high"], df["low"]
        side, sig_df, vol = martin_signals(close, cfg)
        events = cusum_events(close, vol, cfg.cusum_kappa)
        burn = cfg.speeds[-1][1] + cfg.vol_span          # skip signal/vol warmup
        if len(close) > burn:
            events = events[events >= close.index[burn]]
        labels = triple_barrier_labels(close, high, low, vol, side, events, cfg)
        if labels.empty:
            continue
        feats = build_features(close, sig_df, vol, cfg, asset_id=asset)
        XS.append(feats.loc[labels.index])
        YS.append(labels["bin"])
        WS.append(sample_weights(labels, close.index, cfg.time_decay))
        per_asset[asset] = dict(
            close=close, side=side, vol=vol, feats=feats,
            ret=close.pct_change(fill_method=None),
            avg_uniqueness=average_uniqueness(labels, close.index).mean(),
        )

    X, y, w = pd.concat(XS), pd.concat(YS), pd.concat(WS)
    au_pool = float(np.mean([d["avg_uniqueness"] for d in per_asset.values()]))

    # NOTE: skeleton fits on the full pooled sample for the wiring demo. Production
    # must score OOS only, via purged_kfold_indices / CPCV (rail provided above).
    sizer = MetaSizer(cfg).fit(X, y, w, au_pool)

    base_rets, meta_rets, trial_cols = [], [], {}
    for asset, d in per_asset.items():
        m = sizer.predict_proba(d["feats"])
        g = size_from_meta(m, cfg).reindex(d["close"].index).fillna(cfg.g_min)
        ones = pd.Series(1.0, index=d["close"].index)
        base_pos = position(d["side"], ones, d["vol"], d["ret"], cfg)         # baseline g=1
        meta_pos = position(d["side"], g, d["vol"], d["ret"], cfg)            # meta-sized
        warm = cfg.speeds[-1][1] + cfg.vol_span          # exclude warmup P&L from stats
        b = (base_pos.shift(1) * d["ret"]).fillna(0.0).iloc[warm:]
        mt = (meta_pos.shift(1) * d["ret"]).fillna(0.0).iloc[warm:]
        base_rets.append(b); meta_rets.append(mt); trial_cols[asset] = mt

    base_port = pd.concat(base_rets, axis=1).mean(axis=1)
    meta_port = pd.concat(meta_rets, axis=1).mean(axis=1)

    # DSR input: sr_trials_std should be the per-period SR dispersion across the
    # FULL config grid actually searched. Skeleton proxy = cross-asset SR dispersion.
    trial_srs = [c.mean() / c.std() for c in trial_cols.values() if c.std() > 0]
    sr_std = float(np.std(trial_srs)) if len(trial_srs) > 1 else (meta_port.std() or 1e-9)
    n_trials = len(cfg.speeds) * 3        # crude proxy for configs explored; replace with true count

    return {
        "model": sizer,
        "n_events": int(len(y)),
        "baseline_g=1": perf_metrics(base_port, cfg.ann_factor),
        f"meta_sized_gmin={cfg.g_min}": perf_metrics(meta_port, cfg.ann_factor),
        "DSR_meta(proxy)": round(deflated_sharpe_ratio(meta_port, sr_std, n_trials), 3),
        "PBO": round(probability_of_backtest_overfitting(pd.DataFrame(trial_cols), cfg.n_cv_groups), 3),
    }


# ======================================================================
# SMOKE TEST - synthetic daily OHLC, end-to-end run
# ======================================================================
def _synthetic_ohlc(n: int = 2500, seed: int = 0) -> pd.DataFrame:
    """Realistic daily series: regime-switching modest drift + ~16% annual vol,
    additive log-returns (no explosive compounding)."""
    rng = np.random.default_rng(seed)
    drift = 0.0
    rets = np.empty(n)
    for t in range(n):
        if rng.random() < 0.01:                              # ~quarterly regime flips
            drift = rng.choice([-1.0, 1.0]) * rng.uniform(2e-4, 8e-4)
        rets[t] = drift + 0.01 * rng.standard_normal()       # ~1% daily vol
    close = pd.Series(100.0 * np.exp(np.cumsum(rets)), index=pd.bdate_range("2010-01-01", periods=n))
    intr = 0.004 * np.abs(rng.standard_normal(n))
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]),
                         "high": close * (1 + intr),
                         "low": close * (1 - intr),
                         "close": close})


if __name__ == "__main__":
    cfg = Stage1Config()
    panel = {f"ASSET_{k}": _synthetic_ohlc(seed=k) for k in range(4)}
    res = run_stage1(panel, cfg)
    print("=== Stage-1 Size-only Meta-Labeling | synthetic smoke test ===")
    for k, v in res.items():
        if k != "model":
            print(f"{k:28s}: {v}")
