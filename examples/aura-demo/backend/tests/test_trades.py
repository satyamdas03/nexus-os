from core.trades import apply_trades
from generators import universe

PORT = {
    "client_id": "c1", "client_name": "Acme", "adviser": "Pat", "fum": 1_000_000,
    "holdings": [
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad",
         "region": "US", "liquidity_tier": 1, "units": 100, "price": 500, "market_value": 50000},
    ],
    "cash": 20000,
}


def test_buy_new_ticker_carries_region_and_liquidity_tier():
    p = apply_trades(PORT, [{"ticker": "VWO", "action": "buy", "units": 100}])
    h = next(x for x in p["holdings"] if x["ticker"] == "VWO")
    assert h["region"] == universe.UNIVERSE_BY_TICKER["VWO"]["region"]
    assert h["liquidity_tier"] == universe.UNIVERSE_BY_TICKER["VWO"]["liquidity_tier"]
    assert h["asset_class"] == "Equity"
    assert h["price"] == universe.UNIVERSE_BY_TICKER["VWO"]["base_price"]


def test_price_lookup_overrides_universe_base_price():
    p = apply_trades(PORT, [{"ticker": "VWO", "action": "buy", "units": 100}],
                     price_lookup=lambda t: 99.0 if t == "VWO" else None)
    h = next(x for x in p["holdings"] if x["ticker"] == "VWO")
    assert h["price"] == 99.0
    assert h["market_value"] == 99.0 * 100


def test_sell_then_buy_preserves_held_price_region():
    p = apply_trades(PORT, [{"ticker": "SPY", "action": "sell", "units": 100}])
    assert all(h["ticker"] != "SPY" for h in p["holdings"])
    p = apply_trades(p, [{"ticker": "SPY", "action": "buy", "units": 50}])
    h = next(x for x in p["holdings"] if x["ticker"] == "SPY")
    # not held after sell -> falls back to universe base price
    assert h["price"] == universe.UNIVERSE_BY_TICKER["SPY"]["base_price"]
    assert h["region"] == "US"


def test_unknown_ticker_buy_skipped():
    p = apply_trades(PORT, [{"ticker": "ZZZ", "action": "buy", "units": 100}])
    assert all(h["ticker"] != "ZZZ" for h in p["holdings"])