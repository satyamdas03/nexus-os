import copy

from core.rules_engine import check, status_of

PORTFOLIO_GREEN = {
    "client_id": "c1", "client_name": "Acme", "adviser": "Pat", "fum": 1_000_000,
    "holdings": [
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 70, "price": 500, "market_value": 35000},
        {"ticker": "QQQ", "name": "Nasdaq 100", "asset_class": "Equity", "sector": "Broad", "units": 50, "price": 400, "market_value": 20000},
        {"ticker": "TLT", "name": "20+ Yr Treasury", "asset_class": "Bonds", "sector": "Govt", "units": 400, "price": 100, "market_value": 40000},
    ],
    "cash": 5000,
}
MANDATE_OK = {
    "max_asset_class_weight": {"Equity": 0.80, "Bonds": 0.40, "Crypto": 0.0, "Cash": 0.30},
    "max_sector_weight": {"Technology": 0.25, "Healthcare": 0.30, "Broad": 1.0, "Govt": 1.0, "Consumer": 0.25, "Financials": 0.30, "Metals": 0.20, "Crypto": 0.10},
    "approved_universe": ["SPY", "TLT", "QQQ"],
    "max_single_holding": 0.50,
    "min_cash": 0.02,
    "target_allocation": {"Equity": 0.50, "Bonds": 0.50},
    "drift_tolerance": 0.10,
}


def test_green_portfolio_passes_all_rules():
    r = check(PORTFOLIO_GREEN, MANDATE_OK)
    assert status_of(r) == "green"
    assert r["breaches"] == []


def test_sector_breach_red():
    p = {
        "client_id": "c2", "client_name": "B", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "NVDA", "name": "Nvidia", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 500, "market_value": 35000},
            {"ticker": "MSFT", "name": "Microsoft", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 400, "market_value": 40000},
            {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 50, "price": 500, "market_value": 25000},
        ],
        "cash": 0,
    }
    m = dict(MANDATE_OK)
    m["min_cash"] = 0.0
    r = check(p, m)
    tech = next(pr for pr in r["per_rule"] if pr["rule"] == "max_sector_weight:Technology")
    assert tech["pass"] is False
    assert tech["severity"] == "red"
    assert "NVDA" in tech["offending_holdings"] or "MSFT" in tech["offending_holdings"]
    assert status_of(r) == "red"
    assert any(b["rule"] == "max_sector_weight:Technology" for b in r["breaches"])


def test_approved_universe_breach_red():
    p = {
        "client_id": "c3", "client_name": "C", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "AVAX", "name": "Avalanche", "asset_class": "Crypto", "sector": "Crypto", "units": 100, "price": 30, "market_value": 3000},
            {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 100, "price": 500, "market_value": 50000},
        ],
        "cash": 1000,
    }
    m = dict(MANDATE_OK)
    m["min_cash"] = 0.0
    r = check(p, m)
    assert any(pr["rule"] == "approved_universe" and not pr["pass"] for pr in r["per_rule"])
    assert status_of(r) == "red"


def test_drift_orange_not_red():
    p = {
        "client_id": "c4", "client_name": "D", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 62, "price": 500, "market_value": 31000},
            {"ticker": "QQQ", "name": "Nasdaq 100", "asset_class": "Equity", "sector": "Broad", "units": 74, "price": 420, "market_value": 31080},
            {"ticker": "TLT", "name": "20+ Yr", "asset_class": "Bonds", "sector": "Govt", "units": 379, "price": 100, "market_value": 37900},
        ],
        "cash": 0,
    }
    m = dict(MANDATE_OK)
    m["min_cash"] = 0.0
    r = check(p, m)
    drift = next(pr for pr in r["per_rule"] if pr["rule"].startswith("drift"))
    assert drift["severity"] == "orange"
    assert status_of(r) == "orange"
    assert r["breaches"] == []
    assert len(r["watches"]) >= 1


# ---- 34k new rules: holdings carry region + liquidity_tier ----
PORTFOLIO_REGION = {
    "client_id": "r1", "client_name": "R", "adviser": "Pat", "fum": 1_000_000,
    "holdings": [
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 100, "price": 500, "market_value": 50000},
        {"ticker": "QQQ", "name": "Nasdaq", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 100, "price": 420, "market_value": 42000},
        {"ticker": "VWO", "name": "EM", "asset_class": "Equity", "sector": "Broad", "region": "EM", "liquidity_tier": 2, "units": 100, "price": 45, "market_value": 4500},
    ],
    "cash": 3500,
}
MANDATE_NEW = {
    "max_asset_class_weight": {"Equity": 0.95, "Bonds": 0.50, "Crypto": 0.0, "Commodity": 0.20, "Cash": 1.0},
    "max_sector_weight": {"Broad": 1.0, "Technology": 0.30},
    "approved_universe": ["SPY", "QQQ", "VWO", "TLT"],
    "max_single_holding": 0.50,
    "min_cash": 0.02,
    "target_allocation": {"Equity": 0.90},
    "drift_tolerance": 0.20,
    "max_region_weight": {"US": 0.93, "ExUS": 0.50, "EM": 0.10},
    "excluded_tickers": ["MCHI"],
    "max_top_n_concentration": {"n": 5, "limit": 0.95},
    "min_liquid_pct": 0.40,
}


def test_region_cap_breach_red():
    p = copy.deepcopy(PORTFOLIO_REGION)
    p["holdings"][1]["market_value"] = 60000  # US weight now > 0.93
    m = copy.deepcopy(MANDATE_NEW)
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "max_region_weight:US")
    assert rule["pass"] is False
    assert rule["severity"] == "red"
    assert any(b["rule"] == "max_region_weight:US" for b in r["breaches"])


def test_region_cap_pass_when_under():
    r = check(PORTFOLIO_REGION, MANDATE_NEW)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "max_region_weight:US")
    assert rule["pass"] is True


def test_esg_exclusion_breach_red():
    p = copy.deepcopy(PORTFOLIO_REGION)
    p["holdings"].append({"ticker": "MCHI", "name": "China", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 3, "units": 100, "price": 55, "market_value": 5500})
    m = copy.deepcopy(MANDATE_NEW)
    m["excluded_tickers"] = ["MCHI"]
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "esg_exclusions")
    assert rule["pass"] is False
    assert "MCHI" in rule["offending_holdings"]
    assert any(b["rule"] == "esg_exclusions" for b in r["breaches"])


def test_esg_exclusion_pass_when_clean():
    r = check(PORTFOLIO_REGION, MANDATE_NEW)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "esg_exclusions")
    assert rule["pass"] is True


def test_top_n_concentration_breach_red():
    p = {
        "client_id": "t1", "client_name": "T", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 200, "price": 500, "market_value": 100000},
            {"ticker": "QQQ", "name": "Nasdaq", "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1, "units": 100, "price": 420, "market_value": 42000},
        ],
        "cash": 0,
    }
    m = dict(MANDATE_NEW)
    m["max_top_n_concentration"] = {"n": 2, "limit": 0.60}
    m["min_cash"] = 0.0
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "max_top_n_concentration")
    assert rule["pass"] is False
    assert any(b["rule"] == "max_top_n_concentration" for b in r["breaches"])


def test_min_liquid_pct_breach_red():
    # All weight in tier-2/3; tier-1 weight = 0 < 0.40
    p = {
        "client_id": "l1", "client_name": "L", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "MCHI", "name": "China", "asset_class": "Equity", "sector": "Technology", "region": "EM", "liquidity_tier": 3, "units": 1000, "price": 55, "market_value": 55000},
            {"ticker": "XLE", "name": "Energy", "asset_class": "Equity", "sector": "Energy", "region": "US", "liquidity_tier": 2, "units": 1000, "price": 90, "market_value": 90000},
        ],
        "cash": 0,
    }
    m = dict(MANDATE_NEW)
    m["approved_universe"] = ["MCHI", "XLE", "SPY"]
    m["max_asset_class_weight"] = {"Equity": 1.0, "Bonds": 0.5, "Crypto": 0.0, "Commodity": 0.2, "Cash": 1.0}
    m["max_sector_weight"] = {"Broad": 1.0, "Technology": 1.0, "Energy": 1.0}
    m["max_region_weight"] = {"US": 1.0, "ExUS": 1.0, "EM": 1.0}
    m["max_top_n_concentration"] = {"n": 5, "limit": 1.0}
    m["max_single_holding"] = 1.0
    m["min_cash"] = 0.0
    m["min_liquid_pct"] = 0.40
    r = check(p, m)
    rule = next(pr for pr in r["per_rule"] if pr["rule"] == "min_liquid_pct")
    assert rule["pass"] is False
    assert any(b["rule"] == "min_liquid_pct" for b in r["breaches"])


def test_existing_six_rules_still_pass_for_green_book():
    r = check(PORTFOLIO_GREEN, MANDATE_OK)
    assert status_of(r) == "green"
    assert r["breaches"] == []