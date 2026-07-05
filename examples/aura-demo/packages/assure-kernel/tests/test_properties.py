"""Property-based tests for ASSURE kernel invariants."""

import hypothesis.strategies as st
from hypothesis import given, settings

from assure_kernel import evaluate_portfolio


def _portfolio_strategy():
    holding = st.fixed_dictionaries(
        {
            "ticker": st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
            "units": st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
            "price": st.floats(min_value=0, max_value=1e5, allow_nan=False, allow_infinity=False),
            "asset_class": st.sampled_from(["Equity", "FixedIncome", "Cash", "Alternative"]),
            "sector": st.sampled_from(["Technology", "Healthcare", "Finance", "Energy", "Broad"]),
            "region": st.sampled_from(["US", "DevelopedExUS", "Emerging Markets"]),
            "liquidity_tier": st.integers(min_value=1, max_value=3),
        },
    )
    return st.fixed_dictionaries(
        {
            "cash": st.floats(min_value=0, max_value=1e8, allow_nan=False, allow_infinity=False),
            "holdings": st.lists(holding, min_size=0, max_size=50),
        }
    )


def _mandate_strategy():
    return st.fixed_dictionaries(
        {
            "max_asset_class_weight": st.dictionaries(
                st.sampled_from(["Equity", "FixedIncome", "Cash", "Alternative"]),
                st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
            ),
            "max_single_holding": st.one_of(
                st.just(None),
                st.floats(min_value=0.05, max_value=1.0, allow_nan=False, allow_infinity=False),
            ),
            "min_cash": st.one_of(
                st.just(None),
                st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
            ),
        }
    )


@given(_portfolio_strategy(), _mandate_strategy())
@settings(max_examples=200, deadline=None)
def test_status_rollup_invariant(portfolio, mandate):
    """The returned status is always consistent with breaches and watches."""
    result = evaluate_portfolio(portfolio, mandate)
    has_breach = bool(result.breaches)
    has_watch = bool(result.watches)
    if has_breach:
        assert result.status.value == "breach"
    elif has_watch:
        assert result.status.value == "watch"
    else:
        assert result.status.value == "ok"


@given(_portfolio_strategy())
@settings(max_examples=100, deadline=None)
def test_total_value_invariant(portfolio):
    """total_value equals cash + sum of holding market values."""
    from assure_kernel.models import Portfolio

    p = Portfolio(**portfolio)
    computed = sum((h.market_value or 0.0) for h in p.holdings) + p.cash
    assert abs(p.total_value - computed) < 1e-6


@given(_portfolio_strategy(), _mandate_strategy())
@settings(max_examples=200, deadline=None)
def test_evaluate_is_deterministic(portfolio, mandate):
    """Same inputs produce the same status."""
    result1 = evaluate_portfolio(portfolio, mandate)
    result2 = evaluate_portfolio(portfolio, mandate)
    assert result1.status == result2.status
    assert len(result1.breaches) == len(result2.breaches)
    assert len(result1.watches) == len(result2.watches)
