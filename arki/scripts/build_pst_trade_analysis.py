"""pysystemtrade trade-analysis report — starter wrapper around `ata`.

Built using the Carver chapter-15 canonical futures system as the demo system.
Trade unit = position roundtrip (`0 → non-0 → 0`).

Outputs (under arki/results/<date>/<slug>_trade_analysis/):
  pst_chapter15_trades.xlsx           trade ledger (one row per roundtrip)
  pst_chapter15_trade_report.html     self-contained report
  candles/trade_NNNN_<INSTR>.png      per-trade close-only LINE chart
  equity_curve.csv                    daily system NAV
  (no SGD companion — futures account is dollar-native)

Quick-start (from this repo's venv):
    pip install -e ~/Developer/arki-trade-analysis
    python arki/scripts/build_pst_trade_analysis.py
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from ata import ReportConfig, build_report
from ata.adapters.pysystemtrade import PysystemtradeAdapter, pst_nav_loader
from ata.adapters.pysystemtrade_prices import PysystemtradePriceStore

from systems.provided.futures_chapter15.basesystem import futures_system


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TODAY = date.today().isoformat()
OUT_DIR = PROJECT_ROOT / f"arki/results/{TODAY}/pst_chapter15_trade_analysis"


SPEC_BOX = r"""<div class="spec-box">
<h3>Strategy spec — pysystemtrade futures_chapter15 (Carver baseline)</h3>
<div class="row">
  System: <code>systems.provided.futures_chapter15.basesystem.futures_system</code>
  — canonical Robert Carver "Systematic Trading" chapter-15 example with
  EWMAC + carry rules, post-buffer portfolio positions, CSV-backed sim data.
</div>
<div class="row">
  Trade unit: <strong>position roundtrip</strong> (`0 → non-0 → 0`). A sign
  flip without crossing zero counts as ONE trade (the position never closed).
  Source position series = <code>system.accounts.get_actual_position(instr)</code>
  (post-inertia buffered position — what would actually trade).
</div>
<div class="row">
  Equity curve = <code>system.accounts.portfolio().percent</code> compounded
  to a normalized NAV (1.0 base). Per-trade <em>realized_return_pct</em> is
  PRICE-RELATIVE (exit/entry − 1) — informational only for futures. The
  authoritative system NAV (above) drives equity chart + perf metrics.
</div>
<div class="row">
  Candle charts: futures prices are CLOSE-only in pysystemtrade
  (sysobjects.adjusted_prices), so the renderer falls back to a LINE chart
  with the entry/exit markers preserved.
</div>
</div>"""


def main() -> None:
    print("[init] building futures_chapter15 system ...")
    system = futures_system()

    # Bound the work for the smoke test — full chapter15 universe is 39
    # instruments. The CSV sim data shipped with this clone only carries data
    # for a subset; the list below was confirmed available via a one-off
    # `system.get_instrument_list()` + `accounts.get_actual_position()` probe
    # on 2026-05-29. For broader runs, replace with `system.get_instrument_list()`
    # and let the adapter `skipped` counter absorb missing-data ones.
    instruments = ["CORN", "EUROSTX", "MXP", "SOFR", "US10", "V2X"]

    config = ReportConfig(
        title="pysystemtrade futures_chapter15",
        slug="pst_chapter15",
        out_dir=OUT_DIR,
        trade_provider=PysystemtradeAdapter(
            system=system,
            position_source="buffered",
            instruments=instruments,
        ),
        ohlc_store=PysystemtradePriceStore(system=system),
        nav_loader=pst_nav_loader(system),
        nav_col="",
        benchmark_col=None,
        benchmark_label="Buy-and-hold (n/a)",
        baseline_commit="local",
        baseline_tag=f"pst-chapter15-{TODAY}",
        analysis_start=pd.Timestamp("2000-01-01"),
        eras=[
            ("Post-2010", pd.Timestamp("2010-01-01"), pd.Timestamp("2099-12-31")),
            ("Post-2020", pd.Timestamp("2020-01-01"), pd.Timestamp("2099-12-31")),
        ],
        n_holdings=len(instruments),
        report_date=TODAY,
        boot_block=10,
        boot_b=500,  # smaller B for quick smoke test; bump to 2000 for production
        ars_seed=20260529,
        sgd_conversion=False,
        spec_box_html=SPEC_BOX,
        sleeve_label="System",
    )

    build_report(
        config,
        header_meta_extra=(
            f"System: <code>futures_chapter15</code> · "
            f"instruments: {len(instruments)} ({', '.join(instruments)}) · "
            "OHLC source: <code>system.data.get_adjusted_prices(instr)</code> "
            "(close-only — candles fall back to line charts) · "
            "NAV: <code>system.accounts.portfolio().percent</code>"
        ),
        perf_era_note="Era order: Post-2010 (representative), Post-2020 (recent regime).",
    )


if __name__ == "__main__":
    main()
