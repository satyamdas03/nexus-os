"""Pure confidence scoring for ASSURE trade proposals.

Confidence is a weighted combination of:
  1. rules-engine certainty (did the proposal resolve all breaches?)
  2. simulation baseline (historical incidence from the last Hermes simulation)
  3. historical approval success (how often similar trades stayed green after approval)

The score is advisory only — it never overrides the deterministic rules engine.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from core import data_loader
from core.effective import get_effective
from core.rules_engine import check
from core.trades import apply_trades

_AUDIT_PATH = Path(__file__).parent.parent / "data" / "audit.jsonl"


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
    """Compute the simulation baseline from a Hermes book simulation.

    If a simulate_fn is supplied, call it with the contract (days=30,
    mode="prevent", seed=42). If none is supplied, attempt a local deterministic
    fallback via agents.hermes.loop.simulate_book. If nothing is available, or
    the simulation fails, return 0.5 (uncertain) — never a fake high default.
    """
    sim = simulate_fn
    if sim is None:
        try:
            from agents.hermes.loop import simulate_book

            sim = simulate_book
        except Exception:
            return 0.5
    try:
        result = sim(days=30, mode="prevent", seed=42)
        before = result.get("prevent_incidence", result.get("reactive_incidence", 0))
        if before is None:
            return 0.5
        # Lower incidence = higher score. Scale so 0 incidence = 1.0, 500 = 0.0.
        return max(0.0, min(1.0, 1.0 - (before / 500)))
    except Exception:
        return 0.5


def _load_audit(audit_path: Optional[Path] = None) -> list[dict]:
    p = audit_path or _AUDIT_PATH
    if not p.exists():
        return []
    try:
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    except Exception:
        return []


def _trade_signature(trades: list[dict]) -> set[tuple[str, str]]:
    return {
        (t.get("ticker", ""), t.get("action", ""))
        for t in trades
        if t.get("ticker")
    }


def _historical_score(
    client_id: str, trades: list[dict], audit_path: Optional[Path] = None
) -> float:
    """Audit-backed historical success score.

    Scan audit records for prior approvals of the same client + overlapping
    ticker actions. For each matched approval, look up the portfolio's status
    on the following day in status_history. The success rate is how often the
    approved trades kept the portfolio green the next day. If no matching
    history exists, return 0.5 (neutral).
    """
    records = [
        r
        for r in _load_audit(audit_path)
        if r.get("client_id") == client_id and r.get("action_type") == "approve"
    ]
    if not records:
        return 0.5

    current_sig = _trade_signature(trades)
    matched: list[dict] = []
    for rec in records:
        payload = rec.get("payload", {})
        rec_trades = payload.get("trades", [])
        if current_sig and not _trade_signature(rec_trades).intersection(current_sig):
            continue
        matched.append(rec)

    if not matched:
        return 0.5

    conn = data_loader.get_conn_cached()
    successes = 0
    for rec in matched:
        payload = rec.get("payload", {})
        day = payload.get("day")
        status: Optional[str] = None
        if day is not None:
            row = conn.execute(
                "SELECT status FROM status_history WHERE day=? AND client_id=?",
                (day + 1, client_id),
            ).fetchone()
            if row is not None:
                status = row["status"]
        # Fallback for legacy audit entries without a day: use the recorded
        # immediate post-approval status as a proxy.
        if status is None:
            status = payload.get("new_status")
        if status == "green":
            successes += 1

    return successes / len(matched)


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
