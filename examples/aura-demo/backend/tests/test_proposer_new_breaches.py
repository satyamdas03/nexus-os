"""Task 6a: proposer handles the 4 new 34k breach types deterministically.

Each test red-loads a portfolio that triggers one of the new rules, runs the
proposer (no Claude), applies the trades, and re-checks — the gate must be
green. The default priority list must cover all 10 breach types so a strategy
without a custom order still addresses every rule the engine can emit.
"""
from core import rules_engine, trades
from core.trades import UNIVERSE
from agents.hermes.proposer import propose, DEFAULT_BREACH_PRIORITY
from agents.hermes.loop import _severity  # reuse severity helper

STRAT = {"variables": {
    "breach_priority_order": {"value": DEFAULT_BREACH_PRIORITY},
    "preferred_trim_method": {"value": "liquidate"},
    "replacement_preference": {"value": "SPY"},
    "min_trade_size": {"value": 0.0},
    "max_trades_per_portfolio": {"value": 8},
    "cash_buffer_target": {"value": 0.0},
}}

P = lambda holdings, cash=0: {"client_id": "x", "client_name": "X", "adviser": "a", "fum": 1_000_000, "holdings": holdings, "cash": cash}

def h(t, mv, ac="Equity", sec="Broad", reg="US", tier=1):
    meta = {"SPY": ("Equity", "Broad", "US", 1), "QQQ": ("Equity", "Broad", "US", 1), "VWO": ("Equity", "Broad", "EM", 2),
            "MCHI": ("Equity", "Technology", "EM", 3), "XLE": ("Equity", "Energy", "US", 2), "TLT": ("Bonds", "Govt", "US", 1)}
    a, s, r, lt = meta.get(t, (ac, sec, reg, tier))
    # Use the UNIVERSE base_price so apply_trades' fallback (UNIVERSE base_price
    # for re-buys of fully-sold tickers) stays consistent with the held price.
    price = UNIVERSE.get(t, {}).get("base_price", 100.0)
    return {"ticker": t, "name": t, "asset_class": a, "sector": s, "region": r, "liquidity_tier": lt, "units": mv / price, "price": price, "market_value": mv}

MANDATE = {
    "max_asset_class_weight": {"Equity": 1.0, "Bonds": 1.0, "Crypto": 0.0, "Commodity": 0.2, "Cash": 1.0},
    "max_sector_weight": {"Broad": 1.0, "Technology": 1.0, "Energy": 1.0, "Govt": 1.0},
    "approved_universe": ["SPY", "QQQ", "VWO", "MCHI", "XLE", "TLT"],
    "max_single_holding": 1.0, "min_cash": 0.0, "target_allocation": {}, "drift_tolerance": 0.2,
    "max_region_weight": {"US": 0.50, "ExUS": 0.50, "EM": 0.20},
    "excluded_tickers": [], "max_top_n_concentration": {"n": 5, "limit": 0.95}, "min_liquid_pct": 0.40,
}


def _gate(p, m):
    rr = rules_engine.check(p, m)
    prop = propose(p, rr, STRAT)
    post = trades.apply_trades(p, prop["trades"])
    post_rr = rules_engine.check(post, m)
    return prop, post_rr


def test_region_breach_proposed_and_gated():
    p = P([h("SPY", 40000), h("QQQ", 40000), h("VWO", 20000)])  # US=80% > 50%
    prop, post_rr = _gate(p, MANDATE)
    assert prop["trades"], "expected trades for region breach"
    assert not post_rr["breaches"], f"gate still red: {post_rr['breaches']}"


def test_esg_exclusion_proposed_and_gated():
    m = dict(MANDATE); m["excluded_tickers"] = ["MCHI"]
    p = P([h("SPY", 50000), h("MCHI", 30000), h("QQQ", 20000)])
    prop, post_rr = _gate(p, m)
    assert any(t["ticker"] == "MCHI" and t["action"] == "sell" for t in prop["trades"])
    assert not post_rr["breaches"]


def test_topn_concentration_proposed_and_gated():
    m = dict(MANDATE); m["max_top_n_concentration"] = {"n": 2, "limit": 0.50}
    p = P([h("SPY", 60000), h("QQQ", 40000)])  # top-2 = 100% > 50%
    prop, post_rr = _gate(p, m)
    assert prop["trades"]
    assert not post_rr["breaches"]


def test_min_liquid_pct_proposed_and_gated():
    p = P([h("MCHI", 50000), h("XLE", 50000)])  # tier-1 weight = 0 < 0.40
    prop, post_rr = _gate(p, MANDATE)
    assert prop["trades"]
    assert not post_rr["breaches"]


def test_default_priority_covers_all_ten_types():
    assert set(DEFAULT_BREACH_PRIORITY) >= {
        "max_asset_class_weight", "max_sector_weight", "approved_universe",
        "max_single_holding", "min_cash", "drift",
        "max_region_weight", "esg_exclusions", "max_top_n_concentration", "min_liquid_pct",
    }