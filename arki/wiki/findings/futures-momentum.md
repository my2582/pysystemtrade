# Finding — futures_momentum family (single-instrument US10, ongoing)

> **Status (2026-05-31)**: 14 cells in Panel A; 0 in Panel B. No cell clears
> family DSR threshold (N=58) = 0.3326 ann for confident absolute promotion.
> Best risk-shaping result: TBM Stage-1 MaxDD reduction (modest); strongest
> closed-form overlay: sMOM capped (Sharpe lift +0.276 vs baseline 0.347 on
> US10, but `registered, ambiguous` due to G4 control-gate mechanism vs bug
> ambiguity).
>
> **Pointer document, not duplicate.** Full schema in
> [`../../../ars/families/futures_momentum/family.yaml`](../../../ars/families/futures_momentum/family.yaml);
> elasticity in [`../../../ars/families/futures_momentum/findings.md`](../../../ars/families/futures_momentum/findings.md);
> queue in [`../../../ars/families/futures_momentum/queue.md`](../../../ars/families/futures_momentum/queue.md).

---

## What's been tried

Panel A (single-instrument US10) — 14 cells across:

- **Vol estimator** axis: `carver_mixed_35d` vs `martin_20d_ema_of_sq` (Wang-Yan equivalent absolute-change form).
- **Rule structure** axis: `single_ema2_20_40` vs `six_speed_ewmac_equal` vs `fast_tilted_weights`.
- **Overlay** axis: `none` / `carry` / `sMOM` / `dMOM` / `TBM_meta_label` / `fast_tilted_forecast_weights`. (`TBM_x_sMOM` queued.)
- **Exec_profile** enum: `paper_fidelity_numpy` (continuous + cap_off + standalone) vs `carver_native` (integer + cap±20 + buffer + pysystemtrade).
- **Capital** tier: $50K vs $1M.

Panel B (portfolio) — empty; first cell queued = `DM_rates_5 equal_weight TS_only` (queue item #5).

---

## Headline findings (axis-level; for full table see `ars/families/futures_momentum/findings.md`)

- **vol_estimator on US10 ≈ 0 effect** (n=2 clean pairs, mean ΔSharpe 0.0035). Untested on other instruments. Cannot conclude dead in portfolio (vol estimator feeds risk-parity weighting differently).
- **overlay axis is high-risk, high-payoff**: 3 falsified (dMOM, fast_tilt, carry_toggle = refuted), 1 pending remediation (sMOM uncapped), 1 ambiguous (sMOM capped), 1 NO SIGNAL (TBM_meta_label).
- **rule_structure direction NOT cleanly attributable** (n=0 clean pairs — exec_profile coupled in every available comparison). Resolving this is **queue item #2 top priority** (single_ema2 + carver_native cell, holding exec_profile constant vs `martin_baseline_us10_1m`).
- **exec_profile** similarly confounded (n=0 clean pairs) with rule_structure.
- **capital_usd** ≈ 0 Sharpe effect on US10 but big skew_per_trade effect — finer integer grid at $1M lets long-option signature express (skew 4.1 → 6.0).

---

## Defect → Lesson chain (4 entries, 2026-05-29 → 2026-05-31)

Each defect produced a durable rule. Two were caught by owner/reviewer intuition; one by framework itself.

1. **2026-05-29 sMOM unbounded w (6,439× leverage artifact)** → Rule 2 (degenerate-denominator bound).
2. **2026-05-29 Martin §2.3 misreading (Fig 1 as slogan)** → Rule 1 (§+Eq citation discipline) + Rule 3 (assumption_set with empirical check).
3. **2026-05-31 G4 control-gate over-strict on vol-reducing overlays** → vol-paired control-gate diagnostic (`vol_capped/vol_baseline ≤ 0.7` distinguishes mechanism from bug).
4. **2026-05-31 Rule 2 scope refinement** (was "all multiplicative weights" → corrected to "degenerate-denominator class only"; safe forecast-style weights exempt).

Full text: [`../../../ars/LESSONS.md`](../../../ars/LESSONS.md) and the curated extracts at Obsidian `_Inbox/2026-05-31/pysystemtrade_smom_briefing/05_LESSONS_smom_extracts.md`.

---

## TBM Stage-1 verdict (queue item #1, 2026-05-30/31)

**NO SIGNAL** per pre-registered decision tree (§5.1.1 of `tbm_meta_us10_baseline_preregistration.md`).

| | T_max=120 baseline | T_max=40 sensitivity |
|---|---:|---:|
| g_max_observed | 0.551 | 0.591 |
| avg_uniqueness | 0.071 | 0.099 |
| DSR uplift vs g=1 | +0.0115 (PASS) | −0.0026 (FAIL) |
| MaxDD Δ | −0.87% (PASS) | −2.49% (PASS) |
| skew_daily Δ | +0.015 (PASS) | +0.006 (PASS) |
| F1 OOS lift | +0.343 (PASS) | +0.375 (PASS) |

Both g_max < 0.60 boundary → "no learnable conditional edge for meta-labeling on this feature set, this instrument, this regime." Triple evidence:
1. 1.4× effective-sample increase did not materially expand sizer's used range.
2. DSR uplift sign flipped (random oscillation around zero).
3. HANDOFF §7 caveat ("Stage-1 = risk shaping not new alpha") empirically vindicated.

Owner decision pending: [`../../../docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md`](../../../docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md) (3 branches A accept / B re-run / C reframe).

---

## Predict-then-measure scorecard (2026-05-31, first measurement)

10 retroactive predictions from this session scored Popper-style. Hit rate **7.5/10 = 75%** (categorical 100% / quantitative 0%). Naive coin-flip = 50% → ~2.5σ above random, but n=10 sample suggestive not conclusive.

| Category | Count | Score |
|---|---:|---:|
| MATCH (1.0) | 7 | 7.0 |
| MATCH-direction (0.5) | 1 | 0.5 |
| MISS-direction (0.0) | 2 | 0.0 |
| **Total** | **10** | **7.5** |

Most consequential hit: **HANDOFF §7 qualitative prediction "Stage-1 = risk shaping not alpha"** — empirically vindicated by TBM NO SIGNAL verdict.

Detail + Rule 7 proposal: [`../../../docs/arki/session_predictions_scorecard_2026-05-31.md`](../../../docs/arki/session_predictions_scorecard_2026-05-31.md).

Future-evidence threshold: next 30-40 predictions across queue items #2 / #1.2 / #5 either confirm or invalidate the 75% baseline. Below 65% triggers framework discipline review.

---

## Honest scorecard

| Dimension | Grade | Note |
|---|---|---|
| Process built | **B+** | LdP-textbook hygiene; transport untested |
| Alpha discovered | **F** | 0/14 cells with confident lift above family DSR threshold |
| Prediction skill (this session) | **75% (7.5/10)** | Categorical 100% / quantitative 0%; n=10 |
| Confidence justification | **partial** | Non-trivial but small sample on 1 thesis × 1 instrument |

Future grade improvement requires (any of): Stage-2 non-NO-SIGNAL result · Panel B 1 cell with confident lift · cold-start handoff success · 3+ consecutive predict-then-measure ≥ 65% · framework-catches-defect-before-owner case · paper-family-exit successful schema integration.

---

## Forward work queue (time-bound commitments, 2026-05-31)

1. **rule_structure de-confound** (queue #2) — pre-reg lock by 2026-06-07; result by 2026-06-10. Resolves the n=0 clean-pair gap. Missing deadline → process-cost review.
2. **sMOM capped G4 refinement** (queue #1.2) — pre-reg amendment + re-verdict by 2026-06-12. Apply LESSONS Entry 3 vol-paired control-gate rule.
3. **Panel B open — DM_rates_5** (queue #5) — pre-reg lock by 2026-06-21 (after #2 confirms rule choice).

Plus 4 forward enhancements (Handoff #3 D/E/F/G): cold-start test · paper-family exit · process-cost instrumentation · lint Rule 7 predictions block.

---

## Reading order for a new agent / human

1. This page (overview + status).
2. [`../system/system-card.md`](../system/system-card.md) — Status line points back here.
3. [`../../../ars/families/futures_momentum/family.yaml`](../../../ars/families/futures_momentum/family.yaml) — schema + cells.
4. [`../../../ars/families/futures_momentum/findings.md`](../../../ars/families/futures_momentum/findings.md) — axis elasticity detail.
5. [`../../../ars/families/futures_momentum/queue.md`](../../../ars/families/futures_momentum/queue.md) — commitments.
6. [`../../reports/2026-05-31/family/futures_momentum_session_retro_cheatsheet.html`](../../reports/2026-05-31/family/futures_momentum_session_retro_cheatsheet.html) — visual one-pager.
7. [`../../../docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md`](../../../docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md) — pending owner decision.
8. [`../../../docs/arki/session_predictions_scorecard_2026-05-31.md`](../../../docs/arki/session_predictions_scorecard_2026-05-31.md) — prediction track record.
