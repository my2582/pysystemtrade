#!/usr/bin/env python
"""Sanitize cheatsheet + evidence pack artifacts for external review.

Replaces owner/PII/path references with abstract tokens so artifacts can be
shared with external reviewers without leaking sensitive identifiers.
Relative ratios (Sharpe, skew, capital RATIOS) are preserved; absolute capital
numbers are tokenized.

Usage:
    venv/bin/python scripts/sanitize_for_external_review.py \\
        --cheatsheet arki/cheatsheets/2026-05-29_arki_single_instrument_momentum_studies.html \\
        --evidence-packs martin_single_instrument dmom_us10 smom_us10 \\
        --out outputs/external_share/2026-05-29/

What is sanitized:
    - Absolute paths under /Users/<owner>/ -> <repo>/
    - Owner name "Minsu Yeom" -> <owner>
    - Firm name "Arki Finance" / "Arki" -> <firm>
    - Email addresses -> <email>
    - Capital amounts ($50k, $50,000, 50000 USD) -> <capital-token> (with note)
    - "msyeom" username -> <owner>

What is preserved:
    - Instrument tickers (US10, SP500) — public knowledge
    - Strategy slugs (martin_single_instrument, dmom_us10, ...)
    - git SHAs — public reference
    - Quantitative metrics (Sharpe, skew, ratios) — the substance of review
    - Paper citations
    - Run UTC timestamps
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Sanitisation rules: (pattern, replacement, description)
RULES: list[tuple[str, str, str]] = [
    # absolute paths
    (r"/Users/msyeom/Developer/pysystemtrade", "<repo>", "absolute repo path"),
    (r"/Users/msyeom/Developer/", "<dev-root>/", "developer root"),
    (r"/Users/msyeom/", "<home>/", "home directory"),
    (r"~/", "<home>/", "tilde home"),
    # owner identity
    (r"Minsu Yeom", "<owner>", "owner name"),
    (r"msyeom", "<owner-id>", "owner shell user"),
    (r"nlfelix@gmail\.com", "<email>", "owner gmail"),
    (r"minsu\.yeom@arkifinance\.com", "<email>", "owner work email"),
    # firm identity
    (r"Arki Finance Pte\.? Ltd\.?", "<firm>", "firm legal name"),
    (r"Arki Finance", "<firm>", "firm short name"),
    # capital absolute numbers (preserve RATIOS; tokenize ABSOLUTE)
    (r"\$50,000", "<capital-token>", "capital absolute (50k)"),
    (r"\$50k", "<capital-token>", "capital shorthand (50k)"),
    (r"capital_usd: 50000", "capital_usd: <capital-token>", "config capital"),
    (r"USD 50,000", "<capital-token>", "capital USD long"),
    (r"50_000", "<capital-token>", "capital python literal"),
    (r"320,000,000", "<notional-extreme>", "extreme leverage example notional"),
    (r"6,439", "<extreme-leverage-multiple>", "extreme leverage multiple"),
    (r"2,927", "<extreme-position-contracts>", "extreme position contracts"),
    # downstream PROD repo names (rename to abstract)
    (r"b3-saa-etf", "<downstream-saa>", "downstream SAA repo"),
    (r"arki-future-fund-engine", "<downstream-gtaa>", "downstream GTAA repo"),
    (r"arki-gtaa", "<downstream-tactical>", "downstream tactical repo"),
    (r"arki-trade-analysis", "<trade-analysis-pkg>", "trade analysis package"),
    (r"arki-etf-universe-db", "<universe-db>", "universe DB project"),
    # private code SHA hint removal
    (r"git@github\.com:.+\.git", "<git-remote>", "git remote URL"),
]

# Header banner to prepend to sanitized cheatsheet
SANITISATION_BANNER = """
<div style="background:#fef3c7;border-left:5px solid #d97706;padding:14px 18px;margin:12px 0;font-size:13px;line-height:1.5">
<b>EXTERNAL-REVIEW VERSION.</b> This document has been sanitized for external review. Identifiers (owner, firm, absolute paths, capital amounts, downstream PROD repo names) have been replaced with abstract tokens. Quantitative metrics (Sharpe, skew, ratios, percentages) and paper citations are PRESERVED — they are the substance of review.
<br><br>
<b>Tokens used</b>: <code>&lt;owner&gt;</code>, <code>&lt;firm&gt;</code>, <code>&lt;repo&gt;</code>, <code>&lt;capital-token&gt;</code>, <code>&lt;downstream-saa&gt;</code>, <code>&lt;downstream-gtaa&gt;</code>, <code>&lt;downstream-tactical&gt;</code>, <code>&lt;extreme-leverage-multiple&gt;</code>.
<br><br>
<b>Context for the reviewer</b>: see <code>REVIEW_REQUEST.md</code> alongside this file for the high-level project context, the specific review dimensions requested, and how to respond.
</div>
"""


def sanitize_text(text: str) -> tuple[str, list[tuple[str, int]]]:
    """Apply all RULES to text. Return (sanitised_text, list_of_(rule_desc, n_replaced))."""
    out = text
    counts = []
    for pattern, replacement, desc in RULES:
        new_out, n = re.subn(pattern, replacement, out)
        if n > 0:
            counts.append((desc, n))
        out = new_out
    return out, counts


def sanitize_html(path: Path, banner: bool = True) -> tuple[str, list[tuple[str, int]]]:
    """Sanitise an HTML file. If `banner`, prepend the sanitisation banner after <body>."""
    text = path.read_text()
    sanitised, counts = sanitize_text(text)
    if banner:
        sanitised = re.sub(r"(<body[^>]*>)", r"\1\n" + SANITISATION_BANNER, sanitised, count=1)
    return sanitised, counts


def sanitize_markdown(path: Path) -> tuple[str, list[tuple[str, int]]]:
    text = path.read_text()
    sanitised, counts = sanitize_text(text)
    header = ("> **EXTERNAL-REVIEW VERSION**: identifiers sanitised; quantitative metrics + paper "
              "citations preserved. See REVIEW_REQUEST.md for context.\n\n")
    return header + sanitised, counts


def make_review_request(out_dir: Path, included_artifacts: list[Path]) -> Path:
    """Write a REVIEW_REQUEST.md describing what the reviewer is asked to do."""
    artifact_list = "\n".join(f"- `{p.name}`" for p in included_artifacts)
    content = f"""# External Review Request — pysystemtrade momentum studies

**Date prepared**: {date.today().isoformat()}

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

{artifact_list}

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

Sanitised by `scripts/sanitize_for_external_review.py` on {date.today().isoformat()}.
"""
    p = out_dir / "REVIEW_REQUEST.md"
    p.write_text(content)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cheatsheet", type=Path, required=True,
                    help="Path to the cheatsheet HTML to sanitise.")
    ap.add_argument("--evidence-packs", nargs="*", default=[],
                    help="Slugs under ars/evidence_packs/ to sanitise (README.md only; PDFs copied as-is).")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output directory under outputs/external_share/.")
    args = ap.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    included = []

    # 1. Cheatsheet
    if args.cheatsheet.exists():
        s, counts = sanitize_html(args.cheatsheet, banner=True)
        dst = out / f"cheatsheet_sanitized.html"
        dst.write_text(s)
        included.append(dst)
        print(f"[ok] {args.cheatsheet.name} -> {dst.name}: {sum(n for _, n in counts)} replacements")
        for desc, n in counts:
            print(f"      {n:4d}× {desc}")

    # 2. Evidence packs
    packs_root = ROOT / "ars" / "evidence_packs"
    for slug in args.evidence_packs:
        src_pack = packs_root / slug
        if not src_pack.exists():
            print(f"[warn] evidence pack not found: {slug}")
            continue
        dst_pack = out / "evidence_packs_sanitized" / slug
        dst_pack.mkdir(parents=True, exist_ok=True)
        # Sanitize README.md and preregistration.md (text); copy PDFs as-is
        for fname in ["README.md"]:
            sp = src_pack / fname
            if sp.exists():
                s, _ = sanitize_markdown(sp)
                (dst_pack / fname).write_text(s)
        for f in src_pack.iterdir():
            if f.suffix == ".md" and f.name != "README.md":
                s, _ = sanitize_markdown(f)
                (dst_pack / f.name).write_text(s)
            elif f.suffix == ".pdf":
                shutil.copy(f, dst_pack / f.name)
            elif f.name == "verdict.json":
                # JSON sanitisation: same rules, just text replace
                s, _ = sanitize_text(f.read_text())
                (dst_pack / f.name).write_text(s)
        included.append(dst_pack)
        print(f"[ok] evidence_pack {slug} -> {dst_pack.relative_to(out)}/")

    # 3. REVIEW_REQUEST.md
    req = make_review_request(out, included)
    print(f"[ok] {req.name} written")

    # 4. Provenance footer
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        git_sha = "unknown"
    (out / "PROVENANCE.txt").write_text(
        f"Sanitised on: {date.today().isoformat()}\n"
        f"Source repo git SHA: {git_sha}\n"
        f"Sanitiser script: scripts/sanitize_for_external_review.py\n"
        f"Cheatsheet source: {args.cheatsheet}\n"
        f"Evidence packs: {', '.join(args.evidence_packs)}\n"
    )
    print(f"\nOutputs: {out}")


if __name__ == "__main__":
    main()
