"""ASSURE kernel — deterministic portfolio assurance engine."""

from assure_kernel.docs import describe_mandate, describe_rule, rule_type_metadata
from assure_kernel.dsl import (
    dump_mandate,
    dumps_mandate,
    load_mandate,
    parse_mandate,
    to_legacy_dict,
)
from assure_kernel.engine import check, evaluate_portfolio
from assure_kernel.evidence import build_evidence
from assure_kernel.synthetic import (
    PortfolioGenerator,
    Scenario,
    ShockMap,
    generate_portfolios,
    get_scenario,
    list_scenarios,
    stress_portfolio,
)
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
    "load_mandate",
    "parse_mandate",
    "to_legacy_dict",
    "dump_mandate",
    "dumps_mandate",
    "describe_rule",
    "describe_mandate",
    "rule_type_metadata",
    "build_evidence",
    "PortfolioGenerator",
    "generate_portfolios",
    "Scenario",
    "ShockMap",
    "list_scenarios",
    "get_scenario",
    "stress_portfolio",
]
