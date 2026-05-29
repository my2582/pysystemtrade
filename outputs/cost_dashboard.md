# Session cost dashboard

**Date**: 2026-05-29
**Generator**: scripts/session_cost_report.py

## Summary

- Evidence packs scanned: 5
- Budget declared: 0 (0%)
- Over budget (>50%): 0

## Per-experiment cost detail

| Slug | Status | Tokens used | Budget | Over % | Time min | Budget declared |
|---|---|---:|---:|---:|---:|---|
| carry_toggle | refuted | — | — | — | — | — |
| dmom_us10 | falsified | — | — | — | — | — |
| fast_tilt_ewmac | falsified | — | — | — | — | — |
| martin_single_instrument | promoted_post_hoc | — | — | — | — | — |
| smom_us10 | promoted | — | — | — | — | — |

## How to read this

- Budget declared 0% means the framework has data but no pre-registered budgets to compare against.
  This is fine for early adoption; the actuals accumulate so we can see cost patterns.
- "Over budget >50%" is a SOFT signal. Each over-budget entry should have a `cost_retrospective`
  field in its verdict.json describing why.
- Cumulative learning goal: identify experiment classes (single-instrument backtest, multi-variant
  overlay, paper compliance check, ...) and their typical token cost so future budgets are realistic.

## What this dashboard does NOT do

- Does not gate execution.
- Does not abort in-flight work.
- Does not replace verdict.json — it is an aggregation view only.

Updated by re-running this script. See docs/standards/ai_native_research_primitives.md §7 for design rationale.
