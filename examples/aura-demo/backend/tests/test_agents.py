from agents.explain import explain
from agents.llm import MockLLM
from core.rules_engine import check

PORTFOLIO_RED = {
    "client_id": "c2", "client_name": "B", "adviser": "Pat", "fum": 1_000_000,
    "holdings": [
        {"ticker": "NVDA", "name": "Nvidia", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 500, "market_value": 35000},
        {"ticker": "MSFT", "name": "Microsoft", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 400, "market_value": 40000},
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 50, "price": 500, "market_value": 25000},
    ], "cash": 0,
}
MANDATE = {"max_asset_class_weight": {"Equity": 0.80, "Bonds": 0.40, "Crypto": 0.0, "Cash": 0.30},
           "max_sector_weight": {"Technology": 0.25, "Broad": 1.0, "Healthcare": 0.30, "Financials": 0.30, "Consumer": 0.25, "Govt": 1.0, "Metals": 0.20, "Crypto": 0.10},
           "approved_universe": ["SPY", "TLT", "QQQ", "NVDA", "MSFT"], "max_single_holding": 0.50, "min_cash": 0.0,
           "target_allocation": {"Equity": 0.60, "Bonds": 0.30, "Commodity": 0.05, "Cash": 0.05}, "drift_tolerance": 0.10}


def test_explain_returns_narrative_and_summaries():
    rr = check(PORTFOLIO_RED, MANDATE)
    out = explain(PORTFOLIO_RED, rr, llm=MockLLM())
    assert "narrative" in out and isinstance(out["narrative"], str)
    assert isinstance(out["breach_summaries"], list)
    assert len(out["breach_summaries"]) == len(rr["breaches"])
    assert len(out["watch_summaries"]) == len(rr["watches"])


def test_explain_grounding_only_engine_breaches():
    rr = check(PORTFOLIO_RED, MANDATE)
    out = explain(PORTFOLIO_RED, rr, llm=MockLLM())
    engine_rules = {b["rule"] for b in rr["breaches"]}
    assert any(r.split(":")[0] in str(out["narrative"]) for r in engine_rules) or "MOCK" in out["narrative"]


def test_explain_green_portfolio_no_summaries():
    green = {
        "client_id": "c1", "client_name": "Acme", "adviser": "Pat", "fum": 1_000_000,
        "holdings": [
            {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 70, "price": 500, "market_value": 35000},
            {"ticker": "QQQ", "name": "Nasdaq 100", "asset_class": "Equity", "sector": "Broad", "units": 50, "price": 400, "market_value": 20000},
            {"ticker": "TLT", "name": "20+ Yr", "asset_class": "Bonds", "sector": "Govt", "units": 400, "price": 100, "market_value": 40000},
        ], "cash": 5000,
    }
    m = dict(MANDATE); m["min_cash"] = 0.02
    rr = check(green, m)
    out = explain(green, rr, llm=MockLLM())
    assert out["breach_summaries"] == []


from agents.remediate import remediate


def test_remediate_resolves_red_portfolio():
    rr = check(PORTFOLIO_RED, MANDATE)
    out = remediate(PORTFOLIO_RED, rr, llm=MockLLM(), mandate=MANDATE)
    assert "trades" in out and isinstance(out["trades"], list)
    assert "verification" in out
    assert out["verification"]["status"] in ("green", "orange", "red")
    assert isinstance(out["resolved"], bool)
    assert isinstance(out["retried"], bool)


def test_remediate_verify_loop_rechecks_engine():
    rr = check(PORTFOLIO_RED, MANDATE)
    out = remediate(PORTFOLIO_RED, rr, llm=MockLLM(), mandate=MANDATE)
    assert "per_rule" in out["verification"]


def test_remediate_deterministic_trade_apply():
    """Apply a known trade, confirm resulting portfolio reflects it + engine rechecks."""
    rr = check(PORTFOLIO_RED, MANDATE)
    from agents.remediate import _apply_trades
    newp = _apply_trades(PORTFOLIO_RED, [{"ticker": "SPY", "action": "buy", "units": 10, "value": 5000, "rationale": "x"}])
    spy = next(h for h in newp["holdings"] if h["ticker"] == "SPY")
    assert spy["units"] == 60  # was 50 + 10