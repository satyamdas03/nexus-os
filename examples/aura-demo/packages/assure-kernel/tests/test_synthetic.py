"""Tests for the Synthetic Reality Engine portfolio generator."""

from assure_kernel import evaluate_portfolio
from assure_kernel.dsl import parse_mandate
from assure_kernel.synthetic import PortfolioGenerator, generate_portfolios


SAMPLE_MANDATE = {
    "rules": [
        {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0}}},
        {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
        {"type": "min_cash", "parameters": {"min_weight": 0.05}},
    ]
}


def test_generate_portfolios_count():
    portfolios = generate_portfolios(n=100, seed=123)
    assert len(portfolios) == 100
    for p in portfolios:
        assert p.total_value > 0
        assert 5 <= len(p.holdings) <= 15


def test_determinism():
    a = generate_portfolios(n=10, seed=7)
    b = generate_portfolios(n=10, seed=7)
    assert [p.client_id for p in a] == [p.client_id for p in b]
    assert [p.total_value for p in a] == [p.total_value for p in b]
    assert [[h.ticker for h in p.holdings] for p in a] == [
        [h.ticker for h in p.holdings] for p in b
    ]


def test_cash_ratio_range():
    portfolios = generate_portfolios(n=50, seed=42, cash_ratio=(0.08, 0.12))
    for p in portfolios:
        cash_ratio = p.cash / p.total_value
        assert 0.07 <= cash_ratio <= 0.13  # allow small rounding tolerance


def test_holdings_have_market_value():
    portfolios = generate_portfolios(n=10, seed=1)
    for p in portfolios:
        for h in p.holdings:
            assert h.market_value is not None
            assert h.market_value >= 0


def test_breach_bias_single_holding_produces_breaches():
    gen = PortfolioGenerator(
        seed=99,
        n_holdings=(3, 8),
        breach_bias_mode="single_holding",
        breach_bias_prob=1.0,
    )
    portfolios = gen.generate(50)
    parsed_mandate = parse_mandate(SAMPLE_MANDATE)
    breach_count = 0
    for p in portfolios:
        result = evaluate_portfolio(p, parsed_mandate)
        if result.status.value == "breach":
            breach_count += 1
    # The bias is designed to create breaches; expect a strong majority.
    assert breach_count >= 35


def test_breach_bias_asset_class_produces_breaches():
    gen = PortfolioGenerator(
        seed=101,
        n_holdings=(5, 12),
        breach_bias_mode="asset_class",
        breach_bias_prob=1.0,
        asset_class_bias={"Equity": 3.0},
    )
    portfolios = gen.generate(50)
    parsed_mandate = parse_mandate(SAMPLE_MANDATE)
    breach_count = sum(
        1
        for p in portfolios
        if evaluate_portfolio(p, parsed_mandate).status.value == "breach"
    )
    assert breach_count >= 35


def test_custom_total_value_distribution():
    gen = PortfolioGenerator(
        seed=202,
        total_value_mean=500_000.0,
        total_value_std=50_000.0,
    )
    portfolios = gen.generate(100)
    values = [p.total_value for p in portfolios]
    mean = sum(values) / len(values)
    assert 450_000 <= mean <= 550_000


def test_portfolio_client_ids_are_unique():
    portfolios = generate_portfolios(n=1_000, seed=13, client_id_prefix="TST")
    ids = [p.client_id for p in portfolios]
    assert len(set(ids)) == len(ids)
    assert all(cid.startswith("TST-") for cid in ids)
