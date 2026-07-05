"""Deterministic, grounded rule documentation renderer.

No LLM is required: every rule type has a static title and a template that is
filled with the rule's concrete parameters. This makes mandate explanations
regulator-reviewable, testable, and fast.
"""
from typing import Any, Callable

from assure_kernel.models import Mandate, Rule
from assure_kernel.types import Severity


RuleRenderer = Callable[[dict[str, Any]], str]


class _RuleDoc:
    """Static metadata + concrete renderer for one rule type."""

    def __init__(self, title: str, summary: str, render: RuleRenderer):
        self.title = title
        self.summary = summary  # short static description of the rule type
        self.render = render


def _join_weights(weights: dict[str, float]) -> str:
    if not weights:
        return "none"
    return ", ".join(f"{k} at {v:.1%}" for k, v in weights.items())


_RULE_DOCS: dict[str, _RuleDoc] = {
    "max_asset_class_weight": _RuleDoc(
        title="Asset-class weight cap",
        summary="Limits how much of the portfolio can sit in each asset class.",
        render=lambda p: f"Asset-class weights must not exceed: {_join_weights(p.get('weights', {}))}.",
    ),
    "max_sector_weight": _RuleDoc(
        title="Sector weight cap",
        summary="Limits how much of the portfolio can sit in each sector.",
        render=lambda p: f"Sector weights must not exceed: {_join_weights(p.get('weights', {}))}.",
    ),
    "max_region_weight": _RuleDoc(
        title="Regional weight cap",
        summary="Limits how much of the portfolio can be exposed to each region.",
        render=lambda p: f"Regional weights must not exceed: {_join_weights(p.get('weights', {}))}.",
    ),
    "approved_universe": _RuleDoc(
        title="Approved universe",
        summary="Restricts holdings to an explicitly approved ticker list.",
        render=lambda p: (
            f"Holdings must be drawn from the approved universe "
            f"({len(p.get('tickers', []))} tickers)."
        ),
    ),
    "esg_exclusions": _RuleDoc(
        title="ESG / policy exclusions",
        summary="Prohibits holdings on a policy exclusion list.",
        render=lambda p: (
            f"The following tickers are excluded from the portfolio: "
            f"{', '.join(p.get('tickers', [])) or 'none'}."
        ),
    ),
    "max_single_holding": _RuleDoc(
        title="Single-holding concentration cap",
        summary="Limits the maximum weight of any single ticker.",
        render=lambda p: f"No single holding may exceed {p.get('limit', 1.0):.1%} of the portfolio.",
    ),
    "min_cash": _RuleDoc(
        title="Minimum cash buffer",
        summary="Requires a minimum cash allocation.",
        render=lambda p: f"Cash must be at least {p.get('limit', 0.0):.1%} of the portfolio.",
    ),
    "min_liquid_pct": _RuleDoc(
        title="Minimum liquid allocation",
        summary="Requires a minimum allocation to tier-1 liquid holdings.",
        render=lambda p: f"Tier-1 liquid holdings must be at least {p.get('limit', 0.0):.1%} of the portfolio.",
    ),
    "target_allocation_drift": _RuleDoc(
        title="Target-allocation drift watch",
        summary="Flags asset classes that drift above their target plus a tolerance.",
        render=lambda p: (
            f"Asset-class targets are {', '.join(f'{k} {v:.1%}' for k, v in p.get('targets', {}).items())} "
            f"with a drift tolerance of {p.get('drift_tolerance', 0.05):.1%}."
        ),
    ),
    "max_top_n_concentration": _RuleDoc(
        title="Top-N concentration cap",
        summary="Limits the combined weight of the largest N holdings.",
        render=lambda p: (
            f"The top {p.get('n', 5)} holdings combined must not exceed "
            f"{p.get('limit', 1.0):.1%} of the portfolio."
        ),
    ),
}


def _severity_label(severity: Severity | None) -> str | None:
    if severity is None:
        return None
    return {
        Severity.HARD: "hard breach",
        Severity.SOFT: "soft breach",
        Severity.WATCH: "watch",
    }.get(severity)


def rule_type_metadata() -> dict[str, dict[str, str]]:
    """Return static documentation for every registered rule type."""
    return {
        rule_type: {"title": doc.title, "summary": doc.summary}
        for rule_type, doc in _RULE_DOCS.items()
    }


def describe_rule(rule: Rule) -> dict[str, Any]:
    """Render a single rule into a human-readable explanation."""
    doc = _RULE_DOCS.get(rule.type)
    title = doc.title if doc else rule.type
    summary = doc.summary if doc else "Custom rule."
    rendered = doc.render(rule.params) if doc else str(rule.params)
    return {
        "type": rule.type,
        "title": title,
        "summary": summary,
        "description": rendered,
        "parameters": rule.params,
        "enabled": rule.enabled,
        "severity": _severity_label(rule.severity),
        "message": rule.message,
    }


def describe_mandate(mandate: Mandate) -> dict[str, Any]:
    """Render a full mandate into a human-readable summary + rule docs."""
    return {
        "id": mandate.id,
        "name": mandate.name,
        "version": mandate.version,
        "metadata": mandate.metadata,
        "rule_count": len(mandate.rules),
        "enabled_rule_count": sum(1 for r in mandate.rules if r.enabled),
        "rules": [describe_rule(r) for r in mandate.rules],
    }
