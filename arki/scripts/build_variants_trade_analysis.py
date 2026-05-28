"""Trade-analysis reports for the 3 new variants × US10, SP500 = 6 reports.

Variants:
  - smom: baseline trades (sign(w_sMOM) always positive), system NAV overlaid by sMOM scaler.
  - fast_tilt_ewmac: linear-decay forecast weights toward fast EWMAC speeds (NEW positions, NEW trades).
  - carry_toggle: enable carry rule at weight 0.30 (NEW positions, NEW trades).

Pre-registrations (locked at commit 28e4b629 + the subsequent pre-reg commit):
  ars/evidence_packs/{smom_us10, fast_tilt_ewmac, carry_toggle}/*_preregistration.md

Output dirs: arki/results/2026-05-29/<slug>_trade_analysis/
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ata import ReportConfig, build_report
from ata.adapters.pysystemtrade import PysystemtradeAdapter
from ata.adapters.pysystemtrade_prices import PysystemtradePriceStore

from sysdata.config.configdata import Config
from systems.provided.futures_chapter15.basesystem import futures_system

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TODAY = date.today().isoformat()
RESULTS_BASE = PROJECT_ROOT / f"arki/results/{TODAY}"

EWMAC_RULES = ["ewmac2_8", "ewmac4_16", "ewmac8_32",
               "ewmac16_64", "ewmac32_128", "ewmac64_256"]
CAPITAL = 50_000
VOL_TARGET_PCT = 20.0
SMOM_LOOKBACK = 126


def _base_config(instr: str) -> Config:
    cfg = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
    cfg.instruments = [instr]
    cfg.instrument_weights = {instr: 1.0}
    cfg.instrument_div_multiplier = 1.0
    cfg.notional_trading_capital = CAPITAL
    cfg.percentage_vol_target = VOL_TARGET_PCT
    return cfg


def build_baseline(instr): cfg = _base_config(instr); cfg.forecast_weights = {r: round(1/6, 6) for r in EWMAC_RULES}; return futures_system(config=cfg)
def build_fast_tilt(instr): cfg = _base_config(instr); cfg.forecast_weights = {"ewmac2_8":0.30, "ewmac4_16":0.25, "ewmac8_32":0.20, "ewmac16_64":0.15, "ewmac32_128":0.07, "ewmac64_256":0.03}; return futures_system(config=cfg)
def build_carry(instr): cfg = _base_config(instr); ew = round(0.70/6, 6); cfg.forecast_weights = {**{r: ew for r in EWMAC_RULES}, "carry": 0.30}; return futures_system(config=cfg)


def smom_weight(R: pd.Series, lookback: int) -> pd.Series:
    R = R.fillna(0)
    downside_sq = (R**2).where(R < 0, 0)
    semi_var = downside_sq.rolling(lookback, min_periods=30).mean().where(lambda s: s > 1e-12)
    target_var = float((R**2).mean())
    raw_w = (np.sqrt(target_var) / np.sqrt(semi_var)).replace([np.inf, -np.inf], np.nan)
    Rw = (R * raw_w.fillna(0))
    lam = float(np.sqrt(Rw.var() / R.var())) if R.var() > 0 and Rw.var() > 0 else 1.0
    return raw_w / lam


def smom_nav_loader(system):
    """NAV loader for sMOM: baseline daily returns scaled day-by-day by w_sMOM, compounded.
    Returns (nav_series, benchmark_or_None) tuple per ata NavLoader protocol."""
    def loader():
        acc = system.accounts.portfolio(roundpositions=True)
        daily = acc.percent.as_ts.fillna(0)
        w = smom_weight(daily, SMOM_LOOKBACK)
        R = (daily * w).fillna(0)
        nav = (1.0 + R/100.0).cumprod()
        nav.index = pd.to_datetime(nav.index)
        return nav, None
    return loader


def baseline_nav_loader(system):
    def loader():
        acc = system.accounts.portfolio(roundpositions=True)
        curve_pct = acc.percent.curve()
        nav = (1.0 + pd.Series(curve_pct).ffill() / 100.0).dropna()
        nav.index = pd.to_datetime(nav.index)
        return nav, None
    return loader


SPEC_SMOM = """<div class="spec-box">
<h3>Strategy spec — Martin baseline + sMOM overlay (PROMOTED 2026-05-29)</h3>
<div class="row"><b>Trades are identical to Martin baseline</b> because sign(w_sMOM,t) is always positive (downside-vol scaler never flips). Per-trade ledger therefore matches baseline; system NAV (top of report) is sMOM-overlaid and reflects the +0.255 Sharpe lift.</div>
<div class="row">w_sMOM,t = sqrt(target_var) / sqrt(semi_var_126d), normalised so std(R_sMOM) = std(R_baseline) ex-post (closed-form lambda).</div>
<div class="row">Evidence pack: ars/evidence_packs/smom_us10/ · pre-reg locked at 28e4b629.</div>
</div>"""

SPEC_FAST_TILT = """<div class="spec-box">
<h3>Strategy spec — Fast-tilt EWMAC (FALSIFIED 2026-05-29)</h3>
<div class="row">Linear-decay forecast weights: ewmac2_8 0.30, 4_16 0.25, 8_32 0.20, 16_64 0.15, 32_128 0.07, 64_256 0.03. Sum = 1.00. Carry OFF.</div>
<div class="row">US10 Sharpe lift -0.155 (FAILS pre-registered -0.03 floor); turnover +66% (485 -> 806 trades). Small-AUM speed advantage does not materialise in transaction-cost-free integer-contract sim.</div>
<div class="row">Evidence pack: ars/evidence_packs/fast_tilt_ewmac/ · pre-reg locked at 28e4b629.</div>
</div>"""

SPEC_CARRY = """<div class="spec-box">
<h3>Strategy spec — Trend + Carry on (REFUTED Martin §2.3 implication 2026-05-29)</h3>
<div class="row">EWMAC weights renormalised to 0.70 total (0.117 each), carry weight 0.30. Otherwise identical to Martin baseline.</div>
<div class="row">US10 Sharpe lift +0.090; skew_per_trade 5.35 -> 7.34 (INCREASE; carry on rates is itself positively-skewed via roll yield). Single-instrument finding.</div>
<div class="row">Evidence pack: ars/evidence_packs/carry_toggle/ · pre-reg locked at 28e4b629.</div>
</div>"""


def build_one(system, instrument, slug, spec_html, nav_loader):
    out = RESULTS_BASE / f"{slug}_trade_analysis"
    adapter = PysystemtradeAdapter(system=system, position_source="buffered", instruments=[instrument])
    cfg = ReportConfig(
        title=f"pysystemtrade {slug}", slug=slug, out_dir=out,
        trade_provider=adapter,
        ohlc_store=PysystemtradePriceStore(system=system),
        nav_loader=nav_loader,
        nav_col="",
        benchmark_col=None, benchmark_label="Buy-and-hold (n/a)",
        baseline_commit="local", baseline_tag=f"{slug}-{TODAY}",
        analysis_start=pd.Timestamp("1985-01-01"),
        eras=[
            ("Post-2000", pd.Timestamp("2000-01-01"), pd.Timestamp("2099-12-31")),
            ("Post-2015", pd.Timestamp("2015-01-01"), pd.Timestamp("2099-12-31")),
        ],
        n_holdings=1, report_date=TODAY,
        boot_block=10, boot_b=500, ars_seed=20260529,
        spec_box_html=spec_html,
    )
    build_report(cfg)
    return out


def main():
    runs = []
    for instr in ["US10", "SP500"]:
        # sMOM: baseline system, sMOM NAV
        base_sys = build_baseline(instr)
        slug = f"smom_{instr.lower()}"
        print(f"\n[trade-analysis] {slug}")
        out = build_one(base_sys, instr, slug, SPEC_SMOM, smom_nav_loader(base_sys))
        runs.append((slug, out))

        # fast-tilt: new system, native NAV
        ft_sys = build_fast_tilt(instr)
        slug = f"fast_tilt_{instr.lower()}"
        print(f"\n[trade-analysis] {slug}")
        out = build_one(ft_sys, instr, slug, SPEC_FAST_TILT, baseline_nav_loader(ft_sys))
        runs.append((slug, out))

        # carry: new system, native NAV
        carry_sys = build_carry(instr)
        slug = f"carry_{instr.lower()}"
        print(f"\n[trade-analysis] {slug}")
        out = build_one(carry_sys, instr, slug, SPEC_CARRY, baseline_nav_loader(carry_sys))
        runs.append((slug, out))

    print("\n=== built ===")
    for slug, out in runs:
        print(f"  {slug}: {out}")


if __name__ == "__main__":
    main()
