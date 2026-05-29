# Assumption checks — known traps

A reference for the `ars-review-paper` skill. Each entry: paper + section + assumption + how to verify + past LESSON if applicable.

---

## Martin (2023) "Design and analysis of momentum trading strategies"

### §1 Central thesis (verify framing, not equations)

**Assumption**: trading-return skew is "a product of the design of the strategy, not a property of the asset class."

**Check**: scan the pre-registration for asset-attribution language ("rates are good for trend," "equity has negative skew so it's bad for momentum," etc.). If present, raise concern severity `theoretical`: the pre-registration mis-attributes a strategy-product to an asset-property.

**LESSON**: 2026-05-29 "Martin §2.3 misreading" — gates G1/G2 framed as "rates positive / equity negative" → retracted.

### §2 Linear class (verify all assumptions)

**Assumption set**:
1. `φ_n = Σ a_j · U_{n-j}` — linear strategy class.
2. `U_n` i.i.d. with moments `(0, 1, 0)` — vol-normalised, symmetric (κ_3 = 0), unit variance.
3. All `a_j > 0` for the trend (pure-trend) case.
4. Fixed-M non-overlapping aggregation for the trading return.

**Checks**:
- Does the strategy fit the linear class? (Forecast cap is §4 nonlinearity, not §2 linear.)
- Are weights all positive? (Carry on / off — paper §2 assumes pure trend.)
- Is `κ_3(U)` measured for each instrument and reported? (US10 typically ~0.18 OK; SP500 ~-0.25 violates.)
- Is the metric `skew(M-period aggregated return)` for fixed M? Or sign-episode (variable M)?

**Verbatim quotes commonly used in concerns**:
- Eq. 12: `⟨Y_n^(M),3⟩ = 6 · Σ_{k=1}^{M-1} (M-k) · a_{k-1} · R_k^a`
- The peak skew result: `EMA1 max skew ≈ 2.41 at M ≈ 1.07·N`, `EMA2 max skew ≈ 2.1 at M ≈ 1.7(N_α + N_β)`.
- Decay: `M^{-1/2}` decay for large M.

**LESSON**: 2026-05-29 "sign-episode ≠ fixed-M" — pre-reg used sign-episode skew but cited Eq. 12 (fixed-M).

### §3 Option-like structure

**Assumption**: `Y^(M) = u'Γu` quadratic form. Profits arise from few large positive eigenvalues + many small negative eigenvalues. Vol regime condition: high long-term vol / low short-term vol favours trend following.

**Check**: if the pre-reg cites §3 ("long-option signature"), is the eigenvalue structure measured, OR is "low win rate + high trade skew" used as a heuristic stand-in? The heuristic is NOT a verification of §3; flag as `methodological` concern with recommendation to either measure tr(Γ³) or down-weight the claim to "heuristic alignment with §3."

### §4 Nonlinear class (verify scope when overlay added)

**Assumption set**:
1. `φ_n = ψ(V_n)` where `V_n` is a momentum factor (or generalised — past return aggregates).
2. Trading return moments differ from §2 by Eq. 29: `H_k = 2 · a_{k-1} · ⟨ψ(Z_1) · ψ'(Z_1) · ψ(Z_2)⟩_{ρ = R_k^a}`.
3. **Capping (any form, sigmoid or hard) REDUCES max skew.**
4. **Reverting sigmoid** `z · exp(-λ²z²/2)` with `λ ≥ 1.3` can FLIP skew to NEGATIVE. Large losses in long trends (the 2014 oil short example, Fig 9).
5. **Binary `sgn` rule**: skew vanishes; SR flat for `ε < 0.6`, sweet spot `ε ≈ 0.6`.

**Checks**:
- Any overlay with `w = f(past R²)` or `w = f(past R²_neg)` (cMOM, sMOM, dMOM, Barroso-Santa-Clara) is `ψ(V_n)` → §4 class. §2.3 closed form does NOT apply. Flag if pre-reg cites §2.3.
- Soft cap (e.g. `forecast_cap = 20`) is §4 capping → reduces max skew (small effect, but reframing as "Martin-compliant" is REVERSED).
- Multiplicative weight series MUST declare `max(|w|) ≤ N` to avoid the reverting-sigmoid scope.

**Verbatim quotes**:
- "Simple sigmoid: capping → max skew reduced (vertical compression)."
- "Double-step ε → 0 (binary sgn) → skewness disappears."

**LESSON**: 2026-05-29 "sMOM unbounded weight" + "forecast_cap = 20 mis-framing."

### §5 Design conclusions

**Assumption**: (a) Binary ±1 is bad → use threshold. (b) At high momentum, REDUCE position is better than just CAP, but not too much (negative skew, overtrading). (c) Calibration data-history sensitive → SCENARIO-BASED design preferred over historical SR maximisation.

**Checks**:
- Promotion criterion based on full-sample Sharpe lift → §5(c) violation. Flag if no regime decomposition. (Mitigation: PROMOTION.md scenario gate.)
- Capping vs reducing — most pysystemtrade defaults cap. Reverting-sigmoid-style reducing is not standard.

---

## Hanauer & Windmüller (2022) "Enhanced Momentum Strategies"

### §3 Three vol-scalers (cMOM, sMOM, dMOM)

**Assumption set**:
1. Cross-sectional equity context (NOT single-instrument).
2. Each scaler is a position-size multiplier on the standard MOM signal.
3. Practical implementations may cap leverage (HFT desk convention; check paper for explicit cap statement before claiming it as paper position).
4. Headline conclusion: "all three reduce crashes; **none consistently beats plain MOM in factor tests**."

**Checks**:
- Pre-reg framing as "Sharpe enhancement" likely OVERSTATES the paper. Paper position is "crash mitigation, not Sharpe boost."
- Cross-sectional → single-instrument transfer is NOT in the paper. Pre-reg should flag this as an open question, not assume transfer.

**Verbatim quotes**:
- Eq. 6 (sMOM cMOM cMOM-style): `w_sMOM,t = σ_target / σ̂_t,semi` (or paper's exact form — verify).
- Conclusion sentences: "all three reduce momentum crashes" (paraphrase; find verbatim).

### Daniel-Moskowitz (2016) "Momentum Crashes" — referenced by Hanauer

**Assumption set**:
1. `w_dMOM,t = (1/2λ) · μ̂_t / σ̂²_t` — Markowitz-style dynamic scaling.
2. `μ̂_t` from `R_MOM,t = γ_0 + γ_int · I_Bear,t-1 · σ²_RMRF,t-1 + ε_t` regression.
3. Cross-sectional momentum context.
4. Designed for momentum CRASH events (bear-market recoveries with high vol).

**Checks**:
- The bear indicator on `R_MOM` cumulative is paper-defined. On a single rates contract (US10), the equivalent question is what "bear" means for back-adjusted bond price. Pre-reg should explicit this adaptation.
- `σ²_RMRF` is the market-factor variance in the cross-sectional context. On single-instrument, this is the instrument's own variance — different object. Flag.

---

## Wang & Yan (2021) "Semivariance Premium"

[TODO: load paper; this stub is a placeholder. assumption_checks.md grows with each paper-review session.]

---

## General pattern templates (apply to any paper)

### Pattern A — "Author cites Figure as evidence in pre-reg"

If pre-reg cites `Author (Year) Fig X` without `section + equation` reference:

- Severity: `framework` (Rule 1 violation).
- Action: `re-frame` — replace with section + equation citation.
- Confidence: `high`.

### Pattern B — "Multiplicative weight without bound"

If pre-reg defines any time-varying weight `w_t` without an explicit `max(|w|) ≤ N` field:

- Severity: `implementation` (Rule 2 violation).
- Action: `re-run-with-fix` after declaring bound.
- Confidence: `high`.

### Pattern C — "Assumption not measured"

If pre-reg cites paper section X which assumes Y (e.g. `κ_3 = 0`), and the run does NOT measure Y:

- Severity: `methodological` (Rule 3 violation).
- Action: `re-frame` to add assumption check + downgrade verdict to "context, not validation" if violation found.
- Confidence: `medium-high`.

### Pattern D — "Aggregation mismatch"

If pre-reg cites paper equation that assumes fixed-M aggregation, but the metric uses sign-episode (or vice versa):

- Severity: `methodological`.
- Action: `re-frame` — either match aggregation OR explicitly note non-comparison.
- Confidence: `high`.

### Pattern E — "Class membership ambiguous"

If overlay's mathematical form puts it outside the cited paper's class (e.g. sMOM citing Martin §2 linear class):

- Severity: `theoretical`.
- Action: `re-frame` with the correct class membership; note the cited prediction does not apply.
- Confidence: `high`.

---

## Curation policy

- Add a new entry the first time a paper is reviewed under this skill.
- Update verbatim quotes when section / equation numbering changes between paper editions.
- Past LESSONS are surfaced as "Why" anchors so the assumption is remembered.
- This file is append-only with respect to past entries; future entries replace stubs.
