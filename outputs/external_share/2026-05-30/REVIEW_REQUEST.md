# External Review Request — pysystemtrade momentum studies

**Date prepared**: 2026-05-30

## High-level context

This is a research repo at ARS Decision Level 2 (Backtest runner). Single instrument futures momentum studies on US10 (10y Treasury futures) and SP500 (E-mini S&P 500), evaluated under a pre-registration framework. The owner is a discretionary PM running a small-AUM systematic stack; the downstream consumers are separate PROD repos (not shared in this review).

The framework is adapted from a sibling repo's lifecycle (research → pre-register → run → register → evaluate → promote/falsify). Pre-registrations are git-locked before the run; gates have PASS/FAIL thresholds; falsified runs are first-class artifacts; lessons are append-only.

This batch contains five experiments, completed 2026-05-29:

1. **Martin baseline** (6-speed EWMAC equal-weight, no carry, soft cap ±20) — Path Z post-hoc grandfather.
2. **dMOM overlay** (Daniel-Moskowitz dynamic scaler) — Path A pre-registered → **falsified**.
3. **sMOM overlay** (Wang-Yan semi-vol scaler) — Path A pre-registered → **promoted then downgraded** (reviewer found unbounded weight defect).
4. **fast-tilt EWMAC** (forecast weights biased toward fast speeds) — Path A → **falsified**.
5. **carry-toggle** (enable carry rule at weight 0.30) — Path A → **refuted Martin §2.3 implication on rates**.

Two reviewer critiques during the session:
- One reviewer caught the sMOM unbounded weight artifact.
- A different reviewer caught a Martin §2.3 misreading (asset attribution vs strategy-design product).

Both lessons are now in `LESSONS.md`. The framework's evolution is documented in `ai_native_research_primitives.md`.

## Artifacts in this share

- `cheatsheet_sanitized.html`
- `martin_single_instrument`
- `dmom_us10`
- `smom_us10`
- `fast_tilt_ewmac`
- `carry_toggle`

## Specific review dimensions requested

Please critique on AS MANY of these as you have time for:

### A. Theoretical alignment
- For each cited paper section / equation, does the pre-registered gate test what the paper actually claims?
- Are paper assumptions (e.g. symmetry of vol-normalised returns) verified before applying paper-derived gates?
- Is the strategy under test in the paper's CLASS, or outside? (e.g. sMOM's `ψ(V_n)` is paper §4 nonlinear, not §2 linear.)

### B. Implementation safety
- Multiplicative weight series: are upper bounds declared?
- Look-ahead: does any input use `t`-time information for a `t`-time decision?
- Full-sample normalisation: is any time-varying weight calibrated using full-sample statistics?

### C. Methodological match
- Aggregation: when measuring a metric vs a paper's prediction, is the SAME aggregation used?
- Trade definitions (sign-episode vs position-roundtrip): is the choice explicit and consistent?

### D. Framework hygiene
- Is the single-decision rule respected (one design change per experiment)?
- Are falsification criteria pre-registered, not constructed post-hoc?
- Are negative results preserved with the same rigor as promoted results?

### E. Anything else
Whatever caught your eye. Negative findings are MORE valuable than positive ones.

## How to respond

Reply with concerns in this rough schema (free-form OK):

```yaml
- severity: theoretical | implementation | methodological | framework | none
  artifact: <filename>
  location: <section / chip / paragraph>
  claim_in_artifact: "<short quote>"
  why_it_might_be_wrong: "<one or two sentences>"
  recommended_action: <retract | re-frame | re-run | declare-out-of-scope>
```

Even one well-pointed concern is enormously valuable. There is no expected response length.

## What is NOT shared

- Absolute amount of capital.
- Owner name / email / firm name.
- Absolute paths / shell user.
- Downstream PROD repos' contents.
- Any client-specific information.

Quantitative substance (Sharpe ratios, skew values, percentages, paper citations) is fully preserved.

---

Sanitised by `scripts/sanitize_for_external_review.py` on 2026-05-30.
