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
