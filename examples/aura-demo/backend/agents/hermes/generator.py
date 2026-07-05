"""Generate a strategy YAML diff from synthetic simulation results.

Hermes 2.0 extension: run a short prevent-mode simulation for the current
strategy, then perturb each tunable variable one at a time and re-run. If a
single-variable change reduces projected breach incidence by at least 5%, emit a
diff plus an auto-generated regression test.
"""
from __future__ import annotations

import copy
from typing import Any

from agents.hermes.strategy_io import load_strategy
from agents.hermes.loop import simulate_book
from agents.hermes.test_generator import generate_test

# Numeric strategy variables that are safe to perturb automatically.
TUNABLES = [
    "prevent_risk_threshold",
    "auto_approve_band",
    "min_trade_size",
    "cash_buffer_target",
    "prevent_horizon_days",
]


def _candidates(var: str, current: Any) -> list[Any]:
    # One directional perturbation keeps the generator fast enough for UI use.
    if isinstance(current, bool):
        return [not current]
    if isinstance(current, int):
        return [current + 1]
    if isinstance(current, float):
        return [round(current * 1.1, 4)]
    return []


def _simulate(strategy: dict, days: int, seed: int) -> dict:
    return simulate_book(days=days, mode="prevent", seed=seed, strategy=strategy)


def generate_diff(days: int = 7, seed: int = 42) -> dict[str, Any]:
    """Run synthetic reality against baseline + perturbations; return best diff."""
    baseline = load_strategy()
    baseline_result = _simulate(baseline, days=days, seed=seed)
    baseline_incidence = baseline_result.get("prevent_incidence", baseline_result.get("reactive_incidence", 0))
    if baseline_incidence is None:
        baseline_incidence = 0

    best: dict[str, Any] = {"improvement": 0.0, "diff": None, "after": None}

    for var in TUNABLES:
        if var not in baseline.get("variables", {}):
            continue
        current = baseline["variables"][var]["value"]
        candidates = _candidates(var, current)
        for cand in candidates:
            candidate = copy.deepcopy(baseline)
            candidate["variables"][var]["value"] = cand
            result = _simulate(candidate, days=days, seed=seed)
            after_incidence = result.get("prevent_incidence", result.get("reactive_incidence", 0))
            if after_incidence is None:
                after_incidence = baseline_incidence
            if baseline_incidence > 0:
                improvement = (baseline_incidence - after_incidence) / baseline_incidence
            else:
                improvement = 0.0 if after_incidence == 0 else -1.0
            if improvement > best["improvement"] and improvement >= 0.05:
                best = {
                    "improvement": improvement,
                    "diff": {
                        "variable": var,
                        "from": current,
                        "to": cand,
                        "rationale": (
                            f"Synthetic prevent-mode run (seed {seed}, {days} days) showed "
                            f"{improvement * 100:.1f}% fewer projected breaches when "
                            f"{var} changed from {current} to {cand}."
                        ),
                    },
                    "after": result,
                }

    out: dict[str, Any] = {
        "ok": True,
        "diff": best["diff"],
        "simulation": {
            "reactive_incidence": baseline_result.get("reactive_incidence"),
            "prevent_incidence_before": baseline_incidence,
            "prevent_incidence_after": best["after"].get("prevent_incidence") if best["after"] else baseline_incidence,
            "improvement_pct": round(best["improvement"] * 100, 1) if best["diff"] else 0.0,
        },
    }
    if best["diff"]:
        out["test"] = generate_test(best["diff"], out["simulation"], seed=seed)
    return out
