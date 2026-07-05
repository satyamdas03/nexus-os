"""Evaluation runner for ASSURE Conversational Assurance.

The runner executes `agents.conversational.chat` for every case in eval_data and
returns a structured result that can be asserted by pytest or summarized by the
report generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.conversational import chat
from core.data_loader import get_portfolio
from core.effective import effective_portfolio
from core.rules_engine import check

from .eval_data import EvalCase


@dataclass
class EvalResult:
    """Result of running a single eval case."""

    case_id: str
    passed: bool
    intent_match: bool
    grounded: bool
    citation_types_ok: bool
    required_substrings_ok: bool
    missing_substrings: list[str] = field(default_factory=list)
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    actual_intent: str = ""
    expected_intent: str = ""
    error: str | None = None


def _evaluate_real_book(client_id: str, query: str) -> dict:
    """Fetch a real portfolio, run effective + rules engine, then call chat."""
    p = get_portfolio(client_id)
    if not p:
        raise ValueError(f"portfolio {client_id} not found")
    eff = effective_portfolio(p)
    rr = check(eff, p["mandate"])
    return chat(query, eff, p["mandate"], rr)


def _format_required_substrings(case: EvalCase, rules_result: dict | None) -> list[str]:
    """Build required substring list, adding tolerant variants.

    If the case already provides substrings we use those. For real-book cases we
    derive tolerant substrings from the rules result.
    """
    if case.required_substrings:
        return case.required_substrings
    if not rules_result:
        return []
    tokens: list[str] = []
    status = rules_result.get("status")
    if status:
        tokens.append(status)
    for b in rules_result.get("breaches", []):
        plain = b.get("plain", "")
        if plain:
            tokens.append(plain)
    return tokens


def run_case(case: EvalCase) -> EvalResult:
    """Run a single eval case and return a structured result."""
    try:
        if case.source == "synthetic":
            answer_obj = chat(
                case.query,
                case.portfolio or {},
                case.mandate or {},
                case.rules_result or {},
            )
            rr = case.rules_result
        else:
            answer_obj = _evaluate_real_book(case.client_id or "", case.query)
            rr = None

        answer = answer_obj.answer
        actual_intent = answer_obj.intent
        citations = answer_obj.citations or []

        # Intent check.
        intent_match = actual_intent == case.expected_intent

        # Grounding check.
        grounded = answer_obj.grounded is True

        # Citation-type check.
        actual_types = {c.get("type") for c in citations}
        expected_types = set(case.expected_citation_types)
        citation_types_ok = expected_types.issubset(actual_types)

        # Required substring check.
        required = _format_required_substrings(case, rr)
        missing = [s for s in required if s.lower() not in answer.lower()]
        required_substrings_ok = not missing

        passed = (
            intent_match and grounded and citation_types_ok and required_substrings_ok
        )

        return EvalResult(
            case_id=case.id,
            passed=passed,
            intent_match=intent_match,
            grounded=grounded,
            citation_types_ok=citation_types_ok,
            required_substrings_ok=required_substrings_ok,
            missing_substrings=missing,
            answer=answer,
            citations=citations,
            actual_intent=actual_intent,
            expected_intent=case.expected_intent,
        )
    except Exception as exc:  # pragma: no cover — runner must never crash a test
        return EvalResult(
            case_id=case.id,
            passed=False,
            intent_match=False,
            grounded=False,
            citation_types_ok=False,
            required_substrings_ok=False,
            missing_substrings=[],
            answer="",
            citations=[],
            actual_intent="",
            expected_intent=case.expected_intent,
            error=f"{type(exc).__name__}: {exc}",
        )


def run_all(cases: list[EvalCase] | None = None) -> list[EvalResult]:
    """Run all eval cases and return results."""
    from .eval_data import ALL_EVAL_CASES

    cases = cases or ALL_EVAL_CASES
    return [run_case(c) for c in cases]
