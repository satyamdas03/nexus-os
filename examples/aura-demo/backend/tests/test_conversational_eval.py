"""Parametrized eval set for ASSURE Conversational Assurance.

This test runs the 50-case eval dataset (30 synthetic + 20 real-book) and
validates intent classification, grounding, citation types, and hallucination
safety. It also tests intent stability across voice-transcription paraphrases.
"""

import pytest

from agents.conversational import _classify_intent
from evals.conversational_eval import run_case
from evals.eval_data import ALL_EVAL_CASES, SYNTHETIC_CASES


def _case_label(case):
    return f"{case.id}-{case.source}"


@pytest.mark.parametrize("case", ALL_EVAL_CASES, ids=_case_label)
def test_eval_case(case):
    """Every eval case must produce the expected grounded answer."""
    result = run_case(case)
    assert result.intent_match, (
        f"Case {case.id}: expected intent {case.expected_intent}, got {result.actual_intent}"
    )
    assert result.grounded, f"Case {case.id}: answer was not marked grounded"
    assert result.citation_types_ok, (
        f"Case {case.id}: missing citation types {case.expected_citation_types}, got {result.citations}"
    )
    assert result.required_substrings_ok, (
        f"Case {case.id}: answer missing required tokens {result.missing_substrings}\nanswer: {result.answer}"
    )


def test_all_synthetic_cases_covered():
    """Sanity check that we have the intended 30 synthetic cases."""
    assert len(SYNTHETIC_CASES) == 30


def test_all_real_book_cases_covered():
    """Sanity check that we have the intended 20 real-book clients × 6 queries."""
    real_count = len([c for c in ALL_EVAL_CASES if c.source == "real-book"])
    assert real_count == 120  # 20 clients × 6 queries


@pytest.mark.parametrize("case", SYNTHETIC_CASES, ids=lambda c: c.id)
def test_paraphrase_intent_stability(case):
    """Voice/transcription variants must keep the same intent."""
    for paraphrase in case.paraphrases:
        intent = _classify_intent(paraphrase)
        assert intent == case.expected_intent, (
            f"Case {case.id} paraphrase {paraphrase!r}: expected {case.expected_intent}, got {intent}"
        )
