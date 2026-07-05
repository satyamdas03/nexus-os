"""Generate a markdown report of the conversational eval set.

Usage:
    cd backend
    python -m evals.generate_report > ../docs/conversational-eval-report.md
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from evals.conversational_eval import run_all
from evals.eval_data import ALL_EVAL_CASES, EVAL_CATEGORIES


def _escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def generate_report() -> str:
    """Run every eval case and return a markdown report string."""
    results = run_all()
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    lines: list[str] = []
    lines.append("# ASSURE Conversational Assurance — Eval Report")
    lines.append("")
    lines.append(f"- **Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **Total cases:** {len(results)}")
    lines.append(f"- **Passed:** {passed}")
    lines.append(f"- **Failed:** {failed}")
    lines.append("")

    lines.append("## Summary by Category")
    lines.append("")
    lines.append("| Category | Cases | Passed | Failed |")
    lines.append("|----------|------:|-------:|-------:|")
    for category, cases in EVAL_CATEGORIES.items():
        ids = {c.id for c in cases}
        cat_results = [r for r in results if r.case_id in ids]
        cat_passed = sum(1 for r in cat_results if r.passed)
        cat_failed = len(cat_results) - cat_passed
        lines.append(f"| {category} | {len(cat_results)} | {cat_passed} | {cat_failed} |")
    lines.append("")

    lines.append("## Failures")
    lines.append("")
    failures = [r for r in results if not r.passed]
    if not failures:
        lines.append("_No failures._")
    else:
        lines.append("| Case | Error / Missing Tokens |")
        lines.append("|------|------------------------|")
        for r in failures:
            detail = r.error or f"Missing: {r.missing_substrings}"
            lines.append(f"| {r.case_id} | {_escape(detail)} |")
    lines.append("")

    lines.append("## Full Results")
    lines.append("")
    lines.append("| Case | Source | Intent | Grounded | Citations OK | Substrings OK | Answer |")
    lines.append("|------|--------|--------|----------|--------------|-----------------|--------|")
    for r in results:
        case = next((c for c in ALL_EVAL_CASES if c.id == r.case_id), None)
        source = case.source if case else "unknown"
        intent_ok = "✅" if r.intent_match else "❌"
        grounded_ok = "✅" if r.grounded else "❌"
        citations_ok = "✅" if r.citation_types_ok else "❌"
        substrings_ok = "✅" if r.required_substrings_ok else "❌"
        answer = _escape(r.answer[:200] + ("..." if len(r.answer) > 200 else ""))
        lines.append(
            f"| {r.case_id} | {source} | {intent_ok} {r.actual_intent} | {grounded_ok} | {citations_ok} | {substrings_ok} | {answer} |"
        )
    lines.append("")

    lines.append("## Manual Review Flags")
    lines.append("")
    lines.append("Cases where the polished answer grew >2× over the raw fact count.")
    lines.append("")
    verbose = []
    for r in results:
        if r.passed and len(r.answer) > 400:
            verbose.append(r)
    if not verbose:
        lines.append("_No verbose answers flagged._")
    else:
        lines.append("| Case | Length | Answer |")
        lines.append("|------|-------:|--------|")
        for r in verbose:
            answer = _escape(r.answer[:200] + "...")
            lines.append(f"| {r.case_id} | {len(r.answer)} | {answer} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate conversational eval report")
    parser.add_argument(
        "--output",
        help="Optional output file; defaults to stdout",
    )
    args = parser.parse_args()
    report = generate_report()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
