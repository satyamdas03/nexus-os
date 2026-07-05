"""LLM provider interface. MockLLM for tests/offline; ClaudeProvider for real calls.

The agents never call the LLM directly to decide compliance — they're grounded
against rules_engine output. The LLM only drafts prose/proposals.
"""
import json
import os
from typing import Protocol


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


def _extract_first_json_object(text: str) -> dict | None:
    """Return the first top-level JSON object from *text*.

    The remediate() retry prompt concatenates the facts object with the
    remaining-breaches array, so `json.loads(text[start:])` fails on trailing
    text. We scan brace balance (honouring string escapes) to isolate the first
    object and ignore everything after it.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not in_string:
            in_string = True
        elif ch == '"' and in_string:
            in_string = False
        elif not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def _mock_explain_narrative(user: str) -> str:
    """Deterministic offline narrative for the Explain agent.

    When no ANTHROPIC_API_KEY is set the demo still needs to feel intelligent.
    This parses the JSON the explainer puts in its prompt and writes calm,
    grounded prose using only facts from the rules engine. The result is not
    "AI-generated" in the Claude sense, but it is honest, accurate, and useful —
    which is exactly what the demo needs when running offline.
    """
    obj = _extract_first_json_object(user)
    if obj is None:
        return "[MOCK LLM] grounded explanation unavailable."

    # Per-metric explain: the first JSON object is a rules-engine per_rule row.
    if "rule" in obj and "pass" in obj:
        rule = obj["rule"]
        current = obj.get("current")
        limit = obj.get("limit")
        passed = obj.get("pass")
        name = rule.split(":")[-1] if ":" in rule else rule

        # Format current/limit: lists (exclusion lists) vs numbers.
        if isinstance(current, list):
            current_txt = f"holds {', '.join(current)}" if current else "holds none"
        elif isinstance(current, (int, float)):
            current_txt = f"is at {current * 100:.1f}%"
        else:
            current_txt = f"is {current}"

        if isinstance(limit, list):
            limit_txt = f"approved list is {', '.join(limit)}"
        elif isinstance(limit, (int, float)):
            limit_txt = f"{'cap' if 'weight' in rule or 'cash' in rule or 'liquid' in rule else 'limit'} is {limit * 100:.1f}%"
        else:
            limit_txt = f"limit is {limit}"

        status = "passes" if passed else "breaches"
        return (
            f"The {name} check {status}: {current_txt} while the {limit_txt}. "
            f"This is a deterministic rule-maths result, not a model inference."
        )

    # Full portfolio narrative: the first JSON object is the facts bundle.
    breaches = obj.get("engine_breaches", [])
    watches = obj.get("engine_watches", [])
    client = obj.get("client", "Portfolio")
    cash_pct = obj.get("cash_pct")
    holdings = obj.get("holdings", [])

    parts: list[str] = []
    parts.append(f"Assurance scan for {client}.")

    if breaches:
        parts.append(
            f"{len(breaches)} mandate breach(es) flagged: "
            + "; ".join(
                f"{b.get('plain', b.get('rule', 'unknown'))} ({b.get('rule', 'unknown')})"
                for b in breaches
            )
            + "."
        )
    if watches:
        parts.append(
            f"{len(watches)} drift watch(es): "
            + "; ".join(
                f"{w.get('plain', w.get('rule', 'unknown'))} ({w.get('rule', 'unknown')})"
                for w in watches
            )
            + "."
        )
    if not breaches and not watches:
        parts.append("All deterministic mandate checks pass; the portfolio is aligned.")

    if cash_pct is not None:
        parts.append(f"Cash reserve is {cash_pct:.1f}% of portfolio value.")

    if holdings:
        top = sorted(holdings, key=lambda h: h.get("weight_pct", 0), reverse=True)[:3]
        parts.append(
            "Top exposures: "
            + ", ".join(f"{h.get('ticker')} ({h.get('weight_pct', 0):.1f}%)" for h in top)
            + "."
        )

    return " ".join(parts)


def _mock_remediate_trades(user: str) -> str:
    """Deterministic offline remediation. Parses the facts JSON from the user
    prompt and proposes trades that target the specific breach amounts. On a
    retry prompt (previous proposal still breached) it trims more aggressively.

    Strategy:
      - approved_universe / esg_exclusions breaches: sell 100% of offending holdings.
      - max_single_holding / max_region_weight / max_sector_weight / max_asset_class_weight /
        max_top_n_concentration: sell enough of the named offending holdings to bring
        the overweight down to its limit.
      - min_cash: sell holdings and keep proceeds as cash (no buy).
      - Redeploy remaining proceeds into the most underweight approved asset class,
        preferring Bonds when equity is overweight and SPY/Equity when bonds are
        overweight. Avoids buying more of the same offending asset class.

    Returns a JSON trade list string. The rules_engine still verifies.
    """
    facts = _extract_first_json_object(user)
    if facts is None:
        return "[]"

    holdings = {h["ticker"]: h for h in facts.get("holdings", [])}
    mandate = facts.get("mandate", {})
    approved = set(mandate.get("approved_universe", []))
    breaches = facts.get("engine_breaches", [])
    if not breaches:
        return "[]"

    is_retry = "Previous proposal still leaves these breaches" in user or "Revise" in user

    total_value = sum(h.get("market_value", h.get("units", 0) * h.get("price", 0)) for h in holdings.values()) + float(facts.get("cash", 0) or 0)
    if total_value <= 0:
        return "[]"

    # Aggregate required sell value per ticker by scanning each breach.
    sell_target: dict[str, float] = {}
    needs_cash_increase = False
    needs_liquidity_increase = False
    for b in breaches:
        rule = b.get("rule", "")
        current = float(b.get("current", 0))
        limit = float(b.get("limit", 0))
        offenders = b.get("offending_holdings", []) or []
        if not offenders:
            if rule == "min_cash":
                needs_cash_increase = True
            elif rule == "min_liquid_pct":
                needs_liquidity_increase = True
            continue

        # Required reduction in market-value terms.
        reduction = max(0.0, (current - limit) * total_value)
        if rule in ("approved_universe", "esg_exclusions"):
            reduction = float("inf")  # sell all of these holdings

        # Distribute reduction across offenders weighted by their market value.
        offender_mvs = {tk: float(holdings.get(tk, {}).get("market_value", 0)) for tk in offenders}
        total_offender_mv = sum(offender_mvs.values()) or 1.0
        for tk, mv in offender_mvs.items():
            if mv <= 0:
                continue
            share = reduction * (mv / total_offender_mv)
            sell_target[tk] = max(sell_target.get(tk, 0.0), share)
            if is_retry:
                # On retry, be more aggressive: sell the computed amount plus an extra 30%.
                sell_target[tk] = max(sell_target[tk], min(mv, share * 1.3))

    trades: list[dict] = []
    proceeds = 0.0
    liquid_proceeds_lost = 0.0
    for tk, target_mv in sell_target.items():
        h = holdings.get(tk)
        if not h:
            continue
        mv = float(h.get("market_value", 0))
        price = float(h.get("price", 0) or _MOCK_PRICES.get(tk, 100.0))
        if price <= 0:
            continue
        # Sell at least the target market value, but never more than held.
        if target_mv >= mv:
            sell_units = float(h.get("units", 0))
        else:
            sell_units = round(target_mv / price, 4)
        if sell_units <= 1e-6:
            continue
        value = round(sell_units * price, 2)
        trades.append({"ticker": tk, "action": "sell", "units": sell_units,
                       "value": value,
                       "rationale": f"trim {tk} to address mandate breach"})
        proceeds += value
        if h.get("liquidity_tier") == 1:
            liquid_proceeds_lost += value

    # Determine what to buy (if anything) with proceeds.
    if proceeds > 1:
        tier1_candidates = _tier1_tickers(holdings, approved)
        if needs_liquidity_increase and tier1_candidates:
            # Replenish tier-1 liquidity. If cash is also low, split proceeds so we
            # do not starve the cash floor.
            if needs_cash_increase:
                cash_portion = 0.35
            else:
                cash_portion = 0.0
            buy_amount = proceeds * (1 - cash_portion)
            # If we sold tier-1 holdings we need to make up for that loss too.
            if liquid_proceeds_lost:
                buy_amount += liquid_proceeds_lost
                buy_amount = min(buy_amount, proceeds)
            # Split liquidity buys across several approved tier-1 tickers to avoid
            # creating a new single-holding concentration.
            slice_count = min(4, len(tier1_candidates))
            slice_amount = buy_amount / slice_count
            for i in range(slice_count):
                buy_tk = tier1_candidates[i]
                price = _MOCK_PRICES.get(buy_tk, 100.0)
                units = round(slice_amount / price, 4)
                if units > 0:
                    trades.append({"ticker": buy_tk, "action": "buy", "units": units,
                                   "value": round(slice_amount, 2),
                                   "rationale": f"redeploy proceeds into liquid {buy_tk}"})
        elif needs_cash_increase:
            # Leave proceeds as cash to satisfy min_cash; no buy needed.
            pass
        else:
            buy_tk = _choose_buy_target(holdings, mandate, approved)
            if buy_tk:
                price = _MOCK_PRICES.get(buy_tk, 100.0)
                units = round(proceeds / price, 4)
                if units > 0:
                    trades.append({"ticker": buy_tk, "action": "buy", "units": units,
                                   "value": round(proceeds, 2),
                                   "rationale": f"redeploy proceeds into {buy_tk}"})

    return json.dumps(trades)


def _tier1_tickers(holdings: dict[str, dict], approved: set[str]) -> list[str]:
    """Approved tier-1 (liquid) tickers."""
    ordered = ["SPY", "VTI", "QQQ", "IEF", "TLT", "LQD", "VEA", "EFA", "XLF", "XLV", "XLK", "XLY", "XLP", "GLD"]
    return [tk for tk in ordered if tk in approved]


def _choose_buy_target(holdings: dict[str, dict], mandate: dict, approved: set[str]) -> str | None:
    """Pick an approved ticker to buy with sale proceeds that does not worsen the
    most likely breach. Prefers an underweight asset class.
    """
    max_ac = mandate.get("max_asset_class_weight", {})
    targets = mandate.get("target_allocation", {})
    total = sum(h.get("market_value", 0) for h in holdings.values())
    if total <= 0:
        return None
    acw: dict[str, float] = {}
    for h in holdings.values():
        ac = h.get("asset_class", "Equity")
        acw[ac] = acw.get(ac, 0.0) + h.get("market_value", 0)
    for ac in set(list(max_ac.keys()) + list(targets.keys())):
        acw.setdefault(ac, 0.0)

    # Prefer Bonds if there is headroom, otherwise Equity, otherwise cash.
    for preferred_ac in ("Bonds", "Equity", "Cash"):
        current = acw.get(preferred_ac, 0.0)
        limit = max_ac.get(preferred_ac, 1.0)
        target = targets.get(preferred_ac, 0.0)
        if current / total < min(limit, target * 1.05) and limit > 0:
            # Find an approved representative ticker for this asset class.
            tk = _ticker_for_asset_class(preferred_ac, approved, holdings)
            if tk:
                return tk
    # Fallback: broad equity ETF if approved.
    return _ticker_for_asset_class("Equity", approved, holdings)


def _ticker_for_asset_class(asset_class: str, approved: set[str], holdings: dict[str, dict]) -> str | None:
    """Return an approved ticker representative of *asset_class* that is not already
    an offending overweight holding. Falls back to SPY / QQQ / TLT / GLD / Cash.
    """
    by_class = {
        "Equity": ["SPY", "QQQ", "VTI", "EFA", "VEA", "EEM", "VWO", "INDA", "XLF", "XLV", "XLK", "XLY", "XLE", "XLRE"],
        "Bonds": ["TLT", "IEF", "LQD", "BNDX", "HYG"],
        "Commodity": ["GLD", "SLV", "DBC"],
        "Crypto": ["BTC"],
        "Cash": [],
    }
    candidates = by_class.get(asset_class, [])
    for tk in candidates:
        if tk in approved and tk not in holdings:
            return tk
    for tk in candidates:
        if tk in approved:
            return tk
    return None


_MOCK_PRICES = {"SPY": 500.0, "QQQ": 420.0, "XLV": 145.0, "XLF": 45.0, "XLK": 220.0,
                "TLT": 95.0, "GLD": 240.0, "SLV": 22.0, "DBC": 25.0, "AAPL": 225.0,
                "MSFT": 420.0, "NVDA": 130.0, "AMZN": 180.0}


class MockLLM:
    """Deterministic. Returns a structured echo for explain; a JSON trade list
    for remediate (so the offline demo flows end-to-end). The rules_engine
    still has the final say on whatever trades are produced."""

    def complete(self, system: str, user: str) -> str:
        if "STRICT JSON only" in system or "remediation agent" in system.lower():
            return _mock_remediate_trades(user)
        if "assurance explainer" in system.lower():
            return _mock_explain_narrative(user)
        return f"[MOCK LLM] grounded explanation for: {user[:120]}"


class ClaudeProvider:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-5-20250929"):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._client = None

    def complete(self, system: str, user: str) -> str:
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self._api_key)
        msg = self._client.messages.create(
            model=self._model, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))


def get_llm() -> LLMProvider:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeProvider()
    return MockLLM()