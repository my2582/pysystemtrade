"""Trade-analysis report builder for Martin baseline + dMOM overlay.

Produces 4 reports via the arki-trade-analysis `ata` package:
  - martin_us10 / martin_sp500: baseline 6-speed EWMAC trades (engine actual position).
  - dmom_us10 / dmom_sp500: effective position = baseline_pos * sign(w_dMOM); sign-flip
    days from the dMOM overlay become new trade boundaries (different ledger from baseline).

Output dirs: arki/results/2026-05-29/<slug>_trade_analysis/
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ata import ReportConfig, build_report
from ata.adapters.pysystemtrade import PysystemtradeAdapter, pst_nav_loader
from ata.adapters.pysystemtrade_prices import PysystemtradePriceStore

from sysdata.config.configdata import Config
from systems.provided.futures_chapter15.basesystem import futures_system

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TODAY = date.today().isoformat()
RESULTS_BASE = PROJECT_ROOT / f"arki/results/{TODAY}"

INSTRUMENTS = ["US10", "SP500"]
EWMAC_RULES = ["ewmac2_8", "ewmac4_16", "ewmac8_32",
               "ewmac16_64", "ewmac32_128", "ewmac64_256"]
EQUAL_W = round(1.0 / len(EWMAC_RULES), 6)
FORECAST_WEIGHTS = {r: EQUAL_W for r in EWMAC_RULES}
CAPITAL = 50_000
VOL_TARGET_PCT = 20.0

# dMOM hyperparams (from ars/evidence_packs/dmom_us10/preregistration.md)
BEAR_LOOKBACK_DAYS = 504
MKT_VAR_LOOKBACK_DAYS = 126
STRAT_VAR_LOOKBACK_DAYS = 126
REGRESSION_MIN_WARMUP = 504


def build_martin_system(instrument: str):
    config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    config.instruments = [instrument]
    config.instrument_weights = {instrument: 1.0}
    config.instrument_div_multiplier = 1.0
    config.forecast_weights = dict(FORECAST_WEIGHTS)
    config.notional_trading_capital = CAPITAL
    config.percentage_vol_target = VOL_TARGET_PCT
    return futures_system(config=config)


def vol_normalised_market_returns(prices: pd.Series) -> pd.Series:
    diffs = prices.diff()
    rolling_vol = diffs.rolling(25, min_periods=10).std()
    return diffs / rolling_vol


def bear_indicator(prices: pd.Series, lookback: int) -> pd.Series:
    return ((prices - prices.shift(lookback)) < 0).astype(float)


def expanding_ols_mu_hat(R: pd.Series, X1: pd.Series, min_warmup: int) -> pd.Series:
    y = R.values.astype(float); x = X1.values.astype(float); n = len(y)
    valid = ~(np.isnan(y) | np.isnan(x))
    yv = np.where(valid, y, 0.0); xv = np.where(valid, x, 0.0)
    one = valid.astype(float)
    s1 = np.cumsum(one); sx = np.cumsum(xv); sy = np.cumsum(yv)
    sxx = np.cumsum(xv * xv); sxy = np.cumsum(xv * yv)
    mu = np.full(n, np.nan)
    for t in range(min_warmup, n):
        n_eff = s1[t-1]
        if n_eff < min_warmup or np.isnan(x[t]):
            continue
        mx = sx[t-1]/n_eff; my = sy[t-1]/n_eff
        var_x = sxx[t-1]/n_eff - mx*mx
        if var_x <= 0: continue
        g1 = (sxy[t-1]/n_eff - mx*my) / var_x
        g0 = my - g1*mx
        mu[t] = g0 + g1*x[t]
    return pd.Series(mu, index=R.index)


def compute_dmom_effective_position(system, instrument: str) -> pd.Series:
    """effective_pos = baseline_actual_position * sign(w_dMOM,t)."""
    actual_pos = system.accounts.get_actual_position(instrument)
    if isinstance(actual_pos, pd.DataFrame):
        actual_pos = actual_pos.squeeze("columns")
    actual_pos = actual_pos.ffill().fillna(0).round().astype(int)

    acc = system.accounts.portfolio(roundpositions=True)
    daily = acc.percent.as_ts.fillna(0)
    prices = system.rawdata.get_daily_prices(instrument)
    bear = bear_indicator(prices, BEAR_LOOKBACK_DAYS).reindex(daily.index).fillna(0)
    U = vol_normalised_market_returns(prices).reindex(daily.index)
    sigma_sq_mkt = (U**2).rolling(MKT_VAR_LOOKBACK_DAYS, min_periods=30).mean()
    x_interaction = (bear * sigma_sq_mkt).shift(1)
    mu_hat = expanding_ols_mu_hat(daily, x_interaction, REGRESSION_MIN_WARMUP)
    sigma_sq_strat = (daily**2).rolling(STRAT_VAR_LOOKBACK_DAYS, min_periods=30).mean()
    sigma_sq_strat = sigma_sq_strat.where(sigma_sq_strat > 1e-12)
    raw_w = mu_hat / sigma_sq_strat

    sign_w = pd.Series(np.sign(raw_w.fillna(0)).astype(int), index=raw_w.index).reindex(actual_pos.index).fillna(1)
    eff = (actual_pos * sign_w).astype(int)
    return eff


SPEC_BASELINE = """<div class="spec-box">
<h3>Strategy spec — Martin baseline (single-instrument 6-speed EWMAC)</h3>
<div class="row">EWMAC speeds: {rules}. Forecast weights: equal (1/6 each). Carry rule OFF.</div>
<div class="row">Capital $50,000. Vol target 20%. Forecast cap +-20 (soft). Integer contracts.</div>
<div class="row">Trade unit = position roundtrip (0 -> non-0 -> 0). Position source = engine actual buffered.</div>
<div class="row">Evidence pack: ars/evidence_packs/martin_single_instrument/ (5/5 gates PASS, Path Z grandfather).</div>
</div>"""

SPEC_DMOM = """<div class="spec-box">
<h3>Strategy spec — Martin baseline + dMOM overlay (effective position)</h3>
<div class="row">Baseline = Martin 6-speed EWMAC. Overlay = Daniel-Moskowitz 2016 / Hanauer 2022 dynamic scaler.</div>
<div class="row">Effective position = baseline_position x sign(w_dMOM,t). Sign-flip days are new trade boundaries.</div>
<div class="row">w = (1/2lambda) * mu_hat / sigma_sq_strategy; mu_hat from expanding OLS on R_MOM = g0 + g_int * I_Bear * sigma_sq_mkt.</div>
<div class="row">Evidence pack: ars/evidence_packs/dmom_us10/ (FALSIFIED per pre-registered gates).</div>
</div>"""


def build_one(system, instrument: str, slug: str, spec_html: str,
              effective_position: pd.Series | None = None) -> Path:
    out_dir = RESULTS_BASE / f"{slug}_trade_analysis"
    adapter = PysystemtradeAdapter(
        system=system, position_source="buffered",
        instruments=[instrument])
    if effective_position is not None:
        # inject custom (effective) position; override the cache before run
        adapter._positions[instrument] = effective_position
    cfg = ReportConfig(
        title=f"pysystemtrade {slug}",
        slug=slug,
        out_dir=out_dir,
        trade_provider=adapter,
        ohlc_store=PysystemtradePriceStore(system=system),
        nav_loader=pst_nav_loader(system),
        nav_col="",
        benchmark_col=None,
        benchmark_label="Buy-and-hold (n/a)",
        baseline_commit="local",
        baseline_tag=f"{slug}-{TODAY}",
        analysis_start=pd.Timestamp("1985-01-01"),
        eras=[
            ("Post-2000", pd.Timestamp("2000-01-01"), pd.Timestamp("2099-12-31")),
            ("Post-2015", pd.Timestamp("2015-01-01"), pd.Timestamp("2099-12-31")),
        ],
        n_holdings=1,
        report_date=TODAY,
        boot_block=10,
        boot_b=500,
        ars_seed=20260529,
        spec_box_html=spec_html,
    )
    build_report(cfg)
    return out_dir


def main() -> None:
    runs = []
    for instr in INSTRUMENTS:
        print(f"\n[build system] {instr}")
        system = build_martin_system(instr)

        # baseline
        slug_base = f"martin_{instr.lower()}"
        spec_base = SPEC_BASELINE.format(rules=", ".join(EWMAC_RULES))
        print(f"[trade-analysis] {slug_base}")
        out = build_one(system, instr, slug_base, spec_base)
        runs.append((slug_base, out))

        # dMOM (effective position)
        slug_dmom = f"dmom_{instr.lower()}"
        print(f"[trade-analysis] {slug_dmom} (effective position = baseline * sign(w))")
        eff_pos = compute_dmom_effective_position(system, instr)
        out = build_one(system, instr, slug_dmom, SPEC_DMOM, effective_position=eff_pos)
        runs.append((slug_dmom, out))

    print("\n=== built ===")
    for slug, out in runs:
        print(f"  {slug}: {out}")


if __name__ == "__main__":
    main()
