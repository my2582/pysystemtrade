# Pre-registration — carry_primary_us10 (paper-family-exit experiment)

**Path:** A (single-instrument confirmatory, no parameter search beyond the
declared internal grid).
**Author:** Minsu Yeom (Arki Finance), 2026-05-31.
**Status:** LOCKED on commit of this file. Runner pending.
**Family:** futures_momentum (Panel A, single_instrument).
**Handoff origin:** docs/arki/handoff_session_retrospective_cheatsheet_2026-05-31.md
item E — deliberately anchored OUTSIDE the canonical paper family
{Martin 2023, Hanauer 2022, Wang-Yan 2021, Daniel-Moskowitz 2016,
Barroso-Santa-Clara 2015, Carver, López de Prado}. The point of this cell is
NOT to find alpha; it is to stress-test whether the family schema bends or
breaks under a non-EWMAC, non-skew thesis (see §8).

---

## 1. Thesis + literature anchor

**Primary anchor (non-canonical):** Koijen, Moskowitz, Pedersen & Vrugt (2018),
"Carry", *Journal of Financial Economics* 127(2), 197-225.

- §1 Eq.(1): an asset's *carry* is its return assuming prices do not change —
  the model-free expected-return component observable today. For a futures
  contract, §2 Eq.(2) defines carry as the slope between the front and next
  contract, scaled by the time to expiry: `carry_t = (F_near − F_far) / (F_far · Δτ)`.
- §3 claim: carry is a robust *primary* return predictor across asset classes
  (bonds, equities, commodities, FX, rates), distinct from momentum and value.
- §4 claim: carry strategies earn a premium that is partly compensation for
  global recession / liquidity risk (a different risk source than the
  positive-skew long-option payoff that anchors the rest of this family).

This is intentionally a DIFFERENT return source than the family's Martin-2023
positive-skew momentum thesis. In the current schema `carry` exists only as a
LEVEL of the `overlay` axis (a crash-mitigation modifier ON momentum). KMP
2018 treats carry as the PRIMARY signal. Encoding that is the schema test.

**Scope decision (honesty note):** the faithful KMP test is *cross-sectional*
across many futures (a Panel B portfolio construct). To keep this cell
comparable to the existing US10 Panel A cells and isolate the
schema-extension question to a single variable, this pre-reg registers the
*single-instrument time-series* carry-primary cell on US10 first. The full
cross-asset KMP replication is explicitly deferred to Panel B (see §8, §9).

---

## 2. Hypotheses + predictions

**H1 (primary):** A carry-primary spec on US10 (carry as the sole forecast,
no EWMAC) earns a net Sharpe distinguishable from zero over 1969-2026.

**H2 (schema):** The family.yaml Panel A schema cannot express
"primary signal = carry, rule_structure = none" without a new construct
(documented in §8). This is a prediction about the FRAMEWORK, not the market.

```yaml
predictions:
  - id: P1
    statement: "Carry-primary US10 net Sharpe is positive but small (carry on a single rates instrument is weak vs cross-sectional carry)"
    rationale: "KMP 2018 §3 carry premium is strongest cross-sectionally; single time-series rates carry is a degenerate slice. Family scorecard says predict direction, not magnitude."
    type: categorical
    score_method: "sign(Sharpe_net) > 0 -> MATCH; <= 0 -> MISS"
  - id: P2
    statement: "skew_per_trade for carry-primary is LOWER than the momentum baseline (carry is short-volatility, not long-option)"
    rationale: "KMP 2018 §4: carry is compensation for crash risk -> negative-skew payoff, opposite to Martin 2023 momentum long-option skew"
    type: categorical
    score_method: "skew_per_trade(carry) < skew_per_trade(martin_baseline_us10_1m) -> MATCH; else MISS"
  - id: P3
    statement: "The current family.yaml Panel A schema requires a new axis level or a new axis to register this cell faithfully"
    rationale: "overlay=carry presumes a momentum base; rule_structure has no carry/none level"
    type: categorical
    score_method: "schema edit required to encode the cell -> MATCH; cell fits as-is -> MISS"
```

---

## 3. Mechanism — formula, triggering, action

**Forecast (the signal).** Per KMP 2018 §2 Eq.(2), the raw carry forecast on
US10 is the annualised front/next slope. We use pysystemtrade's native carry
rule (`systems.provided.rules.carry`) as the implementation of that definition,
which risk-normalises carry by the instrument's price volatility to produce a
scale-free forecast. This is a `carry / σ` style normalisation.

**Triggering.** Forecast is evaluated every business day; position is taken
whenever |forecast| > 0 (always-on, sign = sign of carry).

**Action / sizing.** Carver-native position sizing:
`position = forecast · (target_risk · capital) / (price_vol · point_value · fx)`,
quantised to integer contracts. The forecast is **capped at ±20** (Carver
hard cap), i.e. `max(|forecast|) ≤ 20`. This finite bound is declared here so
the risk-normalised `carry / σ` forecast cannot diverge when σ collapses
(degenerate-denominator safety bound).

**No EWMAC, no overlay.** This is the schema-bending part: the forecast is
carry ALONE.

---

## 4. Acceptance gates

All gates evaluated out-of-sample. Sharpe / vol use **daily, non-overlapping**
returns annualised at 256. `skew_per_trade` uses **sign-episode aggregation**
(variable holding period, one observation per sign episode). Declaring the
aggregation per metric resolves the skew/return aggregation ambiguity.

| Gate | Definition | assumption_set | assumption_check |
|---|---|---|---|
| G-C1 | net Sharpe distinguishable from 0 (t-stat > 2) | returns ~ stationary post-1990; assumes carry signal is tradable at daily frequency | report rolling 252d Sharpe; confirm not driven by one regime |
| G-C2 | carry premium survives costs (net ≥ 0.5 × gross Sharpe) | assumes pysystemtrade SR cost model for US10 | report gross vs net |
| G-C3 | skew_per_trade sign matches P2 (carry is short-vol) | assumes KMP 2018 §4 crash-risk interpretation transports to single-instrument rates | measure skew_per_trade vs baseline empirically |
| G-recon | trade-attribution reconciles to cumulative daily within 5% | assumes integer positions are not near-zero (the martin_baseline_us10_50k recon artifact) | report |recon_pct| |

**Family DSR awareness (Rule 6).** This cell joins the futures_momentum family.
Per ars/families/futures_momentum/family.yaml § multiple_testing the current
`n_configs_searched = 58` gives an `expected_max_sharpe` of 0.3326 (annualised),
computed via `arki.utils.dsr.expected_max_sharpe(ann_factor=256)`
(deflated_sharpe, López de Prado 2014). Registering this cell adds its
`internal_grid_size` (see §6) to the family N, raising the threshold for ALL
promotions. The headline Sharpe claim (G-C1) is disclosed against this
deflated threshold; promotion requires clearing it, not merely t-stat > 2.

---

## 5. Data + universe

- **Instrument:** US10 (10-year US Treasury note future), the family's anchor
  single instrument, so this cell is directly comparable to
  `exec_friction_martin_baseline_us10_1m`.
- **History:** native pysystemtrade adjusted + carry data for US10
  (1969-12-02 → present), no external API.
- **Capital / exec:** $1,000,000, exec_profile `carver_native` (integer, cap
  ±20, default buffer) — held CONSTANT vs the momentum baseline so the only
  difference is signal = carry vs signal = EWMAC.
- **No data, universe, benchmark, cost, validation-window or seed change**
  relative to the family baseline beyond the trading rule itself.

---

## 6. Dependencies + grid

- **depends_on:** `exec_friction_martin_baseline_us10_1m`
  (ars/runs/20260529T172206Z_martin_baseline_us10_1m) as the comparison anchor.
- **internal_grid_size: 1** — confirmatory, no sweep. (If a carry-lookback
  sweep is later added, the grid and family N must be amended before unlock.)
- **runner:** `scripts/carry_primary_us10_runner.py` (TO BE WRITTEN) — drives
  the pysystemtrade engine with a carry-only forecast on US10. NOTE: the
  family currently has no carry-as-primary runner; building it is part of the
  schema-fit cost measured in §8.

---

## 7. CPC v1 reporting plan

On completion, render `arki/reports/<date>/cells/carry_primary_us10_cpc.html`
via `scripts/build_cpc_v1_arki.py` (mechanism card from §3, risk table vs
baseline, per-trade ledger, acceptance-gate table, family-context block). Append
the cell to registry.yaml + family.yaml only AFTER gates are scored.

---

## 8. Schema-fit assessment (the real deliverable)

Encoding this cell into family.yaml Panel A exposes three friction points:

1. **`overlay` axis cannot host carry-as-primary.** `overlay` levels
   (`none, carry, sMOM, dMOM, TBM_meta_label, ...`) presume a momentum base
   forecast the overlay modifies. There is no way to say "the overlay IS the
   whole signal." → needs either a new `rule_structure` level `carry_primary`
   (signal = carry, no EWMAC) OR a new orthogonal axis `primary_signal:
   [momentum, carry, value, ...]`.

2. **Panel A thesis is skew-specific.** The panel purpose
   ("maximise positive-skew long-option payoff, Martin 2023") does not describe
   a carry strategy (short-vol, negative-skew per KMP 2018 §4). A carry cell is
   technically registrable but thesis-inconsistent — the panel thesis text would
   need to generalise from "positive-skew momentum" to "per-instrument return
   source comparison."

3. **The faithful KMP test is cross-sectional → Panel B.** Single-instrument
   carry is a degenerate slice; the real premium is XS. Panel B inherits spec
   *definitions* from Panel A and has no carry-primary construct either, so the
   bend in (1) propagates to Panel B.

**Verdict to record after the run:** if registering this cell forces a schema
edit (new axis/level), P3 = MATCH and the prior critique "schema is
paper-family-biased" is CONFIRMED. If it slots in cleanly, P3 = MISS and the
schema is more general than feared. Current expectation (pre-run): P3 = MATCH.

---

## 9. Out of scope

- The full cross-asset KMP carry replication (FX, commodities, equities) — that
  is a Panel B portfolio experiment, deferred until the schema extension in §8
  is decided.
- Carry-momentum *combination* signals (that is the existing `overlay: carry`
  cell, already refuted on US10 — see family.yaml `carry_toggle`).
- Live trading (project profile: research only).
