"""Book-level score for Hermes. Reads effective state + audit trail.

Composite of: alignment_rate (green share), avg_trades_per_fix, acceptance_rate
(human approves of AI proposals), breaches_remaining. Deterministic; no LLM.
"""
import json
from pathlib import Path

from core.rules_engine import check
from core.effective import effective_portfolio

_AUDIT_PATH = Path(__file__).parent.parent.parent / "data" / "audit.jsonl"


def _alignment_rate(portfolios: list[dict]) -> float:
    if not portfolios:
        return 1.0
    green = sum(1 for p in portfolios if check(effective_portfolio(p), p["mandate"])["status"] == "green")
    return green / len(portfolios)


def _acceptance_rate() -> float:
    """Share of human approves whose post-trade new_status is green."""
    if not _AUDIT_PATH.exists():
        return 0.0
    total = green = 0
    for line in _AUDIT_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("action_type") != "approve":
            continue
        total += 1
        new = rec.get("payload", {}).get("new_status") or rec.get("new_status")
        if new == "green":
            green += 1
    return green / total if total else 0.0


def score_book(portfolios: list[dict], queue: list[dict], misses: list[dict]) -> dict:
    alignment = _alignment_rate(portfolios)
    acceptance = _acceptance_rate()
    avg_trades = (sum(len(q["trades"]) for q in queue) / len(queue)) if queue else 0.0
    # Each non-green portfolio counts once. `misses` is a subset of non-green
    # portfolios (a miss is a non-green portfolio Hermes failed to surface), so
    # adding len(misses) on top of the non-green count would double-count them.
    non_green_ids = {
        p.get("client_id") or p.get("id") or idx
        for idx, p in enumerate(portfolios)
        if check(effective_portfolio(p), p["mandate"])["status"] != "green"
    }
    breaches_remaining = len(non_green_ids)
    # Composite: alignment dominates, acceptance rewards the human-AI loop,
    # avg_trades penalises churn, breaches_remaining penalises leftovers.
    composite = (
        0.5 * alignment
        + 0.3 * acceptance
        + 0.2 * (1.0 - min(1.0, avg_trades / 4.0))
        - 0.1 * (breaches_remaining / max(1, len(portfolios)))
    )
    composite = max(0.0, min(1.0, composite))
    return {
        "alignment_rate": round(alignment, 3),
        "avg_trades_per_fix": round(avg_trades, 2),
        "acceptance_rate": round(acceptance, 3),
        "breaches_remaining": breaches_remaining,
        "composite": round(composite, 3),
    }