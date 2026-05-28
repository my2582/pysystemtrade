# ARS Promotion Standard — pysystemtrade

This document defines the experiment lifecycle and promotion criteria
for ARS-tracked runs in this repo. Adapted (lightly) from the
b3-saa-etf process spine (`wiki/process/index.md`,
`docs/DECISIONS.md`, `prod/MANIFEST.yaml`).

## Decision-rights cap

This repo is capped at **ARS Decision Level 2 — Backtest runner**
(per `ars/project_ars_profile.yaml`: `live_trading: false`,
`client_specific_recommendation: not_allowed`,
`max_ai_decision_level: 2`).

There is **no PROD zone in this repo.** PROD lives in downstream
repos:

- `b3-saa-etf` — SAA / ETF strategies, PROD-v12 current.
- `arki-future-fund-engine` — GTAA / Macro.
- `arki-gtaa` — GTAA tactical overlays.

The deliverable from this repo to downstream is a **promoted
evidence pack** (decision-grade), not a live strategy. Downstream
repos consume the evidence pack and run their own L5+ promotion to
PROD.

## Lifecycle spine

```
research(references/research/)
  → experiment (ars/runs/<id>/)
    → register (ars/runs/registry.yaml)
      → evaluate (Headline Verification + reconciliation)
        → if PASS → promote to evidence pack (ars/evidence_packs/<slug>/)
                  → handoff downstream (link from downstream MANIFEST)
        → if FAIL → register FALSIFIED + finding note (still in registry)
```

## Stages

| Stage | Where | Artifact | ARS level |
|---|---|---|---|
| Research | `references/research/<date>-<slug>.md` | Synthesised review (e.g. Perplexity run) | L1 |
| Pre-register | `ars/evidence_packs/<slug>/<slug>_preregistration.md` | Locked hypothesis + grid + gates + decision rules | L1 |
| Experiment | `scripts/<name>.py` produces `ars/runs/<UTC>_<slug>/` | run dir: summary.csv, manifest.json, report.html/pdf, etc. | L2 |
| Register | append to `ars/runs/registry.yaml` | YAML row with id, label, config, results, verdict, status | L2 |
| Decide | append entry to `ars/DECISIONS.md` | Chronological decision log entry | L2 |
| Promote | materialise `ars/evidence_packs/<slug>/` | Bundle: pre_reg + manifest + verdict + report + (opt) cheatsheet | L2 |
| Handoff | downstream repo's MANIFEST cites the evidence pack dir + git SHA | Cross-project reference | L5+ (lives downstream) |

## Pre-registration discipline

Every non-trivial experiment MUST start with a pre-registration:

- **Locked at git commit time.** Once the pre-registration file is
  committed, the grid / gates / decision rules MUST NOT change before
  the run.
- **Required sections:**
  1. Background and motivation (link to literature in `references/`).
  2. Hypotheses (H0 null, H1 alternative).
  3. Grid (parameters varied; one decision per row).
  4. Gates / decision rules (PASS/FAIL thresholds, including
     reconciliation tolerance and FALSIFIED criteria).
  5. Data snapshot (which prices, what cutoff).
  6. Code snapshot (git SHA at run-start).
- **Sub-skill applies**: `planning-with-files` (task_plan.md /
  findings.md / progress.md) is acceptable as a richer alternative;
  pre-registration is the minimal version.

**Single-decision rule** (b3 carry-over): each experiment changes
**exactly one** design decision vs. its baseline, so attribution is
unambiguous. Do not bundle decisions.

**Ex-ante parameters** (b3 carry-over, López de Prado AFML Ch.3):
hyperparameters (lookback, vol target, thresholds) are fixed
ex-ante in the pre-registration; adaptive selection via grid-search
fit-on-result is overfitting and is not permitted.

## Promotion criteria (research-grade → evidence pack)

An experiment graduates from `ars/runs/<id>/` to
`ars/evidence_packs/<slug>/` when **ALL** of the following hold:

1. **Pre-registration present** at `ars/evidence_packs/<slug>/<slug>_preregistration.md`, committed before run-start git SHA in `manifest.json`.
2. **Reconciliation `|diff| < 5%`** (sum of attributed P&L vs total strategy P&L, in % points). For trade-attribution experiments specifically.
3. **All headline gates PASS** (defined in pre-registration §4).
4. **Reproducibility manifest complete** — `manifest.json` carries git SHA, python version, data snapshot identifier, full config.
5. **Owner review** — explicit approval recorded in `ars/DECISIONS.md`.

If a gate fails, the experiment is registered as **FALSIFIED** in
`ars/runs/registry.yaml` (status: `falsified`) and a brief finding
note is recorded inline. Falsified experiments stay in the registry
permanently (negative results are first-class).

## Report tiers

| Tier | Artifact | When | Format | Purpose |
|---|---|---|---|---|
| 1 | **ARS run report** | Every `ars/runs/<id>/` | 2-page A4 HTML/PDF via `arki/templates/ars_run_report.html` | Workhorse: verdict block + summary + manifest |
| 2a | **Cheatsheet** (`/cheatsheet` skill) | Promotion candidates + owner-review requests | 1-page HTML, Visual Report Methodology v1 (problem → solution → analysis) | Owner-facing synthesis for ONE experiment |
| 2b | **CPC v1 — Cohort Performance Card** | Multi-variant / cross-cohort runs (parameter sweeps, candidate-vs-baseline, candidate-vs-market) | 1-page HTML + CSV + README, USD-native (ann_factor=252) | "Show me N series side-by-side with the standard slicers" — peer-comparable narrative |
| 3 | **Evidence pack** | At promotion (per criteria above) | Directory bundle (see contents below) | Decision-grade, downstream handoff |
| 4 | SRP 3-pack | (downstream repos only) | deck + report + horizon_study | Experiment-vs-PROD; not produced here |

Tier-1 is automatic. Tier-2a is invoked on demand. **Tier-2b (CPC v1)
is MANDATORY for any run that compares 2+ variants** (e.g. dMOM-on
vs dMOM-off, fast-tilt vs equal-weight EWMAC, rates universe sweep).
Tier-3 requires all promotion criteria to PASS.

### CPC v1 spec (USD-adapted from b3-saa-etf `scripts/build_cpc_v1.py`)

- **Output bundle**: `ars/runs/<id>/cpc/<slug>.html` + `monthly_returns_usd.csv` + `README.md`.
- **Currency**: USD-native (no FX), `ann_factor = 252` for daily returns or `12` for monthly aggregates. pysystemtrade's percent curve gives daily P&L in % of capital; resample to monthly for the standard slicers.
- **Fixed periods** (pysystemtrade-adapted): `Full` = full data history; `Last10y` = last 10 calendar years; optionally `Era` splits for owner-defined regime breakpoints. State periods in pre-registration.
- **Per period, per series:**
  - Risk/return table — `Ann.Ret %, Vol %, Sharpe, Sortino, MDD %, Calmar, Skew, n_obs`.
  - Capture vs benchmark (one series flagged `is_benchmark`) — `up_capture %, down_capture %, spread`.
  - Single-factor regression vs benchmark — `alpha_ann %, beta, R²`.
  - Cumulative NAV chart — log-scale, rebased to 100.
  - Monthly returns heatmap — year × month, % .
- **Series source kinds** (mirrors b3): `panel` (pre-computed monthly returns CSV), `csv` (daily NAV CSV), `parquet` (daily NAV parquet).
- **Benchmark conventions** for pysystemtrade single-instrument work:
  - Instrument-baseline: buy-and-hold raw market return of that instrument (computed from `system.rawdata.get_daily_prices`).
  - Strategy-baseline: a pre-registered baseline variant (e.g. plain 6-speed EWMAC without overlay).
- **Reference impl**: TBD at `scripts/build_cpc_v1_pysys.py` (port + USD-ify when the first multi-variant run lands).
- **Standard deliverable trio for promotion** (mirrors b3):
  - SRP statistical evidence — handled downstream, NOT in this repo.
  - **CPC v1** — peer-comparable narrative; mandatory here for multi-variant.
  - **Cheatsheet** — owner-facing one-pager synthesis; recommended for promotion.

## Evidence pack contents

`ars/evidence_packs/<slug>/`:

| File | Required | Source |
|---|---|---|
| `<slug>_preregistration.md` | yes | Locked at pre-registration commit |
| `manifest.json` | yes | Copy from the promoted `ars/runs/<id>/manifest.json` + add `promoted_utc`, `promoted_by`, link to decision-log anchor |
| `verdict.json` | yes | Machine-readable: per-gate PASS/FAIL, reconciliation, headline metrics, status (`promoted` / `falsified`) |
| `report.html` (or `report.pdf`) | yes | ARS run report from the run dir |
| `cheatsheet.html` | optional | Tier-2 owner-facing one-pager (recommended) |
| Data exports | optional | Selected CSVs from the run dir |
| `README.md` | optional | One-paragraph summary + how to consume |

## Registry schema (`ars/runs/registry.yaml`)

YAML list under top-level `runs:`. Each entry:

```yaml
- id: 20260528T161350Z_martin_single_instrument
  label: martin_single_instrument
  timestamp: '2026-05-28T16:13:50Z'
  hypothesis_ref: null            # link to pre_registration if any
  status: registered              # registered | promoted | falsified
  config:
    capital: 50000
    vol_target_pct: 20.0
    instruments: [US10, SP500]
    rules: [ewmac2_8, ewmac4_16, ewmac8_32, ewmac16_64, ewmac32_128, ewmac64_256]
    config_file: scripts/martin_single_instrument_backtest.py
  results:
    us10:
      sharpe_gross: 0.396
      skew_per_trade: 4.382
      market_skew_at_m60: 0.204
      reconciliation_diff_pct: -1.17
    sp500:
      sharpe_gross: -0.005
      skew_per_trade: 4.327
      market_skew_at_m60: -0.037
      reconciliation_diff_pct: 0.853
  verdict_summary: 'All 5 headline gates PASS (rates positive mkt skew @ M=40-60, equity negative, §2.3 theorem confirmed, §3 long-option signature on US10, Sharpe in [0.2, 0.6]).'
  path: ars/runs/20260528T161350Z_martin_single_instrument
  evidence_pack: null             # populated on promotion
```

## Decision log (`ars/DECISIONS.md`)

Chronological. One entry per promotion or notable verdict
(including FALSIFIED). Recommended structure per entry:

- Date + slug + status (promoted / falsified / no_change).
- Hypothesis / claim under test.
- Measured result table (numbers, vs predecessor / baseline if any).
- Verdict text (PASS / FAIL per gate).
- Promotion path (if any) + artifacts links.
- Implications + next experiments.

## Naming conventions

- Run dir: `ars/runs/<UTC ISO compact>_<slug>` (e.g. `20260528T161350Z_martin_single_instrument`).
- Evidence pack: `ars/evidence_packs/<slug>` (no timestamp; promoted runs are by slug, not by run UTC).
- Slug grammar: lowercase, underscores, no dates inside the slug.
- Falsified runs keep their `ars/runs/<id>/` dir; registry status flips to `falsified`.

## What this standard does NOT do

- Does not introduce a PROD zone (deferred to downstream repos).
- Does not require bootstrap CIs on every metric (downstream SRP does that; here, point estimates + reconciliation + pre-registered gates are sufficient).
- Does not duplicate the b3-saa-etf wiki. The committed wiki at `arki/wiki/` is this repo's source of truth.
