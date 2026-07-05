"""Parity tests between assure-kernel and the original aura-demo rules_engine."""

import pytest

from assure_kernel import evaluate_portfolio
from assure_kernel.models import Portfolio


def _build_portfolio_dict():
    """A fully compliant portfolio used as the baseline for parity tests."""
    return {
        "client_id": "C-001",
        "cash": 12_500,
        "holdings": [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "asset_class": "Equity",
                "sector": "Technology",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 100.0,
                "market_value": 10_000.0,
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft Corp.",
                "asset_class": "Equity",
                "sector": "Technology",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 100.0,
                "market_value": 10_000.0,
            },
            {
                "ticker": "JNJ",
                "name": "Johnson & Johnson",
                "asset_class": "Equity",
                "sector": "Healthcare",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 100.0,
                "market_value": 10_000.0,
            },
            {
                "ticker": "VOO",
                "name": "Vanguard S&P 500 ETF",
                "asset_class": "Equity",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 100.0,
                "market_value": 10_000.0,
            },
            {
                "ticker": "XLV",
                "name": "Health Care Select Sector SPDR",
                "asset_class": "Equity",
                "sector": "Healthcare",
                "region": "US",
                "liquidity_tier": 1,
                "units": 50,
                "price": 100.0,
                "market_value": 5_000.0,
            },
            {
                "ticker": "BND",
                "name": "Vanguard Total Bond",
                "asset_class": "FixedIncome",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 100.0,
                "market_value": 10_000.0,
            },
            {
                "ticker": "IEF",
                "name": "iShares 7-10 Year Treasury",
                "asset_class": "FixedIncome",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 100.0,
                "market_value": 10_000.0,
            },
            {
                "ticker": "EEM",
                "name": "iShares Emerging Markets",
                "asset_class": "Equity",
                "sector": "Broad",
                "region": "Emerging Markets",
                "liquidity_tier": 2,
                "units": 25,
                "price": 100.0,
                "market_value": 2_500.0,
            },
        ],
    }


def _build_mandate_dict():
    return {
        "max_asset_class_weight": {"Equity": 0.60, "FixedIncome": 0.50},
        "max_sector_weight": {"Technology": 0.25},
        "approved_universe": ["AAPL", "MSFT", "BND", "EEM", "VOO", "JNJ", "XLV", "IEF"],
        "max_single_holding": 0.15,
        "min_cash": 0.05,
        "target_allocation": {"Equity": 0.55, "FixedIncome": 0.40},
        "drift_tolerance": 0.05,
        "max_region_weight": {"Emerging Markets": 0.15, "US": 0.90},
        "excluded_tickers": ["TSLA"],
        "max_top_n_concentration": {"n": 3, "limit": 0.50},
        "min_liquid_pct": 0.80,
    }


def test_kernel_status_against_original_engine():
    core = pytest.importorskip("core.rules_engine")
    portfolio = _build_portfolio_dict()
    mandate = _build_mandate_dict()

    legacy = core.check(portfolio, mandate)
    kernel = evaluate_portfolio(portfolio, mandate)

    status_map = {"ok": "green", "watch": "orange", "breach": "red"}
    assert status_map[kernel.status.value] == legacy["status"]

    assert len(kernel.breaches) == len(legacy["breaches"])
    assert len(kernel.watches) == len(legacy["watches"])
    assert len(kernel.per_rule) == len(legacy["per_rule"])


@pytest.mark.parametrize(
    "ticker,asset_class,sector,units,price,expected_status",
    [
        # Approved universe breach: unknown ticker
        ("UNKNOWN", "Equity", "Technology", 100, 100.0, "breach"),
        # ESG exclusion breach
        ("TSLA", "Equity", "Technology", 1000, 200.0, "breach"),
        # Sector breach
        ("AAPL", "Equity", "Technology", 1000, 500.0, "breach"),
        # Aligned
        ("VOO", "Equity", "Broad", 1, 400.0, "ok"),
    ],
)
def test_individual_rule_triggers(ticker, asset_class, sector, units, price, expected_status):
    portfolio = _build_portfolio_dict()
    portfolio["holdings"].append(
        {
            "ticker": ticker,
            "asset_class": asset_class,
            "sector": sector,
            "region": "US",
            "liquidity_tier": 1,
            "units": units,
            "price": price,
        }
    )
    mandate = _build_mandate_dict()
    result = evaluate_portfolio(portfolio, mandate)
    assert result.status.value == expected_status


def test_empty_portfolio_passes_min_cash():
    result = evaluate_portfolio(
        {"cash": 100_000, "holdings": []},
        {"min_cash": 0.05},
    )
    assert result.status.value == "ok"


def test_portfolio_model_input():
    portfolio = Portfolio(
        client_id="C-002",
        cash=100_000,
        holdings=[],
    )
    result = evaluate_portfolio(portfolio, {"min_cash": 0.05})
    assert result.status.value == "ok"
