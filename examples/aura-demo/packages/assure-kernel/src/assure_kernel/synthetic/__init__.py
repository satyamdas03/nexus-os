"""Synthetic Reality Engine for ASSURE.

Generators for realistic portfolios and market scenarios used to stress-test
the deterministic kernel and AI remediation agents at scale.
"""

from assure_kernel.synthetic.generator import (
    PortfolioGenerator,
    generate_portfolios,
)

__all__ = [
    "PortfolioGenerator",
    "generate_portfolios",
]
