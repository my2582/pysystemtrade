#!/usr/bin/env python
"""Execution friction runner — US10 6-cell matrix.

Pre-registration (locked Path A):
  ars/evidence_packs/execution_friction_us10/execution_friction_us10_preregistration.md

The 6 cells = 3 specs * 2 capital tiers:

  Spec                       Engine             Vol estimator         Cap   Position
  ---------------------------- -----------------  --------------------  ----  -----------
  martin_baseline_us10        pysystemtrade      Martin 20d EMA-of-sq  +-20  integer
  martin_primary_ema2_us10    standalone numpy   Martin 20d EMA-of-sq  OFF   continuous
  carver_6speed_us10          pysystemtrade      Carver mixed_vol_calc +-20  integer

Capital tiers per spec: $50,000 and $1,000,000.

Per cell outputs (under ars/runs/<UTC>_<slug>/):
  manifest.json, summary.csv, equity_curves.csv, trades_US10.csv,
  equity_curve.png, trade_dist.png, report.html, report.pdf.

Fork safety: never touches systems/ sysdata/ sysquant/. Vol-estimator override
for martin_baseline goes through `config.volatility_calculation` (config-level
injection), not by editing the engine.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import warnings
from copy import copy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arki.utils.martin_vol import martin_ema_vol  # noqa: E402

INSTRUMENT = "US10"
CAPITAL_TIERS = [50_000, 1_000_000]
VOL_TARGET_PCT = 20.0
EWMAC_RULES = ["ewmac2_8", "ewmac4_16", "ewmac8_32",
               "ewmac16_64", "ewmac32_128", "ewmac64_256"]
EQUAL_W = round(1.0 / len(EWMAC_RULES), 6)
TRADING_DAYS = 256

OUT_BASE = ROOT / "ars" / "runs"

PRE_REG = "ars/evidence_packs/execution_friction_us10/execution_friction_us10_preregistration.md"


# =====================================================================
# Spec definitions
# =====================================================================

def spec_config(spec: str) -> dict:
    """Return the per-spec config block (vol estimator + rules)."""
    if spec == "martin_baseline":
        return {
            "label": "martin_baseline_us10",
            "engine": "pysystemtrade",
            "rules": EWMAC_RULES,
            "forecast_weights": {r: EQUAL_W for r in EWMAC_RULES},
            "forecast_cap": 20.0,
            "roundpositions": True,
            "vol_calc": {
                "func": "arki.utils.martin_vol.martin_ema_vol",
                "name_returns_attr_in_rawdata": "daily_returns",
                "multiplier_to_get_daily_vol": 1.0,
                "N": 20,
                "min_periods": 10,
            },
            "vol_estimator_tag": "martin_20d_ema_of_sq",
        }
    if spec == "carver_6speed":
        return {
            "label": "carver_6speed_us10",
            "engine": "pysystemtrade",
            "rules": EWMAC_RULES,
            "forecast_weights": {r: EQUAL_W for r in EWMAC_RULES},
            "forecast_cap": 20.0,
            "roundpositions": True,
            "vol_calc": None,                # leave default (mixed_vol_calc 35d blend)
            "vol_estimator_tag": "carver_mixed_vol_calc_default",
        }
    if spec == "martin_primary":
        return {
            "label": "martin_primary_ema2_us10",
            "engine": "standalone",
            "N_alpha": 20,
            "N_beta": 40,
            "forecast_cap": None,            # OFF
            "roundpositions": False,         # continuous
            "vol_calc": "arki.utils.martin_vol.martin_ema_vol",
            "vol_estimator_tag": "martin_20d_ema_of_sq",
        }
    raise ValueError(f"unknown spec: {spec}")


# =====================================================================
# Engine A: pysystemtrade (martin_baseline + carver_6speed)
# =====================================================================

def build_pst_system(spec: str, capital: float):
    """Native chapter-15 system on US10 only with per-spec overrides."""
    from sysdata.config.configdata import Config
    from systems.provided.futures_chapter15.basesystem import futures_system
    cfg_dict = spec_config(spec)
    config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    config.instruments = [INSTRUMENT]
    config.instrument_weights = {INSTRUMENT: 1.0}
    config.instrument_div_multiplier = 1.0
    config.forecast_weights = dict(cfg_dict["forecast_weights"])
    config.notional_trading_capital = float(capital)
    config.percentage_vol_target = VOL_TARGET_PCT
    config.forecast_cap = cfg_dict["forecast_cap"]
    if cfg_dict["vol_calc"] is not None:
        config.volatility_calculation = dict(cfg_dict["vol_calc"])
    return futures_system(config=config)


def characterise_pst(system, spec: str, capital: float) -> dict:
    """Compute stats + trades + equity for a pysystemtrade-driven cell."""
    cfg = spec_config(spec)
    rp = bool(cfg["roundpositions"])
    acc = system.accounts.portfolio(roundpositions=rp)
    pct = acc.percent
    gross = acc.gross.percent
    daily = pct.as_ts
    geom_eq, geom_dd = geometric_equity_and_dd(daily)
    pos = system.accounts.get_buffered_position(INSTRUMENT, roundpositions=rp)
    if isinstance(pos, pd.DataFrame):
        pos = pos.squeeze("columns")
    pos = pos.reindex(daily.index)
    trades = extract_trades(pos, daily, round_to_int=rp)
    cum_total = float(daily.fillna(0).sum())
    cum_trade = float(trades["trade_return_pct"].sum()) if len(trades) else 0.0
    # forecast clipping diagnostic (Exp 1/3 assumption-check)
    try:
        fc = system.combForecast.get_combined_forecast(INSTRUMENT)
        fc_aligned = fc.reindex(daily.index).dropna()
        clip_frac = float((fc_aligned.abs() >= cfg["forecast_cap"]).mean())
    except Exception:
        clip_frac = float("nan")
    # vol-estimator series for diagnostics
    sigma = system.rawdata.daily_returns_volatility(INSTRUMENT)
    sigma = sigma.reindex(daily.index)
    return {
        "stats": _stats_dict(spec, capital, daily, gross, pct, trades, geom_dd,
                             ann_turnover=_safe_turnover(system),
                             reconciliation=cum_total - cum_trade,
                             extra={"forecast_clip_frac": round(clip_frac, 4)
                                    if not np.isnan(clip_frac) else None,
                                    "frac_flat": round(float((pos.ffill().fillna(0)
                                                              .round().abs() == 0).mean()), 4),
                                    "mean_abs_pos": round(float(pos.ffill().fillna(0)
                                                                .abs().mean()), 4)}),
        "trades": trades,
        "equity": (geom_eq - 1) * 100,
        "daily": daily,
        "position": pos,
        "vol_est": sigma,
    }


def _safe_turnover(system) -> float:
    try:
        return float(system.accounts.subsystem_turnover(INSTRUMENT))
    except Exception:
        return float("nan")


# =====================================================================
# Engine B: standalone numpy (martin_primary)
# =====================================================================

def _get_us10_price_from_pst() -> pd.Series:
    """Load US10 adjusted price via pysystemtrade rawdata (consistent with Exp 1/3)."""
    from sysdata.config.configdata import Config
    from systems.provided.futures_chapter15.basesystem import futures_system
    config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    config.instruments = [INSTRUMENT]
    system = futures_system(config=config)
    return system.rawdata.get_daily_prices(INSTRUMENT)


def run_martin_primary(capital: float) -> dict:
    """Strict Martin paper-fidelity single-EMA2 continuous backtest.

    Implements: §1 Eq.(1) U_n = dX_n/sigma_hat_{n-1}; §2.1 Eq.(4) phi_n =
    Sum a_j U_{n-j} with a_j = (alpha^{j+1} - beta^{j+1}) / (alpha-beta);
    §2.5 vol estimator (20d EMA of squared changes, gamma=0.95);
    §4 normalisation constant K so std(phi) = 1.

    Position phi/sigma_hat (Martin's footnote 5). PnL uses lagged position
    so today's return is earned by yesterday's EOD position (matching
    pysystemtrade convention).
    """
    from scipy.signal import lfilter

    cfg = spec_config("martin_primary")
    N_alpha, N_beta = cfg["N_alpha"], cfg["N_beta"]
    alpha_M = 1.0 - 1.0 / N_alpha          # 0.95
    beta_M  = 1.0 - 1.0 / N_beta           # 0.975

    price = _get_us10_price_from_pst()
    dX = price.diff()
    sigma = martin_ema_vol(dX, N=20, min_periods=10)
    U = dX / sigma.shift(1)                # vol-normalised return

    # Martin EMA2 via recursive form: 1 / (1 - (alpha+beta) z^{-1} + alpha*beta z^{-2})
    U_arr = U.fillna(0.0).values
    a_den = [1.0, -(alpha_M + beta_M), alpha_M * beta_M]
    phi_raw = lfilter([1.0], a_den, U_arr)
    # Analytical L2-norm of weights -> normalisation so std(phi) = 1 in steady state.
    K = ((1 - alpha_M ** 2) * (1 - beta_M ** 2) * (1 - alpha_M * beta_M)
         / (1 + alpha_M * beta_M)) ** 0.5
    phi = pd.Series(K * phi_raw, index=U.index)
    # Mask warm-up + any index where U is NaN.
    warmup_mask = pd.Series(False, index=U.index)
    warmup_mask.iloc[: max(N_beta, 20) + 10] = True   # be conservative
    phi[warmup_mask | U.isna()] = np.nan

    # Daily P&L (lagged position * today's return), scaled to target vol:
    # daily_frac_return = phi.shift(1) * U_t * (target_vol_annual / sqrt(T))
    # This sidesteps contract specs: phi_norm has std~=1, U has std~=1, so
    # the product has std~=1 and we scale by the target daily vol fraction.
    target_daily_vol_frac = VOL_TARGET_PCT / 100.0 / np.sqrt(TRADING_DAYS)
    pnl_frac = phi.shift(1) * U * target_daily_vol_frac     # fraction of capital, per day
    daily_pct = (pnl_frac * 100.0).rename("daily_pct")      # percent of capital
    daily_pct = daily_pct.dropna()

    geom_eq, geom_dd = geometric_equity_and_dd(daily_pct)
    # Use continuous position (no rounding) for the sign-episode trade ledger.
    position_continuous = phi.shift(1).reindex(daily_pct.index)
    trades = extract_trades(position_continuous, daily_pct, round_to_int=False)
    cum_total = float(daily_pct.fillna(0).sum())
    cum_trade = float(trades["trade_return_pct"].sum()) if len(trades) else 0.0

    # ann turnover proxy on continuous position: 0.5 * sum(|dpos|) / years.
    pos_clean = position_continuous.dropna()
    years = max((daily_pct.index[-1] - daily_pct.index[0]).days / 365.25, 1e-9)
    ann_turnover = 0.5 * float(pos_clean.diff().abs().sum()) / years

    return {
        "stats": _stats_dict("martin_primary", capital, daily_pct,
                             daily_pct, daily_pct, trades, geom_dd,
                             ann_turnover=ann_turnover,
                             reconciliation=cum_total - cum_trade,
                             extra={
                                 "frac_flat": round(float((pos_clean.abs() < 1e-12)
                                                          .mean()), 4),
                                 "mean_abs_pos": round(float(pos_clean.abs()
                                                             .mean()), 4),
                                 "forecast_clip_frac": 0.0,
                                 "K_normalisation": round(float(K), 6),
                             }),
        "trades": trades,
        "equity": (geom_eq - 1) * 100,
        "daily": daily_pct,
        "position": position_continuous,
        "vol_est": sigma,
    }


# =====================================================================
# Shared helpers (trades + equity + stats)
# =====================================================================

def extract_trades(positions: pd.Series, daily_returns: pd.Series,
                   round_to_int: bool = True) -> pd.DataFrame:
    """Sign-episode trade ledger with lagged-position attribution.

    Convention: today's return is earned by the position held entering
    today (= yesterday's EOD). A trade = maximal run of constant non-zero
    sign on that held position.

    `round_to_int=True` is for integer-contract cells (martin_baseline,
    carver_6speed). `False` is for continuous (martin_primary) -- in that
    case the held position is the lagged continuous phi_norm and the sign
    captures regime direction directly.
    """
    pos_clean = positions.ffill().fillna(0.0)
    if round_to_int:
        pos_eod = pos_clean.round().astype(int)
    else:
        pos_eod = pos_clean
    pos_held = pos_eod.shift(1).fillna(0.0)
    if round_to_int:
        pos_held = pos_held.astype(int)
    sign = np.sign(pos_held).astype(int)
    new_ep = (sign != sign.shift(1)).fillna(True).astype(int)
    ep_id = new_ep.cumsum()
    df = pd.DataFrame({"date": pos_eod.index,
                       "pos_held": pos_held.values,
                       "sign": sign.values, "ep": ep_id.values})
    df["ret"] = daily_returns.reindex(df["date"]).values
    trades = (df[df["sign"] != 0]
              .groupby("ep")
              .agg(start=("date", "first"),
                   end=("date", "last"),
                   days=("date", "size"),
                   sign=("sign", "first"),
                   avg_abs_pos=("pos_held", lambda s: float(s.abs().mean())),
                   trade_return_pct=("ret", "sum"))
              .reset_index(drop=True))
    return trades


def geometric_equity_and_dd(daily_pct_points: pd.Series) -> tuple[pd.Series, pd.Series]:
    daily_frac = daily_pct_points.fillna(0) / 100.0
    eq = (1.0 + daily_frac).cumprod()
    eq = eq.clip(lower=1e-6)
    dd = (eq / eq.cummax() - 1.0) * 100
    return eq, dd


def _stats_dict(spec: str, capital: float, daily, gross, pct, trades, geom_dd,
                ann_turnover: float, reconciliation: float, extra: dict) -> dict:
    n_days = int(daily.dropna().shape[0])
    valid_daily = daily.dropna()
    sr_gross = float(gross.sharpe()) if hasattr(gross, "sharpe") else _sharpe(valid_daily)
    sr_net = float(pct.sharpe()) if hasattr(pct, "sharpe") else _sharpe(valid_daily)
    ann_ret_g = float(gross.ann_mean()) if hasattr(gross, "ann_mean") else float(valid_daily.mean() * TRADING_DAYS)
    ann_ret_n = float(pct.ann_mean()) if hasattr(pct, "ann_mean") else ann_ret_g
    ann_vol = float(pct.ann_std()) if hasattr(pct, "ann_std") else float(valid_daily.std() * np.sqrt(TRADING_DAYS))
    skew_d = float(pct.skew()) if hasattr(pct, "skew") else float(valid_daily.skew())
    spec_label = spec_config(spec)["label"]
    out = {
        "spec": spec_label,
        "instrument": INSTRUMENT,
        "capital_usd": int(capital),
        "start": str(daily.index[0].date()),
        "end": str(daily.index[-1].date()),
        "n_days": n_days,
        "ann_return_gross_pct": round(ann_ret_g, 3),
        "ann_return_net_pct": round(ann_ret_n, 3),
        "ann_vol_pct": round(ann_vol, 3),
        "sharpe_gross": round(sr_gross, 3),
        "sharpe_net": round(sr_net, 3),
        "skew_daily": round(skew_d, 3),
        "skew_per_trade": (round(float(trades["trade_return_pct"].skew()), 3)
                           if len(trades) > 2 else None),
        "n_trades": int(len(trades)),
        "median_trade_days": int(trades["days"].median()) if len(trades) else 0,
        "median_trade_return_pct": (round(float(trades["trade_return_pct"].median()), 3)
                                    if len(trades) else 0.0),
        "win_rate_pct": (round(100.0 * (trades["trade_return_pct"] > 0).mean(), 1)
                         if len(trades) else 0.0),
        "max_drawdown_pct_geom": round(float(geom_dd.min()), 3),
        "ann_subsystem_turnover": round(ann_turnover, 2),
        "reconciliation_diff_pct": round(reconciliation, 4),
    }
    out.update(extra)
    return out


def _sharpe(daily_pct: pd.Series) -> float:
    s = daily_pct.dropna()
    if len(s) < 30 or s.std() < 1e-12:
        return float("nan")
    return float(s.mean() / s.std() * np.sqrt(TRADING_DAYS))


# =====================================================================
# Run-dir writer + report
# =====================================================================

def write_run_artifacts(out_dir: Path, res: dict, spec: str, capital: float,
                        git_sha: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = res["stats"]
    pd.DataFrame([stats]).set_index("spec").to_csv(out_dir / "summary.csv")
    pd.DataFrame({INSTRUMENT: res["equity"]}).to_csv(out_dir / "equity_curves.csv")
    res["trades"].to_csv(out_dir / f"trades_{INSTRUMENT}.csv", index=False)

    # plots
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        f1, a1 = plt.subplots(figsize=(8, 4.2))
        a1.plot(res["equity"].index, res["equity"].values, label=spec)
        a1.set_title(f"{spec} @ ${int(capital):,}  -- cumulative % return (compounded)")
        a1.set_ylabel("cumulative % return"); a1.legend(); a1.grid(True, alpha=0.3)
        f1.tight_layout(); f1.savefig(out_dir / "equity_curve.png", dpi=130); plt.close(f1)

        td = res["trades"]
        if len(td):
            f2, a2 = plt.subplots(figsize=(8, 3.2))
            a2.hist(td["trade_return_pct"], bins=60, alpha=0.7, color="steelblue")
            a2.axvline(0, color="k", lw=0.8)
            a2.set_xlabel("trade return (% of capital)"); a2.set_ylabel("count")
            a2.set_title(f"Per-trade return distribution ({spec})")
            a2.grid(True, alpha=0.3)
            f2.tight_layout(); f2.savefig(out_dir / "trade_dist.png", dpi=130); plt.close(f2)
    except Exception as e:
        print(f"[warn] plot skipped: {e}")

    cfg = spec_config(spec)
    manifest = {
        "run_utc": out_dir.name.split("_")[0],
        "spec": cfg["label"],
        "capital_usd": int(capital),
        "purpose": "execution_friction_us10 6-cell matrix",
        "pre_registration": PRE_REG,
        "literature": "references/research/Design and analysis of momentum trading strategies.pdf",
        "engine": cfg["engine"],
        "vol_estimator_tag": cfg["vol_estimator_tag"],
        "vol_calc_func": (cfg["vol_calc"].get("func")
                          if isinstance(cfg.get("vol_calc"), dict) else cfg.get("vol_calc")),
        "rules": cfg.get("rules") or ["ewmac20_40_single_ema2"],
        "forecast_weights": cfg.get("forecast_weights", "single_rule"),
        "forecast_cap": cfg.get("forecast_cap"),
        "roundpositions": cfg.get("roundpositions"),
        "percentage_vol_target": VOL_TARGET_PCT,
        "carry_included": False,
        "instrument": INSTRUMENT,
        "git_sha": git_sha,
        "python": platform.python_version(),
        "trade_def": "sign-episode (constant non-zero sign on " +
                     ("rounded buffered position" if cfg.get("roundpositions") else "continuous phi") + ")",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # standardised ARS report (HTML + PDF) if renderer is available
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from ars_report import render_run_report  # type: ignore
        sharpe = stats.get("sharpe_gross")
        skew_trade = stats.get("skew_per_trade")
        verdicts = [
            ("Reconciliation within 5%", abs(stats["reconciliation_diff_pct"]) < 5,
             f"|recon| = {abs(stats['reconciliation_diff_pct']):.4f}%"),
            ("Sharpe positive (no falsification, reporting only)", (sharpe or 0) > 0,
             f"sharpe_gross = {sharpe}"),
            ("Per-trade skew positive (Martin §2.3 sign check)",
             (skew_trade or 0) > 0, f"skew_per_trade = {skew_trade}"),
        ]
        summary_df = pd.DataFrame([stats]).set_index("spec")
        # trade stats single-row summary
        td = res["trades"]
        trade_stats_df = pd.DataFrame([{
            "n_trades": len(td),
            "median_days": int(td["days"].median()) if len(td) else 0,
            "median_return_pct": float(td["trade_return_pct"].median()) if len(td) else 0.0,
            "win_rate_pct": stats["win_rate_pct"],
            "skew_per_trade": stats["skew_per_trade"],
        }]).set_index(pd.Index([cfg["label"]], name="spec"))
        manifest_pairs = [
            ("spec", cfg["label"]),
            ("capital_usd", f"${int(capital):,}"),
            ("engine", cfg["engine"]),
            ("vol_estimator", cfg["vol_estimator_tag"]),
            ("forecast_cap", cfg.get("forecast_cap")),
            ("roundpositions", cfg.get("roundpositions")),
            ("instrument", INSTRUMENT),
            ("pre_registration", PRE_REG),
            ("git_sha", git_sha[:12]),
        ]
        render_run_report(
            out_dir,
            title=f"{cfg['label']} @ ${int(capital):,}",
            subtitle="execution_friction_us10 -- single cell",
            run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            run_utc=out_dir.name.split("_")[0],
            git_sha=git_sha,
            literature="Martin (2023) Design and analysis of momentum trading strategies",
            summary_df=summary_df,
            trade_stats_df=trade_stats_df,
            manifest_pairs=manifest_pairs,
            verdicts=verdicts,
            equity_png="equity_curve.png",
            equity_caption=f"Compounded % return on ${int(capital):,} capital",
            trade_png="trade_dist.png",
            trade_caption="Per-trade (sign-episode) return distribution",
            instrument_list=INSTRUMENT,
        )
    except Exception as e:
        print(f"[info] standardised ars_report skipped: {e}")


# =====================================================================
# CLI
# =====================================================================

def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "unknown"


def run_one_cell(spec: str, capital: float) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cap_tag = "50k" if capital == 50_000 else ("1m" if capital == 1_000_000 else f"{int(capital)}")
    slug = f"{spec_config(spec)['label']}_{cap_tag}"
    out_dir = OUT_BASE / f"{ts}_{slug}"
    print(f"[run]  spec={spec} capital=${int(capital):,} -> {out_dir.name}")
    if spec_config(spec)["engine"] == "pysystemtrade":
        system = build_pst_system(spec, capital)
        res = characterise_pst(system, spec, capital)
    else:
        res = run_martin_primary(capital)
        # capital is informational only for continuous Martin primary (Sharpe is
        # scale-invariant); we still record it in summary/manifest.
        res["stats"]["capital_usd"] = int(capital)
    write_run_artifacts(out_dir, res, spec, capital, _git_sha())
    s = res["stats"]
    print(f"[done] {slug}: Sharpe_g={s['sharpe_gross']} "
          f"skew_trade={s['skew_per_trade']} n_trades={s['n_trades']} "
          f"win%={s['win_rate_pct']} maxDD={s['max_drawdown_pct_geom']}% "
          f"recon={s['reconciliation_diff_pct']}")
    return out_dir


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec",
                    choices=["martin_baseline", "martin_primary", "carver_6speed", "all"],
                    default="all",
                    help="Spec to run (default: all 3 specs).")
    ap.add_argument("--capital", type=float, default=None,
                    help="Single capital value (default: loop both 50000 and 1000000).")
    args = ap.parse_args()

    specs = (["martin_baseline", "martin_primary", "carver_6speed"]
             if args.spec == "all" else [args.spec])
    caps = [args.capital] if args.capital is not None else CAPITAL_TIERS

    warnings.filterwarnings("ignore", category=FutureWarning)
    paths = []
    for spec in specs:
        for cap in caps:
            paths.append(run_one_cell(spec, float(cap)))
    print(f"\n[ok] wrote {len(paths)} run dir(s):")
    for p in paths:
        print(f"     {p}")


if __name__ == "__main__":
    main()
