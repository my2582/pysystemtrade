#!/usr/bin/env python
"""Run 3 pre-registered momentum variants on US10 + SP500.

Variants (single-decision changes vs Martin baseline):
  - smom: Wang-Yan 2021 semi-vol multiplicative scaler on baseline returns.
  - fast_tilt: linear-decay forecast weights toward fast EWMAC speeds.
  - carry_toggle: enable carry rule at weight 0.30 (EWMAC renormalised to 0.70).

Pre-registrations:
  - ars/evidence_packs/smom_us10/smom_us10_preregistration.md
  - ars/evidence_packs/fast_tilt_ewmac/fast_tilt_ewmac_preregistration.md
  - ars/evidence_packs/carry_toggle/carry_toggle_preregistration.md

Outputs: ars/runs/<UTC>_<variant>/ per variant; report.html via ars_report.
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sysdata.config.configdata import Config
from systems.provided.futures_chapter15.basesystem import futures_system

INSTRUMENTS = ["US10", "SP500"]
EWMAC_RULES = ["ewmac2_8", "ewmac4_16", "ewmac8_32",
               "ewmac16_64", "ewmac32_128", "ewmac64_256"]
CAPITAL = 50_000
VOL_TARGET_PCT = 20.0
SMOM_LOOKBACK = 126
ROOT = Path(__file__).resolve().parent.parent
OUT_BASE = ROOT / "ars" / "runs"


def _base_config(instr: str) -> Config:
    cfg = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    cfg.instruments = [instr]
    cfg.instrument_weights = {instr: 1.0}
    cfg.instrument_div_multiplier = 1.0
    cfg.notional_trading_capital = CAPITAL
    cfg.percentage_vol_target = VOL_TARGET_PCT
    return cfg


def build_baseline(instr: str):
    cfg = _base_config(instr)
    cfg.forecast_weights = {r: round(1/6, 6) for r in EWMAC_RULES}
    return futures_system(config=cfg)


def build_fast_tilt(instr: str):
    cfg = _base_config(instr)
    cfg.forecast_weights = {"ewmac2_8": 0.30, "ewmac4_16": 0.25, "ewmac8_32": 0.20,
                            "ewmac16_64": 0.15, "ewmac32_128": 0.07, "ewmac64_256": 0.03}
    return futures_system(config=cfg)


def build_carry(instr: str):
    cfg = _base_config(instr)
    ew = round(0.70 / 6, 6)
    cfg.forecast_weights = {**{r: ew for r in EWMAC_RULES}, "carry": 0.30}
    return futures_system(config=cfg)


def daily_series(system) -> tuple[pd.Series, pd.Series]:
    """Return (daily strategy % returns, engine actual integer position)."""
    acc = system.accounts.portfolio(roundpositions=True)
    daily = acc.percent.as_ts
    pos = system.accounts.get_actual_position(system.config.instruments[0])
    if isinstance(pos, pd.DataFrame):
        pos = pos.squeeze("columns")
    pos = pos.reindex(daily.index).ffill().fillna(0).round().astype(int)
    return daily, pos, acc


def smom_weight(R: pd.Series, lookback: int) -> pd.Series:
    """Wang-Yan 2021 semi-vol scaler. Returns w_t such that R_sMOM = R * w."""
    R = R.fillna(0)
    downside_sq = (R**2).where(R < 0, 0)
    semi_var = downside_sq.rolling(lookback, min_periods=30).mean()
    semi_var = semi_var.where(semi_var > 1e-12)
    # raw target: full-sample baseline std (matches Hanauer cMOM/sMOM "target=identical full-sample vol")
    target_var = float((R**2).mean())
    raw_w = np.sqrt(target_var) / np.sqrt(semi_var)
    raw_w = raw_w.replace([np.inf, -np.inf], np.nan)
    # closed-form lambda match: scale so std(R*w) == std(R) full-sample
    Rw = (R * raw_w.fillna(0))
    var_R = float(R.var()); var_Rw = float(Rw.var())
    lam = float(np.sqrt(var_Rw / var_R)) if var_R > 0 and var_Rw > 0 else 1.0
    return raw_w / lam


def geom_equity_dd(daily_pct: pd.Series):
    daily_frac = daily_pct.fillna(0) / 100.0
    eq = (1.0 + daily_frac).cumprod().clip(lower=1e-6)
    dd = (eq / eq.cummax() - 1.0) * 100
    return eq, dd


def sign_episode_trades(daily: pd.Series, pos: pd.Series) -> pd.DataFrame:
    pos_eod = pos.ffill().fillna(0).round().astype(int)
    pos_held = pos_eod.shift(1).fillna(0).astype(int)
    sign = np.sign(pos_held).astype(int)
    new_ep = (sign != sign.shift(1)).fillna(True).astype(int)
    ep = new_ep.cumsum()
    df = pd.DataFrame({"date": pos.index, "sign": sign.values, "ep": ep.values,
                       "ret": daily.reindex(pos.index).values})
    return (df[df["sign"] != 0].groupby("ep")
            .agg(start=("date","first"), end=("date","last"),
                 days=("date","size"), sign=("sign","first"),
                 trade_return_pct=("ret","sum"))
            .reset_index(drop=True))


def stats_for(R: pd.Series, pos_for_trades: pd.Series, label: str) -> dict:
    R = R.fillna(0)
    _, dd = geom_equity_dd(R)
    ann_ret = float(R.sum()) / (len(R) / 252)
    ann_vol = float(R.std()) * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")
    trades = sign_episode_trades(R, pos_for_trades)
    skew_trade = float(trades["trade_return_pct"].skew()) if len(trades) else float("nan")
    win = 100.0 * float((trades["trade_return_pct"] > 0).mean()) if len(trades) else float("nan")
    return {
        "label": label,
        "ann_return_pct": round(ann_ret, 3),
        "ann_vol_pct": round(ann_vol, 3),
        "sharpe_gross": round(sharpe, 3),
        "skew_daily": round(float(R.skew()), 3),
        "skew_per_trade": round(skew_trade, 3),
        "max_drawdown_pct_geom": round(float(dd.min()), 3),
        "n_trades": int(len(trades)),
        "win_rate_pct": round(win, 1) if len(trades) else 0.0,
    }


def gates_smom(base: dict, var: dict, sp_var: dict) -> tuple[dict, str, str]:
    sharpe_lift = var["sharpe_gross"] - base["sharpe_gross"]
    mdd_lift = var["max_drawdown_pct_geom"] - base["max_drawdown_pct_geom"]
    g1 = sharpe_lift >= 0.05
    g2 = mdd_lift >= 3.0
    g3 = var["skew_per_trade"] >= 1.0
    g4 = sp_var["sharpe_gross"] < 0.20
    gates = {
        "G1_sharpe_lift": {"observed": round(sharpe_lift, 3), "threshold": ">= +0.05", "verdict": "PASS" if g1 else "FAIL"},
        "G2_maxdd_improvement_pp": {"observed": round(mdd_lift, 3), "threshold": ">= +3.0", "verdict": "PASS" if g2 else "FAIL"},
        "G3_skew_per_trade": {"observed": var["skew_per_trade"], "threshold": ">= 1.0", "verdict": "PASS" if g3 else "FAIL"},
        "G4_sp500_control": {"observed": sp_var["sharpe_gross"], "threshold": "< 0.20", "verdict": "PASS" if g4 else "FAIL"},
    }
    if not g3 or (not g1 and not g2): status, path = "falsified", "FALSIFY"
    elif g1 and g2 and g3 and g4: status, path = "promoted", "A"
    elif g2 and g3 and g4: status, path = "registered_path_b_candidate", "B"
    elif not g4: status, path = "investigate", "INVESTIGATE"
    else: status, path = "registered", "ambiguous"
    return gates, status, path


def gates_fast_tilt(base: dict, var: dict, sp_var: dict) -> tuple[dict, str, str]:
    sharpe_lift = var["sharpe_gross"] - base["sharpe_gross"]
    g1 = sharpe_lift >= 0.05
    g2 = var["skew_per_trade"] >= 1.0
    g3 = sp_var["sharpe_gross"] < 0.20
    gates = {
        "G1_sharpe_lift": {"observed": round(sharpe_lift, 3), "threshold": ">= +0.05", "verdict": "PASS" if g1 else "FAIL"},
        "G2_skew_per_trade": {"observed": var["skew_per_trade"], "threshold": ">= 1.0", "verdict": "PASS" if g2 else "FAIL"},
        "G3_sp500_control": {"observed": sp_var["sharpe_gross"], "threshold": "< 0.20", "verdict": "PASS" if g3 else "FAIL"},
    }
    if not g2 or sharpe_lift < -0.03: status, path = "falsified", "FALSIFY"
    elif g1 and g2 and g3: status, path = "promoted", "A"
    else: status, path = "registered", "no_promotion"
    return gates, status, path


def gates_carry(base: dict, var: dict, sp_var: dict) -> tuple[dict, str, str]:
    sharpe_shift = abs(var["sharpe_gross"] - base["sharpe_gross"])
    skew_reduction = base["skew_per_trade"] - var["skew_per_trade"]
    g1 = sharpe_shift >= 0.03
    g2 = skew_reduction >= 0.5
    g3 = var["skew_per_trade"] >= 1.0
    g4 = sp_var["sharpe_gross"] < 0.20
    gates = {
        "G1_sharpe_shift": {"observed": round(sharpe_shift, 3), "threshold": ">= 0.03", "verdict": "PASS" if g1 else "FAIL"},
        "G2_skew_reduction": {"observed": round(skew_reduction, 3), "threshold": ">= 0.5", "verdict": "PASS" if g2 else "FAIL"},
        "G3_skew_above_floor": {"observed": var["skew_per_trade"], "threshold": ">= 1.0", "verdict": "PASS" if g3 else "FAIL"},
        "G4_sp500_control": {"observed": sp_var["sharpe_gross"], "threshold": "< 0.20", "verdict": "PASS" if g4 else "FAIL"},
    }
    if not g3: status, path = "degraded", "DEGRADED"
    elif g2 and g3: status, path = "confirmed", "CONFIRMED"
    elif not g2: status, path = "refuted", "REFUTED"
    else: status, path = "registered", "ambiguous"
    return gates, status, path


def render_report_for(out: Path, ts: str, manifest: dict, summary_df: pd.DataFrame,
                      verdicts: list, slug: str, equity_png: str):
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from ars_report import render_run_report
        disp = summary_df[["sharpe_gross","ann_return_pct","ann_vol_pct",
                           "max_drawdown_pct_geom","skew_daily","skew_per_trade"]].rename(columns={
            "sharpe_gross":"Sharpe_g","ann_return_pct":"ann_ret %","ann_vol_pct":"ann_vol %",
            "max_drawdown_pct_geom":"maxDD %","skew_daily":"skew_d","skew_per_trade":"skew_t"})
        manifest_pairs = [(k, v) for k, v in manifest.items() if k not in ("verdicts",)]
        render_run_report(
            run_dir=out, title=f"{slug} — pre-registered momentum variant",
            subtitle=f"baseline vs {slug}; US10 + SP500; pre-registered Path A",
            run_date=ts[:8], run_utc=ts, git_sha=manifest.get("git_sha","unknown"),
            literature="ars/evidence_packs/<slug>/<slug>_preregistration.md (locked at pre-reg commit)",
            summary_df=disp, trade_stats_df=disp,
            manifest_pairs=manifest_pairs, verdicts=verdicts,
            equity_png=equity_png, equity_caption="Compounded equity per instrument-variant.",
            trade_png=equity_png, trade_caption="(equity figure shown above; no separate per-trade panel)",
            instrument_list=", ".join(INSTRUMENTS),
        )
    except Exception as e:
        print(f"[warn] report render skipped for {slug}: {e}")


def plot_equity(out: Path, results: dict, slug: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.4))
        for key, R in results.items():
            eq, _ = geom_equity_dd(R)
            ax.plot(eq.index, (eq - 1) * 100, label=key, lw=1.0)
        ax.set_title(f"Compounded % return — {slug}")
        ax.set_ylabel("cumulative % return"); ax.legend(); ax.grid(True, alpha=0.3)
        fig.tight_layout(); fig.savefig(out / "equity_curve.png", dpi=130); plt.close(fig)
    except Exception as e:
        print(f"[warn] plot skipped {slug}: {e}")


def run_variant(slug: str, build_var, gates_fn, ts: str, recon_required: bool):
    out = OUT_BASE / f"{ts}_{slug}"
    out.mkdir(parents=True, exist_ok=True)
    per_instrument = {}
    series_for_plot = {}
    for instr in INSTRUMENTS:
        baseline_sys = build_baseline(instr)
        R_base, pos_base, _ = daily_series(baseline_sys)
        base_stats = stats_for(R_base, pos_base, f"{instr}_baseline")
        if slug == "smom_us10":
            w = smom_weight(R_base, SMOM_LOOKBACK)
            R_var = (R_base * w).fillna(0)
            pos_var = (pos_base * np.sign(w.fillna(0)).astype(int)).reindex(R_var.index).fillna(0).astype(int)
            var_stats = stats_for(R_var, pos_var, f"{instr}_smom")
        else:
            var_sys = build_var(instr)
            R_var, pos_var, _ = daily_series(var_sys)
            var_stats = stats_for(R_var, pos_var, f"{instr}_{slug}")
        per_instrument[instr] = {"baseline": base_stats, "variant": var_stats,
                                 "R_base": R_base, "R_var": R_var}
        series_for_plot[f"{instr} baseline"] = R_base
        series_for_plot[f"{instr} {slug}"] = R_var

    # gates use US10 primary, SP500 control
    us10 = per_instrument["US10"]; sp = per_instrument["SP500"]
    gates, status, path = gates_fn(us10["baseline"], us10["variant"], sp["variant"])

    summary_rows = []
    for instr, d in per_instrument.items():
        summary_rows.append({"instrument": instr, "variant": "baseline", **d["baseline"]})
        summary_rows.append({"instrument": instr, "variant": slug, **d["variant"]})
    summary = pd.DataFrame(summary_rows).set_index(["instrument","variant"])
    summary.to_csv(out / "summary.csv")

    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"
    manifest = {
        "run_utc": ts, "experiment_slug": slug,
        "engine": "native pysystemtrade futures_chapter15",
        "git_sha": git_sha, "python": platform.python_version(),
        "instruments": INSTRUMENTS, "ewmac_rules": EWMAC_RULES,
        "capital_usd": CAPITAL, "vol_target_pct": VOL_TARGET_PCT,
        "verdicts": {**gates, "status": status, "promotion_path": path},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (out / "verdict.json").write_text(json.dumps({"gates": gates, "status": status, "promotion_path": path}, indent=2, default=str))

    plot_equity(out, series_for_plot, slug)
    verdicts_for_report = [(f"{gid} {g['threshold']}", g['verdict'] == 'PASS',
                            f"observed = {g['observed']}") for gid, g in gates.items()]
    render_report_for(out, ts, manifest, summary, verdicts_for_report, slug, "equity_curve.png")

    print(f"=== {slug}: status={status} path={path}")
    print(summary.to_string())
    return out, status


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print("\n>>> sMOM <<<")
    run_variant("smom_us10", None, gates_smom, ts, recon_required=True)
    print("\n>>> fast-tilt EWMAC <<<")
    run_variant("fast_tilt_ewmac", build_fast_tilt, gates_fast_tilt, ts, recon_required=False)
    print("\n>>> carry-toggle <<<")
    run_variant("carry_toggle", build_carry, gates_carry, ts, recon_required=False)


if __name__ == "__main__":
    main()
