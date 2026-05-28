# smom_us10 — Pre-registration

**Date written**: 2026-05-29 (BEFORE run)
**Owner**: Minsu Yeom · **Implementer**: Claude Opus 4.7
**Path**: A (genuine pre-registration; locked by the commit that creates this file)

Locked under `ars/PROMOTION.md`. Grid / gates / decision rules MUST NOT change after run-start.

## 1. Background

Wang & Yan (2021) semi-volatility-scaled momentum (sMOM), per Hanauer & Windmüller (2022) eq. 4-5:

```
w_sMOM,t = sigma_target / sigma_hat_semi,t
sigma_hat_semi^2,t = (21 / 126) * sum_{j=1..126} R_{MOM,d-j}^2 * I{R_{MOM,d-j} < 0}
```

Pure downside-variance scaler. Simpler than dMOM (no regime model). cMOM equivalent is already pysystemtrade's standard vol targeting; sMOM is the strict downside variant.

Single-instrument adaptation: target_sigma = baseline full-sample std (closed-form so std(R_sMOM) == std(R_MOM)). Applied as multiplicative scaler on baseline daily returns.

## 2. Hypotheses

- **H-S1 (Sharpe lift, primary)**: sMOM lifts US10 gross Sharpe vs baseline. Threshold = **+0.05** (lower than dMOM's +0.10 because sMOM is a structurally weaker scaler).
- **H-S2 (crash reduction)**: sMOM reduces US10 geometric maxDD vs baseline. Threshold = **+3.0 pp better**.
- **H-S3 (skew preservation)**: `skew_per_trade >= 1.0` on US10.
- **H-S4 (SP500 control)**: SP500 sMOM Sharpe `< 0.20`.
- **H-S_recon**: overlay reconciliation `|sum diff| ~ 0`.

## 3. Grid

| Cell | Variant | Notes |
|---|---|---|
| cell-0 baseline | Martin 6-speed EWMAC | from martin_single_instrument evidence pack |
| cell-1 sMOM | cell-0 + sMOM multiplicative scaler | US10 + SP500 |

Constants (FIXED): semi-vol lookback 126 trading days, vol-match target = baseline full-sample std (closed-form lambda).

## 4. Gates

| Gate | Metric | Threshold | Verdict on PASS |
|---|---|---|---|
| G1 | US10 Sharpe lift | `>= +0.05` | sMOM enhances Sharpe |
| G2 | US10 maxDD improvement | `>= +3.0 pp better` | sMOM reduces crashes |
| G3 | US10 sMOM skew_per_trade | `>= 1.0` | skew preserved |
| G4 | SP500 sMOM Sharpe | `< 0.20` | no false rescue |
| G_recon | `|sum(R_sMOM) - sum(R_MOM * w_sMOM)|` | `< 1%` | overlay clean |

Path A (strict): G1 AND G2 AND G3 AND G_recon PASS.
Path B (crash-only): G2 AND G3 AND G_recon PASS, G1 may fail.
FALSIFY: G3 FAIL, OR (G1 AND G2 both FAIL).
INVESTIGATE: G4 FAIL.

## 5. Data snapshot

- Source: `data/futures/adjusted_prices_csv/{US10,SP500}.csv` @ run-start git SHA.
- Cutoff: 2026-04-03.

## 6. Code snapshot

- Runner: `scripts/momentum_variants_backtest.py` (shared with fast_tilt + carry_toggle).
- Python: 3.10.15. Engine: native `futures_chapter15`.
