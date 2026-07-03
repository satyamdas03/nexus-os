# backend/tests/test_universe.py
from generators import universe


def test_universe_has_about_35_tickers():
    assert 30 <= len(universe.UNIVERSE) <= 45


def test_every_ticker_has_required_fields():
    for u in universe.UNIVERSE:
        for k in ("ticker", "name", "asset_class", "sector", "region", "liquidity_tier", "base_price", "mu", "sigma"):
            assert k in u, f"{u.get('ticker')} missing {k}"
        assert 1 <= u["liquidity_tier"] <= 3
        assert u["base_price"] > 0
        assert u["mu"] is not None
        assert u["sigma"] > 0


def test_by_region_and_asset_class_consistent():
    us = universe.by_region("US")
    for t in us:
        assert universe.UNIVERSE_BY_TICKER[t]["region"] == "US"
    bonds = universe.by_asset_class("Bonds")
    for t in bonds:
        assert universe.UNIVERSE_BY_TICKER[t]["asset_class"] == "Bonds"


def test_all_asset_classes_and_regions_present():
    assert {"Equity", "Bonds", "Commodity", "Crypto", "Cash"} <= set(universe.ASSET_CLASSES)
    assert {"US", "ExUS", "EM"} <= set(universe.REGIONS)


def test_tickers_unique():
    tickers = [u["ticker"] for u in universe.UNIVERSE]
    assert len(tickers) == len(set(tickers))
