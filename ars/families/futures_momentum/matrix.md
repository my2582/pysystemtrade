# matrix — futures_momentum family

Human-readable dashboard of the family. Schema lives in `family.yaml`;
axis-level findings in `findings.md`; queue in `queue.md`. This file is
for at-a-glance scanning: "what has been tried, what's pending."

---

## Family stats (as of last update)

| Field | Value |
|---|---:|
| n_cells_registered | 12 |
| n_cells_pre_registered_queued (TBM pre-reg locked 2026-05-30) | 13 |
| n_configs_recorded (Σ internal_grid_size) | 20 |
| n_configs_unrecorded (conservative upper bound) | 30 |
| **n_configs_searched (used as DSR N)** | **50** |
| annualization_factor | 256 |
| **expected_max_sharpe_at_N=50** (annualised) | **0.325** |

> **Annualisation footnote (consistency).** Sharpe annualisation = 256 throughout
> (pysystemtrade `BUSINESS_DAYS_IN_YEAR` convention). When ARS reports show
> `rolling_*_252d`, the 252 is the rolling WINDOW length (lookback in trading
> days), NOT an annualisation factor — annualisation is √256 everywhere.
> Per-trade reports (e.g. `scripts/trade_analysis.py` uses PPY=252) are a
> DIFFERENT sample unit (per-trade, N=#trades) — not comparable to family /
> regime daily Sharpe (N=#trading-days), independent of the 252-vs-256 detail.

**Promotion gate at family scope:** candidate cell's annualised Sharpe
must clear `expected_max_sharpe(sr_trials_std=std{SR_n}, n_trials=41,
annualization_factor=256)`. Currently no cell has been DSR-checked at
family scope.

---

## Panel A — single-instrument (status grid)

Rows = overlay axis; columns = (vol_estimator, rule_structure, exec_profile, capital).
Cell content = status code or `—` if untested. Status codes:
`✅PRO` promoted, `✅POH` promoted-post-hoc, `📊MEAS` measurement (no spec verdict),
`⚠REM` pending remediation, `❌FAL` falsified, `❌REF` refuted, `⏳QUE` queued, `—` untested.

### Instrument = US10

| overlay \ (vol, rule, exec, cap) | carver_mixed, 6sp, carver_native, 50k | carver_mixed, 6sp, carver_native, 1m | martin_20d, 6sp, carver_native, 50k | martin_20d, 6sp, carver_native, 1m | martin_20d, 1ema2, paper_fid, 50k | martin_20d, 1ema2, paper_fid, 1m |
|---|---|---|---|---|---|---|
| none      | ✅POH 0.350 / 📊MEAS 0.350 | 📊MEAS 0.317 | 📊MEAS 0.353 ⚠recon | 📊MEAS 0.355 | 📊MEAS 0.316 | 📊MEAS 0.316 |
| carry     | ❌REF | — | — | — | — | — |
| sMOM      | ⚠REM (sizing bug) | — | — | — | — | — |
| dMOM      | ❌FAL | — | — | — | — | — |
| fast_tilt | ❌FAL (weights tilted) | — | — | — | — | — |
| TBM_meta  | ⏳QUE (top of queue) | ⏳QUE | — | — | — | — |

### Instrument = SP500

| overlay \ ... | carver_mixed, 6sp, carver_native, 50k |
|---|---|
| none | ✅POH −0.009 (martin_post_hoc_baseline_sp500) |
| everything else | — |

### Instrument = Bund / BOBL / GILT / JGB

All untested. Highest-priority replication target = `martin_baseline_us10`
finding (vol_estimator near-zero direction): does it hold on Bund?

---

## Panel B — portfolio (empty; awaiting first pre-reg)

Opens with the queue item: `DM_rates_5, equal_weight, TS_only` × best
Panel A US10 spec. No cells yet.

---

## What's been LEARNED (one-liners; details in findings.md)

- **vol_estimator** on US10 ≈ 0 Sharpe effect (n=2 clean pairs). Don't
  burn more US10 cells on this axis.
- **overlay** is high-risk: 3 falsified (carry-on-rates, dMOM, fast-tilt),
  1 pending remediation (sMOM). Each was Path A or Path Z disciplined.
- **rule_structure** direction is NOT YET CLEANLY ATTRIBUTED — confounded
  with exec_profile in the only available pair. **Top de-confound priority.**
- **execution friction at $50K** does NOT manifest as Sharpe penalty
  relative to $1M on US10. The per-trade skew grows at $1M (finer integer
  grid lets long-option signature express), but headline Sharpe is
  capital-invariant within ±0.05.
- **2003-06-13 structural break** (from regime analysis, file pointer in
  `arki/results/2026-05-29/`) splits the family history: pre-2003
  Sharpe ~0.5, post-2003 ~0.15 for integer specs, ~0 for continuous
  Martin primary. Multi-instrument replication should use POST-2003
  sub-sample Sharpe as the primary metric, not full-history.

---

## Pointers

- Layer 1 registry: `ars/runs/registry.yaml`
- Layer 2 schema:   `ars/families/futures_momentum/family.yaml`
- Layer 3 findings: `ars/families/futures_momentum/findings.md`
- Queue:            `ars/families/futures_momentum/queue.md`
- DSR/PBO utility:  `arki/utils/dsr.py` (`python -m arki.utils.dsr` self-check)
- Latest cross-cell results: `arki/results/2026-05-29/execution_friction_us10_*.html`
- Decision log: `ars/DECISIONS.md` (entries dated 2026-05-30 for this family)
