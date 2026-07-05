"""Proactive drift prediction for Hermes 2.0.

Uses the deterministic GBM price model to revalue a portfolio at a future day,
then runs the rules engine against the projected book. This lets Hermes propose
preventive trades *before* a breach actually happens.

All projections are deterministic given (ticker, day, seed). No actual market
data is mutated; callers can simulate many horizons cheaply.
"""
from __future__ import annotations

from typing import Optional

from core import data_loader, market
from core.rules_engine import check as rules_check
from core.trades import apply_trades
from generators import market as MK


def _clock_day_and_seed() -> tuple[int, int]:
    c = market.get_clock()
    return int(c["day"]), int(c.get("seed", 42))


def project_prices(horizon_days: int, seed: Optional[int] = None,
                   base_day: Optional[int] = None) -> dict[str, float]:
    """Return projected prices for all tickers at base_day + horizon_days.

    If seed/base_day are omitted, the current market clock is used.
    """
    if base_day is None or seed is None:
        base_day, seed = _clock_day_and_seed()
    day = base_day + max(0, int(horizon_days))
    return MK.prices_for_day(day, seed)


def project_portfolio(portfolio: dict,
                      horizon_days: int = 14,
                      seed: Optional[int] = None,
                      base_day: Optional[int] = None,
                      prices: Optional[dict[str, float]] = None) -> dict:
    """Return a revalued portfolio copy as of base_day + horizon_days.

    Cash is unchanged (no trades assumed). Holding market_value is recomputed
    from units * projected price."""
    if prices is None:
        prices = project_prices(horizon_days, seed=seed, base_day=base_day)
    p = {
        **portfolio,
        "holdings": [
            {
                **h,
                "price": prices.get(h["ticker"], h["price"]),
                "market_value": round(h["units"] * prices.get(h["ticker"], h["price"]), 2),
            }
            for h in portfolio.get("holdings", [])
        ],
    }
    return p


def predict_breaches(portfolio: dict,
                     mandate: dict,
                     horizon_days: int = 14,
                     seed: Optional[int] = None,
                     base_day: Optional[int] = None,
                     prices: Optional[dict[str, float]] = None) -> dict:
    """Run the rules engine on the projected portfolio.

    Returns a rules result dict augmented with `_meta` containing horizon,
    base_day, and a risk score (0-1)."""
    projected = project_portfolio(portfolio, horizon_days, seed=seed,
                                  base_day=base_day, prices=prices)
    rr = rules_check(projected, mandate)
    rr["_meta"] = {
        "horizon_days": horizon_days,
        "base_day": base_day if base_day is not None else _clock_day_and_seed()[0],
        "projected_day": (base_day if base_day is not None else _clock_day_and_seed()[0]) + horizon_days,
        "risk_score": _risk_score(rr, horizon_days),
    }
    return rr


def _risk_score(rr: dict, horizon_days: int) -> float:
    """0 = green and stable; 1 = red right now. Watches score by closeness."""
    if rr.get("breaches"):
        return 1.0
    watches = rr.get("watches", [])
    if not watches:
        return 0.0
    # Score rises as current approaches limit, faster for short horizons.
    worst = 0.0
    for w in watches:
        current = float(w.get("current", 0))
        limit = float(w.get("limit", 1))
        if limit <= 0:
            continue
        excess = max(0.0, current - limit) / limit
        worst = max(worst, excess)
    # Normalize: a 5% projected excess at 30 days is less urgent than at 5 days.
    horizon_factor = min(1.0, 14.0 / max(1, horizon_days))
    return min(1.0, worst * 5.0 * horizon_factor)


def suggest_preventive_trades(portfolio: dict,
                              mandate: dict,
                              strategy: dict,
                              horizon_days: int = 14,
                              seed: Optional[int] = None,
                              base_day: Optional[int] = None,
                              prices: Optional[dict[str, float]] = None) -> dict:
    """Propose trades now that lower projected breach risk.

    Strategy:
      1. Project portfolio to horizon and check for breaches/watches.
      2. If the projection is green, nothing to do.
      3. If not, run Hermes proposer against the *projected* rules result.
      4. Gate: apply those trades to the CURRENT portfolio and re-check both
         the current state (must stay green) and the projected state (must
         improve vs the unhedged projection).

    Returns {trades, rationale, projected_unhedged, projected_hedged,
             current_after_hedge, risk_before, risk_after, gated}.
    """
    from agents.hermes.proposer import propose

    projected = project_portfolio(portfolio, horizon_days, seed=seed,
                                  base_day=base_day, prices=prices)
    projected_rr = rules_check(projected, mandate)
    if projected_rr["status"] == "green":
        return {
            "trades": [],
            "rationale": f"no predicted breach within {horizon_days} days",
            "projected_unhedged": projected_rr,
            "projected_hedged": projected_rr,
            "current_after_hedge": portfolio,
            "risk_before": 0.0,
            "risk_after": 0.0,
            "gated": True,
        }

    proposal = propose(projected, projected_rr, strategy)
    trades = proposal.get("trades", [])
    if not trades:
        return {
            "trades": [],
            "rationale": f"predicted {projected_rr['status']} in {horizon_days}d but no preventive trade found",
            "projected_unhedged": projected_rr,
            "projected_hedged": projected_rr,
            "current_after_hedge": portfolio,
            "risk_before": _risk_score(projected_rr, horizon_days),
            "risk_after": _risk_score(projected_rr, horizon_days),
            "gated": False,
        }

    # Gate 1: current portfolio must stay green after applying preventive trades.
    current_after = apply_trades(portfolio, trades, price_lookup=lambda t: data_loader.current_prices().get(t))
    current_rr = rules_check(current_after, mandate)
    if current_rr["status"] != "green":
        return {
            "trades": [],
            "rationale": f"preventive trades would make current portfolio {current_rr['status']}; dropped",
            "projected_unhedged": projected_rr,
            "projected_hedged": projected_rr,
            "current_after_hedge": current_after,
            "risk_before": _risk_score(projected_rr, horizon_days),
            "risk_after": _risk_score(projected_rr, horizon_days),
            "gated": False,
        }

    # Gate 2: projected portfolio with trades must improve risk.
    projected_after = apply_trades(
        projected, trades,
        price_lookup=lambda t: project_prices(horizon_days, seed=seed, base_day=base_day).get(t),
    )
    projected_after_rr = rules_check(projected_after, mandate)
    risk_before = _risk_score(projected_rr, horizon_days)
    risk_after = _risk_score(projected_after_rr, horizon_days)
    if risk_after >= risk_before:
        return {
            "trades": [],
            "rationale": f"preventive trades do not lower projected risk ({risk_before:.2f} -> {risk_after:.2f}); dropped",
            "projected_unhedged": projected_rr,
            "projected_hedged": projected_after_rr,
            "current_after_hedge": current_after,
            "risk_before": risk_before,
            "risk_after": risk_after,
            "gated": False,
        }

    return {
        "trades": trades,
        "rationale": f"prevent {projected_rr['status']} at {horizon_days}d horizon: " + proposal.get("rationale", "rebalance"),
        "projected_unhedged": projected_rr,
        "projected_hedged": projected_after_rr,
        "current_after_hedge": current_after,
        "risk_before": risk_before,
        "risk_after": risk_after,
        "gated": True,
    }
