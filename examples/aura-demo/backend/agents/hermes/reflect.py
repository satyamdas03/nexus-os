"""Hermes reflection — proposes a SINGLE strategy-variable change.

Two modes:
  fallback  — deterministic heuristic over the latest heartbeat/score.
  hermes    — Claude proposes one change, grounded in score + history.

Reflection PROPOSES only. It never self-adopts and never writes. The human-gated
`adopt` step (routers/hermes.py) is the sole writer, and strategy_io.write_strategy
structurally refuses any path outside strategy.yaml/history/ — mandate rules and
rules_engine.py are law and are unreachable from here.
"""
import json

from agents.llm import LLMProvider, get_llm
from agents.hermes import HEARTBEAT_PATH, HISTORY_DIR
from agents.hermes.strategy_io import load_strategy
from agents.hermes.proposer import strategy_vars

SYSTEM = (
    "You are Hermes, a self-improving remediation strategy engine. You propose ONE "
    "change to a strategy variable in strategy.yaml to improve the book score. "
    "You are STRICTLY forbidden from touching mandate rules or the rules engine — "
    "those are law. Output STRICT JSON only: "
    '{"variable": str, "to": <value>, "rationale": str}. '
    "Pick from these variables only: breach_priority_order, preferred_trim_method "
    "(proportional|liquidate), replacement_preference, min_trade_size, "
    "max_trades_per_portfolio, cash_buffer_target. No prose outside the JSON."
)


def _history_summary() -> list[dict]:
    if not HISTORY_DIR.exists():
        return []
    out = []
    for f in sorted(HISTORY_DIR.glob("v*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def _fallback_proposal(strategy: dict, score: dict, heartbeat: dict) -> dict:
    """Deterministic: read the book's weak spot and propose one tweak."""
    vars_ = strategy_vars(strategy)
    misses = heartbeat.get("top_misses", [])
    miss_count = heartbeat.get("miss_count", 0)
    alignment = score.get("alignment_rate", 1.0)
    avg_trades = score.get("avg_trades_per_fix", 0.0)

    # High miss rate on trim-based breaches -> switch to liquidate (more decisive).
    if miss_count >= 3 and vars_.get("preferred_trim_method") == "proportional":
        return {"variable": "preferred_trim_method", "to": "liquidate",
                "rationale": f"{miss_count} proposals still breached after proportional trim; "
                             "liquidate the largest offender to clear caps decisively."}
    # Many trades but low alignment -> allow more trades per portfolio.
    if avg_trades >= 3.5 and alignment < 0.8:
        cur = int(vars_.get("max_trades_per_portfolio", 4))
        return {"variable": "max_trades_per_portfolio", "to": cur + 1,
                "rationale": f"avg {avg_trades} trades/fix yet alignment only "
                             f"{alignment*100:.0f}%; allow one more trade to finish fixes."}
    # Tiny noisy trades slipping through -> raise the floor.
    if avg_trades > 0 and alignment < 0.9:
        cur = float(vars_.get("min_trade_size", 0.01))
        return {"variable": "min_trade_size", "to": round(min(0.03, cur + 0.005), 3),
                "rationale": "raise the minimum trade size to cut noisy micro-trades "
                             "that do not move the compliance needle."}
    # Default nudge: cash buffer for redemption safety.
    return {"variable": "cash_buffer_target", "to": 0.04,
            "rationale": "no acute weak spot detected; lift cash buffer to 4% for "
                         "redemption flexibility."}


def reflect(mode: str = "fallback", llm: LLMProvider | None = None) -> dict:
    """Return ONE proposed strategy change {variable, current, to, rationale, mode}.

    Never writes. Never touches mandate rules or rules_engine.py.
    """
    strategy = load_strategy()
    vars_ = strategy_vars(strategy)
    heartbeat = {}
    if HEARTBEAT_PATH.exists():
        try:
            heartbeat = json.loads(HEARTBEAT_PATH.read_text())
        except json.JSONDecodeError:
            heartbeat = {}
    score = heartbeat.get("score", {})

    if mode == "hermes":
        llm = llm or get_llm()
        user = json.dumps({"score": score, "history": _history_summary(),
                           "current_variables": vars_,
                           "heartbeat_counts": heartbeat.get("counts", {})},
                          ensure_ascii=False)
        text = llm.complete(SYSTEM, user)
        try:
            start = text.index("{"); end = text.rindex("}") + 1
            prop = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            prop = _fallback_proposal(strategy, score, heartbeat)
            prop["mode"] = "fallback-fell-through"
        variable = prop.get("variable")
        if variable not in vars_:
            # LLM picked a forbidden/unknown variable — refuse, fall back.
            prop = _fallback_proposal(strategy, score, heartbeat)
            prop["mode"] = "fallback-fell-through"
        to = prop.get("to")
        rationale = prop.get("rationale", "")
    else:
        prop = _fallback_proposal(strategy, score, heartbeat)
        variable = prop["variable"]
        to = prop["to"]
        rationale = prop["rationale"]

    return {"variable": variable, "current": vars_.get(variable),
            "to": to, "rationale": rationale, "mode": mode}