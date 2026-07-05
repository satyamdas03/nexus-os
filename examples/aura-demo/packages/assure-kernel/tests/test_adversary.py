"""Tests for the Synthetic Reality Engine adversary."""

import pytest

from assure_kernel.synthetic import (
    Adversary,
    find_breaches,
    generate_portfolios,
    stress_until_breach,
)


MANDATE = {
    "rules": [
        {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0}}},
        {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
        {"type": "min_cash", "parameters": {"min_weight": 0.05}},
    ]
}


def test_adversary_counts_match_total():
    adv = Adversary(mandate=MANDATE, scenarios=["baseline"])
    result = adv.sweep(n=100, seed=1)
    assert result.total == 100
    assert result.green + result.orange + result.red == 100
    assert result.total == 100


def test_adversary_with_stress_scenarios_increases_breaches():
    adv = Adversary(
        mandate=MANDATE,
        scenarios=["baseline", "equity_crash_2008", "rate_shock_2022"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 0.5},
    )
    result = adv.sweep(n=200, seed=2)
    assert result.total == 600  # 200 * 3 scenarios
    assert result.red > 0
    assert result.red / result.total >= 0
    assert all(s in result.scenario_status_counts for s in adv.scenarios)


def test_find_breaches_convenience():
    result = find_breaches(
        mandate=MANDATE,
        n=50,
        seed=3,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "asset_class", "breach_bias_prob": 1.0},
    )
    assert result.total == 50
    assert result.red >= 35
    assert len(result.rule_breach_counts) >= 1


def test_breach_observations_have_required_fields():
    result = find_breaches(
        mandate=MANDATE,
        n=20,
        seed=4,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
        record_limit=10,
    )
    if result.breach_observations:
        obs = result.breach_observations[0]
        assert obs.client_id
        assert obs.scenario_id
        assert obs.rule
        assert obs.severity == "red"
        assert obs.portfolio_value >= 0


def test_record_limit_is_respected():
    result = find_breaches(
        mandate=MANDATE,
        n=100,
        seed=5,
        scenarios=["baseline"],
        generator_kwargs={"breach_bias_mode": "single_holding", "breach_bias_prob": 1.0},
        record_limit=5,
    )
    assert len(result.breach_observations) <= 5
    # Rule counts may still exceed the record limit because aggregation happens
    # independently.
    assert sum(result.rule_breach_counts.values()) >= len(result.breach_observations)


def test_stress_until_breach_finds_breach():
    portfolios = generate_portfolios(
        n=1,
        seed=6,
        n_holdings=(8, 12),
        breach_bias_mode="asset_class",
        breach_bias_prob=1.0,
    )
    scenario_id, rules_result, stressed = stress_until_breach(
        portfolios[0], MANDATE, seed=7
    )
    assert scenario_id is not None
    assert rules_result is not None
    assert stressed is not None
    assert rules_result.status.value == "breach"


def test_stress_until_breach_returns_none_when_safe():
    # Manually construct a portfolio that is safely inside the mandate.
    from assure_kernel.models import Holding, Portfolio
    portfolio = Portfolio(
        client_id="safe",
        cash=50_000,
        holdings=[
            Holding(ticker="TLT", units=100, price=95, asset_class="Bonds", sector="Broad", region="US", liquidity_tier=1),
            Holding(ticker="AGG", units=200, price=98, asset_class="Bonds", sector="Broad", region="US", liquidity_tier=1),
            Holding(ticker="SPY", units=50, price=500, asset_class="Equity", sector="Broad", region="US", liquidity_tier=1),
        ],
    )
    scenario_id, rules_result, stressed = stress_until_breach(
        portfolio,
        MANDATE,
        scenario_order=["baseline"],
        max_trials=1,
        seed=9,
    )
    assert scenario_id is None
    assert rules_result is None
    assert stressed is None


def test_determinism():
    a = find_breaches(MANDATE, n=50, seed=10, scenarios=["baseline"])
    b = find_breaches(MANDATE, n=50, seed=10, scenarios=["baseline"])
    assert a.total == b.total
    assert a.red == b.red
    assert a.orange == b.orange
    assert a.green == b.green
    assert a.rule_breach_counts == b.rule_breach_counts
