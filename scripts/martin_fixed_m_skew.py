#!/usr/bin/env python
"""Fixed-M trading-return skew measurement for Martin (2023) Eq. 12 validation.

Steps 2 + 3 of the post-review correction (see ars/DECISIONS.md
2026-05-29 retro-correction entry).

Step 2: Paper §2 closed-form predicts skewness of M-period non-overlapping
trading returns: starts at 0, peaks at finite M, decays as M^(-1/2).
EMA1 max skew ≈ 2.41 at M ≈ 1.07·N. EMA2 max skew ≈ 2.1 at M ≈ 1.7(N_α+N_β).
My prior `skew_per_trade` (sign-episode, variable-M) is NOT the same object;
this script measures fixed-M skew for direct comparison.

Step 3: forecast_cap = 20 in chapter15 config is a §4 nonlinearity. Paper §4
says any capping REDUCES max skew. Ablate cap=20 vs cap=9999 (effectively
uncapped) to quantify the §4 effect.

Output: ars/runs/<UTC>_martin_fixed_m_skew/ with summary CSV + plot + manifest.
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
CAPITAL = 50_000
VOL_TARGET_PCT = 20.0
HORIZONS_M = [1, 2, 5, 10, 20, 40, 60, 100, 150, 200, 250]
CAP_VARIANTS = [("cap20", 20.0), ("capINF", 9999.0)]
ROOT = Path(__file__).resolve().parent.parent
OUT_BASE = ROOT / "ars" / "runs"


def build_system(instrument: str, forecast_cap: float):
    cfg = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    cfg.instruments = [instrument]
    cfg.instrument_weights = {instrument: 1.0}
    cfg.instrument_div_multiplier = 1.0
    cfg.forecast_weights = {r: round(1/6, 6) for r in EWMAC_RULES}
    cfg.notional_trading_capital = CAPITAL
    cfg.percentage_vol_target = VOL_TARGET_PCT
    cfg.forecast_cap = forecast_cap
    return futures_system(config=cfg)


def fixed_m_skew(daily_returns: pd.Series, horizons) -> pd.DataFrame:
    """Non-overlapping M-day cumulative skew (Paper §2 fixed-M aggregation)."""
    r = daily_returns.dropna().values
    out = []
    for m in horizons:
        n = len(r) // m
        if n < 10:
            out.append((m, float("nan"), n)); continue
        blocks = r[: n * m].reshape(n, m).sum(axis=1)
        out.append((m, float(pd.Series(blocks).skew()), n))
    return pd.DataFrame(out, columns=["M_days", "skew", "n_blocks"])


def max_combined_forecast(system, instrument: str) -> float:
    fc = system.combForecast.get_combined_forecast(instrument).dropna()
    return float(fc.abs().max())


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_BASE / f"{ts}_martin_fixed_m_skew"
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    skew_tables = {}
    for instr in INSTRUMENTS:
        for variant_label, cap in CAP_VARIANTS:
            print(f"[run] {instr} cap={variant_label} (forecast_cap={cap}) ...")
            sys_ = build_system(instr, cap)
            acc = sys_.accounts.portfolio(roundpositions=True)
            daily = acc.percent.as_ts
            max_fc = max_combined_forecast(sys_, instr)
            skew_M = fixed_m_skew(daily, HORIZONS_M)
            skew_tables[(instr, variant_label)] = skew_M
            row = {
                "instrument": instr,
                "variant": variant_label,
                "forecast_cap": cap,
                "max_observed_combined_forecast": round(max_fc, 2),
                "cap_binding": max_fc >= cap * 0.99,  # cap is effectively active if max touches it
                "ann_return_pct": round(float(daily.fillna(0).sum()) / (len(daily) / 252), 3),
                "ann_vol_pct": round(float(daily.std()) * np.sqrt(252), 3),
                "daily_skew": round(float(daily.skew()), 3),
            }
            # add fixed-M skews to summary
            for _, sr in skew_M.iterrows():
                row[f"skew_M{int(sr['M_days'])}"] = round(sr["skew"], 3) if pd.notna(sr["skew"]) else None
            rows.append(row)
            print(f"  max_fc={max_fc:.2f}  cap_binding={row['cap_binding']}  daily_skew={row['daily_skew']}")
            print(skew_M.to_string(index=False))

    summary = pd.DataFrame(rows).set_index(["instrument", "variant"])
    summary.to_csv(out / "summary.csv")

    # Plot: skew vs M for each (instrument, variant)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
        for ax, instr in zip(axes, INSTRUMENTS):
            for variant_label, _ in CAP_VARIANTS:
                t = skew_tables[(instr, variant_label)]
                ax.plot(t["M_days"], t["skew"], marker="o",
                        label=f"{variant_label} (cap={20 if variant_label=='cap20' else 9999})")
            ax.axhline(0, color="k", lw=0.7)
            ax.set_title(f"{instr} — strategy fixed-M skew (non-overlapping)")
            ax.set_xlabel("M (days)")
            ax.set_ylabel("skew of M-day non-overlapping cumulative strategy return")
            ax.grid(True, alpha=0.3); ax.legend()
        # Paper §2 reference annotation
        axes[0].text(0.02, 0.95, "Paper §2 prediction:\n  skew → 0 at M=1\n  peak at finite M\n  decays as M^(-1/2)\n  EMA1 max ≈ 2.41, EMA2 max ≈ 2.1",
                     transform=axes[0].transAxes, fontsize=8, va="top",
                     bbox=dict(boxstyle="round", fc="lightyellow", ec="gray", alpha=0.85))
        fig.tight_layout()
        fig.savefig(out / "fixed_m_skew_term_structure.png", dpi=130)
        plt.close(fig)
    except Exception as e:
        print(f"[warn] plot failed: {e}")

    # Manifest
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"
    manifest = {
        "run_utc": ts,
        "purpose": "Step 2+3 post-review correction: fixed-M strategy skew (Paper Eq. 12 direct test) + cap=20 vs cap=INF ablation (§4 effect quantification)",
        "engine": "native pysystemtrade futures_chapter15",
        "git_sha": git_sha, "python": platform.python_version(),
        "instruments": INSTRUMENTS,
        "ewmac_rules": EWMAC_RULES,
        "capital_usd": CAPITAL,
        "vol_target_pct": VOL_TARGET_PCT,
        "horizons_M_days": HORIZONS_M,
        "cap_variants": dict(CAP_VARIANTS),
        "paper_predictions": {
            "skew_at_M1": "≈ 0",
            "skew_shape": "peak at finite M, decay as M^(-1/2)",
            "EMA1_max_skew_approx": 2.41,
            "EMA1_peak_at_M": "≈ 1.07 · N",
            "EMA2_max_skew_approx": 2.1,
            "EMA2_peak_at_M": "≈ 1.7 (N_alpha + N_beta)",
            "section_4_capping_effect": "any cap REDUCES max skew (sigmoid sigmoid, hard cap, or binary)",
        },
        "decision_log_anchor": "ars/DECISIONS.md#2026-05-29-post-review-correction",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print("\n=== SUMMARY ===")
    print(summary.to_string())
    print(f"\nOutputs: {out}")


if __name__ == "__main__":
    main()
