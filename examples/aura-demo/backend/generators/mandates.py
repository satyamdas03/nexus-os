"""Mandate template library for the 34k synthetic book.

A *mandate* is the immutable LAW for a portfolio — the rules engine checks
against it and Hermes may never modify it. There are 10 rule dimensions:

  1. max_asset_class_weight   (per asset-class cap)
  2. max_sector_weight        (per sector cap)
  3. approved_universe        (allowed tickers)
  4. max_single_holding       (max weight in one ticker)
  5. min_cash                 (min cash ratio)
  6. target_allocation + drift_tolerance  (one-sided drift watch)
  7. max_region_weight        (per region cap)        [NEW]
  8. excluded_tickers         (ESG exclusion list)    [NEW]
  9. max_top_n_concentration  (top-N weight cap)      [NEW]
 10. min_liquid_pct           (min weight in tier-1)  [NEW]

Templates are base mandates with placeholder params; build_mandate randomizes
the numeric caps and the approved/excluded ticker sets per portfolio so the
34k book has genuinely diverse, complex mandates. ~34k portfolios share a
small library of templates (mandates are deduped in generate_data by their
JSON spec, so far fewer than 34k mandate rows).
"""
import json
import random

from generators import universe as U


def _ac_caps(rng, equity_cap, bond_cap, commodity_cap, crypto_cap):
    return {
        "Equity": equity_cap,
        "Bonds": bond_cap,
        "Commodity": commodity_cap,
        "Crypto": crypto_cap,
        "Cash": 1.0,
    }


def _sector_caps(rng, cap):
    # cap a handful of sectors; leave others uncapped (omitted key = no cap)
    sectors = rng.sample([s for s in U.SECTORS if s not in ("Broad", "Cash")], k=min(3, len(U.SECTORS) - 2))
    return {s: cap for s in sectors}


def _region_caps(rng, us_cap, exus_cap, em_cap):
    return {"US": us_cap, "ExUS": exus_cap, "EM": em_cap}


def _approved(rng, size, allow_crypto):
    pool = [t for t in U.all_tickers() if U.UNIVERSE_BY_TICKER[t]["asset_class"] != "Crypto" or allow_crypto]
    pool = [t for t in pool if t != "CASH"]
    size = min(size, len(pool))
    return sorted(rng.sample(pool, k=size))


def _excluded(rng, approved, k):
    if k <= 0 or len(approved) <= 4:
        return []
    return sorted(rng.sample(approved, k=min(k, len(approved) - 4)))


# Each template: a function(rng) -> dict of params. Templates vary in risk
# appetite, region tilt, ESG strictness, concentration tolerance, liquidity
# floor — so the book spans conservative to aggressive mandates.
_TEMPLATES = [
    # 0: balanced growth
    lambda r: dict(name="balanced_growth", ac=_ac_caps(r, 0.80, 0.30, 0.10, 0.05),
                   sec=_sector_caps(r, 0.30), reg=_region_caps(r, 0.70, 0.35, 0.15),
                   single=0.12, min_cash=0.05, target={"Equity": 0.65, "Bonds": 0.25},
                   drift=0.08, approved_n=18, crypto=True, excl_k=2,
                   topn={"n": 5, "limit": 0.55}, min_liq=0.40),
    # 1: conservative income
    lambda r: dict(name="conservative_income", ac=_ac_caps(r, 0.45, 0.60, 0.05, 0.0),
                   sec=_sector_caps(r, 0.20), reg=_region_caps(r, 0.85, 0.25, 0.05),
                   single=0.10, min_cash=0.10, target={"Equity": 0.35, "Bonds": 0.55},
                   drift=0.06, approved_n=14, crypto=False, excl_k=3,
                   topn={"n": 5, "limit": 0.45}, min_liq=0.60),
    # 2: aggressive growth
    lambda r: dict(name="aggressive_growth", ac=_ac_caps(r, 0.95, 0.15, 0.15, 0.15),
                   sec=_sector_caps(r, 0.40), reg=_region_caps(r, 0.60, 0.40, 0.25),
                   single=0.20, min_cash=0.02, target={"Equity": 0.85, "Bonds": 0.10},
                   drift=0.12, approved_n=20, crypto=True, excl_k=1,
                   topn={"n": 5, "limit": 0.70}, min_liq=0.25),
    # 3: ESG strict (big exclusion list, no crypto, no EM tilt)
    lambda r: dict(name="esg_strict", ac=_ac_caps(r, 0.75, 0.35, 0.10, 0.0),
                   sec=_sector_caps(r, 0.25), reg=_region_caps(r, 0.75, 0.40, 0.05),
                   single=0.12, min_cash=0.06, target={"Equity": 0.60, "Bonds": 0.30},
                   drift=0.07, approved_n=16, crypto=False, excl_k=6,
                   topn={"n": 5, "limit": 0.50}, min_liq=0.50),
    # 4: EM-tilted
    lambda r: dict(name="em_tilt", ac=_ac_caps(r, 0.85, 0.20, 0.10, 0.05),
                   sec=_sector_caps(r, 0.30), reg=_region_caps(r, 0.50, 0.30, 0.35),
                   single=0.15, min_cash=0.04, target={"Equity": 0.75, "Bonds": 0.15},
                   drift=0.10, approved_n=17, crypto=True, excl_k=1,
                   topn={"n": 5, "limit": 0.60}, min_liq=0.35),
    # 5: concentrated high-conviction (loose top-N, tight single-name)
    lambda r: dict(name="high_conviction", ac=_ac_caps(r, 0.90, 0.20, 0.10, 0.05),
                   sec=_sector_caps(r, 0.35), reg=_region_caps(r, 0.65, 0.35, 0.20),
                   single=0.18, min_cash=0.03, target={"Equity": 0.80, "Bonds": 0.12},
                   drift=0.10, approved_n=15, crypto=True, excl_k=0,
                   topn={"n": 3, "limit": 0.65}, min_liq=0.30),
    # 6: liquidity-floored (strict min_liquid_pct)
    lambda r: dict(name="liquid_floored", ac=_ac_caps(r, 0.70, 0.40, 0.08, 0.0),
                   sec=_sector_caps(r, 0.22), reg=_region_caps(r, 0.80, 0.30, 0.10),
                   single=0.11, min_cash=0.08, target={"Equity": 0.55, "Bonds": 0.35},
                   drift=0.07, approved_n=13, crypto=False, excl_k=2,
                   topn={"n": 5, "limit": 0.48}, min_liq=0.75),
    # 7: region-capped (tight US cap to force ex-US/EM)
    lambda r: dict(name="region_capped", ac=_ac_caps(r, 0.88, 0.25, 0.12, 0.05),
                   sec=_sector_caps(r, 0.28), reg=_region_caps(r, 0.45, 0.45, 0.30),
                   single=0.14, min_cash=0.05, target={"Equity": 0.72, "Bonds": 0.18},
                   drift=0.09, approved_n=18, crypto=True, excl_k=1,
                   topn={"n": 5, "limit": 0.58}, min_liq=0.40),
]


def template_count() -> int:
    return len(_TEMPLATES)


def build_mandate(rng: random.Random, template_idx: int) -> dict:
    """Build a complete, valid mandate dict from template `template_idx`,
    randomizing numeric caps within a small band so 34k mandates differ."""
    p = _TEMPLATES[template_idx % len(_TEMPLATES)](rng)

    def jitter(base, lo, hi):
        return round(rng.uniform(base * lo, base * hi), 3)

    ac = {k: (v if k == "Cash" else round(jitter(v, 0.95, 1.05), 3)) for k, v in p["ac"].items()}
    sec = {k: round(jitter(v, 0.90, 1.10), 3) for k, v in p["sec"].items()}
    reg = {k: round(jitter(v, 0.95, 1.05), 3) for k, v in p["reg"].items()}
    approved = _approved(rng, p["approved_n"], p["crypto"])
    excluded = _excluded(rng, approved, p["excl_k"])
    single = round(jitter(p["single"], 0.90, 1.10), 3)
    min_cash = round(jitter(p["min_cash"], 0.80, 1.20), 3)
    target = {k: round(jitter(v, 0.95, 1.05), 3) for k, v in p["target"].items()}
    topn = {"n": p["topn"]["n"], "limit": round(jitter(p["topn"]["limit"], 0.95, 1.05), 3)}
    min_liq = round(jitter(p["min_liq"], 0.90, 1.10), 3)

    return {
        "name": p["name"],
        "max_asset_class_weight": ac,
        "max_sector_weight": sec,
        "approved_universe": approved,
        "max_single_holding": single,
        "min_cash": min_cash,
        "target_allocation": target,
        "drift_tolerance": p["drift"],
        "max_region_weight": reg,
        "excluded_tickers": excluded,
        "max_top_n_concentration": topn,
        "min_liquid_pct": min_liq,
    }


def is_valid_mandate(m: dict) -> bool:
    try:
        for k in (
            "max_asset_class_weight", "max_sector_weight", "approved_universe",
            "max_single_holding", "min_cash", "target_allocation", "drift_tolerance",
            "max_region_weight", "excluded_tickers", "max_top_n_concentration",
            "min_liquid_pct",
        ):
            if k not in m:
                return False
        real = set(U.all_tickers())
        if not (set(m["approved_universe"]) <= real and len(m["approved_universe"]) >= 4):
            return False
        if not set(m["excluded_tickers"]) <= set(m["approved_universe"]):
            return False
        for r in m["max_region_weight"]:
            if r not in U.REGIONS:
                return False
        for caps in (m["max_asset_class_weight"], m["max_sector_weight"], m["max_region_weight"]):
            for v in caps.values():
                if not (0.0 <= v <= 1.0):
                    return False
        if not (0.0 < m["max_single_holding"] <= 1.0):
            return False
        if not (0.0 <= m["min_cash"] <= 1.0):
            return False
        if not (0.0 < m["drift_tolerance"] <= 0.5):
            return False
        if not (0.0 <= m["min_liquid_pct"] <= 1.0):
            return False
        tn = m["max_top_n_concentration"]
        if not (isinstance(tn, dict) and 1 <= tn.get("n", 0) and 0.0 < tn.get("limit", 0) <= 1.0):
            return False
        # round-trip through JSON (mandates are stored as JSON blobs in SQLite)
        json.dumps(m)
        return True
    except Exception:
        return False