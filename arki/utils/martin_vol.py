"""Martin (2023) vol estimator: 20-day EMA of squared price changes.

Reference: Richard J. Martin, "Design and analysis of momentum trading
strategies" (Imperial, 2023), §2.5 p.11:

    "For risk-adjusting the returns we use a 20-day EMA of squared price
     changes to estimate the volatility (sigma_hat_n in the definition of
     U_n)."

Recursive form (Martin's intended implementation):

    sigma_hat_n^2 = gamma * sigma_hat_{n-1}^2 + (1 - gamma) * (X_n - X_{n-1})^2
    gamma         = 1 - 1/N
    sigma_hat_n   = sqrt(sigma_hat_n^2)

For N = 20 -> gamma = 0.95, alpha = 1 - gamma = 0.05.

Difference vs pysystemtrade's `sysquant.estimators.vol.simple_ewvol_calc`:
  - pysystemtrade uses `daily_returns.ewm(span=days).std()` -> smoothing
    constant `alpha_pandas = 2/(span+1)`; for span=20 this is 2/21 ~ 0.0952
    (Martin's alpha for N=20 is 0.05). To match Martin via pandas span you
    would need span ~= 39, NOT 20.
  - pysystemtrade's `.std()` is centred (subtracts the EMA mean); Martin's
    formula is uncentred raw second moment. Under Martin's E[U_n]=0
    assumption the difference is small, but for paper-fidelity we use the
    uncentred form exactly.
  - Carver's `robust_vol_calc` adds `vol_floor` and `vol_abs_min` overlays.
    Martin's paper has neither. We omit both.

Signature is compatible with pysystemtrade `volatility_calculation.func`:
the function takes `daily_returns: pd.Series` (= `prices.diff()`) and
returns a `pd.Series` of sigma_hat aligned to the same index.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def martin_ema_vol(
    daily_returns: pd.Series,
    N: int = 20,
    min_periods: int = 10,
    **ignored_kwargs,
) -> pd.Series:
    """Martin's 20-day EMA-of-squared-price-changes vol estimator.

    Args:
        daily_returns: absolute price-change series ``X_n - X_{n-1}``.
            For futures and rates this is the natural definition (Martin
            picks this over the relative form in section 1 of the paper,
            partly to accommodate possibly-negative prices).
        N: effective lookback in days. Sets ``gamma = 1 - 1/N``. Martin
            uses N=20 throughout the empirical section.
        min_periods: minimum non-NaN squared returns before emitting a
            sigma_hat estimate. Default 10 (matches pysystemtrade's
            ``simple_ewvol_calc`` warm-up).

    Returns:
        pd.Series of sigma_hat_n on the same index, with the first
        ``min_periods - 1`` values NaN. Recursive form is exact; no vol
        floor, no absolute minimum, no centering.

    Notes:
        Uses ``pandas.ewm(alpha=1-gamma, adjust=False)`` which is the
        non-adjusted recursive EMA, i.e. ``ema_n = (1-alpha)*ema_{n-1} +
        alpha*x_n`` -- the exact form in Martin's text. ``adjust=True``
        (pandas default) would normalise by a finite-horizon weight sum
        and is NOT what Martin uses.
    """
    if N <= 0:
        raise ValueError(f"N must be positive, got {N}")
    gamma = 1.0 - 1.0 / N
    alpha = 1.0 - gamma  # = 1/N
    # Squared price changes; NaN inputs propagate as NaN squares.
    sq = daily_returns.astype(float) ** 2
    # Recursive EMA of squared changes (uncentred second moment).
    sq_ema = sq.ewm(alpha=alpha, adjust=False, min_periods=min_periods).mean()
    sigma = sq_ema.pow(0.5)
    return sigma


def martin_daily_vol_given_price(
    price: pd.Series,
    N: int = 20,
    min_periods: int = 10,
    **ignored_kwargs,
) -> pd.Series:
    """Convenience: price series -> sigma_hat via Martin's recipe.

    Mirrors pysystemtrade's ``robust_daily_vol_given_price``: takes the
    raw price series, computes ``price.diff()``, and feeds it through
    :func:`martin_ema_vol`. Used by the standalone Martin primary script
    where we do not have a pysystemtrade ``rawdata`` stage.
    """
    daily_returns = price.diff()
    return martin_ema_vol(daily_returns, N=N, min_periods=min_periods)


# ---- self-check ------------------------------------------------------

def _self_check() -> None:
    """Run a few sanity asserts. Invoked via ``python -m arki.utils.martin_vol``."""
    rng = np.random.default_rng(0)
    n = 4000
    # Synthetic price = cumulative IID Normal increments, scale 1.0.
    increments = rng.standard_normal(n) * 1.0
    price = pd.Series(increments.cumsum(), name="price")
    sigma = martin_daily_vol_given_price(price, N=20)
    # Tail should converge near the population stdev of the increments (=1).
    tail = sigma.dropna().iloc[-500:]
    assert 0.85 < tail.mean() < 1.15, f"vol convergence off: mean={tail.mean():.4f}"
    # gamma=0.95 check (alpha=0.05) via direct recursion vs pandas form.
    # IMPORTANT: pandas ewm(adjust=False) seeds out[first_valid] = x[first_valid].
    # Match that initialisation so the recursive forms are bit-equal, not just
    # asymptotically close (otherwise the (1-alpha)^n transient from a zero seed
    # would dominate the test).
    sq = (price.diff() ** 2).values            # NaN at index 0
    first_valid = int(np.argmax(~np.isnan(sq)))  # = 1 here
    gamma = 0.95
    alpha = 1.0 - gamma
    sq_manual = np.full(n, np.nan)
    sq_manual[first_valid] = sq[first_valid]    # pandas seed
    for i in range(first_valid + 1, n):
        sq_manual[i] = gamma * sq_manual[i - 1] + alpha * sq[i]
    sigma_manual = pd.Series(np.sqrt(sq_manual), index=price.index)
    sigma_pd = martin_ema_vol(price.diff(), N=20, min_periods=1)
    diff_idx = sigma_pd.index[first_valid:]
    max_abs_err = float(np.nanmax(np.abs(sigma_pd.loc[diff_idx].values
                                         - sigma_manual.loc[diff_idx].values)))
    assert max_abs_err < 1e-12, f"recursive form mismatch: {max_abs_err:.3e}"
    print(f"[ok] martin_ema_vol self-check: "
          f"tail_mean={tail.mean():.4f} (target ~1.00), "
          f"recursive_max_abs_err={max_abs_err:.2e}, "
          f"gamma={gamma:.3f}, alpha={alpha:.3f}, N=20")


if __name__ == "__main__":
    _self_check()
