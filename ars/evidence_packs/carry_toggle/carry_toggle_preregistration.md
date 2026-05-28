# carry_toggle — Pre-registration

**Date written**: 2026-05-29 (BEFORE run)
**Owner**: Minsu Yeom · **Implementer**: Claude Opus 4.7
**Path**: A (genuine pre-registration; locked by the commit that creates this file)

Locked under `ars/PROMOTION.md`. Grid / gates / decision rules MUST NOT change after run-start.

## 1. Background

Martin (2023) §2.3 shows that pure-trend strategies (all a_j > 0) produce positively skewed trading returns. Adding a carry rule introduces non-trend components (potentially counter-trend in commodity backwardation/contango cycles), which Martin warns may flatten or even flip skew. This experiment tests the §2.3 assumption directly: enabling pysystemtrade's carry rule (chapter-15 default forecast scalar = 30, smooth_days = 90) at a non-trivial weight should be expected to (a) shift Sharpe (direction-unknown a priori) and (b) reduce per-trade skew if Martin §2.3 holds.

Single-decision change vs baseline: forecast weights now include carry at 0.30 (with EWMAC weights renormalised to sum 0.70 total).

## 2. Hypotheses

- **H-C1 (Sharpe direction-of-change)**: adding carry SHIFTS US10 Sharpe. Direction unknown ex-ante. Threshold for "shift" = `|delta| >= 0.03`. We are testing **whether** carry matters at single-instrument, not which direction is favourable.
- **H-C2 (skew degradation, primary)**: adding carry REDUCES US10 skew_per_trade. Threshold = `skew_per_trade_carry < skew_per_trade_baseline - 0.5`. PASS = Martin §2.3 supported.
- **H-C3 (lower-bound preservation)**: even with carry, US10 `skew_per_trade >= 1.0` (still long-option-shaped overall).
- **H-C4 (SP500 control)**: SP500 carry-on Sharpe `< 0.20`.

## 3. Grid

| Cell | Variant | EWMAC weights | Carry weight |
|---|---|---|---|
| cell-0 baseline | trend-only | equal 1/6 each (0.167) | 0.00 (off) |
| cell-1 carry-on | trend + carry | equal 0.117 each (0.70/6) | 0.30 |

Carry weight 0.30 chosen ex-ante (matches chapter-15 default for the carry rule in the bundled config). EWMAC weights renormalised to keep total = 1.0.

## 4. Gates

| Gate | Metric | Threshold | Verdict |
|---|---|---|---|
| G1 | US10 Sharpe shift | `|delta| >= 0.03` | carry materially affects Sharpe |
| G2 | US10 skew_per_trade reduction | `skew_carry < skew_baseline - 0.5` | Martin §2.3 confirmed |
| G3 | US10 skew_per_trade absolute | `>= 1.0` | long-option signature still present |
| G4 | SP500 carry-on Sharpe (control) | `< 0.20` | no false rescue |

Verdict types:
- **CONFIRMED** (Martin §2.3 supported): G2 PASS AND G3 PASS.
- **REFUTED** (skew NOT reduced): G2 FAIL.
- **DEGRADED** (skew destroyed below 1.0): G3 FAIL.

This experiment is an assumption-test, not a promotion candidate. No Path A/B; the outcome is informational and feeds into design for downstream experiments.

## 5. Data + 6. Code

- Source: shipped CSVs @ run-start SHA. Cutoff 2026-04-03.
- Runner: `scripts/momentum_variants_backtest.py` (shared).
