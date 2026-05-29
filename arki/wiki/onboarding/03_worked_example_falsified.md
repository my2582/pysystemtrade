# 03 — Worked example: `dmom_us10` (falsified, framework's first true Path A)

**Prerequisite**: [02_worked_example_promoted.md](02_worked_example_promoted.md). **Time**: ~5 minutes.

This is the framework's FIRST genuine pre-registered (Path A) experiment. Pre-registration was committed at `65c423bc` BEFORE any code ran. The result triggered the pre-registered FALSIFY rule. The negative result is preserved as a first-class artifact.

## What was tested

Hanauer & Windmüller (2022) dynamic-scaled momentum (dMOM, Daniel-Moskowitz 2016) overlay on the Martin baseline.

```
w_dMOM,t = (1 / 2λ) · μ̂_t / σ̂²_strategy,t

μ̂_t from expanding-window OLS:
    R_MOM,t = γ0 + γ_int · I_Bear,t-1 · σ²_RMRF,t-1 + ε_t
```

Applied to US10 (primary) and SP500 (control). Pre-registered hypotheses:

- **H-D1 (Sharpe lift, primary)**: dMOM lifts US10 Sharpe by ≥ +0.10.
- **H-D2 (crash reduction, primary)**: dMOM improves US10 maxDD by ≥ +5.0 pp.
- **H-D3 (skew preservation)**: US10 dMOM `skew_per_trade ≥ 1.0`.
- **H-D4 (SP500 control)**: SP500 dMOM Sharpe `< 0.20` (no false rescue).

Pre-registered FALSIFY rule: G3 FAIL (skew destroyed) OR (G1 AND G2 both FAIL).

## What happened

| Gate | Threshold | Observed | Verdict |
|---|---|---|---|
| G1 Sharpe lift | ≥ +0.10 | **+0.017** | **FAIL** |
| G2 maxDD improvement | ≥ +5.0 pp | **−1.04 pp** (worse) | **FAIL** |
| G3 skew_per_trade | ≥ 1.0 | +5.46 | PASS |
| G4 SP500 control | < 0.20 | -0.148 | PASS |
| G_recon | overlay = R_baseline × w | 0.00 | PASS |

**Verdict text**: G1 AND G2 both FAIL → pre-registration §4 FALSIFY rule triggers. Status: `falsified`. Promotion path: FALSIFY.

**Finding (triggered verbatim from pre-reg §4)**: "dMOM on single-instrument US10 trend does not enhance Sharpe and does not reduce crashes; the cross-sectional equity result does not transfer to a single rates futures contract."

## Why this matters as a template

1. **Pre-registration was true Path A**. Locked at git SHA `65c423bc` BEFORE any code in `scripts/dmom_overlay_backtest.py` ran. The framework's first GENUINE application.

2. **Falsification rule was pre-registered**. The trigger condition "G1 AND G2 both FAIL → falsified" was written in section 4 of the pre-registration, NOT after the fact. The result fell exactly into the pre-registered trap.

3. **Result is consistent with the source paper**. Hanauer & Windmüller (2022) §3 explicitly concludes dMOM is "a crash-mitigator, not a return-booster"; in this single-instrument context the crash mitigation also failed to appear. The falsification is the paper's own message, surfaced empirically.

4. **The evidence pack was still populated**. Negative results are first-class:
   ```
   ars/evidence_packs/dmom_us10/
   ├── dmom_us10_preregistration.md       ← locked at 65c423bc
   ├── manifest_runsrc.json               ← provenance
   ├── verdict.json                       ← status: falsified
   ├── report.html, report.pdf
   └── README.md                          ← finding text + how to consume
   ```
   The README explicitly tells future agents: "If you are considering dMOM on single-instrument trend in this repo, READ THIS FIRST. The result is clear; do not retry with parameter tweaks."

## Implementation gotcha to remember

The dMOM pre-registration did NOT declare an upper bound on `|w_dMOM,t|`. This was acceptable for dMOM because the regression on `I_Bear · σ²_RMRF` is bounded by construction. BUT — the sister experiment `sMOM` used the SAME pattern (no bound) and the bound assumption FAILED. See LESSONS 2026-05-29 "sMOM unbounded weight."

**Going forward**: every multiplicative weight series declares its bound at pre-registration. dMOM was lucky; sMOM was not. The bound declaration is now mandatory.

## What to take away

| When this happens to your experiment | Do this |
|---|---|
| Pre-registered FALSIFY rule triggers | Status → `falsified`. Write the finding text in the registry entry. Populate the evidence pack. Move on. |
| You're tempted to "adjust the threshold" post-hoc | DON'T. The threshold was the contract. Adjusting it after seeing data is overfitting (López de Prado AFML Ch.3). |
| You're tempted to skip the evidence pack because "it failed" | DON'T. Falsified runs are first-class artifacts. Next AI session needs the finding. |
| The result is consistent with the source paper's caveats | Note this explicitly. It strengthens the finding. |

## Next

→ [04_lessons_distilled.md](04_lessons_distilled.md)
