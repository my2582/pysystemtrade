# 01 — Lifecycle (how an experiment flows)

**Prerequisite**: [00_orientation.md](00_orientation.md). **Time**: ~5 minutes.

## The spine

```
research(references/research/)
  → pre-register (ars/evidence_packs/<slug>/<slug>_preregistration.md)
    → experiment (scripts/<name>.py → ars/runs/<UTC>_<slug>/)
      → register (append to ars/runs/registry.yaml)
        → evaluate (gates per pre-reg §4, regime-decomposed per PROMOTION.md scenario)
          → PASS → promote (ars/evidence_packs/<slug>/ populated)
                 → handoff (downstream MANIFEST cites the pack)
          → FAIL → falsify (registry status; finding text)
```

Full spec: `ars/PROMOTION.md`. This file is the quick read.

## The five stages and your obligations at each

### Stage 1 — Pre-register

**File**: `ars/evidence_packs/<slug>/<slug>_preregistration.md`. **Template**: `ars/evidence_packs/_template/preregistration.md`.

You MUST write, BEFORE running any backtest:

- **Hypotheses** as H0/H1 statements (not "let's see if it works").
- **Grid** of parameters, exactly ONE design decision varying vs baseline.
- **Gates** with PASS/FAIL thresholds. Each gate cites `paper + section + equation OR claim sentence`. NEVER cite `paper + figure name` alone (lesson 2026-05-29).
- **Safety bounds** for any multiplicative weight (declare `max(|w|) ≤ N`, lesson 2026-05-29).
- **Data snapshot** identifier (path + cutoff).
- **Assumption set** of the cited paper sections (e.g. `κ_3(U_n) = 0`, `linear class all a_j > 0`, `fixed-M aggregation`).

Lock by committing the pre-registration. The git SHA of that commit goes into the run's `manifest.json` later.

### Stage 2 — Experiment

**Where**: a script under `scripts/` (or `arki/scripts/` if a wrapper). **Output**: `ars/runs/<UTC>_<slug>/`.

The run dir MUST contain:

- `manifest.json` — git SHA at run-start, python version, data snapshot id, full config.
- `summary.csv` — headline metrics per (instrument, variant).
- `verdict.json` — machine-readable per-gate PASS/FAIL.
- `report.html` + `report.pdf` — ARS Tier-1 report (renderer at `scripts/ars_report.py`).

### Stage 3 — Register

Append to `ars/runs/registry.yaml`. Status options:

- `registered` — run complete, evaluation pending.
- `promoted` — all gates PASS, evidence pack populated, ready for downstream.
- `promoted_post_hoc` — special grandfather case (Martin baseline only).
- `promoted_pending_remediation` — gates PASS but a defect was discovered post-promotion; remediation experiment queued.
- `falsified` — at least one gate FAIL per pre-reg falsification rule.
- `refuted` — directional assumption test (e.g. Martin §2.3 implication) NOT supported by data.

### Stage 4 — Evaluate (with regime decomposition)

For each numerical gate:

1. Compute the metric on **Full sample**.
2. Compute the metric on **Era 1 (1985-1999)**, **Era 2 (2000-2014)**, **Era 3 (2015-2026)**.
3. Promote only if `Full PASSES strict threshold AND ≥ 2/3 Eras direction-aligned vs baseline`.
4. Otherwise downgrade to `registered_regime_dependent` (not promoted).

The regime split is owner-fixed; do not change it to fit a result. Justification: Martin (2023) §5.3 — calibration sensitive to data history.

### Stage 5 — Promote OR Falsify

**Promotion** (Path A — strict): all gates PASS + scenario clearance + reconciliation `|diff| < 5%` + `manifest.json` complete. Populate `ars/evidence_packs/<slug>/`:

- pre-registration (immutable).
- `manifest_runsrc.json` (copy from run dir).
- `verdict.json` (machine-readable verdict).
- `report.html` + `report.pdf` (copy from run dir).
- Mechanism cheatsheet card (write a new card OR add to the active session cheatsheet).
- `README.md` summarising the finding.

**Falsification**: registry status `falsified`, write `finding` text inline. Still populate the evidence pack with the same files (lessons live in falsified runs too).

### Stage 6 — Decide

Append a chronological entry to `ars/DECISIONS.md` with: measured result table + per-gate verdict + promotion path + implications + next experiments. This is append-only.

## What the framework does NOT do (per owner directive 2026-05-29)

The framework does NOT pause for owner sign-off. The framework GENERATES the Mechanism cheatsheet HTML and DELIVERS to Obsidian inbox. Owner reads at owner's pace, asynchronously. If the owner spots a misalignment, they comment; the next session integrates the comment into `LESSONS.md` and re-runs as needed.

This means: you (the AI) keep moving. The audit surface is your output, not a gate.

## Next

→ [02_worked_example_promoted.md](02_worked_example_promoted.md)
