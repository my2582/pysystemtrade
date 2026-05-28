# Evidence pack template — pysystemtrade

Copy this directory to `ars/evidence_packs/<slug>/` when promoting a run
that passes all gates in `ars/PROMOTION.md`. Files marked **(required)**
must be present; **(optional)** are recommended for promotion-grade.

## Files

| File | Required | What to write |
|---|---|---|
| `<slug>_preregistration.md` | required | Locked hypothesis + grid + gates + decision rules. Commit BEFORE run-start. Sections 1–6 from `_template/preregistration.md`. |
| `manifest.json` | required | Copy from the run dir's `manifest.json`; add `promoted_utc`, `promoted_by`, `decision_log_anchor` fields. |
| `verdict.json` | required | Per-gate PASS/FAIL with thresholds. Schema in `_template/verdict.json`. |
| `report.html` (and/or `report.pdf`) | required | Copy from the run dir. ARS run report (Tier 1). |
| `cpc/<slug>.html` + `monthly_returns_usd.csv` | required for multi-variant | CPC v1 Cohort Performance Card. Mandatory when 2+ variants are compared. |
| `cheatsheet.html` | optional | Tier-2a single-experiment owner-facing one-pager (`/cheatsheet` skill). |
| `README.md` | optional | 1-paragraph summary + how to consume downstream. |

## Promotion checklist

Before publishing this evidence pack, confirm in `ars/DECISIONS.md`:

- [ ] All gates listed in the pre-registration are recorded with PASS/FAIL in `verdict.json`.
- [ ] Reconciliation `|diff_pct| < 5%` (where applicable).
- [ ] `manifest.json` has the git SHA at run-start and the data snapshot identifier.
- [ ] `report.html` is the ARS-styled report from `arki/templates/ars_run_report.html`.
- [ ] (Multi-variant) `cpc/<slug>.html` is present.
- [ ] Decision log entry written in `ars/DECISIONS.md` with measured results table + verdict + promotion path.
- [ ] Registry row in `ars/runs/registry.yaml` flipped from `registered` to `promoted` (or `falsified`) with `evidence_pack:` link.

## Falsified runs

Falsified runs still belong here. Keep the pre-registration + verdict.json +
report.html; mark `status: falsified` in verdict.json and add a `finding`
field stating why. Negative results are first-class.
