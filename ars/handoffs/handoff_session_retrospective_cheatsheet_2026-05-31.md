# HANDOFF #3 — Session retrospective cheatsheet + 4 forward enhancements

**Type:** Implementation handoff (deterministic; multiple discrete items).
**Owner:** Minsu Yeom.
**Implementer:** TBD (this session may complete item B inline; this handoff is insurance + covers 4 remaining items).
**Date authored:** 2026-05-31.
**Status of work:** Items A (predict-then-measure scorecard) and C (queue commitments) COMPLETE this session; item B (cheatsheet retro) attempted inline if context allows, else queued here; items D-G (deferred enhancements from 10-item list) all in this handoff.
**Estimated effort:** ~60 min item B + ~3-4 hours items D-G (separable; do as separate turns).

---

## 0. One-line ask per item

| Item | Ask | Status |
|---|---|---|
| **B (cheatsheet)** | One-page Visual Report Methodology v1 HTML retrospective of 2026-05-30/31 session: 8 sections F1-F8. Self-contained (inline CSS/SVG, no external deps). | In-session attempt; if interrupted, finish per §1 below |
| **D (cold-start)** | Stress-test cross-session continuity: a separate Claude session reads only family.yaml + findings.md + queue.md and tries to advance queue item #2 unaided. | Queued |
| **E (paper-family exit)** | Author one pre-reg outside LdP/Hanauer/Carver canon (Koijen carry / Hamilton Markov / Carver instrument-selection). | Queued |
| **F (process-cost instr.)** | Add 5 timestamps to manifest.json + queue.md instrumentation; measure 3 cycle times; flag if avg > 1 business day. | Queued |
| **G (lint Rule 7 predictions)** | Implement `predictions:` block validation in `scripts/validate_preregistration.py` per the scorecard's Rule 7 proposal. | Queued |

---

## 1. Item B — Cheatsheet retrospective (full spec)

### 1.1 Format reference

Source style: `outputs/external_share/2026-05-30/cheatsheet_sanitized.html` (Visual Report Methodology v1 — single HTML, inline CSS, dense scannable layout). Variation allowed but maintain:
- Single self-contained HTML (no external CSS/JS).
- 8 sections in named F1..F8 panels with clear visual separators.
- Tables for data; SVG/inline-block for cumulative chart if any.
- Header: Arki Green (#0d4f3f) palette consistent with existing reports.

### 1.2 Output path

`arki/reports/2026-05-31/family/futures_momentum_session_retro_cheatsheet.html`

(Companion sanitized copy for external share: `outputs/external_share/2026-05-31/futures_momentum_session_retro_sanitized.html` via `scripts/sanitize_for_external_review.py`.)

### 1.3 8-section content spec

**F1 — Session thesis (1 line + 4-week journey)**
- Headline: "ZN 단독 momentum에 layer를 쌓아 alpha를 찾는다 — 진행 결과"
- Sub-bullet: 2026-05-27 paper reading → 05-28 5-experiment batch → 05-29 framework adoption → 05-30 execution_friction 6-cell + regime analysis → 05-31 family layer + TBM Stage-1 + NO SIGNAL verdict.
- 1 KPI line: alpha discovered = 0; process built = 3 layers + 6 lint rules + 14 cells + 3 handoffs.

**F2 — Process built (3 visual cards, side-by-side)**

| Card | Content |
|---|---|
| (a) Family 3-layer system | registry (per-experiment) → family.yaml (panel + dims + multiple-testing) → findings.md (axis-level elasticity). 2 panels, 3-tier dims, no cross-panel inheritance. |
| (b) DSR/PBO single SOT utility | `arki/utils/dsr.py` — Bailey-LdP 2014 with annualisation-aware (per-period vs annualised bug fix). `python -m arki.utils.dsr` self-check PASS. |
| (c) Pre-reg discipline (6 lint rules + 3 gap rules) | Rule 1 (citation §+Eq), Rule 2 (degenerate-denominator bound), Rule 3 (assumption_set), Rule 4 (aggregation per gate), Rule 6 (family DSR awareness), Rule 7 (predictions block — proposed, see Handoff §G). Gap rules 5.2.a/b/c (CUSUM reset / sigma re-warmup / cross-gap label drop). |

**F3 — Experiments scoreboard (14 cells, color-coded)**

Table: `cell_id | panel | spec | overlay | exec_profile | capital | status | Sharpe_net | skew_per_trade | notes`. Source: `family.yaml` panel_A_single_instrument.cells (+ Panel B = empty).

Status color: ✅PRO green / ✅POH light green / 📊MEAS blue / ⚠REM yellow / ❌FAL red / ❌REF red / ⏳QUE grey.

**F4 — Findings axis-level (n_pairs + direction + transport)**

5 axes table from `findings.md`:

| Axis | direction | mean \|ΔSharpe\| | n clean pairs | confound risk | transport status |
|---|---|---:|---:|---|---|
| vol_estimator | ≈ 0 | 0.0035 | 2 | low | UNTESTED elsewhere |
| overlay | mixed (3 falsified, 1 pending, 1 ambiguous) | varies | 4 | medium | UNTESTED elsewhere |
| rule_structure | hint 6sp > single | (0.039 confounded) | 0 | HIGH | not yet attributed |
| exec_profile | hint native > numpy | (0.084 confounded) | 0 | HIGH | not yet attributed |
| capital_usd | ≈ 0 Sharpe; big skew effect | 0.020 | 3 | low | US10 single |

Below the table: "the 0-clean-pair lines are the top de-confound priority (queue item #2)."

**F5 — Defect → Lesson chain (4 entries, narrative format)**

Each as a small card with:
- Date + headline
- What the framework saw
- What was actually wrong
- Durable rule generated

Source: `05_LESSONS_smom_extracts.md` (Obsidian inbox 2026-05-31 sMOM briefing) — 4 entries already curated.

Above the cards: "Each entry shows ARS adapting to the failure mode that exposed it. Reading them as a chain (not in isolation) is the right way to understand the framework's evolution."

**F6 — Honest scorecard (the differentiator)**

| Dimension | Score | Note |
|---|---|---|
| **Process built** | **B+** | LdP-textbook hygiene level; transport untested |
| **Alpha discovered** | **F** | 0/14 cells cleared family DSR threshold 0.3326 with confident lift |
| **Prediction skill (this session)** | **75% (7.5/10)** | Categorical 100%, quantitative 0%; see `docs/arki/session_predictions_scorecard_2026-05-31.md` |
| **Confidence justification** | *partial* | 75% hit rate is non-trivial but n=10. Next 30-40 predictions decide if 75% holds. |

Footnote: "The right confidence stance: we are better than coin-flip at predicting REGIME of momentum overlays; we are at coin-flip on MAGNITUDES; sample is 1 thesis × 1 instrument."

**F7 — What would change the grade (forward)**

A → B+ (alpha) requires:
- Stage-2 (speed-tilt) NON-NO-SIGNAL result OR
- Panel B (multi-instrument DM_rates_5) 1 cell with confirmed lift OR
- Cold-start handoff success (a different session/agent advances queue #2 unaided) OR
- 3+ consecutive predict-then-measure cycles with > 65% hit rate

Process B+ → A requires:
- Framework gate (not owner intuition) catches a critical defect BEFORE promotion
- Process-cost measurement shows avg cell cycle ≤ 1 business day across 3 cells
- One paper-family-exit experiment (item E) successfully integrated into family schema

**F8 — Queue + commitments**

Top 3 from `queue.md` with the time-bound commitments added 2026-05-31:

| Item | Commit deadline | Trigger if missed |
|---|---|---|
| #2 rule de-confound | pre-reg lock by 2026-06-07; result 2026-06-10 | process-cost review |
| #1.2 sMOM capped G4 refinement | pre-reg amendment + re-verdict by 2026-06-12 | G4 redesign |
| #5 Panel B open (DM_rates_5) | pre-reg lock by 2026-06-21 | re-prioritise |

Plus 4 forward enhancements (this handoff items D-G) at the bottom.

### 1.4 Inputs (read before building)

- `docs/arki/session_predictions_scorecard_2026-05-31.md` — provides F6 prediction-skill numbers AND the F8 honest read.
- `ars/families/futures_momentum/family.yaml` — F3 cells, F4 dims.
- `ars/families/futures_momentum/findings.md` — F4 elasticity + transport.
- `ars/families/futures_momentum/queue.md` — F7 + F8 (post-commitments edit applied 2026-05-31).
- `ars/LESSONS.md` — F5 4 entries (extracts available at Obsidian `_Inbox/2026-05-31/pysystemtrade_smom_briefing/05_LESSONS_smom_extracts.md`).
- `ars/DECISIONS.md` — supporting context.
- Reference style: `outputs/external_share/2026-05-30/cheatsheet_sanitized.html`.

### 1.5 Acceptance criteria

- [ ] Single HTML file, ≤ 800 lines, no external CSS/JS.
- [ ] 8 sections clearly delimited and named F1..F8.
- [ ] All data values trace to a source file path (footer pointer per table).
- [ ] Sanitized variant exists at `outputs/external_share/2026-05-31/...`.
- [ ] Delivered to Obsidian inbox: `_Inbox/2026-05-31/pysystemtrade_session_retro/futures_momentum_session_retro_cheatsheet.html` + companion README.md.
- [ ] No diff in upstream-tracked pysystemtrade dirs.

---

## 2. Item D — Cold-start handoff test

### 2.1 One-line ask

Run a separate Claude session, give it ONLY `family.yaml + findings.md + queue.md + CLAUDE.md`, and instruct it to advance queue item #2 (rule_structure de-confound) without any other context.

### 2.2 Method

1. New session, fresh context.
2. Initial prompt: "Read `ars/families/futures_momentum/{family.yaml, findings.md, queue.md}` and `CLAUDE.md`. Then advance queue item #2 (rule_structure de-confound). You may read other files only when explicitly needed by what those three files reference. Do NOT read other files preemptively."
3. Observe: does the session successfully (a) understand the family, (b) author a Path A pre-reg for queue #2, (c) lint Rule 1-6 pass, (d) make the right design decisions (single_ema2 + carver_native, exec_profile constant vs martin_baseline_us10_1m)?

### 2.3 Success criteria

- (a) reads the three files without confusion
- (b) authors a pre-reg that would have been authored similarly by this session
- (c) lint PASS on the new pre-reg
- (d) design matches the "single_ema2 + carver_native, holding exec_profile constant" intent encoded in queue.md item #2

### 2.4 Failure-mode log

Any of the above failing reveals a HIDDEN dependency in family.yaml / findings.md / queue.md on session-context that's not in the files. Each such dependency is a fix to the three-file SOT.

### 2.5 Expected cost

~30 min on the COLD session's side. Recording observed failure-modes is the actual deliverable.

---

## 3. Item E — Paper-family exit experiment

### 3.1 One-line ask

Author one Path A pre-reg whose primary literature anchor is NOT in {Martin 2023, Hanauer 2022, Wang-Yan 2021, Daniel-Moskowitz 2016, Barroso-Santa-Clara 2015, Carver Systematic Trading / AFTS, López de Prado AFML} — i.e., outside the current canonical paper family.

### 3.2 Three candidate theses (pick one)

| Candidate | Literature anchor | Why interesting |
|---|---|---|
| (a) **Koijen-Moskowitz-Pedersen 2018 carry across futures** | "Carry" (JFE 2018) — carry as primary cross-asset alpha source | Tests whether family schema's `overlay: carry` axis can promote carry to PRIMARY signal, not overlay. Stress test of dimension extension. |
| (b) **Hamilton 1989 Markov regime-switching state-space** | "A New Approach to the Economic Analysis of Nonstationary Time Series" (Econometrica 1989) | Adds *side* mechanism that's NOT EWMAC-based. Tests whether family can host a fundamentally different signal type. |
| (c) **Carver AFTS Ch. 19 instrument selection** | Carver, *Advanced Futures Trading Strategies* (2023) Ch. 19 | Carver claims instrument selection itself is larger alpha than rule choice. Tests Panel B's `instrument_set` dimension as the primary axis, not a context. |

### 3.3 Method

1. Pick one (probably (a) — easiest data, clearest signal class extension).
2. Author Path A pre-reg with full lint Rule 1-6 + 7 PASS.
3. Run the cell.
4. Observe whether family.yaml schema needs extension OR successfully accommodates the new spec as-is.

### 3.4 Success criterion (the real test)

The point is NOT whether the experiment finds alpha. The point is whether **the family schema bends or breaks** under a non-canonical thesis. If the schema extends gracefully → framework is genuinely robust beyond LdP-family bias. If extending the schema requires a major refactor → confirms my prior critique that the schema is paper-family-biased.

### 3.5 Expected cost

~1 day (pre-reg + runner adaptation + 1 cell run + family extension decision).

---

## 4. Item F — Process-cost instrumentation

### 4.1 One-line ask

Add 5 timestamps to every new cell's `manifest.json`. Measure cycle times. Flag if average > 1 business day.

### 4.2 Schema additions

In each new cell's `manifest.json`:

```json
{
  ...,
  "timeline": {
    "pre_reg_authored_at": "2026-XX-XX HH:MM:SS UTC",
    "runner_started_at":   "2026-XX-XX HH:MM:SS UTC",
    "runner_finished_at":  "2026-XX-XX HH:MM:SS UTC",
    "gates_evaluated_at":  "2026-XX-XX HH:MM:SS UTC",
    "family_committed_at": "2026-XX-XX HH:MM:SS UTC"
  }
}
```

Cycle time = `family_committed_at − pre_reg_authored_at`, in business days.

### 4.3 Aggregation

After 3 cells with new instrumentation: compute mean / median / p75 cycle times. Append to family.yaml `multiple_testing` block:

```yaml
process_cost:
  cycle_time_days_mean: 0.X
  cycle_time_days_p75: 0.X
  n_measured: 3
  threshold_for_simplification: 1.0  # business day
```

If mean > 1.0 → framework simplification trigger. Specific simplification candidates:
- Reduce CPCV folds (combinatorial → standard k-fold purged)
- Drop one of the rule axes (e.g., overlay sweep deferred to family-level batches)
- Simplify lint Rule 6 family-DSR-awareness check

### 4.4 Expected cost

~30 min instrumentation. Measurement is FREE once next 3 cells run naturally.

---

## 5. Item G — Lint Rule 7 implementation (predictions block)

### 5.1 One-line ask

Implement `check_rule7_predictions_block()` in `scripts/validate_preregistration.py` per the proposal in `docs/arki/session_predictions_scorecard_2026-05-31.md` §"Proposed Rule 7".

### 5.2 Behavior

- Soft check (warning level for first 5 pre-regs, then upgrade to error).
- Required structure: `predictions:` YAML block with at least 1 entry, each having `id`, `statement`, `type`, `score_method`.
- Preferred: `type: categorical` over `type: quantitative` (warn if all quantitative).

### 5.3 Expected cost

~30 min implementation + 10 min retroactive check on existing 3 pre-regs (TBM, sMOM capped, execution_friction). The existing 3 don't have `predictions:` blocks — back-fill OR mark as pre-Rule-7-grandfathered.

---

## 6. Suggested execution order across future sessions

| Session | Items |
|---|---|
| THIS session (already done) | A (scorecard) + C (queue commitments) |
| THIS session (in progress) | B inline if context allows |
| Next session (1) | B (if not finished) + G (Rule 7 lint) |
| Next session (2) | D (cold-start test) — needs OWNER to actually create a separate session and observe |
| Next session (3) | F (process-cost instrumentation) — couple with queue item #2 cell |
| Future session (~1 week out) | E (paper-family exit) — biggest single piece |

Items B, F, G can run in parallel across sessions (no inter-dependency). Items D and E are independent. So total elapsed = max-path = E (~1 day on its own).

---

## 7. Files referenced

- `ars/families/futures_momentum/family.yaml` — family schema + multiple-testing
- `ars/families/futures_momentum/findings.md` — axis elasticity
- `ars/families/futures_momentum/queue.md` — top-3 with commitments (added 2026-05-31)
- `ars/families/futures_momentum/matrix.md` — text matrix (matrix.html still pending per Handoff #2)
- `ars/LESSONS.md` — 4 sMOM entries
- `ars/DECISIONS.md` — chronological log
- `docs/arki/session_predictions_scorecard_2026-05-31.md` — prediction track record (this session, item A)
- `docs/arki/handoff_tbm_stage1_no_signal_decision_2026-05-31.md` — Handoff #1 (TBM decision)
- `docs/arki/handoff_unified_cpc_reporting_2026-05-31.md` — Handoff #2 (CPC reports + matrix.html)
- THIS file — Handoff #3 (retrospective cheatsheet + 4 enhancements)
- `outputs/external_share/2026-05-30/cheatsheet_sanitized.html` — format reference for item B
- `scripts/validate_preregistration.py` — lint script (Rule 7 addition target for item G)
- `arki/utils/dsr.py` — DSR/PBO utility

---

## 8. Out of scope

- Stage-2 speed-tilt design — separate workstream after Stage-1 decision (Handoff #1)
- CPC v1 reporting implementation — Handoff #2
- Family-level findings auto-update script — deferred until family has 5+ post-commitment cells
- External-share sanitization pipeline updates — current pipeline OK
- Cross-family abstraction (futures_momentum + other families) — deferred until ≥ 2 families exist
