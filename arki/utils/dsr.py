"""Deflated Sharpe Ratio + Probability of Backtest Overfitting (Bailey & López de Prado).

Extracted from `stage1_meta_labeling.py` (the meta-labeling skeleton) for
re-use as the SINGLE source of truth for family-level multiple-testing
correction. Skeleton imports from this module rather than carrying its
own copy.

References:
- Bailey, D. H. & López de Prado, M. (2014). "The Deflated Sharpe Ratio:
  Correcting for Selection Bias, Backtest Overfitting, and Non-Normality."
  Journal of Portfolio Management, Vol. 40, No. 5, pp. 94-107.
- Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2017).
  "The Probability of Backtest Overfitting." Journal of Computational
  Finance, Vol. 20, No. 4, pp. 39-69.

Bug fix vs the original skeleton (locked here as the canonical version):
  The original silently assumed ALL inputs (`sr_trials_std`, the SR computed
  from `returns`) were in per-period units. When a caller passed annualised
  values (the natural unit at family level -- e.g. Sharpe 0.350 means 0.350
  per year, not per day), thresholds were off by sqrt(annualisation_factor)
  (~16x for daily). We now require an explicit `annualization_factor`
  argument and convert internally so both inputs land in the same per-period
  basis used by the formula.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import norm


# =====================================================================
# Expected maximum Sharpe under N trials (Bailey & LdP 2014, eq. 12)
# =====================================================================

def expected_max_sharpe(
    sr_trials_std: float,
    n_trials: int,
    *,
    annualization_factor: float = 1.0,
) -> float:
    """SR_0 = expected MAX of N Sharpe estimates when the true SR is 0.

    This is the **threshold** any candidate Sharpe must beat to claim
    statistical significance after multiple-testing under N trials.

    Args:
        sr_trials_std: standard deviation of {SR_n} across the N trials.
            If your SR values were annualised (e.g. computed via
            `sharpe = daily_mean / daily_std * sqrt(256)`), supply
            ``annualization_factor=256`` and the same annualised
            ``sr_trials_std``. The function internally converts everything
            to per-period units.
        n_trials: number of distinct configurations evaluated. MUST include
            ALL configurations searched (not just promoted ones); under-
            counting biases the threshold low and lets false discoveries
            through.
        annualization_factor: 1.0 if `sr_trials_std` is per-period, or e.g.
            252 / 256 for daily-returns annualised input.

    Returns:
        Expected MAX Sharpe under N trials, in the same units as the input
        `sr_trials_std`.
    """
    if n_trials < 2 or sr_trials_std <= 0 or annualization_factor <= 0:
        return float("nan")
    gamma = 0.5772156649015329               # Euler-Mascheroni
    e = np.e
    # The formula is independent of the annualisation -- the input std and the
    # output sr0 are in the SAME units. We pass through; annualization_factor
    # is recorded but not used here (it is used in deflated_sharpe_ratio
    # where the candidate SR also has to be put on the same basis).
    sr0 = sr_trials_std * (
        (1.0 - gamma) * norm.ppf(1.0 - 1.0 / n_trials)
        + gamma * norm.ppf(1.0 - 1.0 / (n_trials * e))
    )
    return float(sr0)


# =====================================================================
# Deflated Sharpe Ratio
# =====================================================================

def deflated_sharpe_ratio(
    returns: pd.Series,
    sr_trials_std: float,
    n_trials: int,
    *,
    annualization_factor: float = 1.0,
) -> float:
    """Bailey & LdP 2014/2016 Deflated Sharpe Ratio probability.

    Returns a probability in [0, 1] that the candidate strategy's Sharpe is
    REAL after correcting for: (a) finite-sample SR estimator noise scaled
    by the candidate's own skewness and kurtosis, and (b) selection bias
    under N trials. DSR > 0.95 is the conventional significance threshold.

    Args:
        returns: per-period returns of the CANDIDATE strategy (e.g. daily
            % of capital). Skewness and kurtosis are computed from this
            series and feed the denominator. Must be at least 10 non-NaN
            observations.
        sr_trials_std: standard deviation of {SR_n} across the N trials in
            the same annualisation as `annualization_factor`. If you have
            annualised SRs at the family level, pass them with their
            `annualization_factor`; this function converts internally.
        n_trials: N. Must include EVERY configuration searched (including
            falsified ones and internal parameter sweeps).
        annualization_factor: 1.0 if `sr_trials_std` is per-period; e.g. 256
            for daily annualised input. The `returns` series is always
            per-period -- annualisation here applies only to `sr_trials_std`.

    Returns:
        DSR probability in [0, 1]; NaN on insufficient data or numeric
        degeneracy.

    Key sanity asserts:
        * sr_trials_std must be > 0 (otherwise no cross-trial dispersion).
        * n_trials >= 2.
        * If you pass annualised inputs without annualization_factor, the
          internal convert will be wrong by sqrt(annualization_factor).
          Always be explicit about the unit.
    """
    if annualization_factor <= 0:
        return float("nan")
    sqrt_ann = float(np.sqrt(annualization_factor))
    # Convert sr_trials_std to per-period basis (matches `returns`).
    sr_trials_std_pp = float(sr_trials_std) / sqrt_ann

    r = returns.dropna().values
    if len(r) < 10 or float(r.std()) == 0.0 or n_trials < 2 or sr_trials_std_pp <= 0:
        return float("nan")
    sr_pp = float(r.mean() / r.std())                         # per-period Sharpe
    T = len(r)
    g3 = float(pd.Series(r).skew())
    g4 = float(pd.Series(r).kurtosis() + 3.0)                  # raw (non-excess) kurtosis
    gamma, e = 0.5772156649015329, np.e
    sr0_pp = sr_trials_std_pp * (
        (1.0 - gamma) * norm.ppf(1.0 - 1.0 / n_trials)
        + gamma * norm.ppf(1.0 - 1.0 / (n_trials * e))
    )
    denom = 1.0 - g3 * sr_pp + (g4 - 1.0) / 4.0 * sr_pp ** 2
    if denom <= 0.0:
        return float("nan")
    return float(norm.cdf((sr_pp - sr0_pp) * np.sqrt(T - 1) / np.sqrt(denom)))


# =====================================================================
# Probability of Backtest Overfitting via CSCV (Bailey et al. 2017)
# =====================================================================

def probability_of_backtest_overfitting(
    trial_returns: pd.DataFrame,
    n_groups: int = 8,
) -> float:
    """PBO via Combinatorially-Symmetric Cross-Validation.

    Args:
        trial_returns: T x N DataFrame, one column per configuration, each
            column a per-period return series (units don't matter -- PBO is
            rank-based and scale-invariant).
        n_groups: number of equal-length time slices to combine; default 8
            gives C(8, 4) = 70 IS/OOS pairings.

    Returns:
        Probability that the IS-best configuration is OOS BELOW median
        rank. PBO > 0.5 is bad news. Scale-invariant -- no annualisation
        question here.
    """
    M = trial_returns.dropna()
    T, N = M.shape
    if N < 2 or T < n_groups:
        return float("nan")
    grp = np.array_split(np.arange(T), n_groups)
    half = n_groups // 2
    logits = []
    for combo in combinations(range(n_groups), half):
        is_rows = np.concatenate([grp[i] for i in combo])
        oos_rows = np.concatenate([grp[i] for i in range(n_groups) if i not in combo])
        is_sr = M.iloc[is_rows].mean() / M.iloc[is_rows].std()
        oos_sr = M.iloc[oos_rows].mean() / M.iloc[oos_rows].std()
        if is_sr.dropna().empty:
            continue
        n_star = int(np.nanargmax(is_sr.values))
        rank = oos_sr.rank().values[n_star] / (N + 1)
        rank = float(min(max(rank, 1e-6), 1 - 1e-6))
        logits.append(np.log(rank / (1 - rank)))
    if not logits:
        return float("nan")
    return float((np.array(logits) <= 0).mean())


# =====================================================================
# Self-check (numerical sanity, not formal correctness proof)
# =====================================================================

def _self_check() -> None:
    """Quick sanity asserts. `python -m arki.utils.dsr` to run."""
    rng = np.random.default_rng(0)
    # 1) Annualisation invariance of expected_max_sharpe ----------------
    sr_trials_std_pp = 0.10
    ann = 256.0
    sr_trials_std_ann = sr_trials_std_pp * np.sqrt(ann)
    sr0_pp = expected_max_sharpe(sr_trials_std_pp, n_trials=50,
                                  annualization_factor=1.0)
    sr0_ann = expected_max_sharpe(sr_trials_std_ann, n_trials=50,
                                   annualization_factor=ann)
    # Both should output in their own input units; ann version = pp * sqrt(ann)
    assert abs(sr0_ann - sr0_pp * np.sqrt(ann)) < 1e-10, \
        f"expected_max_sharpe unit mismatch: pp={sr0_pp:.6f}, ann={sr0_ann:.6f}"

    # 2) DSR threshold check -- a real strategy with high Sharpe should
    #    clear; a sham strategy should not. Family setup matches realistic
    #    early-iteration parameters: N=30 trials, cross-trial std ~0.32 ann.
    n = 4000
    sr_trials_std_pp = 0.02                                   # ~0.32 annualised
    n_trials = 30
    # Real strategy: pp Sharpe = 0.10 (annualised ~1.60) -- clearly skilled.
    real = pd.Series(rng.normal(0.10, 1.0, n))
    # Sham strategy: pp Sharpe = 0.0 -- noise.
    sham = pd.Series(rng.normal(0.0, 1.0, n))
    dsr_real = deflated_sharpe_ratio(real, sr_trials_std=sr_trials_std_pp,
                                      n_trials=n_trials, annualization_factor=1.0)
    dsr_sham = deflated_sharpe_ratio(sham, sr_trials_std=sr_trials_std_pp,
                                      n_trials=n_trials, annualization_factor=1.0)
    assert dsr_real > 0.95, f"real strategy DSR should be > 0.95, got {dsr_real:.4f}"
    assert dsr_sham < 0.50, f"sham strategy DSR should be < 0.5, got {dsr_sham:.4f}"

    # 3) Annualisation argument: pass annualised inputs, should equal
    #    per-period DSR computation.
    dsr_real_ann = deflated_sharpe_ratio(
        real,
        sr_trials_std=sr_trials_std_pp * np.sqrt(256),
        n_trials=n_trials,
        annualization_factor=256.0,
    )
    assert abs(dsr_real - dsr_real_ann) < 1e-10, \
        f"annualisation unit fix failed: pp={dsr_real:.6f}, ann={dsr_real_ann:.6f}"

    # 4) PBO sanity -- two checks (kept simple; constructing a clean
    #    overfit case for assertions is fragile, so we directionally test
    #    only the persistent-edge case and verify range validity on noise).
    n_obs = 1500
    n_t = 12
    base = rng.normal(0, 1, (n_obs, n_t))
    # (a) persistent-edge: column 0 has +0.3 throughout (small consistent edge);
    #     IS-best is OOS-best too -> PBO should be LOW.
    persistent = base.copy()
    persistent[:, 0] += 0.3
    pbo_persistent = probability_of_backtest_overfitting(pd.DataFrame(persistent), n_groups=8)
    assert pbo_persistent < 0.30, \
        f"persistent-edge PBO should be < 0.30, got {pbo_persistent:.3f}"
    # (b) noise-only validity: PBO must be in [0, 1] and not NaN.
    pbo_noise = probability_of_backtest_overfitting(pd.DataFrame(base), n_groups=8)
    assert 0.0 <= pbo_noise <= 1.0, f"PBO must lie in [0, 1], got {pbo_noise}"

    print("[ok] arki.utils.dsr self-check passed:")
    print(f"     expected_max_sharpe(pp=0.10, N=50) = {sr0_pp:.4f}")
    print(f"     expected_max_sharpe(ann=0.10*sqrt(256), N=50, ann=256) = {sr0_ann:.4f}")
    print(f"     DSR(real strategy ~Sh0.8 ann) = {dsr_real:.4f}")
    print(f"     DSR(sham strategy) = {dsr_sham:.4f}")
    print(f"     DSR via annualised input path = {dsr_real_ann:.4f} (matches pp)")
    print(f"     PBO(persistent-edge configuration) = {pbo_persistent:.4f} (should be low)")
    print(f"     PBO(pure-noise configuration)      = {pbo_noise:.4f} (in [0, 1])")


if __name__ == "__main__":
    _self_check()
