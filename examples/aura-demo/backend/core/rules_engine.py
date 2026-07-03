"""Deterministic source of truth. LLM never overrides this.

The only thing that colours a block or verifies a remediation is this module.
Pure functions, no I/O. Every agent and every screen consumes the RulesResult
shape produced here.
"""

_EPS = 1e-9


def _total_value(portfolio: dict) -> float:
    return sum(h["market_value"] for h in portfolio["holdings"]) + portfolio["cash"]


def _all_weights(portfolio: dict) -> tuple[float, dict[str, float], dict[str, float], dict[str, float], dict[str, float], float]:
    """Single-pass computation of total value and all weight maps.

    Returns (total, ticker_weights, asset_class_weights, sector_weights,
             region_weights, liquidity_tier1_weight, cash_ratio).
    """
    total = sum(h["market_value"] for h in portfolio["holdings"]) + portfolio["cash"]
    if total == 0:
        return 0.0, {}, {}, {}, {}, 0.0, 0.0
    ticker_w: dict[str, float] = {}
    asset_w: dict[str, float] = {}
    sector_w: dict[str, float] = {}
    region_w: dict[str, float] = {}
    liq1 = 0.0
    for h in portfolio["holdings"]:
        w = h["market_value"] / total
        ticker_w[h["ticker"]] = w
        asset_w[h["asset_class"]] = asset_w.get(h["asset_class"], 0.0) + w
        sector_w[h["sector"]] = sector_w.get(h["sector"], 0.0) + w
        r = h.get("region")
        if r:
            region_w[r] = region_w.get(r, 0.0) + w
        if h.get("liquidity_tier") == 1:
            liq1 += w
    return total, ticker_w, asset_w, sector_w, region_w, liq1, portfolio["cash"] / total


def _ticker_weights(portfolio: dict) -> dict[str, float]:
    return _all_weights(portfolio)[1]


def _asset_class_weights(portfolio: dict) -> dict[str, float]:
    return _all_weights(portfolio)[2]


def _sector_weights(portfolio: dict) -> dict[str, float]:
    return _all_weights(portfolio)[3]


def _cash_ratio(portfolio: dict) -> float:
    return _all_weights(portfolio)[6]


def _region_weights(portfolio: dict) -> dict[str, float]:
    return _all_weights(portfolio)[4]


def _liquidity_tier1_weight(portfolio: dict) -> float:
    return _all_weights(portfolio)[5]


def check(portfolio: dict, mandate: dict) -> dict:
    """Pure function. Returns RulesResult.

    RulesResult = {status, breaches, watches, per_rule}
    """
    per_rule: list[dict] = []
    breaches: list[dict] = []
    watches: list[dict] = []

    _total, ticker_w, acw, sector_w, region_w, liq1_w, cash_ratio = _all_weights(portfolio)

    for ac, limit in mandate.get("max_asset_class_weight", {}).items():
        current = acw.get(ac, 0.0)
        offending = [h["ticker"] for h in portfolio["holdings"] if h["asset_class"] == ac and current > limit + _EPS]
        passed = current <= limit + _EPS
        per_rule.append({"rule": f"max_asset_class_weight:{ac}", "pass": passed, "current": current,
                         "limit": limit, "offending_holdings": offending, "severity": "red" if not passed else "green"})
        if not passed:
            breaches.append({"rule": f"max_asset_class_weight:{ac}", "current": current, "limit": limit,
                             "offending_holdings": offending, "severity": "red",
                             "plain": f"{ac} {current*100:.0f}% > {limit*100:.0f}% cap"})

    for sec, limit in mandate.get("max_sector_weight", {}).items():
        current = sector_w.get(sec, 0.0)
        offending = [h["ticker"] for h in portfolio["holdings"] if h["sector"] == sec and current > limit + _EPS]
        passed = current <= limit + _EPS
        per_rule.append({"rule": f"max_sector_weight:{sec}", "pass": passed, "current": current,
                         "limit": limit, "offending_holdings": offending, "severity": "red" if not passed else "green"})
        if not passed:
            breaches.append({"rule": f"max_sector_weight:{sec}", "current": current, "limit": limit,
                             "offending_holdings": offending, "severity": "red",
                             "plain": f"{sec} {current*100:.0f}% > {limit*100:.0f}% cap"})

    approved = set(mandate.get("approved_universe", []))
    offending_univ = [h["ticker"] for h in portfolio["holdings"] if h["ticker"] not in approved]
    passed_univ = len(offending_univ) == 0
    per_rule.append({"rule": "approved_universe", "pass": passed_univ, "current": offending_univ,
                     "limit": list(approved), "offending_holdings": offending_univ,
                     "severity": "red" if not passed_univ else "green"})
    if not passed_univ:
        breaches.append({"rule": "approved_universe", "current": offending_univ, "limit": list(approved),
                         "offending_holdings": offending_univ, "severity": "red",
                         "plain": f"{', '.join(offending_univ)} not in approved list"})

    max_single = mandate.get("max_single_holding", 1.0)
    max_w = max(ticker_w.values()) if ticker_w else 0.0
    offending_single = [t for t, w in ticker_w.items() if w > max_single + _EPS]
    passed_single = len(offending_single) == 0
    per_rule.append({"rule": "max_single_holding", "pass": passed_single,
                     "current": max_w, "limit": max_single,
                     "offending_holdings": offending_single, "severity": "red" if not passed_single else "green"})
    if not passed_single:
        breaches.append({"rule": "max_single_holding", "current": max_w, "limit": max_single,
                         "offending_holdings": offending_single, "severity": "red",
                         "plain": f"Single holding {max_w*100:.0f}% > {max_single*100:.0f}% cap"})

    min_cash = mandate.get("min_cash", 0.0)
    passed_cash = cash_ratio >= min_cash - _EPS
    per_rule.append({"rule": "min_cash", "pass": passed_cash, "current": cash_ratio, "limit": min_cash,
                     "offending_holdings": [], "severity": "red" if not passed_cash else "green"})
    if not passed_cash:
        breaches.append({"rule": "min_cash", "current": cash_ratio, "limit": min_cash,
                         "offending_holdings": [], "severity": "red",
                         "plain": f"Cash {cash_ratio*100:.1f}% < {min_cash*100:.1f}% min"})

    target = mandate.get("target_allocation", {})
    tol = mandate.get("drift_tolerance", 0.05)
    # Drift is ONE-SIDED: assurance flags only OVER-allocation past the target
    # (concentration risk). Being UNDER a target allocation is conservative, not
    # a breach — e.g. Equity 51.3% vs a 60% target with 8% tolerance is a PASS.
    # The mandate cap rules above already catch hard over-limit cases; drift
    # catches the softer "crept past target + tolerance" watch.
    for ac, tgt in target.items():
        current = acw.get(ac, 0.0)
        over = current - tgt
        if over > tol + _EPS:
            offending = [h["ticker"] for h in portfolio["holdings"] if h["asset_class"] == ac]
            per_rule.append({"rule": f"drift:{ac}", "pass": False, "current": current, "limit": tgt,
                             "offending_holdings": offending, "severity": "orange"})
            watches.append({"rule": f"drift:{ac}", "current": current, "limit": tgt,
                            "offending_holdings": offending, "severity": "orange",
                            "plain": f"{ac} {current*100:.1f}% exceeds {tgt*100:.0f}% target by {over*100:.0f}% (tol {tol*100:.0f}%)"})

    # ---- 34k new rules ----
    # Geography caps (red breach when a region's weight exceeds its cap).
    for region, cap in mandate.get("max_region_weight", {}).items():
        current = region_w.get(region, 0.0)
        offending = [h["ticker"] for h in portfolio["holdings"] if h.get("region") == region and current > cap + _EPS]
        passed = current <= cap + _EPS
        per_rule.append({"rule": f"max_region_weight:{region}", "pass": passed, "current": current,
                         "limit": cap, "offending_holdings": offending, "severity": "red" if not passed else "green"})
        if not passed:
            breaches.append({"rule": f"max_region_weight:{region}", "current": current, "limit": cap,
                             "offending_holdings": offending, "severity": "red",
                             "plain": f"{region} {current*100:.0f}% > {cap*100:.0f}% region cap"})

    # ESG exclusion list (red breach if any excluded ticker is held).
    excluded = set(mandate.get("excluded_tickers", []))
    offending_esg = [h["ticker"] for h in portfolio["holdings"] if h["ticker"] in excluded]
    passed_esg = len(offending_esg) == 0
    per_rule.append({"rule": "esg_exclusions", "pass": passed_esg, "current": offending_esg,
                     "limit": list(excluded), "offending_holdings": offending_esg,
                     "severity": "red" if not passed_esg else "green"})
    if not passed_esg:
        breaches.append({"rule": "esg_exclusions", "current": offending_esg, "limit": list(excluded),
                         "offending_holdings": offending_esg, "severity": "red",
                         "plain": f"{', '.join(offending_esg)} on ESG exclusion list"})

    # Top-N concentration cap (red breach if the N largest holdings' combined
    # weight exceeds the limit).
    tn = mandate.get("max_top_n_concentration")
    if tn:
        n = tn.get("n", 5)
        limit = tn.get("limit", 1.0)
        top = sorted(ticker_w.values(), reverse=True)[:n]
        current_topn = sum(top)
        offending_topn = [t for t, _ in sorted(ticker_w.items(), key=lambda kv: kv[1], reverse=True)[:n]]
        passed_topn = current_topn <= limit + _EPS
        per_rule.append({"rule": "max_top_n_concentration", "pass": passed_topn, "current": current_topn,
                         "limit": limit, "n": n, "offending_holdings": offending_topn,
                         "severity": "red" if not passed_topn else "green"})
        if not passed_topn:
            breaches.append({"rule": "max_top_n_concentration", "current": current_topn, "limit": limit, "n": n,
                             "offending_holdings": offending_topn, "severity": "red",
                             "plain": f"Top-{n} holdings {current_topn*100:.0f}% > {limit*100:.0f}% cap"})

    # Liquidity floor (red breach if tier-1 weight falls below the minimum).
    min_liq = mandate.get("min_liquid_pct", 0.0)
    passed_liq = liq1_w >= min_liq - _EPS
    per_rule.append({"rule": "min_liquid_pct", "pass": passed_liq, "current": liq1_w, "limit": min_liq,
                     "offending_holdings": [], "severity": "red" if not passed_liq else "green"})
    if not passed_liq:
        breaches.append({"rule": "min_liquid_pct", "current": liq1_w, "limit": min_liq,
                         "offending_holdings": [], "severity": "red",
                         "plain": f"Liquid (tier-1) {liq1_w*100:.0f}% < {min_liq*100:.0f}% min"})

    return {"status": status_of({"breaches": breaches, "watches": watches, "per_rule": per_rule}),
            "breaches": breaches, "watches": watches, "per_rule": per_rule}


def status_of(rules_result: dict) -> str:
    if rules_result.get("breaches"):
        return "red"
    if rules_result.get("watches"):
        return "orange"
    return "green"