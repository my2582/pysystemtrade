#!/usr/bin/env python
"""dMOM overlay backtest -- US10 + SP500.

Implements the Daniel-Moskowitz (2016) / Hanauer-Windmuller (2022)
dynamic-scaled momentum overlay on top of the Martin single-instrument
EWMAC baseline. Pre-registered at
ars/evidence_packs/dmom_us10/dmom_us10_preregistration.md.

Overlay (per pre-reg eq. and Hanauer eq. 6-7), adapted for single-
instrument (no cross-section):

    w_dMOM,t = (1 / (2 lambda)) * mu_hat_t / sigma_sq_strategy_t

    mu_hat from expanding-window OLS:
        R_MOM,t = gamma0 + gamma_int * I_Bear,{t-1} * sigma_sq_mkt,{t-1} + eps

    I_Bear,{t-1} = 1 if 24-mo cumulative back-adjusted price change < 0
    sigma_sq_mkt,{t-1} = 126d realized variance of vol-normalised
        market returns (Martin U_t = dX_t / sigma_hat_t)
    sigma_sq_strategy,t = 126d realized variance of baseline daily
        strategy % returns
    lambda chosen so std(R_dMOM) == std(R_MOM) full-sample (closed form)

R_dMOM,t = R_MOM,t * w_dMOM,t. Engine NOT reimplemented: baseline
positions/returns come from the native pysystemtrade Martin runner;
the overlay is a returns-stream multiplicative scaler.
"""
from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sysdata.config.configdata import Config
from systems.provided.futures_chapter15.basesystem import futures_system

INSTRUMENTS = ["US10", "SP500"]
EWMAC_RULES = ["ewmac2_8", "ewmac4_16", "ewmac8_32",
               "ewmac16_64", "ewmac32_128", "ewmac64_256"]
EQUAL_W = round(1.0 / len(EWMAC_RULES), 6)
FORECAST_WEIGHTS = {r: EQUAL_W for r in EWMAC_RULES}
CAPITAL = 50_000
VOL_TARGET_PCT = 20.0
BEAR_LOOKBACK_DAYS = 504           # 24 months
MKT_VAR_LOOKBACK_DAYS = 126        # 6 months
STRAT_VAR_LOOKBACK_DAYS = 126
REGRESSION_MIN_WARMUP = 504
ROOT = Path(__file__).resolve().parent.parent
OUT_BASE = ROOT / "ars" / "runs"


def build_system(instrument: str):
    config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    config.instruments = [instrument]
    config.instrument_weights = {instrument: 1.0}
    config.instrument_div_multiplier = 1.0
    config.forecast_weights = dict(FORECAST_WEIGHTS)
    config.notional_trading_capital = CAPITAL
    config.percentage_vol_target = VOL_TARGET_PCT
    return futures_system(config=config)


def vol_normalised_market_returns(prices: pd.Series) -> pd.Series:
    """Martin U_t = dX_t / sigma_hat_t (rolling 25d std of price diffs)."""
    diffs = prices.diff()
    rolling_vol = diffs.rolling(25, min_periods=10).std()
    return (diffs / rolling_vol)


def bear_indicator(prices: pd.Series, lookback: int) -> pd.Series:
    """1 if cumulative price change over `lookback` days is < 0, else 0."""
    cum_change = prices - prices.shift(lookback)
    return (cum_change < 0).astype(float)


def expanding_ols_mu_hat(R: pd.Series, X1: pd.Series, min_warmup: int) -> pd.Series:
    """
    Expanding-window OLS for R_t = gamma0 + gamma1 * X1_t + eps, then
    return mu_hat_t = fitted value at t using betas estimated on [0, t).
    Strict OOS (no look-ahead at t).
    """
    # Recursive sums for OLS closed form on a single predictor + intercept.
    # We need at time t: betas from [0, t), then predict at t using X1_t.
    y = R.values.astype(float)
    x = X1.values.astype(float)
    n = len(y)
    valid = ~(np.isnan(y) | np.isnan(x))
    # cumulative sums (treat NaN as missing -> 0 contribution; track n_eff)
    yv = np.where(valid, y, 0.0)
    xv = np.where(valid, x, 0.0)
    one = valid.astype(float)
    s1 = np.cumsum(one)
    sx = np.cumsum(xv)
    sy = np.cumsum(yv)
    sxx = np.cumsum(xv * xv)
    sxy = np.cumsum(xv * yv)
    mu_hat = np.full(n, np.nan)
    for t in range(min_warmup, n):
        n_eff = s1[t - 1]
        if n_eff < min_warmup:
            continue
        mx = sx[t - 1] / n_eff
        my = sy[t - 1] / n_eff
        var_x = sxx[t - 1] / n_eff - mx * mx
        cov_xy = sxy[t - 1] / n_eff - mx * my
        if var_x <= 0:
            continue
        gamma1 = cov_xy / var_x
        gamma0 = my - gamma1 * mx
        # fitted at t using current X1[t]
        if np.isnan(x[t]):
            continue
        mu_hat[t] = gamma0 + gamma1 * x[t]
    return pd.Series(mu_hat, index=R.index)


def apply_dmom_overlay(baseline_daily_pct: pd.Series,
                       prices: pd.Series) -> dict:
    """Compute the dMOM weight series and the overlaid returns."""
    daily = baseline_daily_pct.fillna(0)

    bear = bear_indicator(prices, BEAR_LOOKBACK_DAYS).reindex(daily.index).fillna(0)
    U = vol_normalised_market_returns(prices).reindex(daily.index)
    sigma_sq_mkt = (U ** 2).rolling(MKT_VAR_LOOKBACK_DAYS, min_periods=30).mean()
    # interaction predictor (lag-1 per pre-reg)
    x_interaction = (bear * sigma_sq_mkt).shift(1)

    mu_hat = expanding_ols_mu_hat(daily, x_interaction, REGRESSION_MIN_WARMUP)
    sigma_sq_strat = (daily ** 2).rolling(STRAT_VAR_LOOKBACK_DAYS, min_periods=30).mean()
    sigma_sq_strat = sigma_sq_strat.where(sigma_sq_strat > 1e-12)

    raw_w = mu_hat / sigma_sq_strat
    # closed-form lambda to match full-sample std
    valid = (~raw_w.isna()) & (daily != 0)
    R_times_w = (daily[valid] * raw_w[valid]).dropna()
    var_R = float((daily[valid] ** 2).mean() - daily[valid].mean() ** 2)
    var_Rw = float((R_times_w ** 2).mean() - R_times_w.mean() ** 2)
    if var_R <= 0 or var_Rw <= 0:
        lam = 1.0
    else:
        lam = float(np.sqrt(var_Rw / (4.0 * var_R)))

    w = raw_w / (2.0 * lam)
    R_dmom = (daily * w).fillna(0)

    return {
        "w": w, "mu_hat": mu_hat, "raw_w": raw_w, "lam": lam,
        "bear": bear, "sigma_sq_mkt": sigma_sq_mkt,
        "sigma_sq_strat": sigma_sq_strat,
        "R_dmom": R_dmom, "R_baseline": daily,
    }


def sign_episode_trades(daily_returns: pd.Series,
                        sign_series: pd.Series) -> pd.DataFrame:
    """Trade ledger by sign-episode of `sign_series` (e.g. effective position sign).
    Lagged-position attribution (yesterday's sign earns today's return)."""
    s_eod = sign_series.shift(0).fillna(0)            # end-of-day sign
    s_held = s_eod.shift(1).fillna(0)                  # sign held entering day t
    new_ep = (s_held != s_held.shift(1)).fillna(True).astype(int)
    ep_id = new_ep.cumsum()
    df = pd.DataFrame({"date": daily_returns.index,
                       "sign": s_held.values,
                       "ep": ep_id.values,
                       "ret": daily_returns.values})
    trades = (df[df["sign"] != 0]
              .groupby("ep")
              .agg(start=("date", "first"),
                   end=("date", "last"),
                   days=("date", "size"),
                   sign=("sign", "first"),
                   trade_return_pct=("ret", "sum"))
              .reset_index(drop=True))
    return trades


def geometric_equity_and_dd(daily_pct_points: pd.Series):
    daily_frac = daily_pct_points.fillna(0) / 100.0
    eq = (1.0 + daily_frac).cumprod().clip(lower=1e-6)
    dd = (eq / eq.cummax() - 1.0) * 100
    return eq, dd


def stats_block(label: str, R: pd.Series, sign_for_trades: pd.Series) -> dict:
    R = R.fillna(0)
    geom_eq, geom_dd = geometric_equity_and_dd(R)
    ann_mean = float(R.sum()) / (len(R) / 252)
    ann_vol = float(R.std()) * np.sqrt(252)
    sharpe = ann_mean / ann_vol if ann_vol > 0 else float("nan")
    trades = sign_episode_trades(R, sign_for_trades)
    skew_trade = float(trades["trade_return_pct"].skew()) if len(trades) else float("nan")
    win = 100.0 * float((trades["trade_return_pct"] > 0).mean()) if len(trades) else float("nan")
    return {
        "label": label,
        "ann_return_pct": round(ann_mean, 3),
        "ann_vol_pct": round(ann_vol, 3),
        "sharpe_gross": round(sharpe, 3),
        "skew_daily": round(float(R.skew()), 3),
        "skew_per_trade": round(skew_trade, 3),
        "max_drawdown_pct_geom": round(float(geom_dd.min()), 3),
        "n_trades": int(len(trades)),
        "win_rate_pct": round(win, 1) if len(trades) else 0.0,
    }


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_BASE / f"{ts}_dmom_us10"
    out.mkdir(parents=True, exist_ok=True)

    per_instrument = {}
    for instr in INSTRUMENTS:
        print(f"[build] {instr}")
        system = build_system(instr)
        acc = system.accounts.portfolio(roundpositions=True)
        baseline_daily = acc.percent.as_ts
        prices = system.rawdata.get_daily_prices(instr)

        # baseline sign series (engine's actual rounded position)
        pos = system.accounts.get_buffered_position(instr, roundpositions=True)
        if isinstance(pos, pd.DataFrame):
            pos = pos.squeeze("columns")
        pos = pos.reindex(baseline_daily.index).ffill().fillna(0)
        baseline_sign = np.sign(pos).astype(int)

        dmom = apply_dmom_overlay(baseline_daily, prices)
        eff_sign = (baseline_sign * np.sign(dmom["w"].fillna(0))).astype(int)

        s_base = stats_block(f"{instr}_baseline", dmom["R_baseline"], baseline_sign)
        s_dmom = stats_block(f"{instr}_dmom", dmom["R_dmom"], eff_sign)

        # reconciliation: dMOM returns should equal baseline * w; check magnitude consistency
        recon_diff = float((dmom["R_dmom"] - dmom["R_baseline"] * dmom["w"].fillna(0)).abs().sum())

        per_instrument[instr] = {
            "baseline": s_base, "dmom": s_dmom,
            "lambda": round(dmom["lam"], 4),
            "n_w_negative": int((dmom["w"] < 0).sum()),
            "n_w_positive": int((dmom["w"] > 0).sum()),
            "w_mean": round(float(dmom["w"].mean()), 3),
            "w_std": round(float(dmom["w"].std()), 3),
            "recon_diff_abs_sum": round(recon_diff, 6),
            "series": {
                "baseline_daily": dmom["R_baseline"],
                "dmom_daily": dmom["R_dmom"],
                "w": dmom["w"],
            },
        }
        print(f"[done]  {instr} baseline Sharpe={s_base['sharpe_gross']} "
              f"skew_trade={s_base['skew_per_trade']} | "
              f"dMOM Sharpe={s_dmom['sharpe_gross']} skew_trade={s_dmom['skew_per_trade']} "
              f"lambda={dmom['lam']:.3f} w_neg={int((dmom['w']<0).sum())}")

    # save CSVs
    summary_rows = []
    for instr, d in per_instrument.items():
        summary_rows.append({"instrument": instr, "variant": "baseline", **d["baseline"]})
        summary_rows.append({"instrument": instr, "variant": "dmom", **d["dmom"]})
    summary = pd.DataFrame(summary_rows).set_index(["instrument", "variant"])
    summary.to_csv(out / "summary.csv")

    for instr, d in per_instrument.items():
        pd.DataFrame({
            "baseline_daily_pct": d["series"]["baseline_daily"],
            "dmom_daily_pct": d["series"]["dmom_daily"],
            "w_dmom": d["series"]["w"],
        }).to_csv(out / f"series_{instr}.csv")

    # verdicts per pre-registration §4
    us10 = per_instrument["US10"]
    sp500 = per_instrument["SP500"]
    sharpe_lift_us10 = us10["dmom"]["sharpe_gross"] - us10["baseline"]["sharpe_gross"]
    mdd_lift_us10 = us10["dmom"]["max_drawdown_pct_geom"] - us10["baseline"]["max_drawdown_pct_geom"]
    g1 = sharpe_lift_us10 >= 0.10
    g2 = mdd_lift_us10 >= 5.0
    g3 = us10["dmom"]["skew_per_trade"] >= 1.0
    g4 = sp500["dmom"]["sharpe_gross"] < 0.20
    g_recon_us10 = us10["recon_diff_abs_sum"] < 1e-3 * abs(float(us10["series"]["baseline_daily"].sum()) or 1.0)
    g_recon_sp500 = sp500["recon_diff_abs_sum"] < 1e-3 * abs(float(sp500["series"]["baseline_daily"].sum()) or 1.0)
    g_recon = bool(g_recon_us10 and g_recon_sp500)

    if g1 and g2 and g3 and g_recon and g4:
        promotion_path = "A"
        status = "promoted"
    elif g2 and g3 and g_recon and g4:
        promotion_path = "B"
        status = "promoted_path_b_pending_owner_review"
    elif (not g3) or (not g1 and not g2):
        promotion_path = "FALSIFY"
        status = "falsified"
    elif not g4:
        promotion_path = "INVESTIGATE"
        status = "investigate"
    else:
        promotion_path = "ambiguous"
        status = "registered"

    verdicts_payload = {
        "G1_sharpe_lift_us10": {"observed": round(sharpe_lift_us10, 3), "threshold": ">= +0.10", "verdict": "PASS" if g1 else "FAIL"},
        "G2_maxdd_lift_us10": {"observed": round(mdd_lift_us10, 3), "threshold": ">= +5.0 pp", "verdict": "PASS" if g2 else "FAIL"},
        "G3_skew_us10_dmom": {"observed": us10["dmom"]["skew_per_trade"], "threshold": ">= 1.0", "verdict": "PASS" if g3 else "FAIL"},
        "G4_sp500_dmom_sharpe": {"observed": sp500["dmom"]["sharpe_gross"], "threshold": "< 0.20", "verdict": "PASS" if g4 else "FAIL"},
        "G_recon": {"verdict": "PASS" if g_recon else "FAIL"},
        "status": status,
        "promotion_path": promotion_path,
    }

    # manifest
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"
    manifest = {
        "run_utc": ts,
        "experiment_slug": "dmom_us10",
        "purpose": "dMOM (Daniel-Moskowitz 2016) overlay on Martin single-instrument EWMAC baseline",
        "pre_registration": "ars/evidence_packs/dmom_us10/dmom_us10_preregistration.md @ 65c423bc",
        "literature": [
            "references/research/Enhanced Momentum Strategies.pdf",
            "references/research/Design and analysis of momentum trading strategies.pdf",
        ],
        "engine": "native pysystemtrade futures_chapter15 (do_not_reimplement_engine=true); overlay computed at returns-stream level",
        "git_sha": git_sha, "python": platform.python_version(),
        "instruments": INSTRUMENTS, "ewmac_rules": EWMAC_RULES,
        "forecast_weights": FORECAST_WEIGHTS, "carry_included": False,
        "forecast_cap": 20.0, "percentage_vol_target": VOL_TARGET_PCT,
        "capital_usd": CAPITAL, "roundpositions": True, "idm": 1.0,
        "bear_lookback_days": BEAR_LOOKBACK_DAYS,
        "mkt_var_lookback_days": MKT_VAR_LOOKBACK_DAYS,
        "strat_var_lookback_days": STRAT_VAR_LOOKBACK_DAYS,
        "regression_warmup_days": REGRESSION_MIN_WARMUP,
        "lambda": {instr: per_instrument[instr]["lambda"] for instr in INSTRUMENTS},
        "verdicts": verdicts_payload,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "verdict.json").write_text(json.dumps(verdicts_payload, indent=2))

    # plots
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        f1, axes = plt.subplots(2, 1, figsize=(8, 7))
        for instr, d in per_instrument.items():
            geom_b, _ = geometric_equity_and_dd(d["series"]["baseline_daily"])
            geom_d, _ = geometric_equity_and_dd(d["series"]["dmom_daily"])
            axes[0].plot(geom_b.index, (geom_b - 1) * 100, label=f"{instr} baseline", linestyle="--")
            axes[0].plot(geom_d.index, (geom_d - 1) * 100, label=f"{instr} dMOM")
        axes[0].set_title("Compounded equity: baseline vs dMOM overlay")
        axes[0].set_ylabel("cumulative % return")
        axes[0].legend(); axes[0].grid(True, alpha=0.3)
        for instr, d in per_instrument.items():
            axes[1].plot(d["series"]["w"].index, d["series"]["w"].values, label=instr, lw=0.7)
        axes[1].axhline(0, color="k", lw=0.8)
        axes[1].set_title("dMOM weight w_dMOM,t over time (negative = flip momentum)")
        axes[1].set_ylabel("w_dMOM")
        axes[1].legend(); axes[1].grid(True, alpha=0.3)
        f1.tight_layout(); f1.savefig(out / "equity_and_weight.png", dpi=130); plt.close(f1)
    except Exception as e:
        print(f"[warn] plot skipped: {e}")

    # arki-style report
    try:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from ars_report import render_run_report
        cols_summary = ["sharpe_gross", "ann_return_pct", "ann_vol_pct",
                        "max_drawdown_pct_geom", "skew_daily", "skew_per_trade"]
        # build a tidy display table: rows = (instrument, variant)
        disp = summary[cols_summary].rename(columns={
            "sharpe_gross": "Sharpe_g", "ann_return_pct": "ann_ret %",
            "ann_vol_pct": "ann_vol %", "max_drawdown_pct_geom": "maxDD %",
            "skew_daily": "skew_d", "skew_per_trade": "skew_t"})
        disp.index = [f"{i[0]} {i[1]}" for i in disp.index]
        disp.index.name = "instrument variant"
        verdicts = [
            ("G1 US10 Sharpe lift  [>= +0.10]",
             g1, f"observed Δ = {sharpe_lift_us10:+.3f}"),
            ("G2 US10 maxDD lift  [>= +5.0 pp less negative]",
             g2, f"observed Δ = {mdd_lift_us10:+.2f} pp"),
            ("G3 US10 dMOM skew_per_trade  [>= 1.0]",
             g3, f"observed = {us10['dmom']['skew_per_trade']:+.2f}"),
            ("G4 SP500 dMOM Sharpe  [< 0.20]  (FAIL means INVESTIGATE)",
             g4, f"observed = {sp500['dmom']['sharpe_gross']:+.3f}"),
            ("G_recon  [overlay = R_baseline * w]",
             g_recon, f"|diff sum| US10={us10['recon_diff_abs_sum']:.2e}, SP500={sp500['recon_diff_abs_sum']:.2e}"),
        ]
        manifest_pairs = [
            ("Engine", "native futures_chapter15; overlay at returns stream"),
            ("Instruments", INSTRUMENTS),
            ("Baseline rules", EWMAC_RULES),
            ("Bear lookback", f"{BEAR_LOOKBACK_DAYS} d"),
            ("Mkt-var lookback", f"{MKT_VAR_LOOKBACK_DAYS} d"),
            ("Regression warmup", f"{REGRESSION_MIN_WARMUP} d"),
            ("Lambda (US10 / SP500)", f"{per_instrument['US10']['lambda']} / {per_instrument['SP500']['lambda']}"),
            ("Promotion path", promotion_path),
            ("Status", status),
            ("git SHA", git_sha),
        ]
        render_run_report(
            run_dir=out,
            title="dMOM Overlay — US10 single-instrument (Hanauer 2022 / Daniel-Moskowitz 2016)",
            subtitle="baseline 6-speed EWMAC + dMOM multiplicative overlay · pre-registered Path A",
            run_date=ts[:8], run_utc=ts, git_sha=git_sha,
            literature="Hanauer & Windmüller (2022) Enhanced Momentum Strategies; Daniel & Moskowitz (2016) Momentum Crashes. See references/research/.",
            summary_df=disp,
            trade_stats_df=disp,   # not separately useful for this run; reuse
            manifest_pairs=manifest_pairs,
            verdicts=verdicts,
            equity_png="equity_and_weight.png",
            equity_caption=("Top: compounded equity for baseline vs dMOM overlay. "
                            "Bottom: dMOM weight w_dMOM,t over time -- "
                            "negative values flip momentum exposure (bear + high mkt-vol regimes)."),
            trade_png="equity_and_weight.png",  # placeholder; combined fig
            trade_caption="(top section figure shown above; no separate per-trade panel for this run)",
            instrument_list=", ".join(INSTRUMENTS),
        )
    except Exception as e:
        print(f"[warn] report render failed: {e}")

    print("\n=== SUMMARY ===")
    print(summary.to_string())
    print("\n=== VERDICTS ===")
    print(json.dumps(verdicts_payload, indent=2))
    print(f"\nOutputs: {out}")
    return out


if __name__ == "__main__":
    main()
