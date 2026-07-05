"""Book-wide summariser. Grounded ONLY in aggregate rules-engine output across
the effective book. No invented numbers, no client names beyond what the engine
produced. Replaces the static AssuranceBanner copy with one grounded sub-line.
"""
import json
from collections import Counter
from agents.llm import LLMProvider, get_llm

SYSTEM = ("You are the chief assurance officer's summary writer for a wealth platform. "
          "You are given AGGREGATE deterministic rules-engine output for the whole book. "
          "You may ONLY state facts present in that aggregate: portfolio counts by status, "
          "total breach count, and the most common systemic breach pattern. "
          "Write 2-3 plain-English sentences for a leadership dashboard banner. "
          "Do not invent numbers, client names, or rules. End with the one-line systemic "
          "takeaway. Calm, institutional tone.")


def _aggregate(portfolios: list[dict], rules_results: list[dict]) -> dict:
    counts = Counter(rr["status"] for rr in rules_results)
    breach_count = sum(len(rr["breaches"]) for rr in rules_results)
    pattern = Counter(b["rule"].split(":")[0] for rr in rules_results for b in rr["breaches"])
    top_pattern = pattern.most_common(3)
    return {
        "total_portfolios": len(portfolios),
        "green": counts.get("green", 0),
        "orange": counts.get("orange", 0),
        "red": counts.get("red", 0),
        "total_breaches": breach_count,
        "top_systemic_patterns": [{"rule": r, "count": c} for r, c in top_pattern],
    }


def summarize_book(portfolios: list[dict], rules_results: list[dict],
                   llm: LLMProvider | None = None) -> dict:
    llm = llm or get_llm()
    agg = _aggregate(portfolios, rules_results)
    user = (f"Aggregate rules-engine output (GROUND TRUTH — do not contradict):\n"
            f"{json.dumps(agg, ensure_ascii=False)}\n\n"
            f"Write the leadership banner summary.")
    narrative = llm.complete(SYSTEM, user)
    return {"narrative": narrative, "aggregate": agg}