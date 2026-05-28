# martin_single_instrument — Evidence Pack

**Status**: `promoted_post_hoc` (Path Z) — framework's first registry entry, grandfathered as one-time post-hoc registration. See `martin_single_instrument_preregistration.md` for the disclosure.

## What this is

Reproduces Martin (2023) Fig 1 sign contrast (rates vs equity market-return skew term structure) AND validates Martin §2.3 (pure-trend → positive trading-return skew) + §3 (long-option signature), using the native pysystemtrade `futures_chapter15` engine restricted to a single instrument at $50k notional with integer contracts.

5/5 headline gates PASS. Reconciliation `|diff_pct| < 5%` on both instruments.

## Headline

| Metric | US10 (rates) | SP500 (equity) |
|---|---:|---:|
| Sharpe (gross / net) | 0.396 / 0.350 | -0.005 / -0.009 |
| Ann return / vol (gross) | 8.87 / 22.43 | -0.11 / 24.53 |
| maxDD (geom) | -55.35 % | -85.04 % |
| skew (daily) | +0.18 | -1.99 |
| **skew (per trade)** | **+4.38** | **+4.33** |
| market skew @ M=60 | +0.20 (peak +0.24 @ M=40) | -0.04 (negative for M=1..40, 100..250) |
| n_trades / win % | 342 / 23.4 | 335 / 19.7 |

## How to consume

- **Statistical decision (downstream)**: this evidence pack is L2-level (Backtest runner). Downstream repos that wish to act on it must run their own L5+ promotion process; this pack is the input.
- **Per-trade skew on US10** (+4.38) is the headline finding for any rates-trend strategy considering single-instrument deployment. Median trade is slightly negative (-1.12 %); few large winners drive the +349 % additive cumulative return.
- **SP500 is NOT viable as a single-instrument trend** (Sharpe ≈ 0, daily skew strongly negative).
- **Sharpe ceiling refuted**: prior deep-research claim of 0.7-1.0 single-instrument Sharpe is wrong; the realistic range is 0.3-0.4 and the actual product is positive trade-level skew, not Sharpe.

## Files

| File | What |
|---|---|
| `martin_single_instrument_preregistration.md` | Locked hypothesis + grid + gates (POST-HOC, see disclosure) |
| `manifest_runsrc.json` | Reproducibility manifest from the run dir (git SHA, python, config) |
| `verdict.json` | Machine-readable per-gate PASS/FAIL + headline metrics |
| `report.html` / `report.pdf` | ARS Tier-1 run report (Arki Green template) |
| `README.md` | This file |

## Downstream pointers

- Run dir: `ars/runs/20260528T161350Z_martin_single_instrument/`
- Registry: `ars/runs/registry.yaml` (id `20260528T161350Z_martin_single_instrument`)
- Decision log: `ars/DECISIONS.md` (2026-05-29 entry)
- Code: `scripts/martin_single_instrument_backtest.py` @ git `5fa88c4c`
- Template + renderer: `arki/templates/ars_run_report.html`, `scripts/ars_report.py`
