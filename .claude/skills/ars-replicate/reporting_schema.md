# REPLICATION_REPORT.md template

The orchestrating agent writes this to `ars/evidence_packs/<slug>/replication/REPLICATION_REPORT.md` after the clean-room agent's run.

---

## Template

```markdown
# Replication report — <slug>

**Date**: YYYY-MM-DD
**Replication target**: <slug> headline metrics on <instrument>
**Reference run**: ars/runs/<id>/summary.csv
**Clean-room agent**: <model id / session id>
**Tolerance spec**: .claude/skills/ars-replicate/tolerance.yaml

## Verdict at a glance

**Status**: PASS | FAIL_spec_gap | FAIL_implementation_uncertainty | FAIL_apparent_disagreement

**Per-metric**:

| Metric | Reference | Replicated | |Δ| | Tolerance | Verdict |
|---|---:|---:|---:|---:|---|
| sharpe_gross | 0.396 | 0.392 | 0.004 | 0.05 abs | PASS |
| max_drawdown_pct_geom | -55.35 | -53.91 | 1.44 | 2.0 abs | PASS |
| skew_per_trade | 4.382 | n/a | n/a | n/a | NOT_REPLICATED |

## Spec gaps identified

Each `[ASSUMED]` flag from the clean-room agent is examined here. PASS-with-gaps may still indicate underspecified cheatsheet.

| # | Ambiguity | Interpretation chosen | Impact | Cheatsheet edit |
|---|---|---|---|---|
| 1 | "Position = round(F · ...)" — round to nearest, floor, toward zero? | Nearest (Python `round()`) | Marginal (≤ 0.5 contract on edge cases) | Add to §3 Action: "rounding = nearest integer (banker's rounding via Python round())" |
| 2 | "Vol target 20% annualised" — sqrt(252) vs sqrt(business days)? | sqrt(252) | Negligible (252 ≈ 252) | Add to §1 Core formula: "annualisation factor = sqrt(252)" |
| 3 | "Daily strategy return %" — fraction × 100 or fraction? | × 100 (percentage points) | Affects unit but not Sharpe | Add to §1: "returns reported in percentage points" |

## Pass / fail breakdown

### PASS path
- All metrics within tolerance.
- Number of [ASSUMED] flags: <n>.
- If n > 3: NOTE — cheatsheet is underspecified. Consider edits in §Spec gaps even though replication agreed.

### FAIL_spec_gap path
- One or more metrics outside tolerance.
- Clean-room agent identified the missing spec component.
- Recommended action: update the Mechanism cheatsheet card §1 or §3 with the missing detail.

### FAIL_implementation_uncertainty path
- One or more metrics outside tolerance.
- Clean-room agent could not decide between two interpretations and tried both.
- Recommended action: pick the interpretation that matched the reference; document it in the cheatsheet; mark the experiment as `replication_status: passed_after_disambiguation`.

### FAIL_apparent_disagreement path
- Clean-room implemented faithfully; result differs.
- This is the MOST informative outcome — investigate whether the original code has a bug or the cheatsheet is wrong.
- Recommended action: code review the original; either fix the code or correct the cheatsheet.

## Files produced

- `replicated_<slug>.py` — the clean-room agent's Python file.
- `replication_output.json` — JSON output with replicated metrics + assumptions list.
- This `REPLICATION_REPORT.md`.

## Cross-references

- Original Mechanism cheatsheet card: `arki/cheatsheets/<date>_<title>.html#mech-<slug>`.
- Reference run: `ars/runs/<id>/`.
- Tolerance spec: `.claude/skills/ars-replicate/tolerance.yaml`.
- LESSONS entry (if any spec gap added): `ars/LESSONS.md` (search for date).

## How to consume this report

- **If PASS**: cheatsheet is a complete spec; promote with confidence. Add `📄 spec-verified` chip to the cheatsheet card.
- **If FAIL_spec_gap**: update the cheatsheet per Spec gaps table; re-run skill; should now PASS.
- **If FAIL_implementation_uncertainty**: pick the working interpretation; update cheatsheet; re-run.
- **If FAIL_apparent_disagreement**: this is high-information; do not auto-update. Code review needed.
```

---

End of template.
