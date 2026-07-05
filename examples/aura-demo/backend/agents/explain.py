"""Explainer agent. Grounded against rules_engine output — may only describe
breaches/watches the engine flagged. Never invents rules or numbers."""
import json
from agents.llm import LLMProvider, get_llm

SYSTEM = ("You are an assurance explainer for a wealth-management platform. "
          "You are given a portfolio, its mandate, and the DETERMINISTIC rules-engine result. "
          "You may ONLY describe the breaches and watches the engine flagged. "
          "Do not invent rules, numbers, or breaches. Plain English, calm, 2-4 sentences. "
          "Start with the count of breaches and watches. "
          "Never claim a rule is broken if the engine did not flag it.")


def _facts(portfolio: dict, rules_result: dict) -> str:
    total = sum(x["market_value"] for x in portfolio["holdings"]) + portfolio["cash"]
    return json.dumps({
        "client": portfolio["client_name"],
        "fum": portfolio["fum"],
        "holdings": [{"ticker": h["ticker"], "weight_pct": round(h["market_value"] / total * 100, 1)}
                     for h in portfolio["holdings"]],
        "cash_pct": round(portfolio["cash"] / total * 100, 1),
        "engine_breaches": rules_result["breaches"],
        "engine_watches": rules_result["watches"],
    }, ensure_ascii=False)


def explain(portfolio: dict, rules_result: dict, llm: LLMProvider | None = None,
            metric: str | None = None) -> dict:
    llm = llm or get_llm()
    facts = _facts(portfolio, rules_result)
    if metric:
        # Per-metric popover: one sentence grounded in the matching per_rule row.
        row = next((r for r in rules_result["per_rule"] if r["rule"] == metric
                    or r["rule"].split(":")[-1] == metric), None)
        if row is None:
            return {"narrative": f"No mandate check named '{metric}' applies to this portfolio.",
                    "breach_summaries": [], "watch_summaries": [], "metric": metric}
        user = (f"Rules-engine row (GROUND TRUTH):\n{json.dumps(row, ensure_ascii=False)}\n"
                f"Portfolio facts:\n{facts}\n\n"
                f"Write ONE plain-English sentence (max 25 words) explaining this specific "
                f"check for this client. State the current value, the limit/target, and whether "
                f"it passes. Do not invent numbers; use only the row above.")
        narrative = llm.complete(SYSTEM, user)
        return {"narrative": narrative, "metric": metric,
                "breach_summaries": [], "watch_summaries": []}
    user = (f"Rules-engine result (GROUND TRUTH — do not contradict):\n{facts}\n\n"
            f"Write the plain-English assurance narrative.")
    narrative = llm.complete(SYSTEM, user)
    return {
        "narrative": narrative,
        "breach_summaries": [b["plain"] for b in rules_result["breaches"]],
        "watch_summaries": [w["plain"] for w in rules_result["watches"]],
    }