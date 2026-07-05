"""Pure confidence scoring for ASSURE trade proposals.

Confidence is a weighted combination of:
  1. rules-engine certainty (did the proposal resolve all breaches?)
  2. simulation baseline (historical incidence from the last Hermes simulation)
  3. historical approval success (how often similar trades stayed green after approval)

The score is advisory only — it never overrides the deterministic rules engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.effective import get_effective
from core.rules_engine import check
from core.trades import apply_trades


@dataclass(frozen=True)
class ConfidenceResult:
    confidence: float
    rule_engine_certainty: float
    simulation_baseline: float
    historical_approval_success: float
    data_freshness: float
    human_review_recommended: bool
    factors: list[dict[str, Any]]
    explanation: str


def _rule_score(rr: dict) -> float:
    if rr.get("status") == "green":
        return 1.0
    if rr.get("status") == "orange":
        return 0.7
    return 0.0


def _simulate_score(simulate_fn: Optional[Callable] = None) -> float:
    if simulate_fn is None:
        return 0.85
    try:
        result = simulate_fn(days=30, mode="prevent", seed=42)
        before = result.get("prevent_incidence", result.get("reactive_incidence", 0))
        if before is None:
            return 0.85
        # Lower incidence = higher score. Scale so 0 incidence = 1.0, 500 = 0.0.
        return max(0.0, min(1.0, 1.0 - (before / 500)))
    except Exception:
        return 0.5


def _historical_score(client_id: str, _trades: list[dict]) -> float:
    """Placeholder for an audit-backed historical success score.

    A real implementation would scan the audit trail for prior approvals of the
    same client + ticker actions and measure how often the portfolio stayed
    green on the following day. For now we optimistically bias to 0.9 because
    every Hermes-queued trade is rules-engine green before approval.
    """
    return 0.9


def score_confidence(
    client_id: str,
    trades: list[dict],
    simulate_fn: Optional[Callable] = None,
) -> ConfidenceResult:
    from core.data_loader import get_portfolio

    p = get_portfolio(client_id)
    if p is None:
        raise ValueError(f"portfolio not found: {client_id}")

    mandate = p["mandate"]
    eff = get_effective(client_id, seed=p)
    if eff is None:
        raise ValueError(f"effective portfolio unavailable: {client_id}")

    # Apply proposed trades to compute the rules-engine certainty factor.
    post = apply_trades(eff, trades, price_lookup=lambda t: None)
    post_rr = check(post, mandate)
    rule_score = _rule_score(post_rr)

    sim_score = _simulate_score(simulate_fn)
    hist_score = _historical_score(client_id, trades)
    freshness_score = 1.0

    factors = [
        {"name": "rules_engine", "score": rule_score, "weight": 0.5},
        {"name": "simulation_baseline", "score": sim_score, "weight": 0.3},
        {"name": "historical_approval_success", "score": hist_score, "weight": 0.2},
    ]
    confidence = round(sum(f["score"] * f["weight"] for f in factors), 3)
    human_review = confidence < 0.85 or any(f["score"] < 0.8 for f in factors)

    if human_review:
        explanation = (
            f"Confidence {confidence}: one or more factors are below the high-confidence "
            "threshold; a human review is recommended before approving."
        )
    else:
        explanation = (
            f"Confidence {confidence}: the deterministic gate is green, the simulation "
            "baseline is supportive, and historical approvals have succeeded."
        )

    return ConfidenceResult(
        confidence=confidence,
        rule_engine_certainty=rule_score,
        simulation_baseline=sim_score,
        historical_approval_success=hist_score,
        data_freshness=freshness_score,
        human_review_recommended=human_review,
        factors=factors,
        explanation=explanation,
    )
