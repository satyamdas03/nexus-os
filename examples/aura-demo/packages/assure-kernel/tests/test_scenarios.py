"""Tests for synthetic stress scenarios."""

import pytest

from assure_kernel import Portfolio
from assure_kernel.models import Holding
from assure_kernel.synthetic import (
    Scenario,
    ShockMap,
    generate_portfolios,
    get_scenario,
    list_scenarios,
    stress_portfolio,
)


def test_list_scenarios_returns_builtin_set():
    scenarios = list_scenarios()
    ids = {s["id"] for s in scenarios}
    expected = {
        "baseline",
        "equity_crash_2008",
        "rate_shock_2022",
        "crypto_winter",
        "inflation_spike",
        "tech_selloff",
        "em_contagion",
    }
    assert ids == expected
    assert all("name" in s and "severity" in s for s in scenarios)


def test_get_scenario_unknown_raises():
    with pytest.raises(KeyError):
        get_scenario("black_swan_xyz")


def test_baseline_leaves_portfolio_mostly_unchanged():
    portfolios = generate_portfolios(n=1, seed=1, n_holdings=(5, 5))
    original = portfolios[0]
    stressed = stress_portfolio(original, "baseline", seed=42)
    assert stressed.client_id == original.client_id
    assert len(stressed.holdings) == len(original.holdings)
    for h_before, h_after in zip(original.holdings, stressed.holdings):
        # Baseline noise is small, so prices should stay within ~5%.
        ratio = h_after.price / h_before.price
        assert 0.94 < ratio < 1.06


def test_equity_crash_reduces_equity_value():
    portfolio = Portfolio(
        client_id="stress-test",
        cash=10_000,
        holdings=[
            Holding(ticker="AAPL", units=100, price=180, asset_class="Equity", sector="Technology", region="US", liquidity_tier=1),
            Holding(ticker="TLT", units=50, price=95, asset_class="Bonds", sector="Broad", region="US", liquidity_tier=1),
        ],
    )
    stressed = stress_portfolio(portfolio, "equity_crash_2008", seed=1)
    aapl_before = portfolio.holdings[0].market_value
    aapl_after = stressed.holdings[0].market_value
    tlt_before = portfolio.holdings[1].market_value
    tlt_after = stressed.holdings[1].market_value
    assert aapl_after < aapl_before * 0.7  # equity crash
    assert tlt_after > tlt_before * 0.9  # bonds roughly preserved


def test_crypto_winter_hammers_crypto():
    portfolio = Portfolio(
        client_id="crypto-test",
        cash=10_000,
        holdings=[
            Holding(ticker="BTC", units=1, price=40_000, asset_class="Crypto", sector="Digital", region="US", liquidity_tier=3),
            Holding(ticker="AAPL", units=10, price=180, asset_class="Equity", sector="Technology", region="US", liquidity_tier=1),
        ],
    )
    stressed = stress_portfolio(portfolio, "crypto_winter", seed=2)
    btc_before = portfolio.holdings[0].market_value
    btc_after = stressed.holdings[0].market_value
    assert btc_after < btc_before * 0.35


def test_stress_is_immutable():
    portfolios = generate_portfolios(n=1, seed=3, n_holdings=(6, 6))
    original = portfolios[0]
    original_value = original.total_value
    stress_portfolio(original, "equity_crash_2008", seed=4)
    assert original.total_value == original_value
    # Ensure holdings were not mutated in place.
    assert all(h.market_value > 0 for h in original.holdings)


def test_custom_scenario_combines_shocks():
    scenario = Scenario(
        id="custom",
        name="Custom Test",
        description="Tech + EM double shock.",
        severity="severe",
        shocks=ShockMap(
            asset_class={"Equity": 0.90},
            sector={"Technology": 0.50},
            region={"EM": 0.50},
            default=1.0,
        ),
    )
    portfolio = Portfolio(
        client_id="custom-test",
        cash=0,
        holdings=[
            Holding(ticker="BABA", units=10, price=100, asset_class="Equity", sector="Technology", region="EM", liquidity_tier=2),
        ],
    )
    stressed = scenario.apply(portfolio, seed=1)
    # Combined multiplier = 0.90 * 0.50 * 0.50 = 0.225
    assert stressed.holdings[0].price < 100 * 0.30


def test_determinism_with_seed():
    portfolios = generate_portfolios(n=1, seed=5, n_holdings=(8, 8))
    a = stress_portfolio(portfolios[0], "rate_shock_2022", seed=123)
    b = stress_portfolio(portfolios[0], "rate_shock_2022", seed=123)
    assert a.total_value == b.total_value
    assert [h.price for h in a.holdings] == [h.price for h in b.holdings]


def test_different_seeds_produce_different_noise():
    portfolios = generate_portfolios(n=1, seed=6, n_holdings=(8, 8))
    a = stress_portfolio(portfolios[0], "inflation_spike", seed=1)
    b = stress_portfolio(portfolios[0], "inflation_spike", seed=2)
    assert [h.price for h in a.holdings] != [h.price for h in b.holdings]


def test_scenarios_change_total_value():
    portfolios = generate_portfolios(n=50, seed=7)
    for scenario_id in ["equity_crash_2008", "rate_shock_2022", "crypto_winter"]:
        deltas = []
        for p in portfolios:
            stressed = stress_portfolio(p, scenario_id, seed=10)
            deltas.append(stressed.total_value - p.total_value)
        # On average, severe scenarios should reduce portfolio value.
        assert sum(deltas) / len(deltas) < 0
