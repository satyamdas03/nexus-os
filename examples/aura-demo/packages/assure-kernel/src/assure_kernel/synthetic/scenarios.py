"""Synthetic stress scenarios for the ASSURE kernel.

A scenario is a deterministic, named shock regime that transforms a portfolio
by applying asset-class, sector, and region price multipliers. Scenarios are
immutable maps: the original portfolio is untouched and a new, stressed copy is
returned. This lets the kernel measure mandate fragility under different
market conditions.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from assure_kernel.models import Holding, Portfolio


@dataclass(frozen=True)
class ShockMap:
    """A collection of price multipliers keyed by asset class, sector, or region."""

    asset_class: dict[str, float] = field(default_factory=dict)
    sector: dict[str, float] = field(default_factory=dict)
    region: dict[str, float] = field(default_factory=dict)
    # Default multiplier applied when a holding does not match any specific key.
    default: float = 1.0
    # Optional Gaussian noise (relative std dev) added to individual prices.
    noise_std: float = 0.0

    def multiplier_for(self, holding: Holding) -> float:
        """Compute the combined multiplier for a single holding."""
        factors: list[float] = []
        if holding.asset_class and holding.asset_class in self.asset_class:
            factors.append(self.asset_class[holding.asset_class])
        if holding.sector and holding.sector in self.sector:
            factors.append(self.sector[holding.sector])
        if holding.region and holding.region in self.region:
            factors.append(self.region[holding.region])
        if not factors:
            factors.append(self.default)
        # Combine multipliers multiplicatively so overlapping shocks compound.
        product = 1.0
        for f in factors:
            product *= f
        return product


@dataclass(frozen=True)
class Scenario:
    """A named, deterministic stress regime."""

    id: str
    name: str
    description: str
    severity: str  # mild | moderate | severe | extreme
    shocks: ShockMap

    def apply(
        self,
        portfolio: Portfolio,
        seed: int | None = None,
        rng_factory: Callable[[int | None], random.Random] = random.Random,
    ) -> Portfolio:
        """Return a new Portfolio with prices stressed according to this scenario."""
        rng = rng_factory(seed)
        stressed_holdings: list[Holding] = []
        for h in portfolio.holdings:
            base = h.price
            mult = self.shocks.multiplier_for(h)
            price = base * mult
            if self.shocks.noise_std:
                noise = rng.gauss(1.0, self.shocks.noise_std)
                price *= max(noise, 0.1)
            new_h = Holding(
                ticker=h.ticker,
                name=h.name,
                asset_class=h.asset_class,
                sector=h.sector,
                region=h.region,
                liquidity_tier=h.liquidity_tier,
                units=h.units,
                price=round(price, 4),
            )
            stressed_holdings.append(new_h)
        return Portfolio(
            client_id=portfolio.client_id,
            client_name=portfolio.client_name,
            adviser=portfolio.adviser,
            cash=portfolio.cash,
            holdings=stressed_holdings,
            fum=portfolio.fum,
        )


# -----------------------------------------------------------------------------
# Built-in stress scenarios
# -----------------------------------------------------------------------------

SCENARIOS: dict[str, Scenario] = {
    "baseline": Scenario(
        id="baseline",
        name="Baseline",
        description="No stress; returns a near-identical portfolio (tiny idiosyncratic noise only).",
        severity="mild",
        shocks=ShockMap(default=1.0, noise_std=0.01),
    ),
    "equity_crash_2008": Scenario(
        id="equity_crash_2008",
        name="2008-style Equity Crash",
        description="Global equity market crash: equities sell off sharply, credit spreads widen, flight to quality boosts government bonds.",
        severity="severe",
        shocks=ShockMap(
            asset_class={"Equity": 0.55, "Bonds": 1.05, "Commodity": 0.75, "Crypto": 0.60},
            sector={"Financials": 0.35, "Technology": 0.65, "Consumer": 0.70, "Energy": 0.60},
            region={"ExUS": 0.60, "EM": 0.50},
            default=1.0,
            noise_std=0.08,
        ),
    ),
    "rate_shock_2022": Scenario(
        id="rate_shock_2022",
        name="Rapid Rate-Hiking Cycle",
        description="Central banks hike rates aggressively: long-duration bonds and tech equities fall, cash is unchanged, floating-rate credit outperforms.",
        severity="moderate",
        shocks=ShockMap(
            asset_class={"Equity": 0.85, "Bonds": 0.80, "Commodity": 1.10, "Crypto": 0.55, "Cash": 1.0},
            sector={"Technology": 0.70, "Real Estate": 0.75, "Financials": 0.95},
            region={},
            default=1.0,
            noise_std=0.05,
        ),
    ),
    "crypto_winter": Scenario(
        id="crypto_winter",
        name="Crypto Winter",
        description="Regulatory clampdown and leverage unwind collapse crypto prices; risk-off spillover hits growth equities.",
        severity="extreme",
        shocks=ShockMap(
            asset_class={"Crypto": 0.20, "Equity": 0.90, "Bonds": 1.0, "Commodity": 0.95, "Cash": 1.0},
            sector={"Technology": 0.80, "Digital": 0.20},
            region={},
            default=1.0,
            noise_std=0.12,
        ),
    ),
    "inflation_spike": Scenario(
        id="inflation_spike",
        name="Unexpected Inflation Spike",
        description="Inflation surprises to the upside: nominal bonds suffer, commodities and short-duration credit rally, equities tread water.",
        severity="moderate",
        shocks=ShockMap(
            asset_class={"Bonds": 0.88, "Commodity": 1.25, "Equity": 0.95, "Crypto": 0.90, "Cash": 1.0},
            sector={"Energy": 1.20, "Materials": 1.15, "Precious": 1.30, "Real Estate": 0.90},
            region={},
            default=1.0,
            noise_std=0.04,
        ),
    ),
    "tech_selloff": Scenario(
        id="tech_selloff",
        name="Technology Selloff",
        description="Valuation compression and earnings misses disproportionately hit technology names.",
        severity="moderate",
        shocks=ShockMap(
            asset_class={"Equity": 0.92},
            sector={"Technology": 0.60, "Consumer": 0.90},
            region={"US": 0.90},
            default=1.0,
            noise_std=0.06,
        ),
    ),
    "em_contagion": Scenario(
        id="em_contagion",
        name="Emerging Market Contagion",
        description="Sovereign stress and capital flight hammer emerging-market equities and bonds; developed markets see modest safe-haven flows.",
        severity="severe",
        shocks=ShockMap(
            asset_class={"Equity": 0.90, "Bonds": 0.95},
            sector={"Financials": 0.80, "Energy": 0.85, "Materials": 0.85},
            region={"EM": 0.45, "ExUS": 0.80},
            default=1.0,
            noise_std=0.10,
        ),
    ),
}


def list_scenarios() -> list[dict[str, str]]:
    """Return a human-readable list of all built-in scenarios."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "severity": s.severity,
        }
        for s in SCENARIOS.values()
    ]


def get_scenario(scenario_id: str) -> Scenario:
    """Fetch a built-in scenario by ID."""
    if scenario_id not in SCENARIOS:
        raise KeyError(f"Unknown scenario '{scenario_id}'. Available: {sorted(SCENARIOS)}")
    return SCENARIOS[scenario_id]


def stress_portfolio(
    portfolio: Portfolio,
    scenario_id: str,
    seed: int | None = None,
) -> Portfolio:
    """Convenience function to stress a portfolio using a built-in scenario."""
    return get_scenario(scenario_id).apply(portfolio, seed=seed)
