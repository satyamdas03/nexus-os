"""Build an adviser whiteboard payload for a single portfolio.

The payload is intentionally simple and deterministic: it exposes the current
rules-engine result, a set of proposed remediation trades, and the predicted
post-trade status. The LLM layer (adviser/chat) only ever reads this payload —
it cannot execute trades or override mandate rules.
"""
from __future__ import annotations

from typing import Any

from core.data_loader import get_portfolio
from core.effective import get_effective
from core.rules_engine import check
from agents.remediate import remediate


def build_whiteboard(client_id: str) -> dict[str, Any]:
    """Return a structured whiteboard for the adviser UI."""
    p = get_portfolio(client_id)
    if p is None:
        raise ValueError(f"portfolio not found: {client_id}")

    mandate = p["mandate"]
    eff = get_effective(client_id, seed=p)
    if eff is None:
        raise ValueError(f"effective portfolio unavailable: {client_id}")

    rr = check(eff, mandate)

    # Use the existing remediation agent for a concrete, deterministic fix.
    remediation = remediate(eff, rr, mandate=mandate)
    trades = remediation.get("trades", [])

    # Re-verify the proposed trades against the effective portfolio so the UI
    # can show the predicted post-trade status accurately.
    from core.trades import apply_trades
    post = apply_trades(eff, trades, price_lookup=lambda t: None)
    post_rr = check(post, mandate)

    total_value = sum(h.get("market_value", 0) for h in eff.get("holdings", [])) + eff.get("cash", 0)

    breaches_out: list[dict] = []
    for b in rr.get("breaches", []):
        breaches_out.append({
            "rule": b["rule"],
            "limit": b.get("limit"),
            "current": b.get("current"),
            "offending_holdings": b.get("offending_holdings", []),
            "explanation": b.get("plain", b.get("message", "")),
        })

    trades_out: list[dict] = []
    for t in trades:
        trades_out.append({
            "action": t["action"],
            "ticker": t["ticker"],
            "units": float(t["units"]),
            "value": float(t.get("value", 0)),
            "rationale": t.get("rationale", ""),
        })

    aum_impact = sum(abs(t["value"]) for t in trades_out)
    return {
        "client_id": client_id,
        "client_name": p.get("client_name", client_id),
        "current_status": rr["status"],
        "breaches": breaches_out,
        "proposed_trades": trades_out,
        "post_status": post_rr["status"],
        "impact": {
            "aum_impact_pct": round(aum_impact / total_value, 4) if total_value else 0,
            "trades_count": len(trades_out),
        },
    }
