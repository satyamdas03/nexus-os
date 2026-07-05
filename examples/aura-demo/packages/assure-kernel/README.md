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

## Kernel-as-a-Service

The kernel can run as a standalone HTTP service with a stable, versioned API.

### Run locally

```bash
pip install -e ".[service]"
uvicorn assure_kernel.main:app --host 127.0.0.1 --port 8000
```

### Run in Docker

```bash
docker build -t assure-kernel:0.1.0 .
docker run -p 8000:8000 assure-kernel:0.1.0
# or via compose
docker compose up
```

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/health` | Service health + kernel version |
| POST | `/v1/evaluate` | Full rules check on a portfolio + mandate |
| POST | `/v1/verify` | What-if trade gate: post-trade verdict |
| POST | `/v1/explain` | Deterministic mandate documentation |
| POST | `/v1/evidence` | Regulator-reviewable evidence pack (JSON + optional HTML) |

### Example: evaluate a portfolio

```bash
curl -s -X POST http://127.0.0.1:8000/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio": {
      "cash": 10000,
      "holdings": [
        {"ticker": "SPY", "units": 10, "price": 500, "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1}
      ]
    },
    "mandate": {
      "rules": [
        {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Cash": 1.0}}},
        {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
        {"type": "min_cash", "parameters": {"min_weight": 0.05}}
      ]
    }
  }'
```

### Example: generate an evidence pack

```bash
curl -s -X POST http://127.0.0.1:8000/v1/evidence \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio": {
      "client_id": "C-001",
      "cash": 10000,
      "holdings": [
        {"ticker": "SPY", "units": 10, "price": 500, "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1}
      ]
    },
    "mandate": {
      "rules": [
        {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Cash": 1.0}}},
        {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
        {"type": "min_cash", "parameters": {"min_weight": 0.05}}
      ]
    },
    "client_name": "Jane Smith",
    "adviser": "A-742",
    "include_html": true
  }'
```

## Testing

```bash
pytest
pytest -m assurance --hypothesis-profile=ci
pytest tests/bench/test_perf.py
```
