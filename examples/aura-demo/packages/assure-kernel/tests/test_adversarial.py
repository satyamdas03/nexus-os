"""Adversarial and edge-case tests for the ASSURE kernel."""

import pytest

from assure_kernel import evaluate_portfolio
from assure_kernel.models import Portfolio


@pytest.mark.parametrize("cash", [0.0, 1e-9, -10_000.0])
def test_zero_and_negative_total_value(cash):
    """Engine should not crash when total value is zero or negative."""
    portfolio = {
        "cash": cash,
        "holdings": [],
    }
    result = evaluate_portfolio(portfolio, {"min_cash": 0.05})
    assert result.status.value in {"ok", "breach"}


def test_duplicate_ticker_split_across_holdings():
    """Same ticker split across multiple holdings should aggregate weights."""
    portfolio = {
        "cash": 0,
        "holdings": [
            {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 100.0},
            {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 100.0},
        ],
    }
    result = evaluate_portfolio(portfolio, {"max_single_holding": 0.51})
    # Two equal holdings of AAPL = 100% weight, breach.
    assert result.status.value == "breach"


def test_precision_breach_at_boundary():
    """A weight just above the limit must breach; equal must not."""
    portfolio = {
        "cash": 1_000,
        "holdings": [
            {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 100.00001},
        ],
    }
    # total = 11,000.0001; AAPL weight = 10,000.0001 / 11,000.0001 ≈ 0.90909
    result = evaluate_portfolio(portfolio, {"max_single_holding": 0.90908})
    assert result.status.value == "breach"

    result2 = evaluate_portfolio(portfolio, {"max_single_holding": 0.90909})
    # With 1e-9 EPS, 0.90909... should still breach if strictly above.
    assert result2.status.value == "breach"


def test_conflicting_sector_bounds():
    """A sector can be capped below total asset class."""
    portfolio = {
        "cash": 0,
        "holdings": [
            {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 100.0},
        ],
    }
    result = evaluate_portfolio(
        portfolio,
        {
            "max_asset_class_weight": {"Equity": 1.0},
            "max_sector_weight": {"Technology": 0.05},
        },
    )
    assert result.status.value == "breach"


def test_exclusion_with_existing_position():
    """Holding an excluded ticker is a breach even if all other rules pass."""
    portfolio = {
        "cash": 100_000,
        "holdings": [
            {"ticker": "WEAP", "asset_class": "Equity", "sector": "Defense", "units": 1, "price": 1.0},
        ],
    }
    result = evaluate_portfolio(portfolio, {"excluded_tickers": ["WEAP"]})
    assert result.status.value == "breach"


def test_illiquid_concentration():
    """Low liquidity tier combined with high concentration."""
    portfolio = {
        "cash": 10_000,
        "holdings": [
            {"ticker": "ILLIQ", "asset_class": "Equity", "sector": "Small", "liquidity_tier": 3, "units": 1000, "price": 90.0},
        ],
    }
    result = evaluate_portfolio(portfolio, {"min_liquid_pct": 0.80})
    assert result.status.value == "breach"


def test_boundary_turnover_sell_to_compliance():
    """A portfolio exactly on a boundary passes; just above fails."""
    portfolio = {
        "cash": 0,
        "holdings": [
            {"ticker": "A", "asset_class": "Equity", "sector": "Tech", "units": 60, "price": 1.0},
            {"ticker": "B", "asset_class": "FixedIncome", "sector": "Bond", "units": 40, "price": 1.0},
        ],
    }
    # Equity exactly 60% of 100 total.
    result = evaluate_portfolio(portfolio, {"max_asset_class_weight": {"Equity": 0.60}})
    assert result.status.value == "ok"

    # Equity just over 60%.
    portfolio["holdings"][0]["units"] = 61
    result = evaluate_portfolio(portfolio, {"max_asset_class_weight": {"Equity": 0.60}})
    assert result.status.value == "breach"


def test_zero_price_nonzero_units():
    """Zero price with nonzero units produces zero market value."""
    portfolio = {
        "cash": 100,
        "holdings": [
            {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 0.0},
        ],
    }
    result = evaluate_portfolio(portfolio, {"min_cash": 0.0})
    assert result.status.value == "ok"
    assert result.per_rule[0].current == 1.0  # all value is cash


def test_mandate_with_unsupported_rule_is_ignored():
    """Forward-compatible: unknown future rule types are ignored, not crashed."""
    from assure_kernel.models import Mandate, Rule

    portfolio = Portfolio(cash=100, holdings=[])
    mandate = Mandate(
        rules=[Rule(type="future_magic_rule", params={"limit": 0.5})]
    )
    result = evaluate_portfolio(portfolio, mandate)
    assert result.status.value == "ok"
    assert result.per_rule == []
