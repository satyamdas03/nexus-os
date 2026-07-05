"""Deterministic synthetic portfolio generator for the ASSURE kernel.

Produces realistic portfolios that match real-world distributions so the
kernel and AI agents can be stress-tested at scale. Every sequence is fully
reproducible given the same seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from assure_kernel.models import Holding, Portfolio


# A curated universe of tickers with realistic classification metadata.
_UNIVERSE: list[dict] = [
    # US Large-Cap Equity
    {"ticker": "AAPL", "asset_class": "Equity", "sector": "Technology", "region": "US", "liquidity_tier": 1},
    {"ticker": "MSFT", "asset_class": "Equity", "sector": "Technology", "region": "US", "liquidity_tier": 1},
    {"ticker": "GOOGL", "asset_class": "Equity", "sector": "Technology", "region": "US", "liquidity_tier": 1},
    {"ticker": "AMZN", "asset_class": "Equity", "sector": "Consumer", "region": "US", "liquidity_tier": 1},
    {"ticker": "NVDA", "asset_class": "Equity", "sector": "Technology", "region": "US", "liquidity_tier": 1},
    {"ticker": "META", "asset_class": "Equity", "sector": "Technology", "region": "US", "liquidity_tier": 1},
    {"ticker": "TSLA", "asset_class": "Equity", "sector": "Consumer", "region": "US", "liquidity_tier": 1},
    {"ticker": "BRK.B", "asset_class": "Equity", "sector": "Financials", "region": "US", "liquidity_tier": 1},
    {"ticker": "JPM", "asset_class": "Equity", "sector": "Financials", "region": "US", "liquidity_tier": 1},
    {"ticker": "JNJ", "asset_class": "Equity", "sector": "Healthcare", "region": "US", "liquidity_tier": 1},
    {"ticker": "V", "asset_class": "Equity", "sector": "Financials", "region": "US", "liquidity_tier": 1},
    {"ticker": "UNH", "asset_class": "Equity", "sector": "Healthcare", "region": "US", "liquidity_tier": 1},
    {"ticker": "HD", "asset_class": "Equity", "sector": "Consumer", "region": "US", "liquidity_tier": 1},
    {"ticker": "PG", "asset_class": "Equity", "sector": "Consumer", "region": "US", "liquidity_tier": 1},
    {"ticker": "MA", "asset_class": "Equity", "sector": "Financials", "region": "US", "liquidity_tier": 1},
    {"ticker": "XOM", "asset_class": "Equity", "sector": "Energy", "region": "US", "liquidity_tier": 1},
    {"ticker": "CVX", "asset_class": "Equity", "sector": "Energy", "region": "US", "liquidity_tier": 1},
    {"ticker": "LLY", "asset_class": "Equity", "sector": "Healthcare", "region": "US", "liquidity_tier": 1},
    {"ticker": "AVGO", "asset_class": "Equity", "sector": "Technology", "region": "US", "liquidity_tier": 1},
    # International Equity
    {"ticker": "TSM", "asset_class": "Equity", "sector": "Technology", "region": "ExUS", "liquidity_tier": 1},
    {"ticker": "NESN", "asset_class": "Equity", "sector": "Consumer", "region": "ExUS", "liquidity_tier": 1},
    {"ticker": "SAP", "asset_class": "Equity", "sector": "Technology", "region": "ExUS", "liquidity_tier": 1},
    {"ticker": "ASML", "asset_class": "Equity", "sector": "Technology", "region": "ExUS", "liquidity_tier": 1},
    {"ticker": "SHEL", "asset_class": "Equity", "sector": "Energy", "region": "ExUS", "liquidity_tier": 1},
    {"ticker": "RIO", "asset_class": "Equity", "sector": "Materials", "region": "ExUS", "liquidity_tier": 2},
    # Emerging Markets
    {"ticker": "BABA", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 2},
    {"ticker": "TCEHY", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 2},
    {"ticker": "INFY", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 2},
    # Bonds
    {"ticker": "TLT", "asset_class": "Bonds", "sector": "Broad", "region": "US", "liquidity_tier": 1},
    {"ticker": "AGG", "asset_class": "Bonds", "sector": "Broad", "region": "US", "liquidity_tier": 1},
    {"ticker": "BND", "asset_class": "Bonds", "sector": "Broad", "region": "US", "liquidity_tier": 1},
    {"ticker": "VCIT", "asset_class": "Bonds", "sector": "Corporate", "region": "US", "liquidity_tier": 1},
    {"ticker": "EMB", "asset_class": "Bonds", "sector": "EM", "region": "EM", "liquidity_tier": 2},
    {"ticker": "IGSB", "asset_class": "Bonds", "sector": "Corporate", "region": "US", "liquidity_tier": 1},
    # Commodities / Alternatives
    {"ticker": "GLD", "asset_class": "Commodity", "sector": "Precious", "region": "US", "liquidity_tier": 1},
    {"ticker": "SLV", "asset_class": "Commodity", "sector": "Precious", "region": "US", "liquidity_tier": 1},
    {"ticker": "USO", "asset_class": "Commodity", "sector": "Energy", "region": "US", "liquidity_tier": 1},
    {"ticker": "REET", "asset_class": "Commodity", "sector": "Real Estate", "region": "US", "liquidity_tier": 2},
    # Crypto
    {"ticker": "BTC", "asset_class": "Crypto", "sector": "Digital", "region": "US", "liquidity_tier": 3},
    {"ticker": "ETH", "asset_class": "Crypto", "sector": "Digital", "region": "US", "liquidity_tier": 3},
]


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    """Pick a key according to a weight map."""
    keys = list(weights.keys())
    values = [weights[k] for k in keys]
    return rng.choices(keys, weights=values, k=1)[0]


def _sample_holdings(
    rng: random.Random,
    n: int,
    asset_class_bias: dict[str, float] | None,
) -> list[Holding]:
    """Sample n distinct holdings from the universe with optional asset-class bias."""
    universe = list(_UNIVERSE)
    if asset_class_bias:
        # Bias selection probability toward the desired asset class.
        weights = []
        for u in universe:
            base = 1.0
            ac = u.get("asset_class")
            if ac in asset_class_bias:
                base *= asset_class_bias[ac]
            weights.append(max(base, 0.05))
        selected = rng.sample(universe, counts=[int(w * 100) for w in weights], k=n)
    else:
        selected = rng.sample(universe, k=n)

    holdings: list[Holding] = []
    for info in selected:
        # Realistic price range per asset class.
        if info["asset_class"] == "Crypto":
            price = rng.lognormvariate(7.5, 1.2)  # ~$1k-$50k
        elif info["asset_class"] == "Commodity":
            price = rng.lognormvariate(3.0, 0.5)  # ~$10-$100
        elif info["asset_class"] == "Bonds":
            price = rng.lognormvariate(4.6, 0.15)  # ~$90-$110
        else:
            price = rng.lognormvariate(4.5, 0.6)  # ~$40-$300

        units = rng.lognormvariate(2.0, 1.0)
        holdings.append(
            Holding(
                ticker=info["ticker"],
                asset_class=info["asset_class"],
                sector=info["sector"],
                region=info["region"],
                liquidity_tier=info["liquidity_tier"],
                units=round(units, 4),
                price=round(price, 2),
            )
        )
    return holdings


def _apply_breach_bias(
    holdings: list[Holding],
    cash: float,
    rng: random.Random,
    mode: str,
) -> list[Holding]:
    """Skew a portfolio so it likely violates common mandate rules.

    Modes:
        - "single_holding": one ticker dominates.
        - "asset_class": one asset class dominates.
        - "region": one region dominates.
        - "none": return unchanged.
    """
    if mode == "none" or not holdings:
        return holdings

    if mode == "single_holding":
        target = rng.choice(holdings)
        factor = rng.uniform(5.0, 12.0)
        target.units = round(target.units * factor, 6)
        target.market_value = round(target.units * target.price, 2)
        return holdings

    if mode == "asset_class":
        target_class = rng.choice([h.asset_class for h in holdings if h.asset_class])
        factor = rng.uniform(3.0, 7.0)
        for h in holdings:
            if h.asset_class == target_class:
                h.units = round(h.units * factor, 6)
                h.market_value = round(h.units * h.price, 2)
        return holdings

    if mode == "region":
        target_region = rng.choice([h.region for h in holdings if h.region])
        factor = rng.uniform(3.0, 7.0)
        for h in holdings:
            if h.region == target_region:
                h.units = round(h.units * factor, 6)
                h.market_value = round(h.units * h.price, 2)
        return holdings

    return holdings


@dataclass
class PortfolioGenerator:
    """Configurable, seedable generator for synthetic portfolios.

    Example:
        >>> gen = PortfolioGenerator(seed=42, n_holdings=(5, 15))
        >>> portfolios = gen.generate(10_000)
    """

    seed: int | None = None
    client_id_prefix: str = "SYN"
    n_holdings: tuple[int, int] = (5, 15)
    total_value_mean: float = 1_000_000.0
    total_value_std: float = 400_000.0
    cash_ratio: tuple[float, float] = (0.05, 0.20)
    breach_bias_mode: str = "none"  # none | single_holding | asset_class | region
    breach_bias_prob: float = 0.0  # probability a portfolio is skewed toward a breach
    asset_class_bias: dict[str, float] | None = None
    rng_factory: Callable[[int | None], random.Random] = random.Random

    def __post_init__(self):
        self._rng = self.rng_factory(self.seed)

    def generate(self, n: int = 1) -> list[Portfolio]:
        """Generate n synthetic portfolios."""
        portfolios: list[Portfolio] = []
        for i in range(n):
            # total portfolio value ~ log-normal
            log_total = self._rng.gauss(
                mu=0.0,
                sigma=1.0,
            )
            total_value = self.total_value_mean * (1 + log_total * (self.total_value_std / self.total_value_mean))
            total_value = max(total_value, 10_000.0)

            n_h = self._rng.randint(self.n_holdings[0], self.n_holdings[1])
            holdings = _sample_holdings(self._rng, n_h, self.asset_class_bias)

            if self._rng.random() < self.breach_bias_prob:
                holdings = _apply_breach_bias(
                    holdings, 0.0, self._rng, self.breach_bias_mode
                )

            # Compute current holdings value and set cash residual.
            holdings_value = sum(h.market_value or 0.0 for h in holdings)
            if holdings_value == 0.0:
                cash = total_value
            else:
                cash_ratio = self._rng.uniform(self.cash_ratio[0], self.cash_ratio[1])
                # Adjust holdings proportionally so cash ratio is honored.
                target_holdings_value = total_value * (1 - cash_ratio)
                scale = target_holdings_value / holdings_value
                for h in holdings:
                    h.units = round(h.units * scale, 6)
                    h.market_value = round(h.units * h.price, 2)
                cash = total_value - sum(h.market_value or 0.0 for h in holdings)
                cash = max(cash, 0.0)

            portfolios.append(
                Portfolio(
                    client_id=f"{self.client_id_prefix}-{i:06d}",
                    cash=round(cash, 2),
                    holdings=holdings,
                    fum=round(total_value, 2),
                )
            )
        return portfolios


def generate_portfolios(
    n: int = 1,
    seed: int | None = None,
    **kwargs,
) -> list[Portfolio]:
    """Convenience function to generate synthetic portfolios.

    Args:
        n: Number of portfolios to generate.
        seed: Optional seed for reproducibility.
        **kwargs: Passed to PortfolioGenerator (e.g., breach_bias_mode, n_holdings).

    Returns:
        A list of Portfolio objects ready for the assurance engine.
    """
    return PortfolioGenerator(seed=seed, **kwargs).generate(n)
