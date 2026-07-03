"""Pure trade-application primitives shared by the remediation agent and the
shadow-state layer. Deterministic, no I/O.

Keeping this in `core/` (not `agents/`) means the rules engine and the
effective-portfolio layer can simulate trades without depending on any agent.

34k update: ticker metadata (name, asset_class, sector, region,
liquidity_tier, base_price) comes from generators/universe.py. New holdings
carry region + liquidity_tier so the geography / liquidity rules evaluate
correctly after a remediation. An optional price_lookup lets the live-market
layer inject current prices for buys of new tickers.
"""
import copy
from typing import Callable, Optional

from generators import universe as _U

UNIVERSE_LOOKUP = _U.UNIVERSE  # back-compat alias for any legacy imports
UNIVERSE = _U.UNIVERSE_BY_TICKER


def apply_trades(
    portfolio: dict,
    trades: list[dict],
    price_lookup: Optional[Callable[[str], Optional[float]]] = None,
) -> dict:
    """Return a NEW portfolio with trades applied (units + cash recomputed).

    Sells use the held holding's price. Buys of held tickers reuse the held
    price; buys of new tickers use price_lookup(ticker) if provided, else the
    universe base_price. Unknown tickers on a buy with no metadata are skipped.
    New holdings carry region + liquidity_tier from the universe metadata.
    """
    p = copy.deepcopy(portfolio)
    by_ticker = {h["ticker"]: h for h in p["holdings"]}
    for t in trades:
        tk = t.get("ticker")
        act = t.get("action")
        units = float(t.get("units", 0))
        price = next((h["price"] for h in p["holdings"] if h["ticker"] == tk), None)
        if price is None and act == "buy":
            if price_lookup is not None:
                price = price_lookup(tk)
            if price is None:
                meta = UNIVERSE.get(tk)
                price = meta["base_price"] if meta else None
        if price is None:
            continue
        if act == "sell" and tk in by_ticker:
            h = by_ticker[tk]
            h["units"] = max(0, h["units"] - units)
            h["market_value"] = round(h["units"] * h["price"], 2)
            p["cash"] = round(p["cash"] + units * h["price"], 2)
            if h["units"] <= 1e-6:
                p["holdings"] = [x for x in p["holdings"] if x["ticker"] != tk]
                by_ticker.pop(tk, None)
        elif act == "buy":
            mv = round(units * price, 2)
            if tk in by_ticker:
                by_ticker[tk]["units"] += units
                by_ticker[tk]["market_value"] = round(by_ticker[tk]["units"] * price, 2)
            else:
                meta = UNIVERSE.get(tk, {})
                h = {
                    "ticker": tk,
                    "name": meta.get("name", tk),
                    "asset_class": meta.get("asset_class", "Equity"),
                    "sector": meta.get("sector", "Broad"),
                    "region": meta.get("region", "US"),
                    "liquidity_tier": meta.get("liquidity_tier", 1),
                    "units": units,
                    "price": price,
                    "market_value": mv,
                }
                p["holdings"].append(h)
                by_ticker[tk] = h
            p["cash"] = max(0, round(p["cash"] - mv, 2))
    return p