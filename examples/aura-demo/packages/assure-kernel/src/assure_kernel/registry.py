"""Rule registry for extensible mandate rules."""

from collections.abc import Callable
from typing import Any, overload

from assure_kernel.models import Portfolio, Rule, RuleEvaluation, Violation

RuleEvaluator = Callable[[Rule, Portfolio, float, dict[str, Any]], tuple[list[RuleEvaluation], list[Violation], list[Violation]]]

_REGISTRY: dict[str, RuleEvaluator] = {}


@overload
def register(rule_type: str) -> Callable[[RuleEvaluator], RuleEvaluator]: ...


@overload
def register(rule_type: str, fn: RuleEvaluator) -> RuleEvaluator: ...


def register(rule_type: str, fn: RuleEvaluator | None = None):
    """Register an evaluator for a rule type.

    May be used as a decorator (`@register("type")`) or as a direct call
    (`register("type", evaluator)`).
    """
    if fn is not None:
        _REGISTRY[rule_type] = fn
        return fn

    def decorator(func: RuleEvaluator) -> RuleEvaluator:
        _REGISTRY[rule_type] = func
        return func

    return decorator


def get(rule_type: str) -> RuleEvaluator | None:
    return _REGISTRY.get(rule_type)


def list_rules() -> list[str]:
    return sorted(_REGISTRY.keys())


def has(rule_type: str) -> bool:
    return rule_type in _REGISTRY
