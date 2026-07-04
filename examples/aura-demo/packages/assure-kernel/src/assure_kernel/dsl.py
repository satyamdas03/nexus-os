"""Declarative mandate DSL loader.

Supports YAML/JSON mandate files with a regulator-reviewable rule grammar,
plus round-trip conversion from/to the legacy Python-dict format used by the
original aura-demo.
"""

from pathlib import Path
from typing import Any

import yaml

from assure_kernel.engine import _mandate_from_dict, evaluate_portfolio
from assure_kernel.models import Mandate, Portfolio, Rule, RulesResult


# Canonical mapping from DSL rule type names to kernel rule types.
DSL_TYPE_MAP = {
    "asset_class_weight": "max_asset_class_weight",
    "sector_weight": "max_sector_weight",
    "approved_universe": "approved_universe",
    "single_holding": "max_single_holding",
    "minimum_cash": "min_cash",
    "target_allocation": "target_allocation_drift",
    "region_weight": "max_region_weight",
    "excluded_tickers": "esg_exclusions",
    "top_n_concentration": "max_top_n_concentration",
    "minimum_liquidity": "min_liquid_pct",
    # Allow canonical names directly too.
    "max_asset_class_weight": "max_asset_class_weight",
    "max_sector_weight": "max_sector_weight",
    "max_single_holding": "max_single_holding",
    "min_cash": "min_cash",
    "target_allocation_drift": "target_allocation_drift",
    "max_region_weight": "max_region_weight",
    "esg_exclusions": "esg_exclusions",
    "max_top_n_concentration": "max_top_n_concentration",
    "min_liquid_pct": "min_liquid_pct",
}


def _normalize_rule_type(dsl_type: str) -> str:
    """Map a DSL rule type to the kernel canonical rule type."""
    if dsl_type.startswith("custom:"):
        return dsl_type
    canonical = DSL_TYPE_MAP.get(dsl_type)
    if canonical is None:
        raise ValueError(f"Unknown DSL rule type: {dsl_type}")
    return canonical


def _params_from_dsl(rule_type: str, dsl_params: dict[str, Any]) -> dict[str, Any]:
    """Normalize DSL parameters to the runtime parameter shape."""
    if rule_type in ("max_asset_class_weight", "max_sector_weight", "max_region_weight"):
        return {"weights": dsl_params.get("max_weights", {})}
    if rule_type == "approved_universe":
        return {"tickers": dsl_params.get("tickers", [])}
    if rule_type == "max_single_holding":
        return {"limit": dsl_params.get("max_weight", 1.0)}
    if rule_type == "min_cash":
        return {"limit": dsl_params.get("min_weight", 0.0)}
    if rule_type == "target_allocation_drift":
        return {
            "targets": dsl_params.get("targets", {}),
            "drift_tolerance": dsl_params.get("drift_tolerance", 0.05),
        }
    if rule_type == "esg_exclusions":
        return {"tickers": dsl_params.get("tickers", [])}
    if rule_type == "max_top_n_concentration":
        return {
            "n": dsl_params.get("n", 5),
            "limit": dsl_params.get("max_weight", 1.0),
        }
    if rule_type == "min_liquid_pct":
        return {"limit": dsl_params.get("min_liquid_pct", 0.0)}
    # custom:* and unknown pass params through.
    return dict(dsl_params)


def load_mandate(path: str | Path) -> Mandate:
    """Load a mandate from a YAML or JSON file."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if path.suffix in (".yaml", ".yml") else __import__("json").loads(raw)
    return parse_mandate(data)


def parse_mandate(data: dict[str, Any]) -> Mandate:
    """Parse a mandate dict (DSL or legacy) into a kernel Mandate."""
    # Legacy flat dicts have top-level rule keys like max_asset_class_weight.
    legacy_keys = {
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
    }
    if any(k in data for k in legacy_keys):
        return _mandate_from_dict(data)

    mandate_section = data.get("mandate", data)
    rules: list[Rule] = []
    for raw_rule in mandate_section.get("rules", []):
        rule_type = _normalize_rule_type(raw_rule["type"])
        params = _params_from_dsl(rule_type, raw_rule.get("parameters", {}))
        rules.append(
            Rule(
                type=rule_type,
                params=params,
                enabled=raw_rule.get("enabled", True),
                severity=raw_rule.get("severity"),
                message=raw_rule.get("message"),
            )
        )

    return Mandate(
        id=mandate_section.get("id"),
        name=mandate_section.get("name"),
        version=mandate_section.get("version", "1.0.0"),
        rules=rules,
        metadata=mandate_section.get("metadata"),
    )


def to_legacy_dict(mandate: Mandate) -> dict[str, Any]:
    """Convert a kernel Mandate back into the legacy aura-demo dict shape."""
    out: dict[str, Any] = {
        "id": mandate.id,
        "name": mandate.name,
        "version": mandate.version,
    }
    if mandate.metadata:
        out["metadata"] = mandate.metadata

    for rule in mandate.rules:
        if not rule.enabled:
            continue
        rt = rule.type
        p = rule.params
        if rt == "max_asset_class_weight":
            out.setdefault("max_asset_class_weight", {}).update(p.get("weights", {}))
        elif rt == "max_sector_weight":
            out.setdefault("max_sector_weight", {}).update(p.get("weights", {}))
        elif rt == "approved_universe":
            out["approved_universe"] = p.get("tickers", [])
        elif rt == "max_single_holding":
            out["max_single_holding"] = p.get("limit", 1.0)
        elif rt == "min_cash":
            out["min_cash"] = p.get("limit", 0.0)
        elif rt == "target_allocation_drift":
            out["target_allocation"] = p.get("targets", {})
            out["drift_tolerance"] = p.get("drift_tolerance", 0.05)
        elif rt == "max_region_weight":
            out.setdefault("max_region_weight", {}).update(p.get("weights", {}))
        elif rt == "esg_exclusions":
            out["excluded_tickers"] = p.get("tickers", [])
        elif rt == "max_top_n_concentration":
            out["max_top_n_concentration"] = {"n": p.get("n", 5), "limit": p.get("limit", 1.0)}
        elif rt == "min_liquid_pct":
            out["min_liquid_pct"] = p.get("limit", 0.0)
    return out


def dump_mandate(mandate: Mandate, path: str | Path) -> None:
    """Write a mandate to a YAML file in the DSL format."""
    path = Path(path)
    rules_section = []
    for rule in mandate.rules:
        rules_section.append(
            {
                "id": rule.params.get("id") if "id" in rule.params else None,
                "type": rule.type,
                "enabled": rule.enabled,
                "severity": rule.severity,
                "message": rule.message,
                "parameters": rule.params,
            }
        )
    document = {
        "mandate": {
            "id": mandate.id,
            "name": mandate.name,
            "version": mandate.version,
            "metadata": mandate.metadata,
            "rules": [r for r in rules_section if r["id"] is not None or True],
        }
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(document, f, sort_keys=False)


# Re-export evaluate_portfolio so `from assure_kernel.dsl import evaluate_portfolio` works.
__all__ = [
    "load_mandate",
    "parse_mandate",
    "to_legacy_dict",
    "dump_mandate",
    "evaluate_portfolio",
]
