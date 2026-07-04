"""Mandate template library for the 34k synthetic book.

A *mandate* is the immutable LAW for a portfolio — the rules engine checks
against it and Hermes may never modify it. There are 10 rule dimensions:

  1. max_asset_class_weight   (per asset-class cap)
  2. max_sector_weight        (per sector cap)
  3. approved_universe        (allowed tickers)
  4. max_single_holding       (max weight in one ticker)
  5. min_cash                 (min cash ratio)
  6. target_allocation + drift_tolerance  (one-sided drift watch)
  7. max_region_weight        (per region cap)
  8. excluded_tickers         (ESG exclusion list)
  9. max_top_n_concentration  (top-N weight cap)
 10. min_liquid_pct           (min weight in tier-1)

Templates are now declarative YAML files under `data/mandates/` using the
ASSURE kernel DSL. This module loads a template, applies instance-level
jitter, samples sector caps and approved/excluded ticker sets, and returns a
legacy aura-demo mandate dict so existing storage and checks keep working.
"""
import json
import random
from pathlib import Path

from assure_kernel import Mandate, Rule, load_mandate, to_legacy_dict
from generators import universe as U


_TEMPLATE_DIR = Path(__file__).parent.parent / "data" / "mandates"
_TEMPLATE_FILES = [f"t{i}.yaml" for i in range(8)]


def template_count() -> int:
    return len(_TEMPLATE_FILES)


def load_template(idx: int) -> Mandate:
    """Load a base mandate template from the DSL YAML library."""
    return load_mandate(_TEMPLATE_DIR / _TEMPLATE_FILES[idx % template_count()])


def _jitter(base: float, lo: float, hi: float, rng: random.Random) -> float:
    return round(rng.uniform(base * lo, base * hi), 3)


def _jitter_rule(rule: Rule, rng: random.Random) -> Rule:
    """Apply instance-level jitter to a base rule's numeric parameters."""
    rt = rule.type
    p = dict(rule.params)
    if rt == "max_asset_class_weight":
        # Cash is always 100% allowed; do not jitter it.
        p["weights"] = {
            k: (v if k == "Cash" else _jitter(v, 0.95, 1.05, rng))
            for k, v in p.get("weights", {}).items()
        }
    elif rt == "max_region_weight":
        p["weights"] = {k: _jitter(v, 0.95, 1.05, rng) for k, v in p.get("weights", {}).items()}
    elif rt == "max_single_holding":
        p["limit"] = _jitter(p.get("limit", 1.0), 0.90, 1.10, rng)
    elif rt == "min_cash":
        p["limit"] = _jitter(p.get("limit", 0.0), 0.80, 1.20, rng)
    elif rt == "target_allocation_drift":
        p["targets"] = {k: _jitter(v, 0.95, 1.05, rng) for k, v in p.get("targets", {}).items()}
    elif rt == "max_top_n_concentration":
        p["limit"] = _jitter(p.get("limit", 1.0), 0.95, 1.05, rng)
    elif rt == "min_liquid_pct":
        p["limit"] = _jitter(p.get("limit", 0.0), 0.90, 1.10, rng)
    return Rule(type=rt, params=p, enabled=rule.enabled, severity=rule.severity, message=rule.message)


def _sector_rule(rng: random.Random, cap: float) -> Rule:
    """Sample a small set of sectors to cap; others remain uncapped."""
    sectors = rng.sample(
        [s for s in U.SECTORS if s not in ("Broad", "Cash")],
        k=min(3, len(U.SECTORS) - 2),
    )
    return Rule(type="max_sector_weight", params={"weights": {s: cap for s in sectors}})


def _approved(rng: random.Random, size: int, allow_crypto: bool) -> list[str]:
    pool = [
        t
        for t in U.all_tickers()
        if U.UNIVERSE_BY_TICKER[t]["asset_class"] != "Crypto" or allow_crypto
    ]
    pool = [t for t in pool if t != "CASH"]
    size = min(size, len(pool))
    return sorted(rng.sample(pool, k=size))


def _excluded(rng: random.Random, approved: list[str], k: int) -> list[str]:
    if k <= 0 or len(approved) <= 4:
        return []
    return sorted(rng.sample(approved, k=min(k, len(approved) - 4)))


def build_mandate(rng: random.Random, template_idx: int) -> dict:
    """Build a complete, valid mandate dict from a DSL template, applying
    instance-level jitter and randomizing sector caps / approved / excluded sets."""
    base = load_template(template_idx)
    meta = base.metadata or {}

    sector_cap = _jitter(float(meta.get("sector_cap_base", 0.30)), 0.90, 1.10, rng)
    approved = _approved(rng, int(meta.get("approved_n", 18)), bool(meta.get("allow_crypto", True)))
    excluded = _excluded(rng, approved, int(meta.get("excl_k", 0)))

    rules = [_jitter_rule(r, rng) for r in base.rules]
    rules.append(_sector_rule(rng, sector_cap))
    rules.append(Rule(type="approved_universe", params={"tickers": approved}))
    rules.append(Rule(type="esg_exclusions", params={"tickers": excluded}))

    mandate = Mandate(
        id=base.id,
        name=base.name,
        version=base.version,
        rules=rules,
        metadata=base.metadata,
    )
    return to_legacy_dict(mandate)


def is_valid_mandate(m: dict) -> bool:
    try:
        for k in (
            "max_asset_class_weight",
            "max_sector_weight",
            "approved_universe",
            "max_single_holding",
            "min_cash",
            "target_allocation",
            "drift_tolerance",
            "max_region_weight",
            "excluded_tickers",
            "max_top_n_concentration",
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
