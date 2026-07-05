"""Adversarial breach hunter for the ASSURE Synthetic Reality Engine.

The adversary generates synthetic portfolios, optionally stresses them, evaluates
them against a mandate, and classifies the resulting breaches. It produces a
clean dataset of breach observations that can be used to train/validate AI
remediation agents and to detect any divergence between engine verdicts and
agent claims.

The adversary is intentionally deterministic: the same seed, mandate, and
settings always produce the same breach report.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from assure_kernel import evaluate_portfolio
from assure_kernel.dsl import parse_mandate
from assure_kernel.models import Portfolio, RulesResult
from assure_kernel.synthetic.generator import PortfolioGenerator
from assure_kernel.synthetic.scenarios import Scenario, get_scenario, stress_portfolio
from assure_kernel.types import Status


@dataclass
class BreachObservation:
    """A single observation of a synthetic portfolio that breached a mandate."""

    client_id: str
    scenario_id: str
    status: str
    rule: str
    severity: str
    current: float | list | None
    limit: float | list | None
    plain: str | None
    portfolio_value: float
    day: int

    def to_dict(self) -> dict:
        return {
            "client_id": self.client_id,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "rule": self.rule,
            "severity": self.severity,
            "current": self.current,
            "limit": self.limit,
            "plain": self.plain,
            "portfolio_value": self.portfolio_value,
            "day": self.day,
        }


@dataclass
class AdversaryResult:
    """Aggregate result from an adversarial sweep."""

    total: int
    green: int
    orange: int
    red: int
    breach_observations: list[BreachObservation] = field(default_factory=list)
    rule_breach_counts: dict[str, int] = field(default_factory=dict)
    scenario_status_counts: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "green": self.green,
            "orange": self.orange,
            "red": self.red,
            "breach_rate": self.red / self.total if self.total else 0.0,
            "watch_rate": self.orange / self.total if self.total else 0.0,
            "rule_breach_counts": self.rule_breach_counts,
            "scenario_status_counts": {
                sid: dict(counts)
                for sid, counts in self.scenario_status_counts.items()
            },
            "breach_observations": [o.to_dict() for o in self.breach_observations],
        }


@dataclass
class Adversary:
    """Configurable adversarial sweep over synthetic portfolios and scenarios.

    Example:
        >>> mandate = parse_mandate({...})
        >>> adv = Adversary(mandate=mandate, scenarios=["baseline", "equity_crash_2008"])
        >>> result = adv.sweep(n=1_000, seed=42)
    """

    mandate: dict
    scenarios: list[str] = field(default_factory=lambda: ["baseline"])
    generator_kwargs: dict = field(default_factory=dict)
    record_limit: int | None = None  # cap number of breach observations stored
    rng_factory: Callable[[int | None], random.Random] = random.Random

    def __post_init__(self):
        self._parsed_mandate = parse_mandate(self.mandate)
        # Validate scenario IDs early.
        for sid in self.scenarios:
            get_scenario(sid)

    def sweep(
        self,
        n: int = 100,
        seed: int | None = None,
    ) -> AdversaryResult:
        """Generate n portfolios per scenario and evaluate against the mandate."""
        rng = self.rng_factory(seed)

        generator = PortfolioGenerator(
            seed=rng.randint(0, 2_147_483_647),
            **self.generator_kwargs,
        )

        result = AdversaryResult(total=0, green=0, orange=0, red=0)

        for scenario_id in self.scenarios:
            scenario = get_scenario(scenario_id)
            portfolios = generator.generate(n)
            scenario_counts: dict[str, int] = {"green": 0, "orange": 0, "red": 0}

            for idx, portfolio in enumerate(portfolios):
                # Each stressed portfolio gets a deterministic sub-seed.
                stressed = scenario.apply(portfolio, seed=rng.randint(0, 2_147_483_647))
                rules_result = evaluate_portfolio(stressed, self._parsed_mandate)
                legacy = rules_result.to_legacy()
                status = legacy["status"]
                result.total += 1
                scenario_counts[status] += 1

                if status == "green":
                    result.green += 1
                elif status == "orange":
                    result.orange += 1
                else:
                    result.red += 1
                    self._record_breaches(
                        result, portfolio.client_id or f"SYN-{idx:06d}",
                        scenario_id, rules_result, stressed.total_value
                    )

            result.scenario_status_counts[scenario_id] = scenario_counts

        return result

    def _record_breaches(
        self,
        result: AdversaryResult,
        client_id: str,
        scenario_id: str,
        rules_result: RulesResult,
        portfolio_value: float,
        day: int = 0,
    ) -> None:
        """Append breach observations, respecting the optional record limit."""
        for violation in rules_result.breaches:
            rule_key = violation.rule
            result.rule_breach_counts[rule_key] = result.rule_breach_counts.get(rule_key, 0) + 1

            if self.record_limit is not None and len(result.breach_observations) >= self.record_limit:
                continue

            result.breach_observations.append(
                BreachObservation(
                    client_id=client_id,
                    scenario_id=scenario_id,
                    status=rules_result.status.value,
                    rule=rule_key,
                    severity="red",
                    current=violation.current,
                    limit=violation.limit,
                    plain=violation.plain,
                    portfolio_value=portfolio_value,
                    day=day,
                )
            )


def find_breaches(
    mandate: dict,
    n: int = 100,
    seed: int | None = None,
    scenarios: list[str] | None = None,
    generator_kwargs: dict | None = None,
    record_limit: int | None = None,
) -> AdversaryResult:
    """Convenience wrapper to run a single adversarial sweep."""
    return Adversary(
        mandate=mandate,
        scenarios=scenarios or ["baseline"],
        generator_kwargs=generator_kwargs or {},
        record_limit=record_limit,
    ).sweep(n=n, seed=seed)


def stress_until_breach(
    portfolio: Portfolio,
    mandate: dict,
    scenario_order: list[str] | None = None,
    max_trials: int = 5,
    seed: int | None = None,
) -> tuple[str | None, RulesResult | None, Portfolio | None]:
    """Try a sequence of scenarios on one portfolio until it breaches.

    Returns the scenario ID that caused the breach, the rules result, and the
    stressed portfolio. If no scenario causes a breach, returns (None, None, None).
    """
    scenario_order = scenario_order or ["baseline", "equity_crash_2008", "crypto_winter", "em_contagion"]
    parsed_mandate = parse_mandate(mandate)
    rng = random.Random(seed)

    for scenario_id in scenario_order:
        scenario = get_scenario(scenario_id)
        for _ in range(max_trials):
            stressed = scenario.apply(portfolio, seed=rng.randint(0, 2_147_483_647))
            rules_result = evaluate_portfolio(stressed, parsed_mandate)
            if rules_result.status == Status.BREACH:
                return scenario_id, rules_result, stressed
    return None, None, None
