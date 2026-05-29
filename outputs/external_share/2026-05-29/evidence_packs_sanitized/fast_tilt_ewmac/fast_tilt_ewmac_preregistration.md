> **EXTERNAL-REVIEW VERSION**: identifiers sanitised; quantitative metrics + paper citations preserved. See REVIEW_REQUEST.md for context.

# fast_tilt_ewmac — Pre-registration

**Date written**: 2026-05-29 (BEFORE run)
**Owner**: <owner> · **Implementer**: Claude Opus 4.7
**Path**: A (genuine pre-registration; locked by the commit that creates this file)

Locked under `ars/PROMOTION.md`. Grid / gates / decision rules MUST NOT change after run-start.

## 1. Background

Carver (qoppac blog) and Martin (2023) both note that small-AUM operators have a speed advantage: they can run faster signals than large CTAs because their costs do not scale with size. The Martin baseline uses equal weights across 6 EWMAC speeds; this experiment tilts toward the fast end (ewmac2_8, ewmac4_16) at the cost of the slow end (ewmac32_128, ewmac64_256).

Single-decision change vs baseline: forecast weights only. Same 6 rules, same vol target, same instrument config.

## 2. Hypotheses

- **H-F1 (Sharpe lift, primary)**: Fast-tilt lifts US10 gross Sharpe vs baseline. Threshold = **+0.05**.
- **H-F2 (turnover increase, expected cost)**: Fast-tilt raises subsystem turnover. Threshold = `turnover * 1.5` directionally; not a gate, just a recorded cost.
- **H-F3 (skew preservation)**: `skew_per_trade >= 1.0` (faster signals should peak skew at smaller M, so trade-level skew remains positive though potentially smaller magnitude per Martin §2.3 M^(-1/2) decay).
- **H-F4 (SP500 control)**: SP500 fast-tilt Sharpe `< 0.20`.

## 3. Grid

| Cell | Variant | ewmac2_8 | ewmac4_16 | ewmac8_32 | ewmac16_64 | ewmac32_128 | ewmac64_256 |
|---|---|---|---|---|---|---|---|
| cell-0 baseline | equal | 1/6 | 1/6 | 1/6 | 1/6 | 1/6 | 1/6 |
| cell-1 fast-tilt | linear decay | 0.30 | 0.25 | 0.20 | 0.15 | 0.07 | 0.03 |

Weights chosen ex-ante by linear-decay heuristic (no fit to result). Sum to 1.00.

## 4. Gates

| Gate | Metric | Threshold | Verdict |
|---|---|---|---|
| G1 | US10 Sharpe lift vs baseline | `>= +0.05` | small-AUM speed edge confirmed |
| G2 | US10 skew_per_trade | `>= 1.0` | long-option preserved |
| G3 | SP500 Sharpe (control) | `< 0.20` | no false rescue |
| G_recon | sub-system turnover recorded | none (informational) | cost paid |

Path A: G1 AND G2 PASS.
FALSIFY: G2 FAIL (skew destroyed) OR G1 FAIL by more than -0.03 (faster is worse).

## 5. Data + 6. Code

- Source: shipped CSVs @ run-start SHA. Cutoff 2026-04-03.
- Runner: `scripts/momentum_variants_backtest.py` (shared).
