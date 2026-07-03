"""Seeded per-ticker geometric Brownian motion price model with sector
correlation. Deterministic given (ticker, day, seed). No numpy — stdlib only.

P(d) = P(d-1) * exp((mu - 0.5*sigma**2)*DT + sigma*sqrt(DT)*Z)
Z    = sector_factor * RHO + idiosyncratic * sqrt(1 - RHO**2)

sector_factor is drawn once per (seed, sector, day) and shared by every ticker
in that sector -> same-sector tickers co-move. idiosyncratic is drawn per
(seed, ticker, day). Normals come from Box-Muller on a seeded random.Random.

day 0 is the base price (no stochastic term). Recomputing price_for(t, d) walks
the path from 0..d each call; callers that need many days (tick precompute,
generate_data day-0) use prices_for_day. lru_cache makes repeated reads cheap.
"""
import math
import random
from functools import lru_cache

from generators import universe as U

DT = 1.0 / 252.0
_RHO = U.RHO
_IDIO_SCALE = math.sqrt(1.0 - _RHO * _RHO)


def _normal(rng: random.Random) -> float:
    u1 = rng.random() or 1e-12
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


@lru_cache(maxsize=None)
def _sector_factor(sector: str, day: int, seed: int) -> float:
    if day == 0:
        return 0.0
    # random.Random accepts str/bytes/int seeds; compose a string key so the
    # (seed, sector, day) tuple is reproducible across Python versions.
    return _normal(random.Random(f"{seed}|sec|{sector}|{day}"))


@lru_cache(maxsize=None)
def _idiosyncratic(ticker: str, day: int, seed: int) -> float:
    if day == 0:
        return 0.0
    return _normal(random.Random(f"{seed}|idio|{ticker}|{day}"))


@lru_cache(maxsize=None)
def price_for(ticker: str, day: int, seed: int) -> float:
    meta = U.UNIVERSE_BY_TICKER[ticker]
    if day == 0:
        return meta["base_price"]
    prev = price_for(ticker, day - 1, seed)
    mu = meta["mu"]; sigma = meta["sigma"]; sector = meta["sector"]
    z = _sector_factor(sector, day, seed) * _RHO + _idiosyncratic(ticker, day, seed) * _IDIO_SCALE
    drift = (mu - 0.5 * sigma * sigma) * DT + sigma * math.sqrt(DT) * z
    return prev * math.exp(drift)


def prices_for_day(day: int, seed: int) -> dict:
    return {t: price_for(t, day, seed) for t in U.all_tickers()}