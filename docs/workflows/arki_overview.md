# `pysystemtrade` — Arki Overview

**Repo**: `pysystemtrade` (fork of `pst-group/pysystemtrade`,
upstream `robcarver17/pysystemtrade`) · **Type**: Spec/library (fork) ·
**Status**: Running · **Last verified**: 2026-05-24

Arki-specific usage notes for the Rob Carver pysystemtrade fork.
Co-located at `docs/workflows/arki_overview.md` (not in upstream
`docs/`) so upstream merges stay clean.

## Purpose
Systematic futures trading framework (Carver methodology). Used at Arki
for backtesting and (where deployed) production futures execution via
Interactive Brokers (`ib_insync`). Foundation library; not a "running
pipeline" per se but an underpinning system for any futures workload.

## Consumers
- Internal Arki strategies that incorporate futures or replicate
  Carver-style risk parity / trend following.
- Operator backtests and parameter studies.

## Public surface
- All upstream modules — see upstream `README.md` and the canonical
  guides:
  - `docs/introduction.md` (start here).
  - `docs/backtesting.md`.
  - `docs/data.md`.
  - `docs/IB.md` (Interactive Brokers).
  - `docs/production.md` (production setup).
- IB Insync bridge: `ib-insync` PyPI package.

## SLA / cadence
- Upstream cadence: maintained by Andy Geach + Rob Carver under
  `pst-group` org (since Jan 2026).
- Arki sync cadence: on-demand pull from upstream; no automated
  schedule.

## Version policy
- Origin: `pst-group/pysystemtrade` (the maintained Arki-facing remote).
- Upstream: `robcarver17/pysystemtrade` (the legacy reference; pull
  only).
- Major versions follow upstream releases. Arki-local patches (if any)
  live as branches/PRs against `pst-group` origin.

## Failure modes
- IB Gateway / TWS down → live execution paths fail; backtesting
  unaffected.
- Upstream API breaking changes — Arki sync needs review before pull.
- Heavy backtests are local-machine bound; no cloud target (consistent
  with `ATLAS-D-010` — cloud deferred to Phase 2+).

## Owner / on-call
- Owner: Minsu Yeom (Arki side).
- Upstream owners: Andy Geach + Rob Carver (`pst-group`).

## References
- ATLAS: `ATLAS-D-009`.
- Upstream README + canonical docs/ guides.
- Template: `EA/projects/atlas/templates/spec-library-1pager-template.md`.
