# backend/tests/test_market_model.py
import math
from generators import market, universe


def test_day0_is_base_price():
    for t in universe.all_tickers()[:5]:
        assert market.price_for(t, 0, 42) == universe.UNIVERSE_BY_TICKER[t]["base_price"]


def test_determinism_same_args_identical():
    a = market.price_for("SPY", 10, 42)
    b = market.price_for("SPY", 10, 42)
    assert a == b


def test_determinism_different_seed_differs():
    a = market.price_for("SPY", 20, 42)
    b = market.price_for("SPY", 20, 99)
    assert a != b


def test_prices_positive_and_monotone_path():
    prev = market.price_for("QQQ", 0, 42)
    for d in range(1, 30):
        cur = market.price_for("QQQ", d, 42)
        assert cur > 0
        # path is a function of day; recomputing the prior day matches
        assert market.price_for("QQQ", d - 1, 42) == prev
        prev = cur


def test_prices_for_day_covers_all_tickers():
    ps = market.prices_for_day(5, 42)
    assert set(ps) == set(universe.all_tickers())
    assert ps["SPY"] == market.price_for("SPY", 5, 42)


def test_sector_correlation_stronger_than_cross_sector():
    """Same-sector tickers share a sector factor (rho=0.5) so their returns
    co-move more than cross-sector tickers over a long horizon."""
    def returns(t, seed, days):
        return [math.log(market.price_for(t, d, seed) / market.price_for(t, d - 1, seed))
                for d in range(1, days + 1)]

    def corr(xs, ys):
        n = len(xs)
        mx = sum(xs) / n; my = sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
        sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
        return cov / (sx * sy) if sx > 0 and sy > 0 else 0.0

    days = 200
    # XLK & XLF both US sector ETFs (Technology vs Financials -> different
    # sectors, so pick two same-sector): SPY & VTI both sector=Broad region=US.
    same = corr(returns("SPY", 7, days), returns("VTI", 7, days))
    cross = corr(returns("SPY", 7, days), returns("TLT", 7, days))  # Bonds/Govt
    assert same > cross
    assert same > 0.2  # shared sector factor shows up