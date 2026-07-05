"""Conversational Assurance agent for ASSURE.

Takes a natural-language question, a portfolio, a mandate, and the deterministic
rules-engine result, then returns a grounded answer. The agent classifies the
user's intent, routes to the right facts, and always cites the specific
rules-engine rows it used.

Safety invariant: the agent may only describe breaches, watches, and per_rule
facts the engine produced. It never invents numbers or rules.
"""

import json
import re
from dataclasses import dataclass

from agents.explain import explain
from agents.llm import LLMProvider, get_llm


@dataclass
class ChatAnswer:
    """A grounded conversational answer."""

    intent: str
    answer: str
    citations: list[dict]
    suggested_followups: list[str]
    grounded: bool = True


def _classify_intent(query: str) -> str:
    """Fast rule-based intent classifier."""
    q = query.lower()
    if any(w in q for w in ("why", "breach", "red", "flag", "violation")):
        return "explain_breaches"
    if any(w in q for w in ("watch", "orange", "attention", "drift")):
        return "explain_watches"
    if any(w in q for w in ("rule", "limit", "cap", "check")):
        return "explain_rule"
    if any(w in q for w in ("sell", "buy", "trade", "what if", "whatif", "if i")):
        return "what_if_trade"
    if any(w in q for w in ("status", "how is", "summary", "overview", "tell me about")):
        return "summarize"
    if any(w in q for w in ("cash", "liquid", "money")):
        return "explain_cash"
    return "summarize"


def _extract_rule_mentions(query: str, per_rule: list[dict]) -> list[dict]:
    """Find per_rule rows that the user likely asked about."""
    q = query.lower()
    mentions = []
    for row in per_rule:
        rule = row.get("rule", "")
        if rule.lower() in q:
            mentions.append(row)
            continue
        # Match asset class or sector tokens in the rule name.
        parts = rule.replace(":", " ").replace("_", " ").lower().split()
        if any(p in q for p in parts if len(p) > 2):
            mentions.append(row)
    return mentions


def _explain_breaches(rules_result: dict) -> tuple[str, list[dict]]:
    """Grounded answer for why the portfolio is red."""
    breaches = rules_result.get("breaches", [])
    if not breaches:
        return "The deterministic rules engine found no breaches. The portfolio is aligned with its mandate.", []
    lines = [f"{i + 1}. {b.get('plain', b['rule'])} (rule: {b['rule']})" for i, b in enumerate(breaches)]
    answer = (
        f"The portfolio is in breach because of {len(breaches)} mandate rule(s):\n"
        + "\n".join(lines)
        + "\n\nThese are deterministic rule-maths results, not model inferences."
    )
    citations = [{"type": "breach", **b} for b in breaches]
    return answer, citations


def _explain_watches(rules_result: dict) -> tuple[str, list[dict]]:
    """Grounded answer for drift watches."""
    watches = rules_result.get("watches", [])
    if not watches:
        return "There are no drift watches. The portfolio is not near any advisory threshold.", []
    lines = [f"{i + 1}. {w.get('plain', w['rule'])} (rule: {w['rule']})" for i, w in enumerate(watches)]
    answer = (
        f"The portfolio has {len(watches)} drift watch(es):\n"
        + "\n".join(lines)
        + "\n\nWatches are advisory; they do not violate the mandate but may warrant review."
    )
    citations = [{"type": "watch", **w} for w in watches]
    return answer, citations


def _explain_rule(query: str, rules_result: dict) -> tuple[str, list[dict]]:
    """Grounded answer for a specific rule question."""
    per_rule = rules_result.get("per_rule", [])
    mentions = _extract_rule_mentions(query, per_rule)
    if not mentions:
        return (
            "I couldn't match your question to a specific mandate check. "
            "The portfolio was checked against these rules:\n"
            + "\n".join(f"- {r['rule']}: {'PASS' if r.get('pass') else 'FAIL'}" for r in per_rule),
            [{"type": "per_rule", **r} for r in per_rule],
        )
    lines = []
    for r in mentions:
        status = "passes" if r.get("pass") else "fails"
        current = r.get("current")
        limit = r.get("limit")
        lines.append(
            f"{r['rule']} {status}: current {current}, limit {limit}."
        )
    answer = "\n".join(lines) + "\n\nAll values come from the rules-engine row shown in the citation."
    return answer, [{"type": "per_rule", **r} for r in mentions]


def _summarize(portfolio: dict, rules_result: dict) -> tuple[str, list[dict]]:
    """Grounded high-level summary."""
    total = sum(h.get("market_value", 0) for h in portfolio.get("holdings", [])) + portfolio.get("cash", 0)
    cash_pct = portfolio.get("cash", 0) / total * 100 if total else 0.0
    status = rules_result.get("status", "unknown")
    n_breaches = len(rules_result.get("breaches", []))
    n_watches = len(rules_result.get("watches", []))
    if status == "green":
        verdict = "fully aligned"
    elif status == "orange":
        verdict = "under watch"
    else:
        verdict = "in breach"
    top_holding = max(
        portfolio.get("holdings", []),
        key=lambda h: h.get("market_value", 0),
        default={"ticker": "none", "market_value": 0},
    )
    top_weight = top_holding.get("market_value", 0) / total * 100 if total else 0.0
    answer = (
        f"{portfolio.get('client_name', 'This portfolio')} is {verdict}. "
        f"Status: {status}. "
        f"Breaches: {n_breaches}, watches: {n_watches}. "
        f"Cash is {cash_pct:.1f}% of portfolio value. "
        f"Top holding is {top_holding.get('ticker')} at {top_weight:.1f}%."
    )
    citations = [{"type": "status", "status": status, "cash_pct": cash_pct, "top_weight": top_weight}]
    return answer, citations


def _explain_cash(portfolio: dict, rules_result: dict) -> tuple[str, list[dict]]:
    """Grounded answer about cash/liquidity."""
    total = sum(h.get("market_value", 0) for h in portfolio.get("holdings", [])) + portfolio.get("cash", 0)
    cash_pct = portfolio.get("cash", 0) / total * 100 if total else 0.0
    cash_row = next((r for r in rules_result.get("per_rule", []) if r["rule"] == "min_cash"), None)
    if cash_row:
        limit = cash_row.get("limit")
        answer = (
            f"Cash is {cash_pct:.1f}% of total value; the minimum-cash rule requires {limit * 100:.1f}%. "
            f"Result: {'PASS' if cash_row.get('pass') else 'FAIL'}."
        )
        citations = [{"type": "per_rule", **cash_row}]
    else:
        answer = f"Cash is {cash_pct:.1f}% of total value. No minimum-cash rule applies."
        citations = [{"type": "cash", "cash_pct": cash_pct}]
    return answer, citations


def _what_if_trade(query: str, portfolio: dict, mandate: dict, rules_result: dict) -> tuple[str, list[dict]]:
    """Grounded answer for what-if trade questions.

    Currently extracts simple buy/sell ticker + units from the query and runs
    the rules engine on the simulated portfolio. If no trade can be parsed, it
    asks for clarification.
    """
    # Naive regex extraction: "buy 50 SPY" or "sell 100 AAPL".
    match = re.search(r"(buy|sell)\s+([\d.]+)\s+([A-Z]{1,5})", query, re.IGNORECASE)
    if not match:
        return (
            "To run a what-if, please say something like 'buy 50 SPY' or 'sell 100 AAPL'. "
            "I will then simulate the trade and show the new rules-engine verdict.",
            [],
        )
    action, units_str, ticker = match.groups()
    units = float(units_str)
    from core.rules_engine import check
    from core.trades import apply_trades
    price_map = {h["ticker"]: h.get("price", h.get("market_value", 0) / max(h.get("units", 1), 1))
                 for h in portfolio.get("holdings", [])}
    trade_price = price_map.get(ticker, 0.0)
    if trade_price <= 0:
        return (
            f"I don't have a price for {ticker} in this portfolio, so I can't simulate the trade. "
            "Please provide the intended price.",
            [],
        )
    trade = {"ticker": ticker, "action": action.lower(), "units": units, "price": trade_price}
    try:
        new_portfolio = apply_trades(portfolio, [trade])
    except Exception as exc:
        return f"I couldn't simulate that trade: {exc}", []
    new_result = check(new_portfolio, mandate)
    old_status = rules_result.get("status", "unknown")
    new_status = new_result.get("status", "unknown")
    answer = (
        f"If you {action.lower()} {units} units of {ticker} at ~{trade_price:.2f}, "
        f"the portfolio status moves from {old_status} to {new_status}. "
    )
    new_breaches = new_result.get("breaches", [])
    if new_breaches:
        answer += f"New breaches: {len(new_breaches)} — {new_breaches[0].get('plain', new_breaches[0]['rule'])}"
    else:
        answer += "No new breaches are introduced."
    citations = [{"type": "what_if", "trade": trade, "new_status": new_status}]
    return answer, citations


def chat(
    query: str,
    portfolio: dict,
    mandate: dict,
    rules_result: dict,
    llm: LLMProvider | None = None,
) -> ChatAnswer:
    """Answer a natural-language question with deterministic grounding.

    The response always includes the exact engine facts (breaches, watches, or
    per_rule rows) that support the answer. An optional LLM is used only to
    polish prose; the facts are immutable.
    """
    intent = _classify_intent(query)

    if intent == "explain_breaches":
        answer, citations = _explain_breaches(rules_result)
    elif intent == "explain_watches":
        answer, citations = _explain_watches(rules_result)
    elif intent == "explain_rule":
        answer, citations = _explain_rule(query, rules_result)
    elif intent == "what_if_trade":
        answer, citations = _what_if_trade(query, portfolio, mandate, rules_result)
    elif intent == "explain_cash":
        answer, citations = _explain_cash(portfolio, rules_result)
    else:
        answer, citations = _summarize(portfolio, rules_result)

    # Optional LLM polish is applied only to the text; citations stay untouched.
    llm = llm or get_llm()
    if not isinstance(llm, type(get_llm())) or hasattr(llm, "_api_key"):  # real LLM path
        system = (
            "You are an assurance assistant. Rephrase the FACTS below into calm, "
            "plain English for a wealth-management client. Do not add, remove, or "
            "change any numbers or rules. Keep it under 3 sentences."
        )
        user = f"FACTS to rephrase:\n{answer}\n\nCitations:\n{json.dumps(citations, ensure_ascii=False)}"
        polished = llm.complete(system, user)
        if polished and not polished.startswith("[MOCK LLM]"):
            answer = polished

    followups = _suggested_followups(intent, rules_result)
    return ChatAnswer(
        intent=intent,
        answer=answer,
        citations=citations,
        suggested_followups=followups,
    )


def _suggested_followups(intent: str, rules_result: dict) -> list[str]:
    """Return context-aware follow-up prompts."""
    if rules_result.get("status") == "red":
        return ["Why is it red?", "What trade fixes the first breach?", "Show me the top rule."]
    if rules_result.get("status") == "orange":
        return ["What are the watches?", "How close to a breach is it?"]
    return ["Summarize the portfolio", "What is the cash position?", "What if I buy 10 SPY?"]
