# <Experiment slug> — Pre-registration

**Date written**: YYYY-MM-DD
**Branch**: `experiment/<slug>`
**ARS stage**: Exploratory Research (Stage-0). L2 cap (Backtest runner).
**Owner**: Minsu Yeom
**Implementer**: <agent or human>
**Owner pre-registration sign-off**: YYYY-MM-DD by Minsu Yeom; locked by the git commit that creates this file.

This document is **pre-registered**. The grid, gates, and decision rules
MUST NOT be changed after the run begins. Source data + baseline are the
only post-hoc dependencies allowed, and only via a one-line §3 amendment
commit before runner invocation.

Source handoff: `<path to design doc, if any>`.

---

## 1. Background and motivation

Why this experiment, what literature / prior runs motivate it, what gap
it closes. Link to `references/research/...` and to prior registry
entries via `ars/runs/registry.yaml#<id>`.

## 2. Hypotheses

Statistical and materiality decomposition. State H0 and H1 explicitly.
Material threshold (e.g. `+1.0` skew_per_trade vs baseline) goes here.

- **H-X1 (null)**: ...
- **H-X1 (alternative)**: ...

## 3. Grid (one decision per row)

Each row changes EXACTLY one parameter vs the baseline. Bundling is
banned. State the baseline cell explicitly as cell-0.

| Cell | Parameter | Value | Note |
|---|---|---|---|
| cell-0 baseline | — | — | (Reference run id or config file path) |
| cell-1 | <param> | <value> | <reason> |

Ex-ante constraint: parameters are FIXED before the run. No adaptive
grid-search fit on the result (López de Prado AFML Ch.3).

## 4. Gates / decision rules

Per-gate PASS / FAIL thresholds. Reconciliation tolerance. FALSIFIED criteria.

| Gate | Metric | Threshold | Verdict on PASS |
|---|---|---|---|
| G1 | <metric> | <threshold> | <PASS implication> |
| G_recon | `|reconciliation_diff_pct|` | `< 5%` | Trade attribution clean |

Promotion (Path A — strict): ALL gates PASS, reconciliation clean.
Promotion (Path B — owner override): explicit owner sign-off recorded
in `ars/DECISIONS.md`.
Falsification: any required gate FAIL → status `falsified` in registry.

## 5. Data snapshot

- Source: `<e.g. data/futures/adjusted_prices_csv/US10.csv>`
- Cutoff: `<last date used>`
- Snapshot identifier: `<sha256 of file or other deterministic ref>`

## 6. Code snapshot

- Runner: `scripts/<name>.py`
- git SHA at run-start: `(filled at run time; recorded in run dir manifest.json)`

## 7. (Optional) CPC v1 comparison plan

If this run produces 2+ variants, list the CPC series here:

| Series | Source kind | Path | is_benchmark |
|---|---|---|---|
| baseline | csv/parquet/panel | <path> | true |
| variant-1 | csv/parquet/panel | <path> | false |

## 8. Cost budget (optional but encouraged)

Declare an expected token and time budget per Agent Loop phase. The framework
records actuals in verdict.json; over-budget by >50% triggers a retrospective
"did we lose the plot?" check, not an abort. See
docs/standards/ai_native_research_primitives.md §7.

```yaml
budgets:
  pre_registration_phase:
    tokens: 30000      # for writing this pre-reg + literature check
    time_min: 30
  experiment_phase:
    tokens: 150000     # implementation + run + initial reading of results
    time_min: 60
  register_phase:
    tokens: 50000      # registry + DECISIONS + evidence pack
    time_min: 20
  total_budget:
    tokens: 230000
    time_min: 110
```

Honest framing: this is a SOFT signal, not a hard cap. If you blow past
the budget, log the actuals and write a brief retrospective in the
verdict.json `cost_retrospective` field. Aim is cumulative learning
about which experiment classes are token-efficient, not real-time gating.

If you do not declare a budget, the framework will record actuals only and
flag it as `budget_undeclared: true` (no penalty).
