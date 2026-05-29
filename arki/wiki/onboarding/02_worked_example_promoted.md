# 02 — Worked example: `martin_single_instrument` (promoted post-hoc)

**Prerequisite**: [01_lifecycle.md](01_lifecycle.md). **Time**: ~10 minutes.

This is the framework's FIRST registry entry. It was POST-HOC (Path Z) — grandfathered as a one-time exception because the framework itself was being adopted in the same session. Future runs MUST be true Path A (pre-registration committed before run-start). But the structure of the artifacts is what to copy.

## What the experiment tested

Martin (2023) "Design and analysis of momentum trading strategies." Hypotheses (reconstructed post-hoc):

- **H-M3 (§2.3 implication)**: A multi-speed EWMAC pure-trend strategy with all `a_j > 0` produces per-trade returns whose skew is materially larger than the daily strategy-return skew.
- **H-M4 (§3 long-option signature)**: Low win rate + strong positive trade skew on US10.
- **H-M5 (Sharpe ceiling)**: US10 strategy gross Sharpe in `[0.2, 0.6]`, refuting prior 0.7-1.0 claim.

Two earlier hypotheses (H-M1, H-M2) attempted to verify "Martin Fig 1 sign contrast." Post-review (2026-05-29) these were RETRACTED as misreadings: paper's central thesis is that trading-return skew is a strategy-design product, NOT an asset property. The Figure-citation was a slogan.

## Files you should be able to navigate to

```
ars/evidence_packs/martin_single_instrument/
├── martin_single_instrument_preregistration.md  ← POST-HOC, see disclosure at top
├── manifest_runsrc.json                          ← run-time provenance
├── verdict.json                                  ← machine-readable verdict
├── report.html, report.pdf                       ← ARS Tier-1 report
└── README.md                                     ← summary + how to consume

ars/runs/20260528T161350Z_martin_single_instrument/
├── manifest.json                                 ← AUTHORITATIVE provenance
├── summary.csv                                   ← headline metrics
├── verdict.json                                  ← same content as evidence pack
├── report.html, report.pdf                       ← rendered
├── equity_curve.png, trade_dist.png, fig1_market_skew.png  ← figures
├── equity_curves.csv, market_skew_term_structure.csv       ← data
└── trades_US10.csv, trades_SP500.csv                       ← per-trade ledger
```

## Headline numbers (US10, baseline)

| Metric | Value | Reading |
|---|---|---|
| Sharpe (gross) | 0.396 | Refutes prior 0.7-1.0 claim ✓ |
| Skew per trade | +4.382 | Long-option signature confirmed ✓ |
| Win rate | 23.4% | Low — most trades lose, few big winners drive return ✓ |
| Annual return / vol | 8.87% / 22.43% | Vol-target 20% achieved |
| Max DD (geometric) | -55.35% | Real risk; framework reports compounded, not additive cumsum |

## The single most important framework artifact

The Mechanism cheatsheet card in `arki/cheatsheets/2026-05-29_arki_single_instrument_momentum_studies.html`, "M — Mechanism cheatsheets" → "Martin baseline — 6-speed EWMAC pure trend."

This card tells you EVERYTHING in 3 sub-sections:

1. **Core formula tested**: `F_k,t = (EMA_fast,k(P_t) − EMA_slow,k(P_t)) / σ̂_t`, then `F_combined,t = clip(Σ w_k · scalar_k · F_k,t, ±20)`. Six speeds: {2_8, 4_16, 8_32, 16_64, 32_128, 64_256}. Equal weight 1/6 each.
2. **Triggering condition**: continuous, daily. Position = round(F/10 × capital × vol_target / instr_value_vol).
3. **Action table**: trade shape, observation date, trade date, between-trade behavior, leverage cap, re-entry rule.

If you can reproduce the headline numbers from JUST this card (plus the data path), the card is doing its job. If you cannot, the card has a spec gap and needs updating.

## Post-hoc corrections you should know about

A reviewer (2026-05-29) caught five specific misreadings:

1. **Asset attribution**: I read "US10 market skew positive → rates good for trend" as evidence. Paper §1 explicit thesis is the opposite — skew is a strategy-design product, NOT an asset property. Verdicts G1/G2 (Fig 1 sign contrast) were RETRACTED from "Martin §2.3 validation" to "context reproduction."

2. **Assumption-set check**: Paper §2 assumes `κ_3(U_n) = 0`. SP500 baseline has `κ_3(U) ≈ -0.25` — assumption violated. SP500 results are valid context, NOT a refutation of §2.3 (out of paper's assumption set).

3. **forecast_cap=20 is §4 nonlinearity**: Paper §4 says ANY cap reduces max skew. We had framed `±20` as "Martin-compliant"; this is REVERSED. The baseline is `linear + §4 capping`, not pure §2.3 linear.

4. **`skew_per_trade` ≠ §2.3 fixed-M skew**: Sign-episode aggregation is variable-M; paper's Eq. 12 closed-form is fixed-M. Different objects.

5. **`EWMAC = Martin EMA2` is approximate**: EWMAC = EMA difference of price LEVELS; paper EMA2 = EMA difference of price CHANGES. Both inside linear class, different a_j. The variational optimum `te^(-α̇t)` is a SINGLE Laguerre kernel, not a 6-pair stack.

These corrections live in `ars/DECISIONS.md` (2026-05-29 post-review correction section) and `ars/LESSONS.md` ("Fig-as-slogan" lesson). Future pre-registrations MUST cite `paper + section + equation + assumption_set` per the gates schema.

## What to copy when starting a new experiment

- Pre-registration file structure (sections 1-6).
- The manifest.json field layout.
- The Mechanism cheatsheet card template.
- The way the verdict text traces to numbered gates.

What NOT to copy:

- The POST-HOC disclosure (only Martin gets that pass).
- The Figure-citation pattern (FORBIDDEN; cite section + equation only).
- The "Martin-compliant" framing of forecast_cap (REVERSED; cap is §4).

## Next

→ [03_worked_example_falsified.md](03_worked_example_falsified.md)
