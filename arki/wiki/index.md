# pysystemtrade wiki — index

The durable knowledge base for Arki's pysystemtrade fork. **Start here.** Read [schema.md](schema.md)
for how it works (the one rule: *agent memory is a cache, this wiki is the source of truth*).
Fork-safety + the rules: [`../README.md`](../README.md).

**Current state: IN TRANSITION** — documented baseline **v4** (`arki_production.yaml`, 24 inst, $200k)
→ leading candidate **dm37** (`dm37_1m.yaml`, 37 inst, $1M). Research only; `live_trading: false`; no
run is formally promoted. → [system/system-card.md](system/system-card.md) (session-prime card).

## System — how the live system works
- [system/system-card.md](system/system-card.md) — **session-prime card** (hook-injected); compact, cited production truth.
- [system/architecture.md](system/architecture.md) — the pysystemtrade pipeline (rules → forecasts → sizing → dynamic optimisation).
- [system/lineage.md](system/lineage.md) — version spine v1→v4-fresh + the dm37 candidate; flags config-name drift.
- [system/universe.md](system/universe.md) — instrument universe (24 v4.1 vs 37 dm37) + the stale-data caveat.

## Findings — settled research conclusions
- [findings/universe-sweep.md](findings/universe-sweep.md) — asset-class sweep: keep 25-inst + OilGas + handcraft (positive skew). Settled.
- [findings/futures-momentum.md](findings/futures-momentum.md) — `futures_momentum` family findings: 14 cells, TBM Stage-1 NO SIGNAL verdict, sMOM remediation chain, axis-level elasticity, family DSR @ N=58 = 0.3326 ann. **Ongoing** (not settled — first measurement 2026-05-31).

## Research families — ongoing ARS-governed work
- [`../../ars/families/futures_momentum/`](../../ars/families/futures_momentum/) — 2-panel (single-instrument / portfolio) × 3-tier dims (universe / spec / exec_profile). `family.yaml` (schema), `findings.md` (elasticity), `matrix.md` (status grid), `queue.md` (commitments + cycle-time targets).
- [`../utils/dsr.py`](../utils/dsr.py) — Deflated Sharpe + PBO + expected_max_sharpe utility (annualisation-aware single SOT for the family).
- [`../reports/2026-05-31/`](../reports/2026-05-31/) — CPC v1 cell reports + session retrospective cheatsheet (`family/futures_momentum_session_retro_cheatsheet.html`).

## Handoffs — open / pending action
- [`../../docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md`](../../docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md) — **OWNER decision pending**: TBM Stage-1 NO SIGNAL verdict, 3 branches (A accept / B re-run / C reframe).
- [`../../docs/arki/handoff_unified_cpc_reporting_2026-05-31.md`](../../docs/arki/handoff_unified_cpc_reporting_2026-05-31.md) — Implementer in progress: unified CPC v1 reporting (status check needed for matrix.html + trade_analysis arrow patch).
- [`../../docs/arki/handoff_session_retrospective_cheatsheet_2026-05-31.md`](../../docs/arki/handoff_session_retrospective_cheatsheet_2026-05-31.md) — Insurance + 4 forward enhancements (D cold-start / E paper-family exit / F process-cost / G lint Rule 7).
- [`../../docs/arki/session_predictions_scorecard_2026-05-31.md`](../../docs/arki/session_predictions_scorecard_2026-05-31.md) — Predict-then-measure scorecard (7.5/10, 75% hit rate).

## Process — how we work
- [process/index.md](process/index.md) — backtest process, config map, estimation reference, ops manual, ARS.

## External structured indices (not duplicated here)
- `results/runs/registry.yaml` — run index (no promotion field).
- `docs/arki/strategy_evolution.md` — chronological promotion log (the wiki's `log.md` points to it).
- `scripts/backtest_config/*.yaml` — config definitions of record.
- `ars/` — ARS profile + evidence packs.

## To ingest (backlog — knowledge still only in raw sources / memory)
- **absmom single-position rotation** (active workstream) — promote `references/strategy/2026-05-27_absmom_rotation_spec.md` + the signal-implementation research once the design settles.
- **Stage-2 speed-tilt λ(s_t)** — next iteration after TBM Stage-1 NO SIGNAL decision branches A or C; pre-reg to be authored. Queue position: TBD per Handoff #1 outcome.
- **Paper-family exit experiment** — Koijen-Moskowitz-Pedersen 2018 carry / Hamilton 1989 Markov regime / Carver Ch.19 instrument selection — one non-LdP-family pre-reg as framework robustness stress test (Handoff #3 item E).
- **min-account universe study** (`references/strategy/2026-05-27_min_account_universe_study.html`) → findings page.
- **IBKR price-accumulation pipeline** (`references/research/2026-05-27-ibkr-panama-price-accumulation-pipeline.md`) → system/process page (root cause of stale data).
- **dashboard research upgrade spec** (`docs/arki/dashboard_research_upgrade_spec.md`) → process page when built.
- **macro investment thesis + century factor analysis** (`docs/arki_references/`) → findings pages.
