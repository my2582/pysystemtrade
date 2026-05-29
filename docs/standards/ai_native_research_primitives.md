# AI-Native Research Primitives — pysystemtrade

A design document for the primitives that turn this repo's research from "AI-assisted" into "AI-native," where epistemic integrity is first-class. Pairs with `ars/PROMOTION.md` (the lifecycle) and `ars/LESSONS.md` (the negative-result memory).

**Owner**: Minsu Yeom · **Draft date**: 2026-05-29 · **Status**: skeleton; iterate with each session

---

## 0. Why this exists

This session (2026-05-29) ran five pre-registered momentum experiments. Two of them passed every gate the framework had — and two reviewers (one on implementation, one on theory) caught issues the framework did not. The lessons are recorded in `ars/LESSONS.md`. This document captures the GENERALIZED primitives those lessons demand.

Core re-framing:
- **Old**: "the framework prevents mistakes."
- **New**: "the framework makes mistakes visible to a human reviewer at the moment they are made."

The Human-in-the-Loop (HITL) is not the safety net of last resort; it is the **epistemic verifier** in the loop. The primitives below exist to make verification cheap.

**Owner directive (2026-05-29)**: HITL must NOT block the Agent Loop. Owner consumes audit surfaces (Mechanism cheatsheet HTML in Obsidian inbox; LESSONS append-only log) at owner's pace, asynchronously. The framework's job is to GENERATE and DELIVER these surfaces; the framework does NOT pause for sign-off. Any primitive that requires an explicit owner action to unblock execution is rejected. Adopted primitives must be passive (generation + delivery) or active-on-AI-side (gates the AI applies to itself without owner mediation).

---

## 1. Primitive: Mechanism cheatsheet (per experiment)

**Inspired by**: `~/Downloads/rtv_xbondreit_sgd_cpc.html` "Mechanism cheatsheet" section (b3-saa-etf precedent).

**Purpose**: surface the EXACT formula, the EXACT trigger, and the EXACT action of every mechanism in the experiment, in one panel, so the human verifier can audit alignment with paper / intent in 60 seconds without reading code.

**Structure** (mandatory three sub-sections):

### 1.1 Core formula tested
- **Name** of the mechanism (one line, plain English).
- **Formula** rendered in LaTeX, with every variable named.
- **Variables** defined: lookback windows, decay parameters, source series, estimator computed-per-asset vs portfolio-level.
- **Inheritance note**: what code module / paper convention this derives from.

### 1.2 Triggering condition
- **Event-driven or continuous?** State explicitly.
- **Schedule**: what day, what bar, what cadence.
- **Trigger inequality** in LaTeX: `s_{i,t} = min(σ_target / σ_i,t, 1.0)` etc.
- **Cells in sweep**: enumerated parameter grid (if any).

### 1.3 Action (table)

| Row | What to specify |
|---|---|
| Trade shape | continuous re-sizing? halve? full liquidation? |
| Observation date (T) | exact bar where signal is computed (no look-ahead!) |
| Trade date (T+1) | exact bar where order fires |
| Between rebals | on_daily behavior — no-op, drift, intra-period rule? |
| Leverage / sizing cap | the HARD bound (closing the unbounded-w failure mode) |
| Re-entry rule | after liquidation / halve, when does the strategy come back? |

**Mandatory inclusion**: every overlay / signal in the experiment gets its own Mechanism cheatsheet card on the cheatsheet HTML. Even the baseline has one (the "no overlay" mechanism).

**Why this catches misalignment early**: the act of writing "Core formula" forces you to type out the equation; the act of writing "Trigger" forces you to specify the bar timing; the act of filling the Action table forces you to commit to a sizing cap. Each step is where misalignment would otherwise hide.

---

## 2. Primitive: Paper-citation gate (replaces slogan citations)

**Closes**: 2026-05-29 lesson "Martin §2.3 misreading — Figure-as-slogan vs Equation-as-test."

**Rule**: every pre-registered gate cites the source as `<paper> <section> <equation_number>` or `<paper> <section> <claim_sentence>`. Never as `<paper> <figure_name>` alone.

**Template field** (`ars/evidence_packs/_template/preregistration.md` §4 Gates):

```yaml
G1:
  metric: skew_per_trade
  threshold: ">= 1.0"
  source:
    paper: "Martin (2023) Design and analysis of momentum trading strategies"
    section: "§2.3"
    equation: "Eq. 12 (3rd moment of M-period trading return)"
    claim: "pure trend with all a_j > 0 produces positively skewed trading returns"
    assumption_set:
      - "U_n vol-normalised one-period returns are symmetric (κ_3(U_n) = 0)"
      - "linear class: φ_n = Σ a_j U_{n-j}, all a_j > 0"
      - "M is fixed (non-overlapping aggregation)"
  assumption_check:
    - "measure κ_3(U) empirically before applying gate; flag if |κ_3(U)| > 0.2"
    - "verify all forecast weights > 0 (no carry / mean-reversion)"
    - "use fixed-M aggregation, NOT sign-episode"
```

**Enforcement**: pre-registration commit hook validates that every gate has a non-empty `equation` OR `claim` field AND a non-empty `assumption_set` field. Slogan-only citations fail the commit.

**Companion**: assumption violations downgrade gate verdict from "validation" to "context" automatically (verdict.json schema gains a `gate_status` field: `validated` | `context` | `invalid`).

---

## 3. Primitive: Safety gate (`G_safety`)

**Closes**: 2026-05-29 lesson "sMOM unbounded weight."

**Rule**: every experiment declares safety gates at pre-registration time. Run cannot promote without passing all `G_safety_*` gates.

**Mandatory safety gates** (minimum set):

| Gate | Test | Default threshold |
|---|---|---|
| `G_safety_overlay_weight_bound` | `max(|w_overlay,t|) ≤ declared_cap` | declared per pre-reg; missing = fail |
| `G_safety_no_lookahead` | no input series uses information at time `t` to compute decision at time `≤ t` | enforced by data-flow audit |
| `G_safety_no_full_sample_norm_in_oos` | no full-sample variance / mean used in time-varying weights | static check on code |
| `G_safety_single_day_loss_bound` | `min(R_t) > -N · ann_vol_daily`, N pre-declared | N=10 default |
| `G_safety_recon_tolerance` | `|sum(attributed) - sum(total)| / abs(sum(total)) < 0.05` | already in use |

**Enforcement**: `G_safety` is the first set of gates evaluated; a failure short-circuits all other gates. Status downgrade: `safety_violated` ranks above `falsified` in severity.

---

## 4. Primitive: Lineage manifest (claim ↔ source)

**Purpose**: every claim in the cheatsheet, report, or DECISIONS entry traces to BOTH a code source and a paper source. No floating numbers.

**Format** (one row per claim):

```yaml
claim_id: us10_skew_per_trade_4.38
text: "US10 baseline skew per trade = +4.38"
sources:
  code:
    path: ars/runs/20260528T161350Z_martin_single_instrument/summary.csv
    column: skew_per_trade
    row: US10
    git_sha: 5fa88c4c
  paper:
    paper: "Martin (2023)"
    section: "§2.3"
    equation: "Eq. 12"
    interpretation: "fixed-M closed-form; my measurement is sign-episode = different object"
assumption_alignment:
  paper_assumes_kappa3_U_zero: true
  my_data_kappa3_U: 0.18  # measured for US10 baseline
  alignment: "approximate — within ±0.2 tolerance"
```

**Enforcement**: cheatsheet generator validates that every `<span class="kfig">` value and every table cell has a `claim_id` attribute that resolves to a row in `lineage.yaml`. Unresolved claims fail the verify gate.

---

## 5. Primitive: Adversarial reviewer hook

**Purpose**: introduce a "fresh eyes" pass before promotion, AUTOMATICALLY.

**Form** (initial): a Claude / Codex session invoked with restricted context:
- The Mechanism cheatsheet section (only).
- The pre-registration document.
- The source paper sections cited in §2 above.
- The verdict.json.

NOT given: the run history, the cheerleading prose, the prior verdicts.

**Prompt**: "Read the Mechanism cheatsheet. Read the paper sections cited in the pre-registration. List specific misalignments between the formula written here and the paper's claim. List sanity violations (look-ahead, unbounded weights, full-sample normalisation). Output: a list of `concerns`, each tagged `theoretical | implementation | methodological | none`."

**Promotion gate**: a `concern` tagged `theoretical` or `implementation` blocks promotion until addressed (resolved in DECISIONS, or pre-registration amended).

**Why this works**: the prior misalignments in this session were caught by exactly this kind of fresh-eyes read. The primitive automates it.

---

## 6. Primitive: Cross-experiment dependency graph

**Purpose**: when an evidence pack is updated or falsified, automatically surface the experiments that depend on it.

**Format**: `ars/runs/dependency_graph.yaml`:

```yaml
dependencies:
  smom_us10:
    depends_on: [martin_single_instrument]
    inherits_assumptions: [linear_class_baseline]
    affected_if_baseline_changes: true
  carry_toggle:
    depends_on: [martin_single_instrument]
    inherits_assumptions: [linear_class_baseline, kappa3_U_zero]
    affected_if_baseline_changes: true
```

**Automation**: when `martin_single_instrument` gets a correction note in DECISIONS, an `dependents-affected` warning is appended to every dependent's evidence pack README.

---

## 7. Primitive: Time-budget governance

**Purpose**: prevent the breakneck pace that led to skipping the paper re-read in this session.

**Format**: each `Agent Loop` phase declares an expected duration AND a min/max budget. If a phase runs faster than min budget, the framework flags potential corner-cutting. If slower than max, scope re-evaluation.

**Specifically for paper-derived experiments**: a minimum 30-minute "paper re-read" phase must precede pre-registration. Evidence of compliance = a `paper_notes.md` file in the evidence pack with at least one quoted sentence per cited section.

---

## 8. Primitive: Falsification-amplification

**Purpose**: make negative results MORE visible than promoted results in the cheatsheet. Currently they're treated equally; the human eye glances over `falsified` rows.

**Form**: falsified experiments get a dedicated F-row in the cheatsheet TOC with a distinct color (orange or red banner), and a dedicated "Why this failed" structured section using the Mechanism cheatsheet pattern but with the failure mode prefilled.

**Bonus**: a cumulative count of failure modes ("3 of 5 experiments this session triggered a `G_safety` revision") becomes a hero stat — the FRAMEWORK's own KPI.

---

## 9. Roadmap

| Wave | Primitives | Sequence | Trigger |
|---|---|---|---|
| **Wave 1** (immediate) | §1 Mechanism cheatsheet, §3 G_safety minimum set | start NOW | this session's lessons |
| **Wave 2** (next 2-3 sessions) | §2 Paper-citation gate, §4 Lineage manifest | after Wave 1 lands and is used once | requires schema design |
| **Wave 3** (cross-project) | §5 Adversarial reviewer hook, §6 Dependency graph | medium-term | needs MCP / agent harness work |
| **Wave 4** (cultural) | §7 Time-budget governance, §8 Falsification-amplification | when Wave 1-3 are routine | requires owner buy-in on cadence |

Each wave is itself a pre-registered experiment: "does adopting Primitive X reduce reviewer-caught failures per session?" The framework eats its own dogfood.

---

## 10. What this document IS NOT

- It is not the implementation. Each primitive needs a code change (template, gate logic, hook script). This is the design and the rationale.
- It is not a one-time deliverable. Iterate with each session's lessons. Versioning happens via git history; no need for explicit version numbers.
- It is not the only document of its kind. Pairs with `ars/PROMOTION.md` (the gates), `ars/LESSONS.md` (the failures), and `arki/wiki/process/index.md` (the lifecycle).

---

## Cross-references

- `ars/PROMOTION.md` — promotion lifecycle and gate definitions
- `ars/LESSONS.md` — append-only failure log
- `ars/DECISIONS.md` — chronological promotion / falsification record
- `arki/cheatsheets/` — the Tier-2a HITL audit surface this document operationalises
- Reference: `~/Downloads/rtv_xbondreit_sgd_cpc.html` (b3-saa-etf Mechanism cheatsheet exemplar)
