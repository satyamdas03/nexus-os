"""ASSURE kernel — deterministic portfolio assurance engine."""

from assure_kernel.engine import check, evaluate_portfolio
from assure_kernel.models import (
    Holding,
    Mandate,
    Portfolio,
    Rule,
    RuleEvaluation,
    RulesResult,
    Violation,
)
from assure_kernel.registry import get, list_rules, register
from assure_kernel.types import LegacyStatus, RuleType, Severity, Status

__version__ = "0.1.0"

__all__ = [
    "check",
    "evaluate_portfolio",
    "Portfolio",
    "Holding",
    "Mandate",
    "Rule",
    "RulesResult",
    "RuleEvaluation",
    "Violation",
    "Status",
    "LegacyStatus",
    "Severity",
    "RuleType",
    "register",
    "get",
    "list_rules",
]
