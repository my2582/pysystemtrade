> **EXTERNAL-REVIEW VERSION**: identifiers sanitised; quantitative metrics + paper citations preserved. See REVIEW_REQUEST.md for context.

# dmom_us10 — Evidence Pack (FALSIFIED)

**Status**: `falsified` (Path FALSIFY). Pre-registration locked at git `65c423bc` BEFORE run (genuine Path A pre-registration).

This is a first-class negative result. Per `ars/PROMOTION.md`,
falsified runs are preserved with the same evidence pack contents as
promoted runs so future agents can read the pre-registration, the
gates, and the recorded finding before re-running the same idea.

## Pre-registered finding (triggered verbatim)

> dMOM on single-instrument US10 trend does not enhance Sharpe and does not reduce crashes; the cross-sectional equity result does not transfer to a single rates futures contract.

## Why

Hanauer & Windmüller (2022) themselves report that the three vol-scaling overlays (cMOM, sMOM, dMOM) **reduce momentum crashes** but **do not consistently outperform plain MOM** in factor tests on cross-sectional equity. The crash-mitigation mechanism is specifically tuned to equity-style momentum crashes (sharp bull-trap reversals in bear+high-vol regimes). On a single rates futures (US10), the worst drawdowns come from sharp rate-reversal episodes whose timing is not predicted by the bear×market-vol regression — the US10 bear indicator (cumulative 24-mo back-adjusted price < 0) is dominated by the slow secular rate-down trend, not by the regime states that mattered in equity.

## Headline numbers (US10)

| Metric | baseline | dMOM | Δ | Gate verdict |
|---|---:|---:|---:|---|
| Sharpe (gross) | 0.347 | 0.364 | **+0.017** | G1 FAIL (< +0.10) |
| maxDD (geom %) | -55.35 | -56.39 | **-1.04** | G2 FAIL (not improving) |
| skew_per_trade | 4.382 | 5.461 | +1.08 | G3 PASS (≥ 1.0) |
| n_trades | 342 | 537 | +57% | (more trades from weight flips) |
| win_rate % | 23.4 | 36.3 | +13 | (winners are smaller on average) |

SP500 control: dMOM Sharpe -0.148 (PASS G4, no false rescue). SP500 dMOM produces a degenerate single-day outlier (skew_daily -106, maxDD clipped at -100%) — recorded as expected behaviour when applying a vol-divider scaler to a no-edge baseline, not as a finding.

## How to consume

- **If you are considering dMOM on single-instrument trend in this repo, READ THIS FIRST.** The result is clear; do not retry with parameter tweaks. The structural reason (no equity-style momentum crash on rates) won't be fixed by lookback changes.
- **The Hanauer paper is still useful** — its `sMOM` (semi-vol scaling, no regime model) is a lower-bar alternative that could be tested next. `cMOM` is just standard constant vol targeting, which pysystemtrade already does.
- **Cross-sectional dMOM** (across Bund/BOBL/OAT/JGB/KR10/US2/US5/US20/US30) is a different experiment family. Not falsified by this run. Not in this repo's L2 scope at present.

## Files

| File | What |
|---|---|
| `dmom_us10_preregistration.md` | Hypotheses + gates + decision rules locked at `65c423bc` |
| `manifest_runsrc.json` | Reproducibility manifest from the run dir |
| `verdict.json` | Machine-readable per-gate PASS/FAIL + `status: falsified` |
| `report.html` / `report.pdf` | ARS Tier-1 run report |
| `README.md` | This file |

CPC v1 (`ars/PROMOTION.md` Tier-2b) is waived for falsified runs.

## Downstream pointers

- Run dir: `ars/runs/20260528T173334Z_dmom_us10/`
- Registry: `ars/runs/registry.yaml` (id `20260528T173334Z_dmom_us10`, status `falsified`)
- Decision log: `ars/DECISIONS.md` (2026-05-29 dmom_us10 FALSIFIED entry)
- Pre-registration commit: `65c423bc`
- Code: `scripts/dmom_overlay_backtest.py`
- Literature: `references/research/Enhanced Momentum Strategies.pdf`
