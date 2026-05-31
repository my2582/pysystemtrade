# STATUS — single session-continuity entry point

> **Read this first.** State lives on disk; sessions are disposable (F7). This file mirrors
> the current state — it does **not** make new decisions. Anything undecided is marked
> "owner-undecided". Last reconciled: **2026-05-31**. Source of truth for detail =
> `family.yaml` / `findings.md` / `queue.md` / `registry.yaml`; handoff ledger =
> [`handoffs/_index.md`](handoffs/_index.md).

## Where we are

`futures_momentum` family. On **ZN single-instrument**, the **size-layer overlay** line is
**CLOSED**: sMOM capped = `registered_path_b` (crash-mitigator only), TBM Stage-1 meta-labeling
= `relative_pass_absolute_fail` (both cells). Size overlays **shape risk but do not generate
directional alpha** — the G4 SP500 control proved the sMOM "lift" is mechanical vol-scaling
(vol ratio 6.23/24.3 = **0.26**), not edge. The alpha levers are **breadth** (Panel B) and
**Stage-2 speed-tilt** (side/forecast layer). Family DSR threshold @ N=58 = **0.3326 ann**;
no cell clears it for confident absolute promotion. `live_trading: false`.

## Active front

Size-overlay line on ZN solo = **CLOSED** (no more single-instrument size overlays). The next
research cycle is the alpha hunt: **Stage-2 speed-tilt (A)** or **Panel B breadth (B)** —
**owner-undecided** which goes first. Both are pre-reg-pending (no runner authored yet).

## Open items (pending only)

- **`matrix.html` — RESOLVED, not open.** `arki/reports/family/futures_momentum_matrix.html`
  exists (10,996 B, commit `c1076c77`). The 4th-branch reports' "still pending" was stale.
- **Backfill older 13 cells to CPC v1** (unified_cpc §5-#2) — separate cleanup cycle. Open.
- **Delete deprecated 2026-05-29 reports** (`arki/results/2026-05-29/execution_friction_us10_6cell.html`
  + regime HTML, superseded by the 6-cell CPC) (unified_cpc §5-#3) — **owner purge pending**.
- **External-share re-render** (unified_cpc §5-#4) — separate sanitisation pipeline. Open.
- **family.yaml cell-count counters** (`n_cells_registered`, `n_cells_pre_registered_queued`)
  left as last reconciled snapshot (4th-branch §7-2). DSR N (=58) + threshold (0.3326) are
  **already correct and frozen**; only the bookkeeping counters are a small follow-up.

## Next 3 priorities (from `queue.md`)

1. **stage2_speed_tilt_us10** — alpha lever on the **side/forecast** layer (λ(s_t)); genuinely
   ADDITIVE to size-layer tools (6-speed EWMAC beat single in every crisis window). Author Path A pre-reg.
2. **panel_B_open_dm_rates_5** — **breadth** lever; directly attacks the effective-sample ceiling
   (avg_uniqueness < 0.20) that capped both size overlays. Caveat: rates-only is breadth-limited
   (0.5–0.8 corr) — cheapest first probe, not the destination (low-corr rates+commods+eq+FX is higher-info).
3. **rule_structure_deconfound_us10** — the only axis with **n=0 clean pairs**; confirmatory
   single_ema2 vs carver_native at $1M. Advisable before Panel B to lock the rule choice.

## Pointers

- Family: [`families/futures_momentum/family.yaml`](families/futures_momentum/family.yaml) ·
  [`findings.md`](families/futures_momentum/findings.md) ·
  [`queue.md`](families/futures_momentum/queue.md) ·
  [`matrix.md`](families/futures_momentum/matrix.md)
- Runs registry: [`runs/registry.yaml`](runs/registry.yaml)
- Decisions: [`DECISIONS.md`](DECISIONS.md) · Lessons: [`LESSONS.md`](LESSONS.md)
- Handoff ledger: [`handoffs/_index.md`](handoffs/_index.md)
- Family matrix HTML: `arki/reports/family/futures_momentum_matrix.html`
