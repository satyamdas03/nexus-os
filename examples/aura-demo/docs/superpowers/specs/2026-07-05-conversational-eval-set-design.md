# Conversational Assurance Eval Set — Design Spec

**Date:** 2026-07-05  
**Scope:** Sprint 5 final acceptance criteria — build a 50-question evaluation dataset for the grounded chat agent.

## Goal

Create an automated, version-controlled eval set that proves `agents/conversational.chat`:

1. Classifies user intent correctly.
2. Returns answers grounded in deterministic rules-engine facts.
3. Survives LLM polish without dropping or distorting numeric citations.
4. Handles voice-transcription paraphrases of the same intent.

This is a regression gate and a safety gate before moving to Hermes 2.0.

## Non-Goals

- Full end-to-end voice testing with LiveKit (out of scope; intent classifier tests are enough).
- Measuring narrative quality or tone of polished answers (manual report artifact only).
- Evaluating the rules engine itself (already covered by other tests).

## Architecture

```
backend/evals/
├── eval_data.py              # 50 cases + fixtures + paraphrase tables
├── conversational_eval.py      # runner: assertions over chat()
├── generate_report.py          # CLI to produce markdown report
└── __init__.py
backend/tests/
└── test_conversational_eval.py # pytest wrapper over eval runner
```

## Data Model

```python
class EvalCase(TypedDict):
    id: str
    query: str
    source: Literal["synthetic", "real-book"]
    expected_intent: str
    expected_citation_types: list[str]
    required_substrings: list[str]   # tokens that must survive LLM polish
    portfolio: dict | None           # None for real-book cases
    mandate: dict | None
    rules_result: dict | None
    client_id_for_real_book: str | None
    description: str
    paraphrases: list[str]           # voice/transcription variants
```

## Fixtures

### 30 Synthetic Cases

Five intent categories × six variations:

- `explain_breaches` — red portfolio, zero breaches, multi-breach, per-rule references.
- `explain_watches` — orange status, near-breach thresholds, empty watch list.
- `explain_rule` — named rule, asset class token matching, unknown rule fallback.
- `what_if_trade` — buy/sell Equity/Bonds, fails/succeeds, missing ticker.
- `explain_cash` / `summarize` — green/orange/red status, top holding, cash pct.

Each synthetic case uses deterministic portfolios with controlled holdings so assertions can be exact (e.g., `required_substrings` contains `"98%"`).

### 20 Real-Book Cases

Sample from the seeded 34k portfolios via `core.data_loader.get_portfolio`. For each selected `client_id`, the eval runner computes `effective_portfolio` and `rules_result` at runtime. Assertions are tolerant:

- `grounded == True`
- `len(citations) >= 1`
- `status` in answer matches `rules_result.status`
- `intent` matches expected.

This catches drift in the real book as market ticks without requiring hardcoded numbers.

## Hallucination Guard

For every case, compute `required_substrings` from the citations:

- Breach/watch `current` and `limit` values formatted as they appear in the agent's raw answer.
- Top holding ticker and weight for summaries.
- Cash percentage for cash queries.
- Trade ticker and units for what-if queries.

The test asserts each required substring is present in the final `ChatAnswer.answer`. This works whether MockLLM or Claude polish is active.

## Voice Paraphrases

Each synthetic case has 2–3 alternate phrasings. A separate parametrized test runs `_classify_intent` over all paraphrases and asserts the expected intent. This validates that LiveKit/browser STT noise does not derail routing.

## Test Runner

`backend/tests/test_conversational_eval.py` imports `EvalCase` list and runs:

```python
@pytest.mark.parametrize("case", ALL_EVAL_CASES)
def test_eval_case(case: EvalCase):
    answer = run_case(case)
    assert answer.intent == case["expected_intent"]
    assert all(t in answer.citations for t in case["expected_citation_types"])
    for token in case["required_substrings"]:
        assert token in answer.answer, f"Missing grounding token: {token}"
    assert answer.grounded is True
```

For real-book cases, `run_case` fetches `client_id` from SQLite. For synthetic cases it uses inline fixtures.

## Report Generator

`python -m evals.generate_report` produces `docs/conversational-eval-report.md` with:

- Pass/fail per case.
- Intent, citations, and final answer (polished if `ANTHROPIC_API_KEY` set).
- A manual-review section flagging any answer whose word count grew >2× after polish (a cheap hallucination/verbosity heuristic).

## Acceptance Criteria

- [x] 50 eval cases committed under `backend/evals/eval_data.py`.
- [x] Parametrized pytest runs in under 30 seconds.
- [x] All synthetic cases pass with exact substring assertions.
- [x] All real-book cases pass with tolerant assertions.
- [x] Paraphrase test passes for all synthetic voice variants.
- [x] Report generator produces a readable markdown artifact.
- [x] Sprint 5 implementation plan updated to mark eval set complete.

## Completion Note

- 150 total test parametrizations (30 synthetic + 120 real-book) pass in ~0.45s.
- One unrelated existing performance test (`test_tick_monitor_under_10s`) is slow on this machine (38.6s) and not part of this acceptance gate.

## Dependencies

- Existing `agents.conversational.chat` and `_classify_intent`.
- Existing `core.data_loader`, `core.effective`, `core.rules_engine` for real-book cases.
- `pytest` only for test wrapper.

## Risks

- Real-book values change when market ticks; real-case assertions must not assert exact numbers.
- LLM polish may rephrase numbers (e.g., "98 percent" instead of "98%"). `required_substrings` will include both variants for tolerance.
