"""Backward-compatibility shim for the ASSURE kernel.

The original rules engine has been extracted into the reusable
`assure_kernel` package. This module re-exports the same public API so
existing aura-demo imports continue to work unchanged.

New code should import directly from `assure_kernel`.
"""

from assure_kernel import evaluate_portfolio


def check(portfolio: dict, mandate: dict) -> dict:
    """Deterministic rules check. Returns the legacy aura-demo dict shape."""
    return evaluate_portfolio(portfolio, mandate).to_legacy()


def status_of(rules_result: dict) -> str:
    """Return the legacy green/orange/red status for a rules result dict."""
    if rules_result.get("breaches"):
        return "red"
    if rules_result.get("watches"):
        return "orange"
    return "green"
