"""Deterministic portfolio assurance engine.

Pure functions, no I/O. The same Portfolio + Mandate always produces the
same RulesResult. AI agents propose; this engine verifies.
"""

from collections import Counter

from assure_kernel.models import (
    Holding,
    Mandate,
    Portfolio,
    Rule,
    RuleEvaluation,
    RulesResult,
    Violation,
)
from assure_kernel.registry import get, register
from assure_kernel.types import Severity, Status

_EPS = 1e-9


def _weights(portfolio: Portfolio) -> tuple[
    float,
    dict[str, float],
    dict[str, float],
    dict[str, float],
    dict[str, float],
    float,
    float,
]:
    """Single-pass computation of total value and all weight maps.

    Returns (total, ticker_weights, asset_class_weights, sector_weights,
             region_weights, liquidity_tier1_weight, cash_ratio).
    """
    total = portfolio.total_value
    if total == 0:
        return 0.0, {}, {}, {}, {}, 0.0, 0.0

    ticker_w: dict[str, float] = {}
    asset_w: dict[str, float] = {}
    sector_w: dict[str, float] = {}
    region_w: dict[str, float] = {}
    liq1 = 0.0

    for h in portfolio.holdings:
        mv = h.market_value or 0.0
        w = mv / total
        ticker_w[h.ticker] = ticker_w.get(h.ticker, 0.0) + w
        if h.asset_class:
            asset_w[h.asset_class] = asset_w.get(h.asset_class, 0.0) + w
        if h.sector:
            sector_w[h.sector] = sector_w.get(h.sector, 0.0) + w
        if h.region:
            region_w[h.region] = region_w.get(h.region, 0.0) + w
        if h.liquidity_tier == 1:
            liq1 += w

    return total, ticker_w, asset_w, sector_w, region_w, liq1, portfolio.cash / total


# ---------------------------------------------------------------------------
# Rule evaluators
# ---------------------------------------------------------------------------

@register("max_asset_class_weight")
def _eval_max_asset_class_weight(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    acw = weights["asset_class_weights"]
    per_rule, breaches, watches = [], [], []
    for ac, limit in rule.params.get("weights", {}).items():
        current = acw.get(ac, 0.0)
        offending = [h.ticker for h in portfolio.holdings if h.asset_class == ac and current > limit + _EPS]
        passed = current <= limit + _EPS
        per_rule.append(
            RuleEvaluation(
                rule=f"max_asset_class_weight:{ac}",
                pass_=passed,
                current=current,
                limit=limit,
                offending_holdings=offending,
                severity=Severity.HARD if not passed else None,
            )
        )
        if not passed:
            breaches.append(
                Violation(
                    rule=f"max_asset_class_weight:{ac}",
                    current=current,
                    limit=limit,
                    offending_holdings=offending,
                    severity=Severity.HARD,
                    plain=f"{ac} {current*100:.0f}% > {limit*100:.0f}% cap",
                )
            )
    return per_rule, breaches, watches


@register("max_sector_weight")
def _eval_max_sector_weight(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    sector_w = weights["sector_weights"]
    per_rule, breaches, watches = [], [], []
    for sec, limit in rule.params.get("weights", {}).items():
        current = sector_w.get(sec, 0.0)
        offending = [h.ticker for h in portfolio.holdings if h.sector == sec and current > limit + _EPS]
        passed = current <= limit + _EPS
        per_rule.append(
            RuleEvaluation(
                rule=f"max_sector_weight:{sec}",
                pass_=passed,
                current=current,
                limit=limit,
                offending_holdings=offending,
                severity=Severity.HARD if not passed else None,
            )
        )
        if not passed:
            breaches.append(
                Violation(
                    rule=f"max_sector_weight:{sec}",
                    current=current,
                    limit=limit,
                    offending_holdings=offending,
                    severity=Severity.HARD,
                    plain=f"{sec} {current*100:.0f}% > {limit*100:.0f}% cap",
                )
            )
    return per_rule, breaches, watches


@register("approved_universe")
def _eval_approved_universe(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    approved = set(rule.params.get("tickers", []))
    offending = [h.ticker for h in portfolio.holdings if h.ticker not in approved]
    passed = len(offending) == 0
    per_rule = [
        RuleEvaluation(
            rule="approved_universe",
            pass_=passed,
            current=offending,
            limit=sorted(approved),
            offending_holdings=offending,
            severity=Severity.HARD if not passed else None,
        )
    ]
    breaches = []
    if not passed:
        breaches.append(
            Violation(
                rule="approved_universe",
                current=offending,
                limit=sorted(approved),
                offending_holdings=offending,
                severity=Severity.HARD,
                plain=f"{', '.join(offending)} not in approved list",
            )
        )
    return per_rule, breaches, []


@register("max_single_holding")
def _eval_max_single_holding(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    ticker_w = weights["ticker_weights"]
    limit = rule.params.get("limit", 1.0)
    max_w = max(ticker_w.values()) if ticker_w else 0.0
    offending = [t for t, w in ticker_w.items() if w > limit + _EPS]
    passed = len(offending) == 0
    per_rule = [
        RuleEvaluation(
            rule="max_single_holding",
            pass_=passed,
            current=max_w,
            limit=limit,
            offending_holdings=offending,
            severity=Severity.HARD if not passed else None,
        )
    ]
    breaches = []
    if not passed:
        breaches.append(
            Violation(
                rule="max_single_holding",
                current=max_w,
                limit=limit,
                offending_holdings=offending,
                severity=Severity.HARD,
                plain=f"Single holding {max_w*100:.0f}% > {limit*100:.0f}% cap",
            )
        )
    return per_rule, breaches, []


@register("min_cash")
def _eval_min_cash(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    limit = rule.params.get("limit", 0.0)
    cash_ratio = weights["cash_ratio"]
    passed = cash_ratio >= limit - _EPS
    per_rule = [
        RuleEvaluation(
            rule="min_cash",
            pass_=passed,
            current=cash_ratio,
            limit=limit,
            offending_holdings=[],
            severity=Severity.HARD if not passed else None,
        )
    ]
    breaches = []
    if not passed:
        breaches.append(
            Violation(
                rule="min_cash",
                current=cash_ratio,
                limit=limit,
                offending_holdings=[],
                severity=Severity.HARD,
                plain=f"Cash {cash_ratio*100:.1f}% < {limit*100:.1f}% min",
            )
        )
    return per_rule, breaches, []


@register("target_allocation_drift")
def _eval_target_allocation_drift(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    target = rule.params.get("targets", {})
    tol = rule.params.get("drift_tolerance", 0.05)
    acw = weights["asset_class_weights"]
    per_rule, breaches, watches = [], [], []
    for ac, tgt in target.items():
        current = acw.get(ac, 0.0)
        over = current - tgt
        if over > tol + _EPS:
            offending = [h.ticker for h in portfolio.holdings if h.asset_class == ac]
            per_rule.append(
                RuleEvaluation(
                    rule=f"drift:{ac}",
                    pass_=False,
                    current=current,
                    limit=tgt,
                    offending_holdings=offending,
                    severity=Severity.WATCH,
                )
            )
            watches.append(
                Violation(
                    rule=f"drift:{ac}",
                    current=current,
                    limit=tgt,
                    offending_holdings=offending,
                    severity=Severity.WATCH,
                    plain=f"{ac} {current*100:.1f}% exceeds {tgt*100:.0f}% target by {over*100:.0f}% (tol {tol*100:.0f}%)",
                )
            )
    return per_rule, breaches, watches


@register("max_region_weight")
def _eval_max_region_weight(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    region_w = weights["region_weights"]
    per_rule, breaches, watches = [], [], []
    for region, cap in rule.params.get("weights", {}).items():
        current = region_w.get(region, 0.0)
        offending = [h.ticker for h in portfolio.holdings if h.region == region and current > cap + _EPS]
        passed = current <= cap + _EPS
        per_rule.append(
            RuleEvaluation(
                rule=f"max_region_weight:{region}",
                pass_=passed,
                current=current,
                limit=cap,
                offending_holdings=offending,
                severity=Severity.HARD if not passed else None,
            )
        )
        if not passed:
            breaches.append(
                Violation(
                    rule=f"max_region_weight:{region}",
                    current=current,
                    limit=cap,
                    offending_holdings=offending,
                    severity=Severity.HARD,
                    plain=f"{region} {current*100:.0f}% > {cap*100:.0f}% region cap",
                )
            )
    return per_rule, breaches, watches


@register("esg_exclusions")
def _eval_esg_exclusions(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    excluded = set(rule.params.get("tickers", []))
    offending = [h.ticker for h in portfolio.holdings if h.ticker in excluded]
    passed = len(offending) == 0
    per_rule = [
        RuleEvaluation(
            rule="esg_exclusions",
            pass_=passed,
            current=offending,
            limit=sorted(excluded),
            offending_holdings=offending,
            severity=Severity.HARD if not passed else None,
        )
    ]
    breaches = []
    if not passed:
        breaches.append(
            Violation(
                rule="esg_exclusions",
                current=offending,
                limit=sorted(excluded),
                offending_holdings=offending,
                severity=Severity.HARD,
                plain=f"{', '.join(offending)} on ESG exclusion list",
            )
        )
    return per_rule, breaches, []


@register("max_top_n_concentration")
def _eval_max_top_n_concentration(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    n = rule.params.get("n", 5)
    limit = rule.params.get("limit", 1.0)
    ticker_w = weights["ticker_weights"]
    top = sorted(ticker_w.values(), reverse=True)[:n]
    current = sum(top)
    offending = [t for t, _ in sorted(ticker_w.items(), key=lambda kv: kv[1], reverse=True)[:n]]
    passed = current <= limit + _EPS
    per_rule = [
        RuleEvaluation(
            rule="max_top_n_concentration",
            pass_=passed,
            current=current,
            limit=limit,
            n=n,
            offending_holdings=offending,
            severity=Severity.HARD if not passed else None,
        )
    ]
    breaches = []
    if not passed:
        breaches.append(
            Violation(
                rule="max_top_n_concentration",
                current=current,
                limit=limit,
                n=n,
                offending_holdings=offending,
                severity=Severity.HARD,
                plain=f"Top-{n} holdings {current*100:.0f}% > {limit*100:.0f}% cap",
            )
        )
    return per_rule, breaches, []


@register("min_liquid_pct")
def _eval_min_liquid_pct(rule: Rule, portfolio: Portfolio, total: float, weights: dict) -> tuple:
    limit = rule.params.get("limit", 0.0)
    liq1_w = weights["liquidity_tier1_weight"]
    passed = liq1_w >= limit - _EPS
    per_rule = [
        RuleEvaluation(
            rule="min_liquid_pct",
            pass_=passed,
            current=liq1_w,
            limit=limit,
            offending_holdings=[],
            severity=Severity.HARD if not passed else None,
        )
    ]
    breaches = []
    if not passed:
        breaches.append(
            Violation(
                rule="min_liquid_pct",
                current=liq1_w,
                limit=limit,
                offending_holdings=[],
                severity=Severity.HARD,
                plain=f"Liquid (tier-1) {liq1_w*100:.0f}% < {limit*100:.0f}% min",
            )
        )
    return per_rule, breaches, []


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def evaluate_portfolio(portfolio: Portfolio | dict, mandate: Mandate | dict) -> RulesResult:
    """Evaluate a portfolio against a mandate and return a deterministic result."""
    if isinstance(portfolio, dict):
        portfolio = _portfolio_from_dict(portfolio)
    if isinstance(mandate, dict):
        mandate = _mandate_from_dict(mandate)

    total, ticker_w, asset_w, sector_w, region_w, liq1_w, cash_ratio = _weights(portfolio)
    weights = {
        "total": total,
        "ticker_weights": ticker_w,
        "asset_class_weights": asset_w,
        "sector_weights": sector_w,
        "region_weights": region_w,
        "liquidity_tier1_weight": liq1_w,
        "cash_ratio": cash_ratio,
    }

    per_rule: list[RuleEvaluation] = []
    breaches: list[Violation] = []
    watches: list[Violation] = []

    for rule in mandate.rules:
        if not rule.enabled:
            continue
        evaluator = get(rule.type)
        if evaluator is None:
            # Unknown rule types are ignored so the engine stays forward-compatible.
            continue
        rule_per, rule_breaches, rule_watches = evaluator(rule, portfolio, total, weights)
        per_rule.extend(rule_per)
        breaches.extend(rule_breaches)
        watches.extend(rule_watches)

    status = _rollup(breaches, watches)
    return RulesResult(status=status, breaches=breaches, watches=watches, per_rule=per_rule)


def _rollup(breaches: list, watches: list) -> Status:
    if breaches:
        return Status.BREACH
    if watches:
        return Status.WATCH
    return Status.OK


def _portfolio_from_dict(data: dict) -> Portfolio:
    """Convert a legacy aura-demo portfolio dict into a kernel Portfolio."""
    holdings = []
    for h in data.get("holdings", []):
        holdings.append(
            Holding(
                ticker=h["ticker"],
                name=h.get("name"),
                asset_class=h.get("asset_class"),
                sector=h.get("sector"),
                region=h.get("region"),
                liquidity_tier=h.get("liquidity_tier"),
                units=h.get("units", 0.0),
                price=h.get("price", 0.0),
                market_value=h.get("market_value"),
            )
        )
    return Portfolio(
        client_id=data.get("client_id"),
        client_name=data.get("client_name"),
        adviser=data.get("adviser"),
        cash=data.get("cash", 0.0),
        holdings=holdings,
        fum=data.get("fum"),
    )


def _mandate_from_dict(data: dict) -> Mandate:
    """Convert a legacy aura-demo mandate dict into kernel Rules."""
    rules: list[Rule] = []

    for ac, limit in data.get("max_asset_class_weight", {}).items():
        rules.append(
            Rule(type="max_asset_class_weight", params={"weights": {ac: limit}})
        )

    for sec, limit in data.get("max_sector_weight", {}).items():
        rules.append(
            Rule(type="max_sector_weight", params={"weights": {sec: limit}})
        )

    if "approved_universe" in data:
        rules.append(
            Rule(type="approved_universe", params={"tickers": data["approved_universe"]})
        )

    if data.get("max_single_holding") is not None:
        rules.append(
            Rule(type="max_single_holding", params={"limit": data["max_single_holding"]})
        )

    if data.get("min_cash") is not None:
        rules.append(Rule(type="min_cash", params={"limit": data["min_cash"]}))

    target = data.get("target_allocation", {})
    if target:
        rules.append(
            Rule(
                type="target_allocation_drift",
                params={
                    "targets": target,
                    "drift_tolerance": data.get("drift_tolerance", 0.05),
                },
            )
        )

    for region, cap in data.get("max_region_weight", {}).items():
        rules.append(
            Rule(type="max_region_weight", params={"weights": {region: cap}})
        )

    if "excluded_tickers" in data:
        rules.append(
            Rule(type="esg_exclusions", params={"tickers": data["excluded_tickers"]})
        )

    tn = data.get("max_top_n_concentration")
    if tn:
        rules.append(
            Rule(
                type="max_top_n_concentration",
                params={"n": tn.get("n", 5), "limit": tn.get("limit", 1.0)},
            )
        )

    if "min_liquid_pct" in data:
        rules.append(
            Rule(type="min_liquid_pct", params={"limit": data["min_liquid_pct"]})
        )

    return Mandate(
        id=data.get("id"),
        name=data.get("name"),
        version=data.get("version", "1.0.0"),
        rules=rules,
        metadata=data.get("metadata"),
    )


# Convenience alias matching the original aura-demo function name.
check = evaluate_portfolio
