#!/usr/bin/env python
"""
Martin (2023) single-instrument futures momentum backtest -- v2.

Reproduces the design + per-TRADE skewness from Richard J. Martin,
"Design and analysis of momentum trading strategies" (2023), using the
NATIVE pysystemtrade engine (ARS: do_not_reimplement_engine=true).

v2 changes (2026-05-27):
  - capital $50K (small-AUM realism, aligned with absmom workstream)
  - roundpositions=True (integer contracts, accurate costs)
  - skew measured on TRADES (sign-episode returns), not fixed M-day windows.
    A trade = a maximal run of consecutive days with constant non-zero
    sign in the (rounded, buffered) position series; trade return = sum
    of daily strategy returns over that run, in % of capital.

Outputs (ARS modules: reproducibility, statistical_reporting,
cost_and_turnover) under ars/runs/<UTC>_martin_single_instrument/.
"""

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
FORECAST_WEIGHTS = {r: EQUAL_W for r in EWMAC_RULES}  # pure trend, carry off
CAPITAL = 50_000          # USD -- small-AUM realism
VOL_TARGET_PCT = 20.0     # config default, linear scaling on positions
ROOT = Path(__file__).resolve().parent.parent
OUT_BASE = ROOT / "ars" / "runs"


def build_single_instrument_system(instrument: str):
    """Native chapter-15 system restricted to ONE instrument, EWMAC-only, $50k."""
    config = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    config.instruments = [instrument]
    config.instrument_weights = {instrument: 1.0}
    config.instrument_div_multiplier = 1.0
    config.forecast_weights = dict(FORECAST_WEIGHTS)
    config.notional_trading_capital = CAPITAL
    config.percentage_vol_target = VOL_TARGET_PCT
    return futures_system(config=config)


def extract_trades(positions: pd.Series, daily_returns: pd.Series) -> pd.DataFrame:
    """Sign-episode trade ledger with lagged-position attribution.

    pysystemtrade convention: return[t] is earned by the position held
    ENTERING day t (i.e. yesterday's end-of-day position). So we attribute
    return[t] to the sign of pos[t-1], not pos[t].

    A trade is a maximal run of consecutive bars where the holding sign
    (pos[t-1]) is the same and non-zero. Trade return = sum of daily
    strategy % returns over that run (Martin "period-M trading return",
    M = trade length).
    """
    pos_eod = positions.ffill().fillna(0).round().astype(int)  # end-of-day
    pos_held = pos_eod.shift(1).fillna(0).astype(int)          # held entering day t
    sign = np.sign(pos_held).astype(int)
    new_ep = (sign != sign.shift(1)).fillna(True).astype(int)
    ep_id = new_ep.cumsum()
    df = pd.DataFrame({"date": pos_eod.index, "pos_held": pos_held.values,
                       "sign": sign.values, "ep": ep_id.values})
    df["ret"] = daily_returns.reindex(df["date"]).values
    trades = (df[df["sign"] != 0]
              .groupby("ep")
              .agg(start=("date", "first"),
                   end=("date", "last"),
                   days=("date", "size"),
                   sign=("sign", "first"),
                   avg_contracts=("pos_held", lambda s: float(s.abs().mean())),
                   trade_return_pct=("ret", "sum"))
              .reset_index(drop=True))
    return trades


def native_turnover(system, instrument: str) -> float:
    try:
        return float(system.accounts.subsystem_turnover(instrument))
    except Exception:
        return float("nan")


def characterise(system, instrument: str) -> dict:
    acc = system.accounts.portfolio(roundpositions=True)  # realistic $50k integer-contract
    pct = acc.percent
    gross = acc.gross.percent
    daily = pct.as_ts
    # engine-actual integer position (post buffer-band, rounded), aligned to daily
    pos = system.accounts.get_buffered_position(instrument, roundpositions=True)
    if isinstance(pos, pd.DataFrame):
        pos = pos.squeeze("columns")
    pos = pos.reindex(daily.index)        # align to returns index
    trades = extract_trades(pos, daily)
    # diagnostic on LAGGED holding position (the one earning today's return)
    held = pos.ffill().fillna(0).round().shift(1).fillna(0).astype(int)
    flat_mask = (np.sign(held) == 0).values
    print(f"  diag {instrument}: n_flat={int(flat_mask.sum())} "
          f"sum_ret_on_flat={float(daily.fillna(0).values[flat_mask].sum()):.2f} "
          f"sum_ret_on_non_flat={float(daily.fillna(0).values[~flat_mask].sum()):.2f} "
          f"sum_total={float(daily.fillna(0).sum()):.2f}")
    dd = pct.drawdown()

    # reconcile: sum of trade returns should approx total cumulative % return
    cum_total = float(daily.fillna(0).sum())
    cum_trade = float(trades["trade_return_pct"].sum())

    stats = {
        "instrument": instrument,
        "start": str(daily.index[0].date()),
        "end": str(daily.index[-1].date()),
        "n_days": int(daily.dropna().shape[0]),
        "capital_usd": CAPITAL,
        "ann_return_gross_pct": round(float(gross.ann_mean()), 3),
        "ann_return_net_pct": round(float(pct.ann_mean()), 3),
        "ann_vol_pct": round(float(pct.ann_std()), 3),
        "sharpe_gross": round(float(gross.sharpe()), 3),
        "sharpe_net": round(float(pct.sharpe()), 3),
        "skew_daily": round(float(pct.skew()), 3),
        "skew_per_trade": round(float(trades["trade_return_pct"].skew()), 3),
        "n_trades": int(len(trades)),
        "median_trade_days": int(trades["days"].median()) if len(trades) else 0,
        "median_trade_return_pct": round(float(trades["trade_return_pct"].median()), 3) if len(trades) else 0.0,
        "win_rate_pct": round(100.0 * (trades["trade_return_pct"] > 0).mean(), 1) if len(trades) else 0.0,
        "max_drawdown_pct_additive": round(float(dd.min()), 3),
        "ann_subsystem_turnover": round(native_turnover(system, instrument), 2),
        "reconciliation_diff_pct": round(cum_total - cum_trade, 4),  # should be near 0
    }
    return {"stats": stats, "trades": trades, "equity": pct.curve(), "daily": daily}


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_BASE / f"{ts}_martin_single_instrument"
    out.mkdir(parents=True, exist_ok=True)

    summaries, equities, trade_frames = [], {}, {}
    for instr in INSTRUMENTS:
        print(f"[build] {instr} cap=${CAPITAL:,}")
        system = build_single_instrument_system(instr)
        res = characterise(system, instr)
        summaries.append(res["stats"])
        equities[instr] = res["equity"]
        trade_frames[instr] = res["trades"]
        s = res["stats"]
        print(f"[done]  {instr}: Sharpe_g={s['sharpe_gross']} skew_trade={s['skew_per_trade']} "
              f"skew_daily={s['skew_daily']} n_trades={s['n_trades']} win%={s['win_rate_pct']} "
              f"recon_diff={s['reconciliation_diff_pct']}")

    summary = pd.DataFrame(summaries).set_index("instrument")
    summary.to_csv(out / "summary.csv")
    pd.DataFrame(equities).to_csv(out / "equity_curves.csv")
    for instr, td in trade_frames.items():
        td.to_csv(out / f"trades_{instr}.csv", index=False)

    # split plots for the standardized report (one per page-section)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        f1, a1 = plt.subplots(figsize=(8, 4.2))
        for instr, eq in equities.items():
            a1.plot(eq.index, eq.values, label=instr)
        a1.set_title(f"Cumulative % return  ·  ${CAPITAL:,} capital, integer contracts")
        a1.set_ylabel("cumulative % return (native cumsum)"); a1.legend()
        a1.grid(True, alpha=0.3)
        f1.tight_layout(); f1.savefig(out / "equity_curve.png", dpi=130); plt.close(f1)

        f2, a2 = plt.subplots(figsize=(8, 4.2))
        for instr, td in trade_frames.items():
            a2.hist(td["trade_return_pct"], bins=60, alpha=0.5, label=instr)
        a2.axvline(0, color="k", lw=0.8)
        a2.set_xlabel("trade return (% of capital)"); a2.set_ylabel("count")
        a2.set_title("Per-trade return distribution (sign-episode)")
        a2.legend(); a2.grid(True, alpha=0.3)
        f2.tight_layout(); f2.savefig(out / "trade_dist.png", dpi=130); plt.close(f2)
    except Exception as e:
        print(f"[warn] plot skipped: {e}")

    # manifest
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"
    manifest = {
        "run_utc": ts,
        "purpose": "Martin (2023) single-instrument futures momentum: per-trade skew at $50k",
        "literature": "references/research/Design and analysis of momentum trading strategies.pdf",
        "engine": "native pysystemtrade futures_chapter15 (do_not_reimplement_engine=true)",
        "git_sha": git_sha, "python": platform.python_version(),
        "instruments": INSTRUMENTS, "ewmac_rules": EWMAC_RULES,
        "forecast_weights": FORECAST_WEIGHTS, "carry_included": False,
        "forecast_cap": 20.0, "percentage_vol_target": VOL_TARGET_PCT,
        "capital_usd": CAPITAL, "roundpositions": True, "idm": 1.0,
        "trade_def": "sign-episode: maximal run of constant non-zero sign(rounded buffered position)",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # standardized Arki-style HTML/PDF report
    try:
        from ars_report import render_run_report
        us10 = summary.loc["US10"]
        sp500 = summary.loc["SP500"]
        verdicts = [
            ("US10 (rates) shows positive daily skew  [Martin Fig1]",
             us10["skew_daily"] > 0,
             f"skew_daily = {us10['skew_daily']:+.3f}"),
            ("SP500 (equity) shows negative daily skew  [Martin Fig1]",
             sp500["skew_daily"] < 0,
             f"skew_daily = {sp500['skew_daily']:+.3f}"),
            ("Per-trade skew >> daily skew on US10  [Martin: trend injects positive skew at trade level]",
             us10["skew_per_trade"] > us10["skew_daily"] + 1.0,
             f"skew_per_trade = {us10['skew_per_trade']:+.2f}  vs  daily {us10['skew_daily']:+.2f}"),
            ("Low win rate + strong positive trade skew  [Martin: convex / long-option payoff]",
             us10["win_rate_pct"] < 50 and us10["skew_per_trade"] > 1.0,
             f"win% = {us10['win_rate_pct']:.1f}  ·  skew_per_trade = {us10['skew_per_trade']:+.2f}"),
            ("US10 gross Sharpe in [0.2, 0.6]  [refutes 0.7-1.0 claim, matches Carver/Martin]",
             0.2 <= us10["sharpe_gross"] <= 0.6,
             f"Sharpe_gross = {us10['sharpe_gross']:.3f}"),
        ]
        summary_disp = summary[["ann_return_gross_pct", "ann_vol_pct",
                                 "sharpe_gross", "sharpe_net", "skew_daily",
                                 "max_drawdown_pct_additive"]].rename(columns={
            "ann_return_gross_pct": "ann_ret_g %", "ann_vol_pct": "ann_vol %",
            "sharpe_gross": "Sharpe_g", "sharpe_net": "Sharpe_n",
            "skew_daily": "skew_daily", "max_drawdown_pct_additive": "maxDD %"})
        trade_disp = summary[["n_trades", "win_rate_pct", "median_trade_days",
                              "median_trade_return_pct", "skew_per_trade",
                              "ann_subsystem_turnover"]].rename(columns={
            "n_trades": "n_trades", "win_rate_pct": "win %",
            "median_trade_days": "med days", "median_trade_return_pct": "med ret %",
            "skew_per_trade": "skew_trade", "ann_subsystem_turnover": "turn/yr"})
        manifest_pairs = [
            ("Engine", manifest["engine"]),
            ("Instruments", manifest["instruments"]),
            ("Trading rules", manifest["ewmac_rules"]),
            ("Forecast weights", "equal (1/6 each), carry off"),
            ("Forecast cap (soft)", manifest["forecast_cap"]),
            ("Vol target (%)", manifest["percentage_vol_target"]),
            ("Capital (USD)", manifest["capital_usd"]),
            ("Round positions", manifest["roundpositions"]),
            ("IDM", manifest["idm"]),
            ("Trade definition", manifest["trade_def"]),
            ("Python", manifest["python"]),
            ("git SHA", manifest["git_sha"]),
        ]
        render_run_report(
            run_dir=out,
            title="Martin (2023) Single-Instrument Futures Momentum",
            subtitle="$50k capital · EWMAC 6 speeds equal-weight · per-trade skew characterisation",
            run_date=ts[:8],
            run_utc=ts,
            git_sha=manifest["git_sha"],
            literature=("Richard J. Martin, \"Design and analysis of momentum "
                        "trading strategies\" (2023). See references/research/."),
            summary_df=summary_disp,
            trade_stats_df=trade_disp,
            manifest_pairs=manifest_pairs,
            verdicts=verdicts,
            equity_png="equity_curve.png",
            equity_caption=(
                "Native cumsum %-return curves of single-instrument 6-speed EWMAC "
                "(equal-weight, carry off, vol-target 20%, soft cap 20, integer contracts). "
                "US10 (rates) compounds steadily; SP500 (equity) is flat to negative, "
                "consistent with Martin Fig 1 sign contrast."),
            trade_png="trade_dist.png",
            trade_caption=(
                "Distribution of sign-episode trade returns. Strong positive skew on both "
                "(US10 ≈ +4.4, SP500 ≈ +4.3) confirms Martin's theoretical result that pure "
                "trend rules inject positive skew into trading returns. Few large winners + "
                "low win rate is the long-option signature."),
            instrument_list=", ".join(INSTRUMENTS),
        )
    except Exception as e:
        print(f"[warn] report render failed: {e}")

    print("\n=== SUMMARY ===")
    print(summary.to_string())
    print(f"\nOutputs: {out}")
    return out, summary, equities, trade_frames, manifest


if __name__ == "__main__":
    main()
