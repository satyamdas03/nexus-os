"""Remediation agent + closed verify loop. AI proposes, rules_engine disposes.

The resulting portfolio is re-checked by the deterministic engine; if still
red/orange, the agent gets ONE retry. The engine — not the LLM — is final.
"""
import json
from agents.llm import LLMProvider, get_llm
from core.rules_engine import check
from core.trades import apply_trades as _apply_trades  # re-exported; tests import this name

SYSTEM = ("You are a portfolio remediation agent. Given a portfolio, its mandate, and the "
          "deterministic rules-engine result, propose the MINIMAL set of compliant trades to "
          "bring the portfolio to GREEN. Trades must use tickers from the approved universe and "
          "respect max_single_holding and min_cash. Output STRICT JSON only: a list of objects "
          "with keys ticker, action ('buy'|'sell'), units (number), value (number), rationale (str). "
          "Do not include prose outside the JSON. Never sell tickers not held; never buy unapproved tickers.")


def _facts(portfolio: dict, rules_result: dict, mandate: dict) -> str:
    return json.dumps({"holdings": portfolio["holdings"], "cash": portfolio["cash"],
                       "mandate": mandate, "engine_breaches": rules_result["breaches"]},
                      ensure_ascii=False)


def _parse_trades(text: str) -> list[dict]:
    # MockLLM returns [MOCK LLM]... — handle gracefully as empty trades for tests
    try:
        start = text.index("["); end = text.rindex("]") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return []


def remediate(portfolio: dict, rules_result: dict, llm: LLMProvider | None = None,
              mandate: dict | None = None) -> dict:
    llm = llm or get_llm()
    mandate = mandate or portfolio.get("mandate")
    if mandate is None:
        raise ValueError("remediate needs a mandate (portfolio['mandate'] or mandate=)")
    facts = _facts(portfolio, rules_result, mandate)
    trades = _parse_trades(llm.complete(SYSTEM, facts))
    resulting = _apply_trades(portfolio, trades)
    verification = check(resulting, mandate)
    retried = False
    if verification["status"] != "green" and verification["breaches"]:
        retry_prompt = (facts + "\n\nPrevious proposal still leaves these breaches: "
                        + json.dumps(verification["breaches"]) + "\nRevise the trades.")
        trades = _parse_trades(llm.complete(SYSTEM, retry_prompt))
        resulting = _apply_trades(portfolio, trades)
        verification = check(resulting, mandate)
        retried = True
    return {"trades": trades, "verification": verification,
            "resulting_portfolio": resulting, "retried": retried,
            "resolved": verification["status"] == "green"}