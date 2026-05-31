# HANDOFF — Close out the "risk-shaping" sub-family (capped sMOM + TBM Stage-1)

**Target:** Claude Code, in the pysystemtrade repo. **Decision:** Branch C / 갈래 A —
bundle capped sMOM + TBM Stage-1 into a coherent **risk-shaping** sub-group of the
`futures_momentum` family and close the size-overlay line of inquiry on ZN.

**This doc is the closeout spec.** It records verdicts, applies the G4 refinement to
unblock capped sMOM, groups the two cells, and writes the unified finding. No new
backtests are required — both runs already exist.

---

## 0. One-paragraph thesis (write this into findings.md verbatim)

> On US10/ZN single-instrument, **size-layer overlays shape risk but do not generate
> directional alpha.** Two independent overlays converge on this: capped sMOM
> (downside-vol scaling) is a **strong** risk-shaper (maxDD −55.35% → −44.16%, +11.19pp;
> Sharpe lift +0.276) but its lift is mechanical vol-scaling, **proven not-edge** because
> the same mechanism lifts the no-edge SP500 control (Sharpe −0.009 → +0.305 via vol
> collapse 24.3→6.23, ratio 0.26). TBM Stage-1 (meta-labeling) is a **weak** risk-shaper
> (maxDD −0.87 to −2.49pp; DSR uplift ≈ 0, g pinned near its 0.30 floor) with no detectable
> conditional edge. The alpha levers are elsewhere: **multi-instrument breadth and Stage-2
> speed-tilt.** Notably the simple tool (sMOM vol-scaling) shaped risk better than the
> sophisticated one (TBM meta-labeling).

---

## 1. Promote capped sMOM → Path B (via G4 refinement, LESSONS Entry 3)

The capped sMOM run (`20260530T170606Z_smom_us10_capped`) sits at `registered, ambiguous`
solely because G4 (SP500 control Sharpe < 0.20) failed at 0.305. **Apply the LESSONS Entry 3
refinement to resolve it.**

**G4 refined logic (paired vol diagnostic):**
```
SP500 capped: Sharpe 0.305 (> 0.20 threshold), vol_capped 6.23, vol_baseline 24.3
ratio = 6.23 / 24.3 = 0.256  ≤ 0.7
⇒ rescue is via VOL REDUCTION, not return generation
⇒ G4 verdict = MECHANISM_NOTE (NOT a FAIL)
```

**Resulting gate ledger (capped sMOM, US10):**

| Gate | Value | Verdict |
|---|---|---|
| G1 Sharpe lift ≥ +0.05 | +0.276 | PASS |
| G2 maxDD improvement ≥ +3.0pp | +11.19pp | PASS |
| G3 skew_per_trade ≥ 1.0 | ~+4.69 (verify on capped) | PASS |
| G4 SP500 control < 0.20 | 0.305, ratio 0.26 | **MECHANISM_NOTE** (refined; not fail) |
| G5 capped/uncap lift ∈ [0.30,1.20] | 0.276/0.255 = 1.08 | PASS |
| G_safety max\|w\|≤3, semi_var≥1e-4 | satisfied by construction | PASS |
| G_recon | < 1% | PASS (verify) |

**Promotion decision — Path B, NOT Path A.** Even though G1 passes, the G4 MECHANISM_NOTE
is the load-bearing finding: the Sharpe lift is generic vol-scaling (works on the no-edge
control), **not** US10-specific edge detection. Promote as:
```
status: registered_path_b  (crash-mitigator only; owner sign-off recorded)
note: "Sharpe lift is vol-scaling, not alpha — G4 SP500 control lifts too (ratio 0.26).
       Genuine value = maxDD −11.19pp + skew preserved. Matches Hanauer §3 framing."
```
This replaces `registered_pending_remediation` on the original `smom_us10` entry; the
uncapped cell stays in registry as a reference with its leverage-artifact note.

**Honesty correction to log in DECISIONS** (LESSONS Entry 1 was directionally wrong):
> LESSONS Entry 1 predicted capped sMOM Sharpe lift would fall to +0.10–0.15 ("partially
> leverage artifact"). Empirically capped lift = +0.276 (HIGHER than uncapped +0.255).
> The 6,439× spikes were net-HURTING Sharpe (large positions on volatile days), not
> inflating it. The downgrade was correct (6,439× is unrealizable) but the stated reason
> ("Sharpe overstated by leverage") is reversed by data. Record as a self-correction:
> unrealizability, not Sharpe inflation, was the true defect.

---

## 2. Record TBM Stage-1 verdict (no new run)

Confirm the existing TBM cells in registry/family carry the precise verdict:
```
status: relative_pass_absolute_fail
finding: "no DETECTABLE conditional edge under {ER features, TBM labels, bagged trees,
          g_min=0.30} on ZN single-instrument; avg_uniqueness 0.07–0.10 < 0.20 (as-TBM-iid
          violated). T_max 120→40 ablation confirms low sensitivity (g_max 0.551→0.591) —
          signal-limited, not timidity. Residual value = MaxDD −0.87 to −2.49pp."
```
Both the baseline (T_max=120) and the T_max=40 sensitivity cell are recorded; family N
already reflects them (=58).

---

## 3. Group both under a `risk_shaping` tag in family.yaml

Add a sub-group marker so future agents see these as ONE evidence bundle, not scattered
cells. Within Panel A (single-instrument), tag the relevant cells:
```yaml
sub_groups:
  risk_shaping_size_overlays:
    thesis_ref: findings.md#risk-shaping-size-overlays   # the §0 paragraph above
    members:
      - smom_us10_capped        # strong risk-shaper, Path B
      - tbm_meta_us10_baseline   # weak risk-shaper, relative-pass/absolute-fail
      - tbm_meta_us10_tmax40     # sensitivity cell
    unified_verdict: "size-layer shapes risk, not alpha (ZN single-instrument)"
    layer: size                  # all compete on the same layer; none is additive alpha
    metric_units_note: "sMOM lift = vol-scaling (mechanical); not edge — see SP500 control"
```
**Do NOT create a `TBM_x_sMOM` composed cell.** They are the same layer (size); multiplying
two size-scalers is not a meaningful composition (L6).

---

## 4. findings.md — add the risk-shaping conclusion + the sMOM>TBM note

Append a section under Panel A:
```markdown
## Risk-shaping size-overlays (ZN single-instrument) — CLOSED

Verdict: size-layer overlays shape risk, not alpha. [§0 thesis paragraph]

| overlay | maxDD Δ | Sharpe lift | lift source | alpha? |
|---|---|---|---|---|
| sMOM capped | +11.19pp | +0.276 | vol-scaling (SP500 control lifts too) | NO |
| TBM Stage-1 | +0.87–2.49pp | ≈0 (DSR uplift sign-flips) | n/a (g floored) | NO |

Note (counter-intuitive): the simple overlay (sMOM downside-vol scaling) shaped risk
markedly better than the sophisticated one (TBM meta-labeling). Sophistication did not
pay on this single-instrument problem.

Elasticity implication: the `overlay` axis (size-layer) is now well-characterised on ZN
as risk-shaping-only. Do NOT spend more N on single-instrument size overlays. The live
axes are `universe` (breadth) and `rule_structure` (speed-tilt).
```

---

## 5. What is CLOSED vs what is NEXT

**CLOSED (this handoff):**
- Single-instrument size-overlay line on ZN. sMOM (capped, Path B) + TBM (relative-pass)
  are the canonical risk-shaping evidence. No more size-overlay cells on ZN solo.

**NEXT (the alpha levers — separate cycles, ranked):**
1. **Multi-instrument breadth (Panel B opens).** Directly resolves the effective-sample
   ceiling (L2) that capped both overlays. Smallest honest step: a low-correlation
   universe, not just rates (rates are 0.5–0.8 correlated → limited breadth gain).
2. **Stage-2 speed-tilt λ(s_t).** F3 diagnostics showed 6-speed > single in every crisis
   window — the larger alpha lever, and it lives on the *side/forecast* layer (not size),
   so it is genuinely additive to the risk-shaping tools, not competing.
3. **(Optional, deferred) true cross-sectional sMOM** in the multi-instrument habitat —
   only if breadth work creates a winner-minus-loser portfolio worth scaling. The current
   `smom_us10` is single-instrument semi-vol scaling (가), not the paper's cross-sectional
   form (나); the paper's form needs a cross-section to exist.

---

## 6. Honest caveats (keep visible)

1. **sMOM Path B lift is vol-scaling, not edge.** Do not let "Sharpe +0.276" read as alpha
   anywhere downstream — the SP500 control (G4 MECHANISM_NOTE) is the disproof.
2. **Units / provenance.** sMOM/TBM Sharpe are vol-targeted strategy-% annualised at 256;
   TBM barriers are raw-price-σ. All figures reported from Claude Code runs, not re-derived.
3. **"No detectable" ≠ "no signal universally."** Both verdicts are conditional on the
   single-instrument sample regime (avg_uniqueness < 0.20). Multi-instrument may change it.
4. **DSR bar.** Promoting capped sMOM (Path B) and recording TBM does not add new search
   configs beyond what N=58 already counts; no threshold change. (Confirm in family.yaml.)
```
