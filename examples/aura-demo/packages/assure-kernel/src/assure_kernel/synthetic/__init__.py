"""Synthetic Reality Engine for ASSURE.

Generators for realistic portfolios and market scenarios used to stress-test
the deterministic kernel and AI remediation agents at scale.
"""

from assure_kernel.synthetic.generator import (
    PortfolioGenerator,
    generate_portfolios,
)
from assure_kernel.synthetic.adversary import (
    Adversary,
    AdversaryResult,
    BreachObservation,
    find_breaches,
    stress_until_breach,
)
from assure_kernel.synthetic.report import StressReport, build_report
from assure_kernel.synthetic.scenarios import (
    Scenario,
    ShockMap,
    get_scenario,
    list_scenarios,
    stress_portfolio,
)

__all__ = [
    "PortfolioGenerator",
    "generate_portfolios",
    "Scenario",
    "ShockMap",
    "get_scenario",
    "list_scenarios",
    "stress_portfolio",
    "Adversary",
    "AdversaryResult",
    "BreachObservation",
    "find_breaches",
    "stress_until_breach",
    "StressReport",
    "build_report",
]
