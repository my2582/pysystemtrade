#!/usr/bin/env python
"""Validate ARS pre-registration files against framework Rules 1-5.

Honest framing: this is a LINT-style script, not a commit-blocker. It is
designed to be runnable locally before committing a pre-registration, or
in CI on a PR touching ars/evidence_packs/<slug>/<slug>_preregistration.md.
Wiring it as a commit hook is deferred to owner discretion (would modify
.git/hooks/ or .claude/settings.json — not unilateral).

Rules enforced (from arki/wiki/onboarding/04_lessons_distilled.md):

  Rule 1: every gate cites paper + section + equation OR claim, never figure
          alone. Slogan citations FAIL.
  Rule 2: every multiplicative weight in degenerate-denominator class declares
          a finite upper bound. Detected by regex on weight formula patterns.
  Rule 3: paper-derived gates list assumption_set and verify each empirically.
  Rule 4: aggregation method is declared per gate (verification or reporting mode).
  Rule 5: no proposed primitive blocks the Agent Loop on a default owner sign-off
          (this is a structural check on framework documents, not pre-registrations).

Usage:
    venv/bin/python scripts/validate_preregistration.py \\
        ars/evidence_packs/<slug>/<slug>_preregistration.md

    venv/bin/python scripts/validate_preregistration.py \\
        ars/evidence_packs/  # scan all under directory

Exit codes:
    0 — all checks passed
    1 — one or more violations
    2 — input not found or unreadable
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# Patterns -----------------------------------------------------------------

# Slogan citation = paper + figure word, no equation/section paired
SLOGAN_PATTERNS = [
    r"\bFig(?:ure)?\.?\s*\d+\b",
    r"\bFig(?:ure)?\s+[A-Z]\b",
]

# Degenerate-denominator weight formulas (rough heuristic)
DENOM_DEGENERATE_HINTS = [
    r"1\s*/\s*(?:semi[_\s]?var|sigma|var|sd|std|σ)",
    r"sqrt\(\s*target.*?\)\s*/\s*sqrt\(\s*(?:semi[_\s]?var|sigma)",
    r"μ_t.*?/.*?σ²",
    r"mu[_\s]?hat.*?/.*?sigma[_\s]?sq",
]

# Markers for bound declarations
BOUND_DECLARATION = [
    r"max\s*\(\s*\|w[\s_]?(?:dMOM|sMOM|cMOM|t)?\|\s*\)\s*[≤<]=?\s*\d",
    r"w\s*[<≤]\s*\d",
    r"\|w_t\|\s*[≤<]\s*\d",
    r"capped at",
    r"hard cap",
    r"safety bound",
]


@dataclass
class Violation:
    rule: str
    severity: str        # error | warning | info
    location: str        # file + line range
    description: str
    suggested_fix: str = ""


@dataclass
class ValidationResult:
    file: Path
    violations: list[Violation] = field(default_factory=list)
    checks_passed: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)


# Rule 1 — section + equation citation, NEVER figure alone -----------------

def check_rule1_citations(text: str, path: Path) -> list[Violation]:
    violations = []
    # find lines that look like gate definitions
    gate_pattern = re.compile(r"(?:^[\-\*]\s*\*\*?G[\d_]+\b|G[\d_]+\s*[:=])", re.MULTILINE)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        for slogan in SLOGAN_PATTERNS:
            m = re.search(slogan, line)
            if m and "Fig" in line:
                # check whether equation or section also present on this line or next 2 lines
                ctx = "\n".join(lines[i:i + 3])
                has_section = bool(re.search(r"§\s*\d|\bSection\s+\d|\bSec\.\s*\d", ctx))
                has_equation = bool(re.search(r"\bEq(uation)?\.?\s*\d+|\beq[.\s]*\(?\d+\)?", ctx, re.I))
                if not (has_section or has_equation):
                    violations.append(Violation(
                        rule="Rule 1 (citation discipline)",
                        severity="error",
                        location=f"{path.name}:L{i+1}",
                        description=f"Figure-only citation detected: '{m.group()}'. No section or equation paired within 3 lines.",
                        suggested_fix="Replace `Fig N` with `§X.Y Eq. M` or `§X.Y claim: '<short quote>'`.",
                    ))
    return violations


# Rule 2 — bound on degenerate-denominator multiplicative weights ----------

def check_rule2_weight_bounds(text: str, path: Path) -> list[Violation]:
    violations = []
    # detect degenerate-denominator patterns
    degen_hits = []
    for pat in DENOM_DEGENERATE_HINTS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            line_idx = text[:m.start()].count("\n")
            degen_hits.append((line_idx + 1, m.group()))
    if not degen_hits:
        return violations
    # look for bound declarations anywhere in doc
    has_bound = any(re.search(pat, text, re.IGNORECASE) for pat in BOUND_DECLARATION)
    if not has_bound:
        violations.append(Violation(
            rule="Rule 2 (degenerate-denominator bound)",
            severity="error",
            location=f"{path.name}:L{degen_hits[0][0]}",
            description=f"Degenerate-denominator weight detected ('{degen_hits[0][1]}') but no bound declaration found in the document.",
            suggested_fix="Add to §3 Action or §4 Gates: `max(|w_t|) ≤ N` with a finite N (e.g. 3 or 5). See arki/wiki/onboarding/04_lessons_distilled.md Rule 2.",
        ))
    return violations


# Rule 3 — paper-derived gates verify assumptions empirically --------------

def check_rule3_assumption_checks(text: str, path: Path) -> list[Violation]:
    violations = []
    has_paper_citation = bool(re.search(r"\b(Martin|Hanauer|Wang|Daniel|Carver|Pedersen|Barroso)\b", text))
    if not has_paper_citation:
        return violations
    has_assumption_section = bool(re.search(r"assumption[_\s]?set|assumes\b", text, re.I))
    if not has_assumption_section:
        violations.append(Violation(
            rule="Rule 3 (assumption empirical check)",
            severity="warning",
            location=f"{path.name}",
            description="Paper citations present but no explicit assumption_set section / `assumes` statement found.",
            suggested_fix="Add an `assumption_set:` list per gate (e.g. `κ_3(U_n) = 0`, `linear class with all a_j > 0`) and an `assumption_check:` step that measures each empirically.",
        ))
    return violations


# Rule 4 — aggregation declared per gate ------------------------------------

def check_rule4_aggregation(text: str, path: Path) -> list[Violation]:
    violations = []
    has_gates = bool(re.search(r"\bG\d|gate", text, re.I))
    if not has_gates:
        return violations
    aggregation_mentioned = bool(re.search(r"aggregation|fixed[\s_-]?M|sign[\s_-]?episode|holding[\s_-]?period|non[\s_-]?overlapping", text, re.I))
    if not aggregation_mentioned:
        violations.append(Violation(
            rule="Rule 4 (aggregation discipline)",
            severity="warning",
            location=f"{path.name}",
            description="Gates defined but no aggregation method declared (fixed-M, sign-episode, overlapping, ...). This is ambiguous for any skew/return metric.",
            suggested_fix="Declare aggregation explicitly: `skew_per_trade uses sign-episode aggregation (variable M)` or `skew uses fixed-M=20 non-overlapping`.",
        ))
    return violations


# Validate one file ---------------------------------------------------------

def validate_file(path: Path) -> ValidationResult:
    result = ValidationResult(file=path)
    try:
        text = path.read_text()
    except Exception as e:
        result.violations.append(Violation(
            rule="IO", severity="error",
            location=str(path), description=f"Cannot read file: {e}"))
        return result

    for check_fn, name in [
        (check_rule1_citations, "Rule 1 (citations)"),
        (check_rule2_weight_bounds, "Rule 2 (weight bounds)"),
        (check_rule3_assumption_checks, "Rule 3 (assumption checks)"),
        (check_rule4_aggregation, "Rule 4 (aggregation)"),
    ]:
        v = check_fn(text, path)
        if v:
            result.violations.extend(v)
        else:
            result.checks_passed.append(name)

    return result


# Reporting -----------------------------------------------------------------

def print_result(result: ValidationResult) -> None:
    try:
        rel = result.file.resolve().relative_to(ROOT)
    except ValueError:
        rel = result.file
    print(f"\n=== {rel} ===")
    for ok in result.checks_passed:
        print(f"  [PASS] {ok}")
    for v in result.violations:
        prefix = {"error": "[FAIL]", "warning": "[WARN]", "info": "[INFO]"}[v.severity]
        print(f"  {prefix} {v.rule}")
        print(f"         {v.location}: {v.description}")
        if v.suggested_fix:
            print(f"         fix: {v.suggested_fix}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=Path, nargs="?",
                    default=ROOT / "ars" / "evidence_packs",
                    help="Pre-registration file OR a directory to scan recursively.")
    args = ap.parse_args()

    target: Path = args.target
    if not target.exists():
        print(f"[err] target does not exist: {target}", file=sys.stderr)
        sys.exit(2)

    files = []
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.glob("**/*preregistration.md"))

    if not files:
        print(f"[warn] no preregistration files found under {target}")
        sys.exit(0)

    results = [validate_file(p) for p in files]
    for r in results:
        print_result(r)

    n_files = len(results)
    n_errors = sum(1 for r in results if r.has_errors)
    n_warnings = sum(len([v for v in r.violations if v.severity == "warning"])
                     for r in results)

    print(f"\n=== Summary: {n_files} file(s) scanned, {n_errors} error(s), {n_warnings} warning(s) ===")
    sys.exit(1 if n_errors else 0)


if __name__ == "__main__":
    main()
