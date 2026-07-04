# assure-kernel

Deterministic portfolio assurance engine — the verified core of ASSURE.

The kernel is a pure-function library: it receives a `Portfolio` and a `Mandate` and returns a `RulesResult`. It performs no I/O, makes no network calls, and contains no LLM logic. AI agents may propose; the kernel verifies.

## Install

```bash
pip install -e .
# or with dev dependencies
pip install -e ".[dev]"
```

## Quick start

```python
from assure_kernel import evaluate_portfolio, Portfolio, Holding, Mandate, Rule

portfolio = Portfolio(
    client_id="C-001",
    cash=10_000,
    holdings=[
        Holding(ticker="AAPL", units=50, price=180.0, asset_class="Equity", sector="Technology"),
    ],
)

mandate = Mandate(
    id="moderate-growth",
    rules=[
        Rule(type="max_asset_class_weight", params={"asset_class": "Equity", "limit": 0.60}),
        Rule(type="max_single_holding", params={"limit": 0.10}),
    ],
)

result = evaluate_portfolio(portfolio, mandate)
print(result.status)        # "ok" | "watch" | "breach"
print(result.breaches)      # list of deterministic violations
print(result.per_rule)      # every rule check with current/limit/pass
```

## Design principles

1. **Determinism first.** The same portfolio + mandate always produces the same result.
2. **No I/O.** The kernel never reads files, databases, or environment variables.
3. **Extensible rules.** New rule types register through the rule registry.
4. **Backward compatible.** Legacy aura-demo dicts are translated into kernel models.

## Testing

```bash
pytest
pytest -m assurance --hypothesis-profile=ci
pytest tests/bench/test_perf.py
```
