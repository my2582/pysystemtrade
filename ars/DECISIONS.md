# ARS Decisions — pysystemtrade

Chronological promotion log for ARS-tracked runs. One entry per
promotion, falsification, or other notable verdict. Mirrors
`b3-saa-etf/docs/DECISIONS.md`.

Schema per entry:
- Date + slug + status.
- Hypothesis under test.
- Measured result (numbers, vs baseline if any).
- Verdict text (per-gate PASS / FAIL).
- Promotion path (if any) + artifacts.
- Implications + next experiments.

---

## 2026-05-29 (post-review correction, written after paper re-read)

The Martin entry below was written before a careful re-read of Martin (2023) §2 and §4. A subsequent review surfaced material misreadings that affect the framing (not the numerical results) of gates G1 and G2 specifically. Rather than rewriting the original entry (which is locked at its run-time git SHA), this correction is appended chronologically per ARS append-only convention.

**Specific misreadings**:

1. **Asset attribution**: I read "US10 market skew positive at M=40-60 / SP500 market skew negative" as evidence that "rates are good for trend, equity is bad for trend." Paper §1 explicitly states the opposite mechanism: trading-return skew is "a product of the design of the strategy ... not a property of the asset class." Even on symmetric market returns, all-a_j-positive linear trend produces positively skewed trading returns. Therefore G1/G2 (Martin Fig 1 verdicts) do NOT validate Martin §2.3, they merely confirm the market-context plot the paper used to introduce the problem.

2. **Underlying assumption**: Paper §2 assumes κ_3(U_n) = 0 (one-period vol-normalised returns are symmetric). My SP500 U has strong daily skew ≈ -0.25 → paper's closed-form Eq. 12 does not apply cleanly. The negative strategy-return skew I observed on SP500 is consistent with U-leak, NOT a refutation of Martin §2.3 nor evidence of "equity bad for trend."

3. **`forecast_cap = 20` is a §4 nonlinearity, not "Martin-compliant"**: Paper §4 establishes that any cap (sigmoid or hard) REDUCES max trading-return skew. I framed `forecast_cap = 20` as Martin-compliant in cheatsheet F2; this is reversed. My baseline is `linear + §4 capping`, not pure §2.3 linear.

4. **`skew_per_trade` ≠ Paper's M-period skew**: My sign-episode `skew_per_trade` measures skew over variable-length holding periods. Paper's Eq. 12 closed-form and the M^(-1/2) decay refer to **fixed-M non-overlapping aggregations** of trading returns. The two are different mathematical objects; my measurement does not directly test Paper's central prediction.

5. **"EWMAC = Martin EMA2" mapping is approximate**: Paper EMA2 = difference of two EMAs of dX_s (price *changes*). pysystemtrade EWMAC = (fast_EMA(price) - slow_EMA(price))/σ̂ = difference of EMAs of price *levels*. Both inside the linear-strategy class, but with different a_j weights. The variational optimum te^(-α̇t) ("EMA2=") is a single Laguerre-style kernel, not a 6-pair equal-weight stack.

**Net implication for the Martin entry**: numerical results stand. Verdict text needs reframing:
- G1/G2 (Fig 1 sign contrast): downgraded from "Martin §2.3 validated" to "Fig 1 market-context reproduced; does not validate §2.3."
- G3/G4 (per-trade skew): note that sign-episode skew is NOT Paper's fixed-M trading return skew; remeasurement needed (Step 2 below).
- G5 (Sharpe ceiling): unchanged; refutes the prior 0.7-1.0 claim independently of Martin's framework.

A follow-up experiment (`scripts/martin_fixed_m_skew.py`, Step 2) measures fixed-M trading-return skew on the baseline. A second experiment (Step 3) ablates `forecast_cap` to separate the linear-vs-§4 effect.

The lesson, recorded under ARS process change: pre-registered gates must reference specific paper sections + equations, not Figure/section slogans. See `ars/LESSONS.md` (forthcoming).

---

## 2026-05-29 — martin_single_instrument — POST-HOC REGISTRATION

**Status:** `promoted_post_hoc` (framework's first registry entry; pre-registration written after the run as a special-case grandfathering).

**Hypothesis under test (reconstructed post-hoc):**
- H-M1 (Fig 1, rates side): on a single rates futures (US10), market-return skewness term-structure is positive at intermediate horizons (M ≈ 40-60 days).
- H-M2 (Fig 1, equity side): on a single equity-index futures (SP500), market-return skewness is negative across most M.
- H-M3 (§2.3): a multi-speed EWMAC pure-trend strategy with all a_j > 0 produces positively skewed per-trade returns much larger than the daily skew.
- H-M4 (§3): the per-trade distribution shows the long-option signature (low win rate + strong positive trade skew) on US10.
- H-M5 (single-instrument Sharpe ceiling): US10 strategy gross Sharpe lies in [0.2, 0.6], refuting the optimistic 0.7-1.0 range from the prior uncited deep-research run.

**Measured result** ($50k notional, integer contracts, 6-speed EWMAC equal-weight, carry off, soft cap 20, vol target 20%, 1982-08-30 → 2026-04-03):

| Gate | Threshold | US10 | SP500 | Verdict |
|---|---|---|---|---|
| Fig 1 rates positive @ M=60 | `mkt_skew > 0` | +0.204 (peak +0.244 @ M=40) | — | PASS |
| Fig 1 equity negative @ M=60 | `mkt_skew < 0` | — | -0.037 (negative for M=1..40, 100..250) | PASS |
| §2.3 trade-skew >> daily-skew (US10) | `skew_per_trade > skew_daily + 1.0` | +4.38 vs +0.18 | — | PASS |
| §3 long-option signature (US10) | `win% < 50 AND skew_per_trade > 1.0` | 23.4% / +4.38 | — | PASS |
| §M5 Sharpe ceiling (US10) | `0.2 ≤ Sharpe_gross ≤ 0.6` | 0.396 | — | PASS |

Reconciliation (sum of trade-attributed P&L vs total strategy P&L): US10 -1.17%, SP500 +0.85% (both << 5% tolerance).

**Verdict text:** All 5 headline gates PASS. Reconciliation tight. Per-trade skew result (+4.38 US10, +4.33 SP500) materially exceeds prior expectation. Crucially, the run REFUTES the prior uncited deep-research claim of Sharpe 0.7-1.0 — single-instrument trend Sharpe is in the 0.3-0.4 range and the actual edge is the convex / long-option payoff, not a high Sharpe.

**Promotion path:** Path Z — post-hoc grandfathering. Promotion criterion #1 (pre-registration committed before run-start) FAILS; criteria #2-#4 PASS; criterion #5 owner review = this entry. Owner discretion accepted as one-time grandfathering for the framework's first entry. Future runs MUST pre-register before run-start.

**Artifacts:**
- Run: `ars/runs/20260528T161350Z_martin_single_instrument/`
- Evidence pack: `ars/evidence_packs/martin_single_instrument/`
- Registry: `ars/runs/registry.yaml` (id `20260528T161350Z_martin_single_instrument`)
- Literature: `references/research/Design and analysis of momentum trading strategies.pdf`
- git SHA at run-start: 5fa88c4c (commit `fix(martin): correct Fig 1 attribution, vol-normalised market skew, geometric maxDD`)

**Implications + next experiments:**
- Single-instrument trend on rates futures is a working concept; on equity-index futures it is not.
- Skew amplification trade-level vs daily (~25x on US10) is the strategy's actual product.
- **Next**: dMOM overlay (Hanauer & Windmüller 2022 / Daniel-Moskowitz 2016) on US10 — does the bear×market-vol regime scaler add value over the EWMAC baseline? Pre-register first.

---

## 2026-05-29 — dmom_us10 — FALSIFIED

**Status:** `falsified` (Path FALSIFY). Pre-registration locked at git `65c423bc` (genuine pre-run, not post-hoc). Framework's first true Path A application; result triggered the pre-registered FALSIFY rule.

**Hypothesis under test (from `ars/evidence_packs/dmom_us10/dmom_us10_preregistration.md`):**
The Daniel-Moskowitz / Hanauer dMOM dynamic-scaling overlay (`w = (1/2λ)·μ̂/σ̂²` with `μ̂` from bear×market-vol regression) should lift the US10 single-instrument trend Sharpe (H-D1) AND reduce its crashes (H-D2) WHILE preserving the per-trade positive skew (H-D3). Control: should NOT rescue SP500 baseline (H-D4).

**Measured result** (run `ars/runs/20260528T173334Z_dmom_us10/`; full history 1982–2026):

| Gate | Metric | Threshold | Observed | Verdict |
|---|---|---|---|---|
| G1 | US10 Sharpe lift | `≥ +0.10` | **+0.017** | **FAIL** |
| G2 | US10 maxDD improvement | `≥ +5.0 pp better` | **−1.04 pp** (slightly worse) | **FAIL** |
| G3 | US10 dMOM `skew_per_trade` | `≥ 1.0` | +5.46 | PASS |
| G4 | SP500 dMOM Sharpe (control) | `< 0.20` | −0.148 | PASS |
| G_recon | overlay reconciliation `|R_dMOM − R_baseline·w|` | ≈ 0 | 0.00e+00 | PASS |

Per-instrument detail (Sharpe / maxDD geom / skew_per_trade / n_trades):
- US10: baseline 0.347 / −55.3% / 4.38 / 342 → dMOM 0.364 / −56.4% / 5.46 / 537.
- SP500: baseline −0.009 / −85.0% / 4.33 / 335 → dMOM −0.148 / −100.0% / 14.25 / 521 (skew_daily −106 = degenerate single-day outlier; SP500 baseline has no edge so multiplying by a vol-divider produces extreme leverage; recorded as expected degenerate behaviour, not a finding).

**Verdict text:** G1 AND G2 both FAIL → per pre-registration §4: status `falsified`. The pre-registered finding triggers verbatim: "dMOM on single-instrument US10 trend does not enhance Sharpe and does not reduce crashes; the cross-sectional equity result does not transfer." The skew preservation (G3 PASS) and control (G4 PASS) confirm the overlay is implemented correctly and is not creating spurious returns — it just does not help. λ closed-form value 0.45 (US10); weight goes negative on roughly 30% of days (bear+vol regimes) as designed, but those flips do not produce the crash-mitigation benefit observed by Hanauer on cross-sectional equity.

**Why the result is consistent with the source paper.** Hanauer & Windmüller (2022, §3) report that their three vol-scaling variants reduce momentum crashes but **none consistently beats plain MOM in factor tests**. On a single rates instrument, there is no "momentum crash" of the kind dMOM was designed to catch — the US10 EWMAC's worst drawdowns come from sharp rate-reversal episodes that the bear×market-vol regression cannot anticipate (the bear indicator on US10 back-adjusted price is dominated by the slow secular rate-down trend, not by the regime states that mattered in the equity cross-section).

**Promotion path:** FALSIFY (no promotion). The run is preserved in the registry as a first-class negative result. The evidence pack at `ars/evidence_packs/dmom_us10/` is published (pre-reg + verdict.json + run report + finding README) for downstream consumers to read before re-running the same idea.

**Artifacts:**
- Run: `ars/runs/20260528T173334Z_dmom_us10/`
- Evidence pack (falsified): `ars/evidence_packs/dmom_us10/`
- Registry: `ars/runs/registry.yaml` (id `20260528T173334Z_dmom_us10`, status `falsified`)
- Code: `scripts/dmom_overlay_backtest.py`
- Pre-registration commit: `65c423bc`
- git SHA at run-start: (recorded in `manifest.json`)

**CPC v1 status:** waived for this falsified run. Per `ars/PROMOTION.md` Tier-2b is mandatory for multi-variant comparisons; falsified runs may waive CPC because no peer comparison is needed when the verdict is negative on primary gates. Future falsified runs follow this precedent.

**Implications + next experiments:**
- The "dMOM as crash overlay" idea is dead for single rates instruments at small AUM. Do not retry with parameter tweaks; the structural reason (no equity-style momentum crash to catch on rates) is unlikely to be fixed by lookback changes.
- The Tier-3 alternative crash overlay worth testing on US10 is `sMOM` (semi-vol scaling, Wang & Yan 2021) which does NOT require a regime model. Lower-bar test; pre-register before running.
- Conversely, dMOM might still apply to a CROSS-SECTIONAL momentum portfolio across multiple rates futures (Bund, BOBL, OAT, JGB, KR10, ...). That is a different experiment family, not in this repo's L2 scope at present.
- For Sharpe enhancement on US10 single-instrument trend, the path forward is NOT crash management; it is either (a) faster signals trading the small-AUM speed advantage, or (b) trend + carry combination (one further design decision at a time).

---

## 2026-05-29 — smom_us10 — PROMOTED (Path A, borderline control)

**Status:** `promoted` (Path A — all 4 pre-registered gates PASS, BUT G4 SP500 control passes at 0.161 vs threshold 0.20 — near-miss flagged).

**Hypothesis under test:** Wang-Yan 2021 semi-vol scaler `w = sqrt(target_var)/sqrt(downside_var_126d)` lifts US10 single-instrument trend Sharpe by ≥ 0.05, improves maxDD by ≥ 3 pp, preserves trade-level skew, no false rescue on SP500.

**Measured result:**

| Gate | Threshold | Observed | Verdict |
|---|---|---|---|
| G1 Sharpe lift US10 | ≥ +0.05 | **+0.255** | PASS |
| G2 maxDD improvement | ≥ +3.0 pp | **+11.19 pp** | PASS |
| G3 skew_per_trade US10 | ≥ 1.0 | 4.69 | PASS |
| G4 SP500 control | < 0.20 | 0.161 | PASS_borderline |

US10: Sharpe 0.347 → 0.602; ann ret 7.72 → 13.39; vol 22.26 → 22.26; maxDD geom -55.35 → -44.16; n_trades 485 → 485 (same trade boundaries).
SP500: Sharpe -0.009 → 0.161; skew_daily -1.99 → **+105.9 (degenerate, single huge outlier)**; maxDD -85.0 → -0.32.

**Verdict text:** sMOM is a **genuine enhancement on US10**: a +0.255 Sharpe lift with 11 pp better maxDD without destroying the long-option skew is materially favourable. The mechanism (scale up in calm periods, scale down in downside-vol periods) works on the bond trend because secular rate-down regime gives many low-downside-vol windows for leverage. **Caveats:** (a) absolute leverage level depends on the closed-form lambda match using full-sample baseline var, which is a standard Hanauer convention but does involve full-sample scaling; the relative time-pattern is OOS-clean. (b) SP500 sMOM shows degenerate behaviour (skew_daily +106 = single huge outlier dominates) and a near-miss control pass at 0.161 — investigate before any cross-instrument generalisation.

**Promotion path:** Path A. Evidence pack at `ars/evidence_packs/smom_us10/`. Downstream consumers should treat as a US10-rates-specific finding pending replication on Bund / BOBL / OAT.

**Artifacts:**
- Run: `ars/runs/20260528T181556Z_smom_us10/`
- Code: `scripts/momentum_variants_backtest.py`
- Pre-reg commit: (this commit's predecessor; locked before run)

**Next experiments queued:** replication on Bund / BOBL / OAT; test sMOM with bear filter (intersection of sMOM and dMOM regime conditioning).

---

## 2026-05-29 — fast_tilt_ewmac — FALSIFIED

**Status:** `falsified` (FALSIFY path triggered: sharpe_lift -0.155 < -0.03 "faster is worse" rule).

**Hypothesis under test:** Linear-decay forecast weights toward fast EWMAC (0.30, 0.25, 0.20, 0.15, 0.07, 0.03) capture the small-AUM speed advantage Carver-restricted CTAs cannot use, lifting US10 Sharpe.

**Measured result:**

| Gate | Threshold | Observed | Verdict |
|---|---|---|---|
| G1 Sharpe lift US10 | ≥ +0.05 | **-0.155** | FAIL |
| G2 skew_per_trade US10 | ≥ 1.0 | 4.36 | PASS |
| G3 SP500 control | < 0.20 | -0.185 | PASS |

US10: Sharpe 0.347 → 0.192 (-0.155); maxDD -55.35 → -58.68 (worse); n_trades 485 → 806 (+66% turnover).
SP500: Sharpe -0.009 → -0.185; maxDD -85 → -97.

**Verdict text:** Fast-tilt weights the wrong end. The pre-registered rule "faster is worse if sharpe_lift < -0.03" triggers: -0.155 is far below the threshold. Higher turnover (485 → 806 trades, +66%) costs without lift. The small-AUM speed advantage (Carver) is **theoretical** — it requires a cost differential between large vs small CTAs, not just a faster signal at the same simulated cost structure. In a transaction-cost-free integer-contract $50k simulation, fast signals just whipsaw more. Skew preservation (G2 PASS at 4.36) means the strategy still has the long-option shape — it just has worse mean.

**Promotion path:** FALSIFY. Finding: do not retry with weight tweaks; the speed-advantage hypothesis requires a different test surface (e.g. tick-data with realistic cost-by-size models). Out of L2 scope here.

**Artifacts:** Run `ars/runs/20260528T181556Z_fast_tilt_ewmac/`. Evidence pack `ars/evidence_packs/fast_tilt_ewmac/`. Code `scripts/momentum_variants_backtest.py`.

---

## 2026-05-29 — carry_toggle — REFUTED (Martin §2.3 implication contradicted on rates)

**Status:** `refuted` (REFUTED path: G2 skew-reduction FAIL — carry did NOT reduce skew; it INCREASED it).

**Hypothesis under test:** Martin §2.3 says pure-trend (all a_j > 0) is sufficient for positive skew. Implication: adding non-trend signal (carry) should reduce skew. Test: enable carry at weight 0.30 (EWMAC renormalised to 0.70) — expect skew_reduction ≥ 0.5.

**Measured result:**

| Gate | Threshold | Observed | Verdict |
|---|---|---|---|
| G1 Sharpe shift US10 | \|Δ\| ≥ 0.03 | 0.090 | PASS |
| G2 skew reduction US10 | ≥ +0.5 | **-1.998** (carry INCREASED skew) | FAIL |
| G3 skew floor US10 | ≥ 1.0 | 7.34 | PASS |
| G4 SP500 control | < 0.20 | 0.011 | PASS |

US10: Sharpe 0.347 → 0.437 (+0.090); skew_per_trade 5.35 → **7.34 (+1.99 INCREASE)**; maxDD -55.35 → -55.94; n_trades 485 → 365 (carry is slower than EWMAC → fewer trades).
SP500: Sharpe -0.009 → 0.011 (essentially zero, no rescue).

**Verdict text:** Adding carry **does NOT reduce** US10 per-trade skew — it INCREASES it by +2.0. The pre-registered hypothesis (Martin §2.3 implication for this trade structure) is REFUTED on this instrument. Interpretation: bond futures carry (roll yield in backwardation under secular rate-down) is **itself a positively-skewed return source** on US10, so combining it with trend stacks two long-option payoffs rather than diluting one. Sharpe also lifts (+0.09), so carry is a structurally good addition on US10 rates — NOT a clean test of "trend purity" but rather a finding that the rates carry source is well-aligned with trend.

This is an important nuance for downstream: Martin §2.3 holds AS WRITTEN (pure trend → positive skew, mathematically); the implication "non-trend dilutes skew" is contingent on whether the non-trend signal is itself zero-skew (or oppositely-skewed). For US10 rates, carry is not zero-skew. The finding is single-instrument; do not generalise to commodities in contango or to FX without re-testing.

**Promotion path:** REFUTED (assumption test, not promotion candidate per pre-reg §4). Finding registered; informs future carry-vs-trend design discussions.

**Artifacts:** Run `ars/runs/20260528T181556Z_carry_toggle/`. Evidence pack `ars/evidence_packs/carry_toggle/`. Code `scripts/momentum_variants_backtest.py`.

**Implications:** since carry on US10 (a) lifts Sharpe by ~0.09 AND (b) lifts skew, carry-toggle is a candidate enhancement for a future trend+carry production system on US10. Note this would be a Path A promotion candidate in a separate experiment with appropriate pre-registered Sharpe-lift gates.


---

## 2026-05-29 — top1rot_pit50k — FALSIFIED (implementation finding: vol-target sizing mismatch)

**Status:** `falsified` (pre-reg Path A requires G1+G2 both PASS; G1 PASS, G2 FAIL; does not fit Path B which requires G2 PASS with G1 allowed to fail).

**Hypothesis under test (H-T1, H-T2):** weekly top-1 momentum rotation over the PIT-eligible universe lifts gross Sharpe by ≥ +0.05 AND reduces geometric MaxDD by ≥ +5pp vs the martin US10 single-instrument baseline. Single-decision variable = instrument selection rule (fixed-US10 vs rotation); all other parameters (6-speed EWMAC signal, 20% vol target, $50k, integer contracts) held identical.

**Measured result (rotation vs martin US10 baseline):**

| Gate | Threshold | Observed | Verdict |
|---|---|---|---|
| G1 Sharpe lift | ≥ +0.05 | **+0.073** | PASS |
| G2 maxDD lift (pp) | ≥ +5.0 | **−25.69** | FAIL |
| G3 ann turnover | ≤ 68.82 | 38.70 | PASS |
| G4 skew_per_trade | ≥ 1.0 | 7.17 | PASS |
| G_recon | < 5% | 1.67% | PASS |

Rotation: Sharpe 0.469, ann_ret +24.62%, ann_vol **52.50%** (vs target 20%), maxDD −81.04%, 435 trades, 12-year cum +265.5%.
Baseline US10: Sharpe 0.396, ann_vol 22.43%, maxDD −55.35%.

**Verdict text:** G1 confirms direction-of-edge — rotation does extract Sharpe lift from the cross-section. But G2 fails by 26pp and the cause is a runner-design problem, not a strategy-thesis problem: realized vol is **52.5% (2.6× the target 20%)**. The pre-registered sizing rule ("fixed-vol-target integer contracts to hit capital × vol_target $-vol") does not scale by forecast magnitude. Top-1 selection biases the held forecast toward the 15–20 range (we always pick the strongest signal), so unit-scaled sizing systematically over-sizes by ~1.5–2× relative to a forecast-scaled implementation. Martin baseline uses pysystemtrade-native forecast-scaled sizing (position ∝ forecast/10), which keeps realized vol close to target.

This makes the single-decision rule **compromised**: the run varies TWO things vs baseline (universe choice AND effective sizing rule), not one. Sharpe-lift PASS is direction-of-edge evidence, but maxDD comparison at unequal vol levels is structurally unfavorable to the higher-vol arm and cannot be cleanly attributed to universe choice.

**Promotion path:** FALSIFIED with implementation finding; not eligible for promotion until the sizing rule mismatch is corrected.

**Artifacts:** Run `ars/runs/20260529T145911Z_top1rot_pit50k/`. Pre-registration `ars/evidence_packs/top1rot_pit50k/top1rot_pit50k_preregistration.md` (locked at git `a430628e`). Runner `scripts/run_top1rot_pit50k.py`. Strategy module `src/arki_strategies/absmom_rotation.py`. No evidence pack created (falsified, runner needs revision).

**Implications and next experiment:**

1. **Bug postmortem** — the runner had two real bugs found during execution (trade ledger gross_pnl_usd accumulator missing for continued-hold weeks; daily P&L timestamp normalization missing). Both fixed in-flight; reconciliation PASS confirms the post-fix daily P&L matches trade ledger to 1.67%. These were not pre-reg compliance issues; they were implementation defects.
2. **Design correction needed** — sizing rule must change from "fixed-vol-target" to "pysystemtrade-native forecast-scaled vol-target" to match baseline. This is a runner change, NOT a pre-reg amendment, but the pre-reg's §3 cell-1 description should explicitly state forecast-scaled sizing for the next iteration.
3. **Next run** — a fresh pre-registration is recommended (e.g. `top1rot_pit50k_v2` or amend §3 of current pre-reg if owner agrees the original sizing language was an oversight). The fix-and-rerun should preserve the single-decision posture: only universe choice differs from baseline.
4. **Single-decision discipline lesson** — when reusing a baseline's sizing language, write the pre-reg §3 to point explicitly at the baseline's sizing FUNCTION (e.g. "pysystemtrade `positionSize.get_subsystem_position`") rather than describing the abstract objective ("hit capital × vol_target $-vol"). Otherwise an implementer can satisfy the words while diverging from the baseline's behavior.
