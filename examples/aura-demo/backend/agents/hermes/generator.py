"""Generate a strategy YAML diff from synthetic simulation results.

Hermes 2.0 extension: run a short simulation for the current strategy, then
perturb each tunable variable one at a time and re-run. If a single-variable
change reduces projected breach incidence by at least 5%, emit a diff plus an
auto-generated regression test.

The generator is fast by default (prevent-only, single-direction perturbations)
for UI use. Expanded search (reactive + prevent baselines, bidirectional
perturbations, and optional Claude-assisted candidate ranking) is opt-in via
parameters or the ``HERMES_GENERATOR_LLM`` environment variable.
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any

from agents.hermes.strategy_io import load_strategy
from agents.hermes.loop import simulate_book
from agents.hermes.test_generator import generate_test
from agents.llm import ClaudeProvider, _extract_first_json_object

# Numeric strategy variables that are safe to perturb automatically.
TUNABLES = [
    "prevent_risk_threshold",
    "auto_approve_band",
    "min_trade_size",
    "cash_buffer_target",
    "prevent_horizon_days",
]

# Per-variable safe bounds and perturbation knobs. Bounds may be overridden by
# optional ``min`` / ``max`` keys placed alongside ``value`` in strategy.yaml.
_VAR_BOUNDS: dict[str, dict[str, Any]] = {
    "prevent_risk_threshold": {"min": 0.0, "max": 1.0, "factor": 0.1},
    "auto_approve_band": {"min": 0.0, "max": 0.2, "factor": 0.1},
    "min_trade_size": {"min": 0.0, "max": 0.1, "factor": 0.1},
    "cash_buffer_target": {"min": 0.0, "max": 0.5, "factor": 0.1},
    "prevent_horizon_days": {"min": 1, "max": 90, "step": 1},
}


LLM_SYSTEM_PROMPT = (
    "You are a strategy optimization assistant for a portfolio assurance system. "
    "Recommend which tunable variables to perturb to reduce future breach incidence. "
    "Return STRICT JSON only."
)


def _var_bounds(var: str, strategy: dict) -> dict[str, Any]:
    """Return bounds for *var*, preferring strategy.yaml metadata if present."""
    defaults = _VAR_BOUNDS.get(var, {})
    meta = strategy.get("variables", {}).get(var, {})
    return {
        "min": meta.get("min", defaults.get("min")),
        "max": meta.get("max", defaults.get("max")),
        "step": meta.get("step", defaults.get("step")),
        "factor": meta.get("factor", defaults.get("factor", 0.1)),
    }


def _clamp_int(value: int, bounds: dict[str, Any]) -> int:
    if bounds.get("min") is not None:
        value = max(bounds["min"], value)
    if bounds.get("max") is not None:
        value = min(bounds["max"], value)
    return value


def _clamp_float(value: float, bounds: dict[str, Any]) -> float:
    if bounds.get("min") is not None:
        value = max(float(bounds["min"]), value)
    if bounds.get("max") is not None:
        value = min(float(bounds["max"]), value)
    return round(value, 6)


def _candidates(var: str, current: Any, strategy: dict, bidirectional: bool = False) -> list[Any]:
    """Generate perturbation candidates for *var* within safe bounds.

    By default (``bidirectional=False``) only an upward/multiplicative step is
    tried, keeping the generator fast enough for UI use. When expanded search is
    enabled both upward and downward moves are attempted.
    """
    bounds = _var_bounds(var, strategy)
    if isinstance(current, bool):
        return [not current]
    if isinstance(current, int):
        step = bounds.get("step") or 1
        cands: list[int] = [current + step]
        if bidirectional:
            cands.insert(0, current - step)
        return list(dict.fromkeys(_clamp_int(v, bounds) for v in cands))
    if isinstance(current, float):
        factor = 1.0 + bounds.get("factor", 0.1)
        cands = [round(current * factor, 4)]
        if bidirectional:
            cands.insert(0, round(current / factor, 4))
        return list(dict.fromkeys(_clamp_float(v, bounds) for v in cands))
    return []


def _simulate(strategy: dict, days: int, seed: int, mode: str) -> dict:
    return simulate_book(days=days, mode=mode, seed=seed, strategy=strategy)


def _should_use_llm(use_llm: bool | None) -> bool:
    if use_llm is not None:
        return use_llm
    return os.environ.get("HERMES_GENERATOR_LLM", "").lower() in ("1", "true", "yes")


def _llm_suggest_vars(
    strategy: dict,
    breach_history: list[dict] | None,
    provider: ClaudeProvider,
) -> list[str]:
    """Ask the LLM which tunables to perturb first, based on recent breach history.

    Falls back to the default TUNABLES order if the LLM response cannot be parsed
    or the provider is unavailable. This keeps tests offline-safe when the
    autouse MockLLM fixture is active.
    """
    variables = strategy.get("variables", {})
    lines = []
    for name in TUNABLES:
        if name in variables:
            lines.append(f"- {name}: current={variables[name].get('value')}")
    if not lines:
        return list(TUNABLES)

    user = (
        f"Recent breach history:\n{json.dumps(breach_history or [], indent=2)}\n\n"
        f"Tunable strategy variables:\n" + "\n".join(lines) + "\n\n"
        "Recommend the top 3 variables to perturb to reduce future breach incidence. "
        "Return ONLY a JSON object with key 'variables' containing a list of variable names "
        "in priority order, e.g. {\"variables\": [\"prevent_risk_threshold\", \"auto_approve_band\", \"min_trade_size\"]}."
    )
    try:
        text = provider.complete(system=LLM_SYSTEM_PROMPT, user=user)
    except Exception:
        return list(TUNABLES)

    obj = _extract_first_json_object(text)
    if obj and isinstance(obj.get("variables"), list):
        suggested = [v for v in obj["variables"] if v in TUNABLES]
        if suggested:
            return suggested

    # Last resort: any tunable name that happens to appear in the response,
    # preserving the canonical order so the result is deterministic.
    found = [v for v in TUNABLES if v in text]
    return found or list(TUNABLES)


def generate_diff(
    days: int = 7,
    seed: int = 42,
    modes: tuple[str, ...] = ("prevent",),
    bidirectional: bool = False,
    use_llm: bool | None = None,
    llm_provider: Any = None,
    recent_breach_history: list[dict] | None = None,
) -> dict[str, Any]:
    """Run synthetic reality against baseline + perturbations; return best diff.

    Args:
        days: simulation length.
        seed: deterministic RNG seed.
        modes: which simulation modes to evaluate. Default is ("prevent",) for
            speed. Expanded search can pass ("reactive", "prevent").
        bidirectional: if True, try both upward and downward perturbations for
            each numeric variable (within safe bounds). Default is False.
        use_llm: if True, ask a Claude LLM to rank candidate variables. When
            None, the ``HERMES_GENERATOR_LLM`` environment variable is consulted.
        llm_provider: optional LLM provider override (tests can inject
            MockLLM or a fake here). When omitted and use_llm is True, a
            ``ClaudeProvider`` is instantiated.
        recent_breach_history: optional breach history payload for the LLM.

    Returns:
        Dict with keys ``ok``, ``diff``, ``simulation``, and optionally ``test``.
    """
    baseline = load_strategy()
    baseline_by_mode: dict[str, int] = {}
    for mode in modes:
        baseline_result = _simulate(baseline, days=days, seed=seed, mode=mode)
        baseline_by_mode[mode] = baseline_result.get(
            "reactive_incidence" if mode == "reactive" else "prevent_incidence", 0
        ) or 0

    # Determine the order in which to try tunables.
    want_llm = _should_use_llm(use_llm)
    if want_llm:
        provider = llm_provider if llm_provider is not None else ClaudeProvider()
        llm_order = _llm_suggest_vars(baseline, recent_breach_history, provider)
    else:
        llm_order = []
    # Ensure every tunable is tried even if the LLM omits some.
    ordered_tunables = list(dict.fromkeys(llm_order + [v for v in TUNABLES if v not in llm_order]))

    best: dict[str, Any] = {"improvement": 0.0, "diff": None, "after": None, "mode": None}

    for var in ordered_tunables:
        if var not in baseline.get("variables", {}):
            continue
        current = baseline["variables"][var]["value"]
        candidates = _candidates(var, current, baseline, bidirectional=bidirectional)
        for cand in candidates:
            candidate = copy.deepcopy(baseline)
            candidate["variables"][var]["value"] = cand
            for mode in modes:
                result = _simulate(candidate, days=days, seed=seed, mode=mode)
                after_incidence = result.get(
                    "reactive_incidence" if mode == "reactive" else "prevent_incidence", 0
                ) or 0
                baseline_incidence = baseline_by_mode[mode]
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
                            "mode": mode,
                            "rationale": (
                                f"Synthetic {mode}-mode run (seed {seed}, {days} days) showed "
                                f"{improvement * 100:.1f}% fewer projected breaches when "
                                f"{var} changed from {current} to {cand}."
                            ),
                        },
                        "after": result,
                        "mode": mode,
                    }

    out: dict[str, Any] = {
        "ok": True,
        "diff": best["diff"],
        "simulation": {
            "reactive_incidence": baseline_by_mode.get("reactive"),
            "prevent_incidence_before": baseline_by_mode.get("prevent"),
            "prevent_incidence_after": (
                best["after"].get("prevent_incidence")
                if best["after"] and best["mode"] == "prevent"
                else baseline_by_mode.get("prevent")
            ),
            "reactive_incidence_after": (
                best["after"].get("reactive_incidence")
                if best["after"] and best["mode"] == "reactive"
                else None
            ),
            "improvement_pct": round(best["improvement"] * 100, 1) if best["diff"] else 0.0,
            "modes_run": list(modes),
        },
    }
    if best["diff"]:
        out["test"] = generate_test(best["diff"], out["simulation"], seed=seed)
    return out
