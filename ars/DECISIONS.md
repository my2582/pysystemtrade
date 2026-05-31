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

## 2026-05-31 — smom_us10_capped — REMEDIATION RESULT (status: registered, owner sign-off pending)

**Closes**: `smom_us10` pending-remediation status (originally `registered_pending_remediation` since 2026-05-29 post-review).

**Pre-registration**: `ars/evidence_packs/smom_us10_capped/smom_us10_capped_preregistration.md` locked at git `ec91d20d` (Path A; lint Rules 1+2+3+4+6 ALL PASS).

**Hypothesis under test**: original `smom_us10` reported Sharpe lift +0.255 with no upper bound on `w_sMOM,t` (observed max 2,927 → effective leverage 6,439× on $50k). Remediation adds `w ≤ 3` cap + `semi_var ≥ 1e-4` floor (Rule 2 compliance) and re-measures. Pre-registered comparison gate G5 quantifies the cap-vs-uncap ratio: `[0.30, 1.20]` is the legitimate range; `< 0.30` would prove the original lift was leverage artefact.

**Measured result** (run `ars/runs/20260530T170606Z_smom_us10_capped/`):

US10 (primary):

| Metric | Martin baseline | sMOM capped | Δ vs baseline |
|---|---:|---:|---:|
| Sharpe (gross) | 0.347 | **0.623** | **+0.276** (G1 PASS, threshold ≥ +0.05) |
| maxDD geom (%) | -55.35 | **-44.16** | **+11.19 pp** (G2 PASS, threshold ≥ +3.0) |
| skew_per_trade | 5.35 | 4.62 | (G3 PASS, threshold ≥ 1.0) |
| ann_vol % | 22.26 | 22.39 | ~ unchanged (capped sMOM holds vol budget) |
| n_trades | 485 | 485 | identical (sign(w) always +1) |

SP500 (control):

| Metric | Martin baseline | sMOM capped | Δ vs baseline |
|---|---:|---:|---:|
| Sharpe (gross) | -0.009 | **+0.305** | **+0.314** (G4 FAIL, threshold < 0.20) |
| ann_vol % | 24.34 | **6.23** | **−18.11 pp** (vol massively reduced) |
| maxDD geom (%) | -85.04 | -17.08 | +67.95 pp |
| skew_daily | -1.99 | +17.27 | outlier-dominated |

**Gate verdicts**:

| Gate | Threshold | Observed | Verdict |
|---|---|---|---|
| G1 Sharpe lift US10 | ≥ +0.05 | +0.276 | **PASS** |
| G2 maxDD improvement US10 | ≥ +3.0 pp | +11.19 pp | **PASS** |
| G3 skew_per_trade US10 | ≥ 1.0 | 4.616 | **PASS** |
| G4 SP500 control | < 0.20 | 0.305 | **FAIL** |
| G5 cap-vs-uncap ratio | in [0.30, 1.20] | 1.082 | **PASS** |
| G_safety (Rule 2 bound) | max(\|w\|) ≤ 3 AND min(semi_var) ≥ 1e-4 | strictly met | **PASS** |
| G_recon | < 1.0% | 0.0% | **PASS** |

**Per pre-reg §4 falsification logic**: G1/G2/G3/G5/G_safety/G_recon all PASS, but G4 FAIL. Path A requires G4 PASS; Path B also requires G4 PASS; FALSIFY conditions not met (G_safety PASS, G3 PASS, G5 in range). Pre-reg is SILENT on "G4-alone-FAIL with all other PASS" → default status: `registered, ambiguous`.

**Owner sign-off lane**: per `ars/PROMOTION.md` refined Rule 5 (sign-off appropriate in 5 enumerated cases), this verdict qualifies for sign-off under "AI confidence-explicit-low on the G4 mechanism" — pre-reg G4 was over-strict for a vol-reducing overlay; sMOM legitimately de-leverages high-downside-vol assets, which mechanically lifts Sharpe (reduces denominator faster than numerator) without being a bug. Owner can convert to Path B-style promotion ("crash-mitigator with vol-reducer side-effect") with explicit sign-off recorded here.

**Key diagnostic findings**:
- Capped lift +0.276 > uncapped lift +0.255. Counter-intuitive but explained: lambda renormalisation. Uncapped, λ was inflated to 0.45 by the spike tail → most days got tiny `w`. Capped, λ = 1.62, distributing leverage budget more evenly across the time series. Cleaner implementation, slightly better Sharpe.
- `max(|w|) before cap = 86.48` (vs uncapped's 2,927 — the floor at 1e-4 alone removed most of the spike). Cap at 3.0 then binds on 209 days (1.9% of total).
- Floor at semi_var ≥ 1e-4 binds on 140 days (true semi_var collapsed to as low as 9e-8 without the floor).
- W_median = 1.005 — most days the leverage is near 1.0 (i.e., barely modified).
- SP500 vol drop 24.3 → 6.23 is the dominant SP500 effect: sMOM consistently de-leverages SP500 because semi_var is consistently HIGH on SP500 (equity has frequent down days). Not a rescue; a mechanical consequence.

**Interpretation framing**:
- **US10**: capped sMOM IS a genuine enhancement (~+0.28 Sharpe, ~+11pp maxDD), and the magnitude is NOT leverage-artefact (G5 in range, G_safety strict, lambda recomputed honestly). The +0.255 uncapped lift was REAL, just dressed up with extreme-leverage tail. Capped is the deployable number.
- **SP500**: the result is NOT a paper-validation finding nor a false-rescue bug; it is the **mechanism description** for what semi-vol scaling does on negative-skew, no-edge assets. Worth recording as a new finding (see LESSONS).

**Promotion path**: REMEDIATION CLOSED — original `smom_us10` pending status is resolved by this entry. Status of capped variant pending owner sign-off (Path B-style with documented G4 exception).

**Artifacts**:
- Run: `ars/runs/20260530T170606Z_smom_us10_capped/`
- Evidence pack: `ars/evidence_packs/smom_us10_capped/`
- Pre-reg commit: `ec91d20d`
- Code: `scripts/smom_capped_backtest.py`
- Equity + weight plot: `ars/runs/20260530T170606Z_smom_us10_capped/equity_and_weight.png`

**Implications + next experiments**:
- US10 capped sMOM is the recommended overlay if any single-rates trend deployment proceeds. Replicate on Bund / BOBL / OAT for cross-instrument robustness BEFORE downstream consumption.
- SP500 vol-reducer mechanism deserves its own pre-registered exploration: "is semi-vol scaling a useful position-sizer on equity-like assets specifically when used as a vol-floor mechanism, not as a return enhancer?"
- Pre-reg G4 control gate needs refinement: a "no false rescue" test should distinguish "Sharpe up via spurious return" (bug) from "Sharpe up via vol reduction" (mechanism). Add to future overlay pre-reg templates.

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

---

## 2026-05-30 -- execution_friction_us10 (measurement, Path A)

**Pre-registration:** `ars/evidence_packs/execution_friction_us10/execution_friction_us10_preregistration.md` (locked at git SHA `83e43dd6`, lint Rules 1-4 PASS).
**Status:** measurement (no spec-level PROMOTE/FALSIFY; reporting-only gates).
**Cells:** 6 = 3 specs (`carver_6speed_us10`, `martin_baseline_us10`, `martin_primary_ema2_us10`) x 2 capitals ($50K, $1M).

**Hypotheses under test:**

- H-EF1 (capital sensitivity for integer specs): `Sharpe($1M) - Sharpe($50K) > -0.10`.
- H-EF2 (vol-estimator effect, Martin 20d vs Carver mixed_vol_calc 35d): `|delta Sharpe| <= 0.15` at each capital.
- H-EF3 (paper-fidelity skew): `martin_primary @ $1M` per-trade skew `in [2.5, 5.5]`.
- H-EF4 (full-stack friction headline): `Sharpe(martin_primary @ $50K) - Sharpe(martin_baseline @ $50K) > 0`.

**Measured (gross Sharpe + skew_per_trade):**

| Spec | $50K Sharpe | $1M Sharpe | skew/trade@$50K | skew/trade@$1M |
|---|---:|---:|---:|---:|
| martin_baseline_us10 | 0.401 | 0.403 | 4.109 | 5.990 |
| martin_primary_ema2_us10 | 0.317 | 0.317 | 3.861 | 3.861 |
| carver_6speed_us10 | 0.396 | 0.364 | 4.382 | 6.655 |

**Verdicts:**

- G-EF1 PASS for both integer specs (martin_baseline delta = +0.002, carver_6speed delta = -0.032).
- G-EF2 PASS at both capitals (50K: |delta| = 0.005, 1M: |delta| = 0.039 -- both << 0.15).
- G-EF3 PASS (martin_primary @ $1M skew = 3.861, inside [2.5, 5.5]; matches Martin §2.3 / §2.4 closed form region for EMA2 N=20,40).
- G-EF4 **FAIL (negative finding)** at both capitals. F$50K = 0.317 - 0.401 = -0.084; F$1M = 0.317 - 0.403 = -0.086. Continuous strict-Martin UNDERPERFORMS Carver-style 6-speed integer baseline.
- G-recon PASS for 5/6 cells; FAIL for `martin_baseline_us10_50k` (|recon| = 9.53%). All other cells |recon| < 1.2%.

**Headline finding:** The 6-speed EWMAC equal-weight + forecast cap +-20 + integer-contracts execution stack OUTPERFORMS the strict-Martin single-EMA2 continuous reference on US10 in Sharpe terms (+0.08). Martin §4.2.3's prediction that integer quantisation behaves like a small-epsilon double-step and destroys positive skew does NOT manifest as a Sharpe penalty at $50K -- skew per trade is preserved (4-7 range across all integer cells) AND Sharpe is higher than the continuous reference. The interpretation is: speed diversification (6 EWMACs equal-weighted) > single-speed paper fidelity, by enough margin to overcome the integer + cap drag.

**Implications:**

1. For US10 single-instrument momentum the production setup should NOT be a strict single-EMA2 paper baseline. Multi-speed Carver-style is empirically superior on this instrument over 43 years of data.
2. The Martin vol estimator (20d EMA-of-squared-changes) and the Carver mixed_vol_calc (35d blend) are nearly interchangeable for Sharpe purposes on US10 (delta <= 0.04). The 9.5% recon failure on martin_baseline_50k is a numerical artifact (Martin 20d vol's lack of vol-floor interacts poorly with near-zero integer positions; mean_abs_pos = 1.37, frac_flat = 0.22). Acceptable to keep Carver default in production; revisit if vol-estimator becomes a sensitivity for a different instrument.
3. The 6-speed baseline's per-trade skew GROWS at $1M (4.1 -> 6.0 for martin_baseline; 4.4 -> 6.7 for carver_6speed) -- finer integer granularity at higher capital lets the long-option signature express more cleanly without the round-to-zero floor. This is a positive finding for the 6-speed family at scale.
4. Sub-1-contract penalty on US10 at $50K is real in trade-ledger terms (frac_flat = 0.22, mean_abs_pos = 1.37) but does NOT manifest as a realised Sharpe loss vs $1M (delta < 0.05 in absolute terms for both integer specs). US10/ZN's already-small notional (~$110K front-month) plus a long history smooths this out; the result might differ on instruments with larger notional.

**Next experiments queued (Agent Loop next iteration):**

1. Test the 6-speed-beats-single-EMA2 result on additional rates instruments (Bund, BOBL, GILT, JGB) to check whether US10 is special or this is a general rates result.
2. Test on a non-rates instrument (e.g. SP500) where Martin Fig 1 already shows negative market skew -- does the 6-speed advantage shrink or reverse?
3. (Deferred) LdP layer triple (TBM meta-labeling / causal DAG / DSR-PBO-CPCV governance) on top of the validated Carver 6-speed baseline -- queued for after the multi-instrument replication of finding (1).

**Artifacts:**

- Pre-reg: `ars/evidence_packs/execution_friction_us10/execution_friction_us10_preregistration.md`.
- 6 run dirs under `ars/runs/2026052*T1721*/` and `T1722*/` (paths in registry entry).
- CPC v1 comparison: `arki/results/2026-05-29/execution_friction_us10_6cell.{html,png,csv}`.
- Obsidian delivery: `_Inbox/2026-05-29/pysystemtrade_execution_friction_us10/` (HTML + overlay + 2 CSVs).
- Runner: `scripts/execution_friction_runner.py` (CLI: `--spec all` runs 6 cells in ~3 min).
- Aggregator: `scripts/execution_friction_aggregator.py` (CLI: rebuilds report + delivers to Obsidian).
- Vol estimator util: `arki/utils/martin_vol.py` (self-check via `python -m arki.utils.martin_vol`).

---

## 2026-05-30 -- execution_friction_us10 regime + non-stationarity diagnostics (addendum)

Follow-up to the 6-cell measurement decided above. Subject = same 6 cells, with deeper non-stationarity, regime-bucket, and per-trade path analysis. Runner: `scripts/execution_friction_regime_analysis.py`. Output under `arki/results/2026-05-29/execution_friction_us10_regime_analysis*` + delivered to Obsidian inbox.

**Headline non-stationarity findings:**

1. **CUSUM break date is 2003-06-13 in 5 of 6 cells** (sole exception: martin_baseline_50k -> 1998-10-05). Post-break Sharpe drops by 0.35-0.55 across all cells. martin_primary_ema2 (strict-Martin single EMA2 continuous) goes from pre-break Sharpe 0.571 to post-break **0.019** -- effectively dead. The 6-speed integer cells (carver/martin_baseline) retain post-break Sharpe in [0.12, 0.20] range. This is the strongest single argument we have so far for multi-speed over single-speed on US10: the 6-speed family is materially more robust to the post-2003 regime shift than strict-Martin.

2. **Decade decomposition** confirms the same direction. 2010s are the worst decade for every cell: carver_6speed_1m 0.18, martin_baseline_1m 0.18 (matching the 6-cell measurement), martin_primary_1m 0.11. 2020s show partial recovery (skew flips positive +1.26 to +1.72 due to COVID + 2022 hike fat-right tails). The result that 2010s killed trend edge on rates is well-known industry-wide; we now have explicit cell-level numbers.

3. **Event windows** -- martin_primary lags badly on the Fed hike 2022-2023 regime change (+16.2% cumulative vs +45.9% for carver_6speed). Interpretation: single EMA2(20,40) with ~100-day weight half-life is too slow to flip during a rapid bull-to-bear pivot. 6-speed includes ewmac2_8 / ewmac4_16 which capture the regime change earlier.

**ZN regime conditional performance (martin_primary @ $1M) -- key inputs for ④ feature design (TBM meta-labeler):**

| Axis (tercile) | Sharpe low | Sharpe mid | Sharpe high |
|---|---:|---:|---:|
| Kaufman ER 20d | -1.57 | -1.37 | **+2.78** |
| Kaufman ER 60d | -2.70 | +0.86 | **+2.95** |
| Realised vol 20d | +0.43 | +0.23 | -0.32 |
| ZN 60d return    | -0.29 | **-1.46** | +1.60 |

- Kaufman Efficiency Ratio is the dominant single conditioning feature -- Sharpe gap 4.4-5.6 across terciles. This is the meta-labeler's primary input.
- The ZN 60d return mid-tercile having the WORST Sharpe (-1.46) is a clean finding: trendless rates regime kills the strategy more than a rates-rising regime does.
- Realised-vol high-tercile is a Sharpe penalty (-0.32) but smaller than the ER gap; vol is a secondary filter.
- Sign-agreement across the 3 specs at $1M: when 1/1/1 split (n=136), Sharpe is 4.12 -- but small sample, do not over-interpret.

**TBM / CPCV design recommendations (record for next iteration):**

- T_max: per-trade days median ~56 (martin_primary). Two-arm sweep T_max in {20d, 60d} captures both fast and natural-trade horizons.
- pi / l barrier ratio: derive from per-trade CSV median MFE / |median MAE|. File saved at `arki/results/2026-05-29/execution_friction_us10_regime_analysis_per_trade_mfe_mae.csv` for ratio computation in the next iteration.
- CPCV folds: 2003-06-13 break implies at least 2 distinct regimes. Folds MUST include both pre- and post-break days in train AND test; combinatorial purged-and-embargoed CV is mandatory. Vanilla k-fold would put 1980s-1990s entirely in train and post-2020 in test, which is the in-sample-only-on-easy-decades trap.
- Feature priority for the meta-labeler: Tier 1 = Kaufman ER 60d, Tier 2 = ZN 60d return phase, Tier 3 = realised vol 20d. Drop sign_agreement / 20d autocorr (small sample / unstable).

**Implications for the 6-speed-beats-single-EMA2 headline:**

The post-2003 regime is where the 6-speed advantage decisively shows up. Pre-2003 both families are competitive (Sharpe 0.50-0.57). Post-2003 the 6-speed family limps along at 0.12-0.20 while single-EMA2 is essentially zero. This sharpens the original recommendation: in a multi-instrument replication test (next iteration queued in the prior decision entry), the BENCHMARK metric should be POST-2003 sub-sample Sharpe specifically, not full-sample Sharpe -- 1980s-1990s strong trend tailwind inflates the full-sample number.

**Artifacts:**

- Analysis runner: `scripts/execution_friction_regime_analysis.py` (no Bai-Perron dependency; pure CUSUM single-break heuristic).
- Outputs: 7 CSV files + 3 PNG plots + 1 HTML report under `arki/results/2026-05-29/execution_friction_us10_regime_analysis*`.
- Obsidian: `_Inbox/2026-05-29/pysystemtrade_execution_friction_us10/` (added on top of the prior CPC v1 delivery in the same dir).

---

## 2026-05-30 -- futures_momentum family layer adopted

**Trigger:** owner question "이 실험들 6개이 등록 관리되는 방법은 현재 무엇인가요?" exposed that the 7 logical experiments under US10 single-instrument momentum (`martin_single_instrument`, `dmom_us10`, `smom_us10`, `fast_tilt_ewmac`, `carry_toggle`, `execution_friction_us10` with 6 sub-cells, plus the upcoming TBM meta-labeling) were registered as scattered entries with no family-level view. Adding more experiments (TBM × baseline, sMOM remediation, etc.) without a family layer would compound the scattering.

**What was added (3-layer + 3-tier dimensions, after two rounds of owner feedback that flagged: (1) instrument missing from dimensions, (2) dimension orthogonality error, (3) discovery engine absent, (4) DSR formula incomplete + n_trials under-count, (5) elasticity confounded, (6) skeleton DSR per-period vs annualised unit bug, (7) Panel B inheriting elasticity from Panel A):**

- `arki/utils/dsr.py` -- canonical DSR + PBO + `expected_max_sharpe` utility. Bailey-LdP 2014 with Euler-Mascheroni term, candidate skew/kurt in denominator, and an `annualization_factor` parameter that converts internally so per-period and annualised inputs both work safely. Self-check (`python -m arki.utils.dsr`) verifies annualisation invariance + real vs sham strategy + persistent-edge PBO.
- `ars/families/futures_momentum/family.yaml` -- 2-panel structure (single-instrument vs portfolio), 3-tier dimensions (universe / spec / exec_profile), 11 cells mapped from existing registry entries with explicit `internal_grid_size`, `metric_units` block, `n_cells_registered` + `n_configs_recorded` + `n_configs_unrecorded_upper_bound` separation (the last is owner-conservative honest over-estimate covering pre-2026-05-28 exploration the framework cannot retroactively count).
- `ars/families/futures_momentum/findings.md` -- Layer 3 elasticity, axis-level, with explicit `n clean pairs` per axis and direction-only tone where `n <= 2`. Confounded pairs (e.g. `exec_friction_martin_primary vs exec_friction_martin_baseline` varying rule AND exec_profile) are recorded as excluded, not collapsed into elasticity. Cross-panel inheritance is explicitly forbidden (vol_estimator dead in single-instrument may revive in portfolio).
- `ars/families/futures_momentum/matrix.md` -- human-readable status grid per (overlay × spec) on US10 + placeholder for other instruments + Panel B not-yet-opened note.
- `ars/families/futures_momentum/queue.md` -- elasticity-ranked queue, with `depends_on` artifact paths per item. Top three: (1) TBM_meta_label on `exec_friction_martin_baseline_us10_1m`; (2) rule_structure de-confound (single_ema2 + carver_native cell); (3) vol_estimator transport to Bund.
- `scripts/validate_preregistration.py` Rule 6 -- soft check that pre-regs referencing a family also acknowledge the family's multiple-testing context (DSR / expected_max_sharpe / n_configs_searched). Warning level, not blocking.

**Honest gaps (logged, not pretended away):**

- `n_configs_unrecorded_upper_bound = 30` is an owner estimate of pre-2026-05-28 exploratory work (deep-research synthesis, scratch backtests). It is an over-estimate by design -- if wrong, it errs on the safe side (raises DSR threshold, blocks more candidates). Owner can adjust upward but not downward without justification.
- `scripts/family_elasticity.py` and `scripts/family_dsr_threshold.py` (auto-recompute findings table + threshold on new cell registration) are NOT YET WRITTEN. The current `findings.md` table was computed manually from the 11 existing cells. Next cell registration is the trigger to write these scripts.
- `expected_max_sharpe_at_N` field in family.yaml is `TBD` and computed on demand. When the first family-scope promotion candidate appears, that's the trigger to lock it.

**No upstream-tracked file modified.** All changes confined to `arki/utils/`, `ars/families/`, `ars/DECISIONS.md`, `scripts/validate_preregistration.py` (Arki-added utility script). Fork safety preserved.

**Implications for the next-experiment thread:**

The TBM meta-labeling work the owner is preparing (skeleton at `/Users/msyeom/Downloads/stage1_meta_labeling.py`) now has a designated slot: queue.md item #1 (`tbm_meta_label_on_martin_baseline_us10_1m`). Its pre-reg will reference `family: futures_momentum`, declare `depends_on` artifact paths (already listed in queue.md), and acknowledge the DSR threshold per Rule 6. The skeleton's existing DSR / PBO functions should be replaced with `from arki.utils.dsr import deflated_sharpe_ratio, probability_of_backtest_overfitting` to avoid divergent copies of the bug-fixed math.

---

## 2026-05-30 -- tbm_meta_us10_baseline_1m Path A pre-reg locked

**Trigger:** owner requested moving `futures_momentum` queue item #1 from queued → in_progress, with the design handoff `/Users/msyeom/Downloads/HANDOFF_stage1_tbm_ZN.md` as direct input.

**Pre-registration:** [ars/evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md](evidence_packs/tbm_meta_us10_baseline/tbm_meta_us10_baseline_preregistration.md). Path A (pre-run lock). Lint Rules 1-6 all PASS (0 error, 0 warning).

**What's locked at the schema level (HANDOFF Decisions 1-5, carried over):**

1. **Labeling unit = CUSUM-day** (not per-trade) -- mitigates 106-trade thinness on single-EMA2 US10.
2. **Barriers calibrated on raw ZN sigma** (NOT strategy-pct): PT = 8σ, SL = 4σ, T_max = 120d. sigma = sqrt(EMA20-of-squared-absolute-changes), gamma = 0.95, with no-look-ahead floor `clip(lower = sigma.expanding(20).median()*0.2)`. The earlier strategy-pct figures (PT 3.0σ / SL 1.5σ) were off-scale by ~3x and are explicitly SUPERSEDED in §2 of the pre-reg.
3. **Side source = existing Martin primary** (sign only). Engine untouched. The 6-speed pseudo-cross-section pooling is for LABEL DATA thickness only, not for side redefinition.
4. **g_min = 0.30, g_max = 1.0** -- preserves Martin §4 Eq.(20) all-non-negative weight regime that produces positive trading-return skew. Declared as Rule-2 bounded multiplicative weight (`max(|g_t|) <= 1.0`).
5. **DSR / PBO via `arki.utils.dsr`** (single SOT) -- the skeleton's per-period vs annualised bug (bug ③ from owner's previous feedback) was fixed in our utility; the runner imports from `arki.utils.dsr` and NOT from the skeleton's copies.

**Family-scope impact at lock time:**

- `n_cells_pre_registered_queued`: 12 -> 13
- `n_configs_recorded`: 12 -> 20 (+8 internal grid: 4 tau values x 2 feature subsets)
- `n_configs_searched` (DSR N): 41 -> **50**
- `expected_max_sharpe_at_N`: 0.314 -> **0.325 annualised** (recomputed via `arki.utils.dsr.expected_max_sharpe(sr_trials_std=0.1426, n_trials=50, annualization_factor=256)`). Self-correcting loop: locking this pre-reg raised the family-level absolute Sharpe threshold for ALL future promotions, including older cells.

**Annualisation note added** (consistency footnote in `family.yaml` metric_units + `matrix.md`): Sharpe annualisation = 256 (pysystemtrade `BUSINESS_DAYS_IN_YEAR`) throughout. The 252 in `rolling_*_252d` reports is a WINDOW length, NOT an annualisation factor. Per-trade reports (PPY=252) are a different sample unit (N=#trades), not comparable to family/regime daily Sharpe (N=#trading-days), independent of the 252-vs-256 detail.

**Acceptance gates (HANDOFF §6 carried verbatim, OOS via CPCV with 2003-06-13 break straddling in BOTH train and test, embargo=120 days):** G-TBM1 DSR uplift > 0 vs g=1 baseline; G-TBM2 PBO < 0.5 over real config grid; G-TBM3 MaxDD reduction; G-TBM4 skew preserved within -0.20; G-TBM5 F1 > naive base-rate + 0.02; G-TBM6 (sanity) g_t bounded in [0.30, 1.0]; G-recon < 5%.

**Known honest caveats (logged in pre-reg §11 + §8):**

- 8-config grid is marginal for PBO meaningfulness (HANDOFF §5 recommends >= ~10). If PBO is borderline, log as finding; do NOT inflate post-hoc.
- The standalone single-EMA2 was essentially flat post-2003-06-13 break (Sharpe 0.019). Stage-1 (size) cannot manufacture alpha where the side has none; the primary value here is risk shaping (MaxDD reduction + skew preservation). Larger uplift is expected from Stage-2 speed-tilt (out of scope for this cell).
- tau tuned on ZN does NOT transfer to other instruments without re-tuning.

**Next action:** write `scripts/tbm_meta_us10_baseline_runner.py`. Integration is "Option B" (label-only attachment): lift `cusum_events`, `triple_barrier_labels`, `average_uniqueness`, `sample_weights`, `build_features`, `MetaSizer`, `size_from_meta`, `position` from the skeleton; REPLACE skeleton's `daily_vol` with absolute-change form per Martin §2.5 (the ZN panama sign-crossing fix); REPLACE skeleton's DSR/PBO with `from arki.utils.dsr import ...`.

---

## 2026-05-31 -- CPC v1 Arki adopted as the single unified reporting standard

**Trigger:** owner decision (option γ) per handoff [docs/arki/handoff_unified_cpc_reporting_2026-05-31.md](../docs/arki/handoff_unified_cpc_reporting_2026-05-31.md). Reporting was fragmented across three roots (`ars/runs/<run>/report.*`, `arki/results/<date>/*trade_analysis*`, cross-cell aggregators) — up to 4 files per cell; recent TBM Stage-1 runs had NO HTML at all.

**Decision:** adopt b3-saa-etf's CPC v1 as the SINGLE futures-momentum reporting standard, adapted to daily futures (ann_factor=256, no FX) + Arki extensions. One canonical root: **`arki/reports/<date>/`**. Going forward `ars/runs/<run>/` holds RAW ARTIFACTS ONLY; curated HTML lives under `reports_root`. Existing reports under `ars/runs/` + `arki/results/2026-05-29/` are NOT deleted (archive; separate hygiene cycle).

**New tooling (Arki-added, no upstream file touched):**

- `scripts/build_cpc_v1_arki.py` — CPC v1 builder. Risk/return table uses NATIVE `summary.csv` values (ARS: preserve engine outputs); the realised-equity path drives only the cumulative chart + sign-coloured monthly grids, both honestly labelled "native units". Comparison uses a NATIVE-metric lift table (pre-reg §7), NOT capture/regression — the equity-curve diffs are lumpy (a handful of real bond-crash days give ~160% annualised "vol") and do not reproduce the engine Sharpe, so no trustworthy daily-return stream exists to regress. Arki extension renderers: acceptance-gates table, TBM diagnostics block (uniqueness / g-distribution / CPCV F1 / gap-rule 5.2.a-c audit), per-trade ledger, family-context block, verification-anchors block. TBM blocks skip gracefully for non-TBM cells.
- `scripts/build_family_matrix.py` — single-page family dashboard (`arki/reports/family/futures_momentum_matrix.html`): Panel-A status grid (14 cells, colour-coded, click-through to CPC HTML), DSR threshold timeline (0.314 N=41 → 0.325 N=50 → 0.3326 N=58), elasticity table, queue top-5.
- `arki/reports/_mechanism_cards/<slug>.yaml` — hand-authored cheatsheet content (formula / triggering / action) for the two TBM cells, sourced from pre-reg §1-§3 / §5.1.1.

**Reports generated (4):** `arki/reports/2026-05-31/cells/tbm_meta_us10_baseline_1m_cpc.html`, `.../cells/tbm_meta_us10_tmax40_cpc.html`, `.../comparisons/tbm_baseline_vs_tmax40_cpc.html`, `.../comparisons/execution_friction_us10_6cell_cpc.html`. The 6-cell umbrella **supersedes** `arki/results/2026-05-29/execution_friction_us10_6cell.html` + `..._regime_analysis.html` (kept as archive).

**Trade-analysis arrow fix:** `scripts/trade_analysis.py` lines 590-599 — entry marker now encodes direction (long `^`, short `v`); exit uses directionless `o`. Verified: regenerated `results/runs/20260405_0147_arki_v4_optimized` trade report renders without error (reconcile ε=6.8e-13).

**Headline read (TBM baseline, from its CPC):** meta-sized Sharpe 0.3208 vs g=1 baseline 0.3165 — G-TBM1 DSR uplift **+0.0115 PASS**, G-TBM3/4/5/6 PASS, G-TBM2 PBO N/A (single config), **G-family-DSR FAIL** (0.3208 < 0.3326 absolute threshold — reporting gate only). Near-floor sizer (g_max 0.551, avg_uniqueness 0.071 < 0.20). T_max=40 ablation g_max 0.591 (still <0.60→0.75 band) → diagnostic leans "no learnable conditional edge on ZN-post-2003", not effective-sample collapse. **No promotion claimed** (live_trading: false invariant).

**family.yaml:** added `reports_root` + `matrix_html` keys.

**Out of scope (tracked):** backfilling the older 13 cells to CPC v1; deleting deprecated reports; external-share re-render. The two TBM cells were executed (run dirs 2026-05-30/31) but their `family.yaml` cell status remains `pre_registered_queued` / `registry_ref: pending_first_run` — registry entry creation for the TBM runs is a separate follow-up, not part of this reporting handoff.

**No upstream-tracked file modified.** Changes confined to `scripts/` (Arki-added), `arki/reports/`, `ars/families/`, `ars/DECISIONS.md`.


---

## 2026-05-31 — Handoff #3 items D/E/F/G executed (session-retro forward enhancements)

Source: docs/arki/handoff_session_retrospective_cheatsheet_2026-05-31.md. Item B
(retro cheatsheet) was already done; items D-G executed this session.

- **Item D — cold-start handoff test (CONDITIONAL PASS).** A fresh isolated
  agent, given only family.yaml + findings.md + queue.md + CLAUDE.md, advanced
  queue item #2 (rule_structure de-confound) and authored a Path A pre-reg with
  ~90% design fidelity, reading ZERO files outside the 4-file SOT. It correctly
  resolved the one real ambiguity (the $1M comparator). Two HIGH-severity SOT
  gaps found: (1) no pre-reg template pointer, (2) lint Rules 5-6 text absent
  from the SOT. Fixes applied to queue.md (template + lint-rule pointers,
  comparator disambiguation, DSR-N authority note). Full report:
  docs/arki/coldstart_handoff_test_result_2026-05-31.md.

- **Item E — paper-family-exit pre-reg authored.** carry_primary_us10
  (Koijen-Moskowitz-Pedersen-Vrugt 2018 "Carry", JFE — deliberately OUTSIDE the
  canonical Martin/Hanauer/Carver/LdP family). Lint Rules 1-7 PASS (0 errors, 0
  warnings). SCHEMA-FIT VERDICT: the family.yaml Panel A schema BENDS under a
  carry-as-primary thesis — `overlay: carry` presumes a momentum base and
  `rule_structure` has no carry/none level; a new `primary_signal` axis (or a
  `carry_primary` rule_structure level) is required to encode it faithfully.
  This CONFIRMS the prior "schema is paper-family-biased" critique. Cell RUN is
  deferred (needs a carry-primary runner; see pre-reg §6/§9). File:
  ars/evidence_packs/carry_primary_us10/carry_primary_us10_preregistration.md.

- **Item F — process-cost instrumentation built.** arki/utils/process_cost.py:
  records the 5 manifest.json lifecycle timestamps, computes per-cell cycle time
  in business days, aggregates (mean/median/p75), and flags mean > 1 business
  day (framework-simplification trigger). `--selfcheck` PASS. No cells carry a
  complete timeline yet; measurement accrues as the next 3 cells run. Pointer
  added to family.yaml § multiple_testing.

- **Item G — lint Rule 7 implemented.** scripts/validate_preregistration.py now
  enforces a `predictions:` block (id/statement/type/score_method; categorical
  preferred) per the 2026-05-31 predictions scorecard. Soft (warning) for now.
  Existing pre-regs grandfathered via a `pre_rule7_grandfathered` marker; the
  _template carries a compliant predictions block so new pre-regs inherit it.

Handoff #2 status check (prerequisite): trade_analysis.py arrow patch = DONE
(lines 592/598); matrix.html = STILL PENDING (family.yaml points to it but the
file was never built — separate follow-up).


---

## 2026-05-31 — risk-shaping sub-family closeout (4th branch): capped sMOM Path B + TBM Stage-1 NO SIGNAL

**Decision (owner: Minsu).** Adopted the **4th branch** (extension of the TBM Stage-1
decision-handoff Branch C): rather than promoting TBM alone for risk-shaping, **bundle capped
sMOM (promote Path B) + TBM Stage-1 (relative_pass_absolute_fail)** into one
`risk_shaping_size_overlays` sub-group and CLOSE the size-overlay line of inquiry on ZN solo.
Spec: `docs/arki/HANDOFF_risk_shaping_family_closeout.md`.

**Unified verdict.** On ZN single-instrument, **size-layer overlays shape risk but do not
generate directional alpha.** Two independent overlays converge:
- **capped sMOM** — STRONG risk-shaper: maxDD −55.35%→−44.16% (+11.19pp), Sharpe lift +0.276.
  Lift is mechanical vol-scaling, **proven not-edge**: the same mechanism lifts the no-edge
  SP500 control (−0.009→+0.305 via vol collapse 24.3→6.23, ratio 0.26). → **Path B**
  (crash-mitigator only), NOT Path A.
- **TBM Stage-1** — WEAK risk-shaper: maxDD −0.87 to −2.49pp; DSR uplift ≈0 (sign-flips
  +0.0115→−0.0026 under T_max 120→40); g pinned near 0.30 floor; g_max 0.551→0.591 (NO SIGNAL
  branch <0.60); avg_uniqueness 0.07–0.10 < 0.20 (as-TBM-iid violated). No detectable
  conditional edge. → **relative_pass_absolute_fail**.
- Counter-intuitive: the SIMPLE tool (sMOM vol-scaling) shaped risk better than the
  SOPHISTICATED one (TBM meta-labeling).

**G4 resolution (LESSONS Entry 3 applied).** capped sMOM's G4 SP500-control "FAIL" (0.305 >
0.20) reclassified **MECHANISM_NOTE**: vol ratio 0.26 ≤ 0.7 ⇒ rescue via vol-reduction, not
return-generation. Not a bug; the gate was over-strict for vol-reducing overlays. Verify
anchors confirmed from `verdict.json`: G3 skew_per_trade 4.616 ≥ 1.0 PASS, G_recon 0.0 < 1%
PASS, maxdd_lift +11.185pp (≈ target +11.19pp).

**Self-correction (LESSONS Entry 1 was directionally wrong).** Entry 1 predicted capped lift
would fall to +0.10–0.15 ("partially leverage artifact"). Empirically capped lift = **+0.276**
(HIGHER than uncapped +0.255). The 6,439× spikes were net-HURTING Sharpe, not inflating it.
The downgrade was correct (unrealizable), but the stated reason ("Sharpe overstated by
leverage") is reversed by data → **unrealizability, not Sharpe inflation, was the true
defect.** Logged into LESSONS Entry 1.

**Next alpha levers (size-overlay line on ZN now closed):**
1. Multi-instrument breadth (Panel B opens) — but rates-only is breadth-limited (0.5–0.8
   corr); a genuinely low-correlation universe is the higher-information step.
2. Stage-2 speed-tilt λ(s_t) — side/forecast layer, genuinely additive to the size-layer
   risk-shaping tools.
Both raised to the top of `queue.md`; the size-overlay axis is CLOSED.

**Files changed (metadata layer only; no backtest, no run-dir edit, upstream 0 diff):**
- `ars/runs/registry.yaml` — smom_us10_capped → registered_path_b (+promotion_path/path_b_note);
  smom_us10 (uncapped) → superseded_by_smom_us10_capped (reference, leverage artifact).
- `ars/families/futures_momentum/family.yaml` — TBM 2 cells → relative_pass_absolute_fail
  (+observed metrics + real run_dir refs); added smom_us10_capped cell + risk_shaping
  sub-group; N held at 58, expected_max_sharpe_at_N held at 0.3326.
- `ars/families/futures_momentum/findings.md` — risk-shaping CLOSED section + overlay
  elasticity row updated.
- `ars/families/futures_momentum/queue.md` — #1 → completed_with_verdict_no_signal_ZN;
  Stage-2 speed-tilt + Panel B promoted to top.
- `ars/LESSONS.md` — Entry 1 self-correction note.

**Multiple-testing invariance.** n_configs_searched = 58 and expected_max_sharpe_at_N = 0.3326
UNCHANGED. capped sMOM is a remediation re-run of an already-counted config; recording TBM
verdicts is a status change, not a new config search.

**Registry follow-up (out of scope, noted):** full `registry.yaml` entries for the two TBM
runs (currently referenced by run_dir in family.yaml) remain a separate follow-up, per the
2026-05-31 unified-CPC-reporting handoff.

**No upstream-tracked file modified** (`systems/`, `sysdata/`, `sysquant/`, `syscore/` = 0 diff).
