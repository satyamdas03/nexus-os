"""Business logic layer for the Kernel-as-a-Service API.

This module wraps the deterministic engine in thin, validated operations.
It performs no I/O and no state mutation — the same inputs always produce
the same outputs, which is the trust anchor of the entire ASSURE system.
"""
from __future__ import annotations

from assure_kernel import evaluate_portfolio, describe_mandate, parse_mandate
from assure_kernel.engine import _portfolio_from_dict
from assure_kernel.models import Portfolio


def check_portfolio(portfolio: dict, mandate: dict) -> dict:
    """Evaluate a portfolio against a mandate and return a deterministic result.

    Accepts both legacy aura-demo dicts and the new declarative DSL dict.
    """
    mandate_model = parse_mandate(mandate)
    return evaluate_portfolio(portfolio, mandate_model)


def verify_trades(portfolio: dict, mandate: dict, trades: list[dict]) -> dict:
    """Apply a list of proposed trades to the portfolio and re-evaluate.

    This is the pre-trade gate: it shows the post-trade verdict without ever
    mutating persisted state. A trade is {"ticker": str, "action": "buy"|"sell",
    "units": float}. Buy trades add units at the portfolio's current price for
    that ticker; sell trades subtract units (floor at zero).
    """
    pf = _portfolio_from_dict(portfolio)
    prices = {h.ticker: h.price for h in pf.holdings}
    by_ticker: dict[str, float] = {}
    for h in pf.holdings:
        by_ticker[h.ticker] = by_ticker.get(h.ticker, 0.0) + h.units

    cash_delta = 0.0
    for t in trades:
        tk = t["ticker"]
        units = float(t.get("units", 0.0))
        price = prices.get(tk, 0.0)
        if t.get("action") == "buy":
            by_ticker[tk] = by_ticker.get(tk, 0.0) + units
            cash_delta -= units * price
        elif t.get("action") == "sell":
            by_ticker[tk] = max(0.0, by_ticker.get(tk, 0.0) - units)
            cash_delta += units * price

    # Rebuild holdings from the post-trade units, preserving classification metadata.
    new_holdings: list[dict] = []
    for tk, units in by_ticker.items():
        if units <= 1e-9:
            continue
        h = next((_h for _h in pf.holdings if _h.ticker == tk), None)
        if h is None:
            continue
        new_holdings.append({
            "ticker": tk,
            "units": units,
            "price": prices.get(tk, 0.0),
            "asset_class": h.asset_class,
            "sector": h.sector,
            "region": h.region,
            "liquidity_tier": h.liquidity_tier,
        })

    post = Portfolio(
        client_id=pf.client_id,
        client_name=pf.client_name,
        adviser=pf.adviser,
        cash=max(0.0, pf.cash + cash_delta),
        holdings=new_holdings,
        fum=pf.fum,
    )
    mandate_model = parse_mandate(mandate)
    return evaluate_portfolio(post, mandate_model)


def explain_mandate(mandate: dict) -> dict:
    """Return deterministic, structured documentation for a mandate.

    No LLM is involved; every description is derived from the rule parameters
    via the static registry in docs.py. This makes the output suitable for
    regulator review and evidence packs.
    """
    parsed = parse_mandate(mandate)
    return describe_mandate(parsed)
