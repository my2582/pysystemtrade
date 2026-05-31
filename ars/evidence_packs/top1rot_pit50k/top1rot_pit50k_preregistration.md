# top1rot_pit50k — Pre-registration

<!-- pre_rule7_grandfathered: authored before Rule 7 (2026-05-31); see docs/arki/session_predictions_scorecard_2026-05-31.md -->

**Date written**: 2026-05-29 (BEFORE run)
**Branch**: `feat/arki-backtest-toolkit`
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner).
**Owner**: Minsu Yeom
**Implementer**: Claude Opus 4.7
**Owner pre-registration sign-off**: 2026-05-29 by Minsu Yeom; locked by the git commit that creates this file.

This document is **pre-registered under `ars/PROMOTION.md`**. The grid, gates, and decision rules MUST NOT be changed after the run begins. Data and code snapshots are recorded at §5/§6 below and re-confirmed in `manifest.json` at run-start.

Path A genuine pre-registration (locked BEFORE runner is written). First experiment under the formalised `<engine>_<universe>` slug convention introduced in `ars/PROMOTION.md` §Naming on 2026-05-29.

Design doc: `references/strategy/2026-05-27_absmom_rotation_spec.md` (v0.3, single-position momentum rotation). PIT universe builder spec + verify: same dir.

---

## 1. Background and motivation

Two motivating prior runs:

- `ars/runs/registry.yaml#20260528T161350Z_martin_single_instrument` — Martin Fig 1 single-instrument reproduction. US10 alone with 6-speed EWMAC, $50k, vol_target=20%, achieves **Sharpe_gross 0.396** with per-trade skew 4.38; SP500 with the same setup achieves **Sharpe_gross −0.005** (positive-skew on rates, negative-skew on equity). Reconciliation tight.
- `references/strategy/2026-05-27_signal_implementation_research.md` — single-position trend SR is structurally weak (Carver ~0.24 individual; ~0.30–0.40 pseudo-diversified). Diversification — not signal cleverness — is what lifts portfolio SR. Hanauer & Windmüller's `cMOM` vol-targeting is the strongest sourced enhancement; cross-sectional ranking is decile-based portfolio (never single-name top-1) in the sourced literature.

**The question E1 asks**: if the cross-sectional / diversification benefit is what lifts SR, does a **single-position weekly rotation** over a PIT-eligible universe (always invested in the strongest-momentum instrument) deliver materially more Sharpe and lower MDD than a **fixed single-instrument** baseline using the same EWMAC trend signal?

This is the single-decision test of universe choice — fixed vs rotation — with everything else (signal, vol_target, capital, integer-contract sizing, baseline cost model) held identical to the martin baseline.

Theoretical expectation (per signal-implementation research note):
- E[Sharpe lift] is modest (small AUM cannot capture full Carver portfolio uplift); we set the gate at **+0.05** (sleeve-screening level), not at the Carver +0.30–0.60 portfolio range.
- E[MDD reduction] is the more plausible mechanism: rotation away from underperforming instruments during regime breaks should cap left-tail relative to a frozen-instrument allocation. Set gate at **+5.0 pp** (less negative).
- E[Cost burden] from rotation is the principal risk; the turnover gate constrains it.

## 1.1 Paper assumption set + empirical checks (Rule 3 compliance)

Source basis: Carver "Systematic Trading" + Hanauer & Windmüller (2022) §3 + Martin (2023) §2-§3 (for the baseline this experiment is compared against).

| Assumption | What the source claims | Empirical check on this run |
|---|---|---|
| Cross-sectional rotation requires breadth (Carver) | Carver per-instrument trend SR ≈ 0.24; ~1.0 portfolio SR achieved with 30-100 instruments and low cross-correlation. Top-1 single-name rotation is NOT what Carver's diversification math addresses. | **Acknowledged limitation by design**: gate at +0.05 lift (sleeve-screening level), not at portfolio-uplift levels. If lift absent, "rotation does not transfer at single-name top-1" finding registers without falsifying Carver. |
| Hanauer's literature is decile-portfolio based | Hanauer & Windmüller (2022) uses 10-decile cross-sectional portfolios, NOT top-1. | **VIOLATED by design.** Top-1 selection is OUT of paper's setting. Verdict is about top-1 on this universe, not about Hanauer's mechanism. |
| Baseline (martin US10) is in-class for §2.3 | `forecast_cap=20` is §4 nonlinear (per martin pack post-review correction); sign-episode aggregation ≠ Eq. 12 fixed-M. | Documented in baseline pack. Carry-through here: comparison is "rotation vs fixed-US10 baseline" both in §4-nonlinear regime; cap effect cancels (ratio of two §4 instances). |
| PIT universe membership is stable enough | Membership must be stable enough that "always-invested top-1" is meaningful, not dominated by inclusion/exclusion noise. | Parquet manifest: 50 instruments, 5+ year history, ADV ≥ 1000, staleness ≤ 15d. Stability recorded in manifest. |

### Note on assumption violations vs gates

The dominant assumption violation is "top-1 selection over a small AUM-restricted universe is not in either Carver's or Hanauer's papers." The experiment is therefore framed as a **discovery probe**, not a paper validation. Verdict reads "top-1 weekly rotation on PIT50k achieves / does not achieve gates G1 and G2 vs the martin US10 baseline," not "Carver / Hanauer validated / refuted."

## 2. Hypotheses

Material thresholds are pre-registered ex-ante; no grid-search on the result (López de Prado AFML Ch.3).

- **H-T1 (Sharpe lift, primary)**: top-1 rotation lifts gross Sharpe materially vs the martin US10 baseline. Material threshold = **+0.05** (consistent with b3 SRP Profile B screening convention).
- **H-T2 (crash reduction, primary)**: top-1 rotation reduces geometric maxDD materially vs the martin US10 baseline. Material threshold = **+5.0 pp** (less-negative; the diversification mechanism).
- **H-T3 (turnover budget)**: rotation does not blow the cost budget. Material threshold = `ann_subsystem_turnover ≤ 2.0 × baseline_turnover` (baseline = 34.41 → ceiling 68.82). Above that, transaction costs would erode the headline numbers.
- **H-T4 (skew preservation)**: rotation does NOT destroy the per-trade positive skew of the underlying EWMAC trend signal. Threshold = **`skew_per_trade ≥ 1.0`** (long-option signature preserved).
- **H-T5 (false-rescue control)**: rotation Sharpe is not entirely explained by the rotation collapsing into a single high-vol equity name (proxy-for-SP500 effect). Diagnostic = report the per-name fraction of weeks held; if **any single instrument is held > 60% of weeks**, flag for investigation (no automated FAIL; owner judgement).
- **H-T_recon (reconciliation)**: `|sum(daily strategy P&L) − sum(per-trade P&L from ledger)| / |sum(daily P&L)| < 5%` — trade attribution is clean.

## 3. Grid (one decision per row)

**Single decision**: instrument selection rule = fixed-US10 (baseline) vs weekly top-1 rotation over the PIT-eligible universe (treatment).

Everything else (signal, vol_target, capital, sizing, costs) is held IDENTICAL to the martin baseline so attribution is unambiguous.

| Cell | Variant | Notes |
|---|---|---|
| cell-0 (baseline) | martin US10 standalone — 6-speed EWMAC (2/8, 4/16, 8/32, 16/64, 32/128, 64/256) equal-weight; carry off; soft cap ±20; vol_target=20%; capital=$50k; IDM=1.0; integer contracts (round-positions); buffered position | results from `ars/runs/20260528T161350Z_martin_single_instrument/` (US10 row): Sharpe_gross 0.396; maxDD_geom −55.35%; ann_turnover 34.41; skew_per_trade 4.38; n_trades 342 |
| cell-1 (treatment) | same EWMAC signal + vol_target + capital + sizing as cell-0, but **weekly top-1 selection** over the PIT universe (rebuilt at vol_target=20%, k=3); always invested in argmax of combined EWMAC forecast | runner: `scripts/run_top1rot_pit50k.py` |

Constants (ex-ante, FIXED):

- **Signal**: combined 6-speed EWMAC forecast, equal weights (1/6 each), soft cap at ±20. Identical to martin.
- **Vol target**: 20.0% annualised. Matches martin baseline (single-decision rule). The strategy spec's 30% target is a SEPARATE future experiment (`top1rot_pit50k_v30` vs `top1rot_pit50k_v20`).
- **Capital**: $50,000 USD.
- **Rebalance frequency**: weekly (W-FRI) — both for top-1 selection and for position re-sizing.
- **PIT universe filter** (rebuilt at vol_target=0.20, k=3 for this experiment):
  - exclude FX, exclude OilGas, exclude China patterns
  - require ≥ 5 years price history at the rebalance date
  - require most-recent price ≤ 15 days stale at the rebalance date
  - require ADV ≥ 1000 contracts/day (static, exchange-ref)
  - require `E_d × 3 ≤ $50,000` where `E_d = mult × dailyDiffVol_d × √256 × FX_d / 0.20`
- **Tie-break** (when argmax forecast ties to 4 decimals): higher trailing 21-day realized Sharpe; if still tied, alphabetical instrument code.
- **Contract sizing**: vol-target integer contracts (no fractional) using engine `mixed_vol_calc(backfill=False)`.
- **Transaction costs**: spread cost from `data/futures/csvconfig/spreadcosts.csv` (per-instrument); applied symmetrically on entry + exit.
- **Cutoff**: 2026-04-02 (matches martin baseline last data date).
- **Backtest start**: 2015-01-04 (last 10y window — same start as the `Last10y` slicer in CPC v1; ensures sufficient warm-up of PIT history requirement).

No grid-search on any H-T threshold.

## 4. Gates / decision rules

| Gate | Metric | Threshold | Hypothesis |
|---|---|---|---|
| G1 (primary) | `Sharpe_gross_lift = Sharpe_rotation − Sharpe_baseline` | `≥ +0.05` | H-T1 |
| G2 (primary) | `maxDD_geom_lift_pp = maxDD_rotation − maxDD_baseline` (less negative) | `≥ +5.0 pp` | H-T2 |
| G3 | `ann_subsystem_turnover` (rotation) | `≤ 2.0 × baseline_turnover = 68.82` | H-T3 |
| G4 | `skew_per_trade` (rotation) | `≥ 1.0` | H-T4 |
| G5 (diagnostic) | max-share-of-weeks held by any single instrument | `< 60%` (FLAG if exceeded; owner judgement, no automated FAIL) | H-T5 |
| G_recon | reconciliation diff of daily P&L cumsum vs per-trade ledger cumsum | `< 5%` | H-T_recon |

**Promotion paths:**

- **Path A (strict promotion)**: G1 PASS AND G2 PASS AND G3 PASS AND G4 PASS AND G_recon PASS → promote to evidence pack as a VALIDATED enhancement of fixed-instrument trend. Universe-choice attribution clean.
- **Path B (regime-conditional)**: G2 PASS AND G3 PASS AND G4 PASS AND G_recon PASS (G1 may fail) → promote as CRASH-MITIGATING ROTATION (the diversification mechanism shows in tail but not in mean). Owner sign-off required.
- **FALSIFY**: G2 FAIL AND G1 FAIL → status `falsified`. Finding: rotation over PIT universe does not deliver the diversification uplift at $50k single-position; cross-sectional benefit is too small to overcome transaction cost + thin-pool risk on this account size.
- **REFUTE (partial)**: G4 FAIL (skew destroyed) → status `refuted`. Finding: rotation destroys the long-option signature of EWMAC trend (e.g., averaging across cohorts smooths the skew); the per-trade tail-shape that makes the strategy theoretically defensible is lost.
- **INVESTIGATE**: G5 flag triggers (single instrument held > 60% of weeks) → halt promotion; investigate whether the rotation degenerated into a fixed-instrument proxy. Owner judgement before any status change.

## 5. Data snapshot

- **Source instruments**: `data/futures/adjusted_prices_csv/*.csv` (all instruments passing the §3 PIT filter — names enumerated at runtime, frozen in `manifest.json`).
- **FX**: `data/futures/fx_prices_csv/<CCY>USD.csv` (full daily series).
- **Instrument config**: `data/futures/csvconfig/instrumentconfig.csv` (pointsize, currency, asset class).
- **Spread costs**: `data/futures/csvconfig/spreadcosts.csv`.
- **PIT membership matrix**: rebuilt by `scripts/build_pit_universe.py` with `--vol-target 0.20 --min-contracts-held 3 --capital 50000 --label c50k_n1_v20_k3`. Output parquet: `references/strategy/pit_universe_c50k_n1_v20_k3.parquet`. SHA256 of this parquet recorded in `manifest.json`.
- **Cutoff**: 2026-04-02.
- **Snapshot identifier**: git SHA of run-start commit (recorded in `manifest.json`).

## 6. Code snapshot

- **Strategy module (new)**: `src/arki_strategies/absmom_rotation.py` — top-1 selection + integer-contract vol-targeted sizing on PIT universe.
- **Runner (new)**: `scripts/run_top1rot_pit50k.py` — driver that loads PIT universe, calls strategy module, emits standard run artifacts (`stats.yaml`, `daily_returns.csv`, `equity_curve.csv`, `position_snapshot.csv`, `manifest.json`, `report.html`).
- **Baseline regeneration**: not re-run; we reference the martin baseline US10 row as-is from `ars/runs/20260528T161350Z_martin_single_instrument/` (single-decision rule means baseline must be unchanged).
- **Engine**: pysystemtrade `sysquant.estimators.vol.mixed_vol_calc(backfill=False)` for vol; EWMAC computed natively in numpy/pandas on adjusted prices (same finite-state form as engine's `systems.provided.rules.ewmac.ewmac`).
- **Python**: 3.10.15.
- **git SHA at run-start**: recorded in `manifest.json` at run time.

## 7. CPC v1 comparison plan

This run is a 2-variant comparison (martin US10 baseline vs top-1 rotation) → CPC v1 is **MANDATORY** per `ars/PROMOTION.md` §Report-tiers.

**Implementation status (declared ex-ante)**: the pysystemtrade CPC v1 reference impl `scripts/build_cpc_v1_pysys.py` is still TBD (per PROMOTION.md §CPC v1 spec). All prior multi-variant runs in this repo (`dmom_us10`, `smom_us10`, `fast_tilt_ewmac`, `carry_toggle`) shipped without CPC v1 output for the same reason — framework infrastructure not yet ported from `b3-saa-etf/scripts/build_cpc_v1.py`.

**Owner decision (locked here)**: E1 ships without CPC v1 (matching the existing in-repo precedent). CPC v1 porting from `b3-saa-etf` will be triggered at the start of E2 (`dualmom_pit50k`) and applied retroactively to E1's evidence pack at that time. The porting must reflect any recent upstream upgrades to `b3-saa-etf/scripts/build_cpc_v1.py` (owner-flagged: "최근 업그레이드됨").

**Series planned** (for E2 retrofit):

| Series | Source kind | Path | is_benchmark |
|---|---|---|---|
| baseline_US10 | panel | re-extracted from martin run dir | true |
| rotation_PIT | panel | from this run's `daily_returns.csv` | false |
| US10_buy_and_hold | panel (price diff / σ_norm) | derived | (market reference) |

Periods: `Full` = 2015-01 to 2026-04; `Last5y` = 2021-04 onward. Both pre-registered ex-ante.

## 8. Out of scope (deferred)

- vol_target = 30% (strategy spec target). Will be tested in a follow-up experiment after E1 attribution is clean.
- Dead-zone whipsaw overlay (`top1rot_dz_pit50k`). E3.
- dMOM-style bear-state down-weighting (`top1rot_dmom_pit50k`). E4.
- Dual-momentum 3/6/12M signal (`dualmom_pit50k`). E2 — triggers CPC v1 porting.
- Live trading (forbidden by `ars/project_ars_profile.yaml`: `live_trading: false`).
- Cross-account / multi-strategy portfolio. Downstream (b3-saa-etf, arki-future-fund-engine, arki-gtaa) territory.
