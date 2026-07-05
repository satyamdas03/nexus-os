"""Hermes proposer — deterministic + strategy-driven. No Claude call.

Input: effective portfolio + rules_result + strategy vars.
Output: proposed trades (structured) + a deterministic one-line rationale.

A strategy-variable change MUST change the output (unit test asserts). The
rules engine still disposes — the loop gates every proposal through check().
"""
from core.trades import UNIVERSE

_EPS = 1e-9
_TRIM_SAFETY = 0.005  # 0.5% headroom under the cap so float noise can't re-trip the engine

# Deterministic ordering used when the strategy omits `breach_priority_order`.
# Covers all 10 breach types the rules engine can emit (6 original + 4 new 34k).
DEFAULT_BREACH_PRIORITY = [
    "approved_universe", "esg_exclusions",
    "max_single_holding", "max_top_n_concentration",
    "max_asset_class_weight", "max_sector_weight", "max_region_weight",
    "min_liquid_pct", "min_cash", "drift",
]


def _total(p: dict) -> float:
    return sum(h["market_value"] for h in p["holdings"]) + p["cash"]


def _holding(p: dict, ticker: str) -> dict | None:
    return next((h for h in p["holdings"] if h["ticker"] == ticker), None)


def _sell_trade(h: dict, units: float) -> dict:
    units = min(h["units"], max(0.0, units))
    return {"ticker": h["ticker"], "action": "sell", "units": round(units, 6),
            "value": round(units * h["price"], 2),
            "rationale": f"trim {h['ticker']} to address mandate breach"}


def _buy_trade(ticker: str, units: float, price: float) -> dict:
    return {"ticker": ticker, "action": "buy", "units": round(units, 4),
            "value": round(units * price, 2),
            "rationale": f"redeploy proceeds into {ticker}"}


def _tier1_weight(p: dict) -> float:
    total = _total(p)
    if total == 0:
        return 0.0
    return sum(h["market_value"] / total for h in p["holdings"] if h.get("liquidity_tier") == 1)


def _max_buy_under_caps(portfolio: dict, trades: list[dict], ticker: str,
                        rules_result: dict, headroom: float = _TRIM_SAFETY) -> float:
    """Max dollar buy of `ticker` that keeps the upper-weight caps green.

    Caps are reconstructed from `rules_result["per_rule"]` (the mandate is not
    passed to the proposer). Weights are computed from the post-sell state:
    sells already in `trades` reduce the holding market values, but the
    portfolio total is invariant under sells+buys (cash absorbs the difference),
    so weights = post_sell_mv / total. Any proceeds that cannot be deployed
    within the caps stay as cash — the brief's "rotate into allowed region/cash"
    intent. No safety margin: the rules engine disposes with a 1e-9 tolerance,
    and a safety here would conflict with floor rules (e.g. min_liquid_pct)
    that need the buy to reach the exact cap.
    """
    total = _total(portfolio)
    if total <= 0:
        return 0.0
    region_caps: dict[str, float] = {}
    sector_caps: dict[str, float] = {}
    ac_caps: dict[str, float] = {}
    single_cap = 1.0
    for pr in rules_result.get("per_rule", []):
        r = pr["rule"]
        if r.startswith("max_region_weight:"):
            region_caps[r.split(":", 1)[1]] = pr["limit"]
        elif r.startswith("max_sector_weight:"):
            sector_caps[r.split(":", 1)[1]] = pr["limit"]
        elif r.startswith("max_asset_class_weight:"):
            ac_caps[r.split(":", 1)[1]] = pr["limit"]
        elif r == "max_single_holding":
            single_cap = pr["limit"]
    post_mv: dict[str, float] = {h["ticker"]: h["market_value"] for h in portfolio["holdings"]}
    for t in trades:
        if t["action"] == "sell":
            post_mv[t["ticker"]] = max(0.0, post_mv.get(t["ticker"], 0.0) - t["value"])
    meta = UNIVERSE.get(ticker, {})
    held = _holding(portfolio, ticker)
    region = (held or {}).get("region") or meta.get("region")
    sector = (held or {}).get("sector") or meta.get("sector", "Broad")
    asset_class = (held or {}).get("asset_class") or meta.get("asset_class", "Equity")

    def _agg(key_fn) -> dict[str, float]:
        w: dict[str, float] = {}
        for h in portfolio["holdings"]:
            k = key_fn(h)
            if k is None:
                continue
            w[k] = w.get(k, 0.0) + post_mv.get(h["ticker"], 0.0) / total
        return w

    region_w = _agg(lambda h: h.get("region"))
    sector_w = _agg(lambda h: h.get("sector"))
    ac_w = _agg(lambda h: h.get("asset_class"))
    ticker_w = post_mv.get(ticker, 0.0) / total
    max_v = float("inf")
    # Leave the same 0.5% headroom under every upper cap that trimming uses,
    # so a replacement buy does not re-trip a cap due to float rounding.
    max_v = min(max_v, max(0.0, (single_cap - headroom - ticker_w) * total))
    if region in region_caps:
        max_v = min(max_v, max(0.0, (region_caps[region] - headroom - region_w.get(region, 0.0)) * total))
    if sector in sector_caps:
        max_v = min(max_v, max(0.0, (sector_caps[sector] - headroom - sector_w.get(sector, 0.0)) * total))
    if asset_class in ac_caps:
        max_v = min(max_v, max(0.0, (ac_caps[asset_class] - headroom - ac_w.get(asset_class, 0.0)) * total))

    # Top-N concentration is also an upper cap: a replacement buy must not push
    # the N largest holdings above the limit. If the bought ticker is already in
    # the top-N, the increase is the buy value; otherwise it displaces the Nth
    # holding and the increase is (new_value - old_Nth_value).
    topn = next((pr for pr in rules_result.get("per_rule", []) if pr["rule"] == "max_top_n_concentration"), None)
    if topn:
        n = int(topn.get("n", 5))
        limit = float(topn["limit"])
        values = sorted(post_mv.values(), reverse=True)
        current_topn_sum = sum(values[:n])
        limit_value = (limit - headroom) * total
        if current_topn_sum <= limit_value + _EPS:
            current_value = post_mv.get(ticker, 0.0)
            # Is ticker already among the top-N after the prior sells?
            top_n_tickers = {t for t, _ in sorted(post_mv.items(), key=lambda kv: kv[1], reverse=True)[:n]}
            if ticker in top_n_tickers:
                room = limit_value - current_topn_sum
            else:
                nth_value = values[n - 1] if n <= len(values) else 0.0
                room = limit_value - (current_topn_sum - nth_value) - current_value
            max_v = min(max_v, max(0.0, room))
    return max_v


def _trim_to_cap(p: dict, current: float, limit: float, offenders: list[dict],
                 method: str, buffer: float = 0.0,
                 remaining_mv: dict[str, float] | None = None) -> list[dict]:
    """Return sell trades that bring `current` weight down below `limit`.

    Aims for `limit - SAFETY` (0.5% headroom) so float rounding at the exact cap
    boundary does not re-trip the deterministic engine. The engine still disposes.

    `remaining_mv` maps ticker -> post-prior-sells market value so later branches
    see earlier branches' trims and don't over-sell the same holding. Defaults to
    each offender's original market value.
    """
    target_weight = limit - _TRIM_SAFETY - buffer
    over = current - target_weight
    if over <= _EPS or not offenders:
        return []
    target_value = over * _total(p)  # dollars to remove
    rmv = remaining_mv if remaining_mv is not None else {h["ticker"]: h["market_value"] for h in offenders}
    if method == "liquidate":
        # sell the largest offender first until target met
        offenders_sorted = sorted(offenders, key=lambda h: rmv.get(h["ticker"], 0.0), reverse=True)
        trades, remaining = [], target_value
        # Residuals smaller than this are absorbed by the 0.5% safety margin;
        # avoids consuming a trade slot with a rounding-noise micro-sell.
        residual_floor = max(_EPS, 1e-6 * target_value)
        for h in offenders_sorted:
            if remaining <= residual_floor:
                break
            avail_units = rmv.get(h["ticker"], 0.0) / h["price"]
            units = min(avail_units, remaining / h["price"])
            if units * h["price"] <= _EPS:
                break
            trades.append(_sell_trade(h, units))
            remaining -= trades[-1]["value"]
        return trades
    # proportional: trim each offender by the same fraction of its remaining value
    total_offender_value = sum(rmv.get(h["ticker"], 0.0) for h in offenders) or 1.0
    trades = []
    for h in offenders:
        avail_mv = rmv.get(h["ticker"], 0.0)
        if avail_mv <= _EPS:
            continue
        frac = target_value / total_offender_value
        units = min(frac * avail_mv / h["price"], avail_mv / h["price"])
        if units > _EPS:
            trades.append(_sell_trade(h, units))
    return trades


def _replacement_candidates(portfolio: dict, rules_result: dict) -> list[str]:
    """Return tickers that are safe to buy as a redeployment landing.

    A replacement must be in the approved universe and not on the ESG
    exclusion list. When the portfolio does not carry its mandate (e.g. unit
    tests), the approved/excluded lists are reconstructed from the rules
    engine's per_rule output. We prefer the strategy's replacement preference
    when valid; otherwise we fall back to any broad tier-1 ETF.
    """
    mandate = portfolio.get("mandate", {})
    approved = set(mandate.get("approved_universe", []))
    excluded = set(mandate.get("excluded_tickers", []))
    # Fall back to the rules engine's view of the mandate when the portfolio
    # object does not embed it.
    for pr in rules_result.get("per_rule", []):
        if pr["rule"] == "approved_universe":
            approved = approved or set(pr.get("limit", []))
        elif pr["rule"] == "esg_exclusions":
            excluded = excluded or set(pr.get("limit", []))
    if not approved:
        approved = {h["ticker"] for h in portfolio["holdings"]}
    candidates = []
    for tk, meta in UNIVERSE.items():
        if tk not in approved or tk in excluded:
            continue
        candidates.append((tk, meta.get("liquidity_tier", 2), meta.get("base_price", 0.0)))
    # Tier-1 first, then deterministic ticker order for reproducibility.
    candidates.sort(key=lambda x: (x[1], x[0]))
    return [tk for tk, _, _ in candidates]


def propose(portfolio: dict, rules_result: dict, strategy: dict) -> dict:
    """Produce deterministic, strategy-driven trades. Returns {trades, rationale}."""
    vars_ = strategy if "variables" not in strategy else strategy_vars(strategy)
    strategy_priority = vars_.get("breach_priority_order") or []
    # Priority is ORDER, not a whitelist. Any breach type not named in the
    # strategy is still handled at the end using the default priority.
    seen = set(strategy_priority)
    priority = list(strategy_priority) + [r for r in DEFAULT_BREACH_PRIORITY if r not in seen]
    method = vars_.get("preferred_trim_method", "proportional")
    replacement_pref = vars_.get("replacement_preference", "SPY")
    min_size = float(vars_.get("min_trade_size", 0.0))
    max_trades = int(vars_.get("max_trades_per_portfolio", 4))
    cash_buffer = float(vars_.get("cash_buffer_target", 0.0))

    breaches = rules_result.get("breaches", [])
    by_type: dict[str, list[dict]] = {}
    for b in breaches:
        by_type.setdefault(b["rule"].split(":")[0], []).append(b)
    # Floor breaches (e.g. min_liquid_pct) need the replacement buy to reach
    # the exact limit, so we relax the cap headroom for tier-1 replacements.
    floor_mode = any(b["rule"].split(":")[0] == "min_liquid_pct" for b in breaches)

    trades: list[dict] = []
    proceeds = 0.0
    notes: list[str] = []
    total = _total(portfolio)
    # Running post-sell market values so later branches see earlier branches'
    # trims and don't over-sell the same holding. Total is invariant under
    # sells+buys (cash absorbs the difference), so weights = post_mv / total.
    post_mv: dict[str, float] = {h["ticker"]: h["market_value"] for h in portfolio["holdings"]}

    def add(t: dict) -> None:
        nonlocal proceeds
        if t["action"] == "sell":
            proceeds += t["value"]
            post_mv[t["ticker"]] = max(0.0, post_mv.get(t["ticker"], 0.0) - t["value"])
        trades.append(t)

    for breach_type in priority:
        # Reserve one slot for the final redeploy buy; without it portfolios with
        # overlapping caps can sell through all slots and never land proceeds in
        # tier-1, leaving min_liquid_pct / min_cash unresolved.
        if len(trades) >= max_trades - 1:
            break
        bs = by_type.get(breach_type, [])
        if not bs:
            continue
        if breach_type == "approved_universe":
            for b in bs:
                for tk in b.get("offending_holdings", []):
                    h = _holding(portfolio, tk)
                    if h and len(trades) < max_trades:
                        add(_sell_trade(h, h["units"]))
                        notes.append(f"liquidate unapproved {tk}")
        elif breach_type in ("max_sector_weight", "max_asset_class_weight"):
            key = "sector" if breach_type == "max_sector_weight" else "asset_class"
            for b in bs:
                cls = b["rule"].split(":")[1]
                offenders = [h for h in portfolio["holdings"] if h[key] == cls]
                current = sum(post_mv.get(h["ticker"], 0.0) for h in offenders) / total
                t = _trim_to_cap(portfolio, current, b["limit"], offenders, method, remaining_mv=post_mv)
                for tr in t:
                    if len(trades) >= max_trades:
                        break
                    add(tr)
                notes.append(f"trim {cls} to {b['limit']*100:.0f}% cap")
        elif breach_type == "max_single_holding":
            limit = bs[0]["limit"]
            weights = {h["ticker"]: post_mv.get(h["ticker"], 0.0) / total for h in portfolio["holdings"]}
            for b in bs:
                for tk in b.get("offending_holdings", []):
                    h = _holding(portfolio, tk)
                    if not h or len(trades) >= max_trades:
                        continue
                    over_value = (weights[tk] - (limit - _TRIM_SAFETY)) * total
                    if over_value <= _EPS:
                        continue
                    units = min(post_mv.get(tk, 0.0) / h["price"], over_value / h["price"])
                    add(_sell_trade(h, units))
                    notes.append(f"trim {tk} to single-holding cap")
        elif breach_type == "min_cash":
            need = (bs[0]["limit"] + cash_buffer) * total - (portfolio["cash"] + proceeds)
            if need > _EPS:
                biggest = max(portfolio["holdings"], key=lambda h: post_mv.get(h["ticker"], 0.0))
                if len(trades) < max_trades:
                    units = min(post_mv.get(biggest["ticker"], 0.0) / biggest["price"], need / biggest["price"])
                    add(_sell_trade(biggest, units))
                    notes.append(f"raise cash to {bs[0]['limit']*100:.0f}% min + buffer")
        elif breach_type == "max_region_weight":
            for b in bs:
                region = b["rule"].split(":")[1]
                offenders = [h for h in portfolio["holdings"] if h.get("region") == region]
                current = sum(post_mv.get(h["ticker"], 0.0) for h in offenders) / total
                t = _trim_to_cap(portfolio, current, b["limit"], offenders, method, remaining_mv=post_mv)
                for tr in t:
                    if len(trades) >= max_trades:
                        break
                    add(tr)
                notes.append(f"trim {region} to {b['limit']*100:.0f}% region cap")
        elif breach_type == "esg_exclusions":
            for b in bs:
                for tk in b.get("offending_holdings", []):
                    h = _holding(portfolio, tk)
                    if h and len(trades) < max_trades:
                        add(_sell_trade(h, h["units"]))
                        notes.append(f"liquidate excluded {tk}")
        elif breach_type == "max_top_n_concentration":
            tn = bs[0]
            offenders = [_holding(portfolio, tk) for tk in tn.get("offending_holdings", [])]
            offenders = [o for o in offenders if o]
            current = sum(post_mv.get(o["ticker"], 0.0) for o in offenders) / total
            t = _trim_to_cap(portfolio, current, tn["limit"], offenders, method, remaining_mv=post_mv)
            for tr in t:
                if len(trades) >= max_trades:
                    break
                add(tr)
            notes.append(f"trim top-N concentration to {tn['limit']*100:.0f}% cap")
        elif breach_type == "min_liquid_pct":
            tier1_w = sum(post_mv.get(h["ticker"], 0.0) for h in portfolio["holdings"]
                          if h.get("liquidity_tier") == 1) / total
            need_weight = bs[0]["limit"] - tier1_w
            if need_weight > _EPS:
                # Oversell by the same 0.5% safety margin used for replacement
                # buys so that the post-buy state can actually reach the floor
                # without being blocked by an upper cap headroom.
                target_value = (need_weight + _TRIM_SAFETY) * total
                # sell the largest REMAINING non-tier-1 holdings to free proceeds;
                # the end-of-loop redeploy buys the tier-1 replacement (SPY).
                non_tier1 = [h for h in portfolio["holdings"] if h.get("liquidity_tier") != 1]
                non_tier1 = sorted(non_tier1, key=lambda h: post_mv.get(h["ticker"], 0.0), reverse=True)
                remaining = target_value
                for h in non_tier1:
                    if remaining <= _EPS or len(trades) >= max_trades:
                        break
                    avail_mv = post_mv.get(h["ticker"], 0.0)
                    if avail_mv <= _EPS:
                        continue
                    units = min(avail_mv / h["price"], remaining / h["price"])
                    add(_sell_trade(h, units))
                    remaining -= trades[-1]["value"]
                notes.append(f"rotate into liquid (tier-1) to clear {bs[0]['limit']*100:.0f}% floor")
        # drift is a watch, not a breach — handled by trim above; nothing here

    # Redeploy proceeds into an approved, non-excluded replacement, but only
    # up to the mandate caps (region/sector/asset_class/single-holding). Excess
    # proceeds stay as cash — the brief's "rotate into allowed region/cash"
    # intent. This prevents a US replacement (SPY) from re-triggering a US region
    # cap after the trim branches freed proceeds, and from over-concentrating
    # when several breach branches each sold into the same proceeds pool.
    if proceeds > min_size * _total(portfolio) and len(trades) < max_trades:
        candidates = _replacement_candidates(portfolio, rules_result)
        # Prefer the strategy's replacement if it is mandate-safe.
        if replacement_pref in candidates:
            candidates = [replacement_pref] + [c for c in candidates if c != replacement_pref]
        for replacement in candidates:
            held = _holding(portfolio, replacement)
            price = held["price"] if held else UNIVERSE.get(replacement, {}).get("base_price")
            if not price:
                continue
            max_buy = _max_buy_under_caps(portfolio, trades, replacement, rules_result)
            buy_value = min(proceeds, max_buy)
            units = buy_value / price
            if units > _EPS:
                add(_buy_trade(replacement, units, price))
                notes.append(f"redeploy into {replacement}")
                break

    # Drop sub-min_trade_size sells
    total = _total(portfolio)
    trades = [t for t in trades if t["action"] == "buy" or t["value"] >= min_size * total]
    # Final cap
    trades = trades[:max_trades]

    rationale = "; ".join(notes[:3]) + ("; ..." if len(notes) > 3 else "") or "no breaches to remediate"
    return {"trades": trades, "rationale": rationale}


def strategy_vars(strategy: dict) -> dict:
    """Flatten a {variables: {name: {value}}} strategy to {name: value}."""
    return {k: v["value"] for k, v in strategy.get("variables", {}).items()}