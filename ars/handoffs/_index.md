# Handoffs — register (futures_momentum + tooling)

> Single ledger of every session handoff + completion report. **Status is judged by disk
> evidence** (run dirs, output files, registry rows) — NOT by what a completion report
> claims. Where a report and the disk disagree, the disk wins and the discrepancy is noted.
> Session-continuity entry point is `ars/STATUS.md`. Files here are **preserved verbatim**;
> this index is the only thing that interprets them.
>
> Reconciled: 2026-05-31. Gathered into `ars/handoffs/` from `docs/arki/` + `~/Downloads/`
> (Downloads dependency removed).

## Status table

| handoff | type | status | evidence (on disk) |
|---|---|---|---|
| `HANDOFF_stage1_tbm_ZN.md` | spec + runner | **EXECUTED** | Both TBM run dirs exist: `ars/runs/20260530T154455Z_tbm_meta_us10_baseline_1m/` + `ars/runs/20260530T164615Z_tbm_meta_us10_tmax40_1m/` (8 artifacts each). Runner `stage1_meta_labeling.py` now committed alongside (was Downloads-only). |
| `handoff_tbm_stage1_no_signal_decision_2026-05-31.md` | owner decision menu (A/B/C) | **CLOSED** | 4th branch (extends C) chosen + executed. `DECISIONS.md` 2026-05-31 closeout entry; completion report below. |
| `handoff_tbm_stage1_no_signal_decision_COMPLETION_2026-05-31.md` | completion report | **DONE** | Records the 4th-branch execution (6 steps). Note: its §7 flagged "registry yaml parse defect" + "matrix.html pending" — **both resolved 2026-05-31** (parse fix + matrix.html confirmed present). |
| `HANDOFF_risk_shaping_family_closeout.md` | execution spec | **EXECUTED** | §1–§5 applied: `family.yaml` has `sub_groups.risk_shaping_size_overlays`; `registry.yaml` `smom_us10_capped` → `registered_path_b`, `smom_us10` → `superseded_by_smom_us10_capped`. Extends + supersedes the no_signal_decision's Branch C. |
| `handoff_unified_cpc_reporting_2026-05-31.md` | reporting | **COMPLETE** | `arki/reports/family/futures_momentum_matrix.html` **exists** (10,996 B, valid Plotly), commit `c1076c77`, 7/7 acceptance. CPC 4 reports + 2 builders on disk. ⚠ The 4th-branch reports called matrix.html "pending" — **stale; disk says done**. §5 follow-ups (#2/#3/#4) are separate downstream cycles, not part of this handoff. §5 #1 (TBM registry entries) **done 2026-05-31** (this session). |
| `handoff_unified_cpc_reporting_2026-05-31_COMPLETION.md` | completion report | **DONE** | 7/7 acceptance PASS; commit `c1076c77`; design judgment (native `summary.csv` for risk, equity curve path-only) recorded. |
| `handoff_session_retrospective_cheatsheet_2026-05-31.md` | forward enhancements (D/E/F/G) | **EXECUTED** | Commit `dbaf07a2` "Handoff #3 forward enhancements — Rule 7 lint + process-cost + cold-start test + carry primary". `scripts/validate_preregistration.py` (Rule 7), `arki/utils/process_cost.py`, cold-start test all present. |
| `handoff_futures_trade_analyzer_2026-05-27.md` | tooling | **DONE** (folded into CPC) | `scripts/trade_analysis.py` exists; the trade-arrow fix it specified was completed under unified_cpc step 1 (`trade_analysis.py:590-599`). |

## Pointers

- Session-continuity entry point: [`ars/STATUS.md`](../STATUS.md)
- Family: [`ars/families/futures_momentum/`](../families/futures_momentum/) (`family.yaml`, `findings.md`, `queue.md`, `matrix.md`)
- Runs registry: [`ars/runs/registry.yaml`](../runs/registry.yaml)
- Decision log: [`ars/DECISIONS.md`](../DECISIONS.md) · Lessons: [`ars/LESSONS.md`](../LESSONS.md)
- Related test result kept in `docs/arki/` (referenced by `queue.md` by path): `coldstart_handoff_test_result_2026-05-31.md`.
