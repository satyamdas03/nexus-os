"""Tests for the Conversational Assurance agent."""

import pytest

from agents.conversational import chat


MANDATE = {
    "max_asset_class_weight": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0},
    "max_single_holding": 0.4,
    "min_cash": 0.05,
}


def portfolio(status="green"):
    if status == "red":
        holdings = [
            {"ticker": "SPY", "asset_class": "Equity", "sector": "Broad", "units": 1000, "price": 500, "market_value": 500_000},
        ]
        cash = 10_000
    else:
        holdings = [
            {"ticker": "TLT", "asset_class": "Bonds", "sector": "Broad", "units": 100, "price": 95, "market_value": 9500},
            {"ticker": "SPY", "asset_class": "Equity", "sector": "Broad", "units": 10, "price": 500, "market_value": 5000},
        ]
        cash = 50_000
    return {
        "client_id": "C-001",
        "client_name": "Test Client",
        "adviser": "A-1",
        "cash": cash,
        "holdings": holdings,
        "fum": cash + sum(h["market_value"] for h in holdings),
    }


def rules_result(status="green"):
    if status == "red":
        return {
            "status": "red",
            "breaches": [
                {"rule": "max_asset_class_weight:Equity", "current": 0.98, "limit": 0.6,
                 "offending_holdings": ["SPY"], "severity": "red", "plain": "Equity 98% > 60% cap"},
                {"rule": "max_single_holding", "current": 0.98, "limit": 0.4,
                 "offending_holdings": ["SPY"], "severity": "red", "plain": "Single holding 98% > 40% cap"},
            ],
            "watches": [],
            "per_rule": [
                {"rule": "max_asset_class_weight:Equity", "pass": False, "current": 0.98, "limit": 0.6,
                 "offending_holdings": ["SPY"], "severity": "red"},
                {"rule": "max_single_holding", "pass": False, "current": 0.98, "limit": 0.4,
                 "offending_holdings": ["SPY"], "severity": "red"},
                {"rule": "min_cash", "pass": True, "current": 0.02, "limit": 0.05,
                 "offending_holdings": [], "severity": "green"},
            ],
        }
    return {
        "status": "green",
        "breaches": [],
        "watches": [],
        "per_rule": [
            {"rule": "max_asset_class_weight:Equity", "pass": True, "current": 0.06, "limit": 0.6,
             "offending_holdings": [], "severity": "green"},
            {"rule": "min_cash", "pass": True, "current": 0.77, "limit": 0.05,
             "offending_holdings": [], "severity": "green"},
        ],
    }


def test_explain_breaches_intent():
    p = portfolio("red")
    rr = rules_result("red")
    ans = chat("Why is this portfolio red?", p, MANDATE, rr)
    assert ans.intent == "explain_breaches"
    assert "98%" in ans.answer or "Equity" in ans.answer
    assert len(ans.citations) == 2


def test_explain_rule_intent():
    p = portfolio("red")
    rr = rules_result("red")
    ans = chat("Tell me about the equity rule", p, MANDATE, rr)
    assert ans.intent == "explain_rule"
    assert ans.citations[0]["rule"] == "max_asset_class_weight:Equity"


def test_summarize_intent():
    p = portfolio("green")
    rr = rules_result("green")
    ans = chat("Give me a summary", p, MANDATE, rr)
    assert ans.intent == "summarize"
    assert "Test Client" in ans.answer
    assert ans.citations[0]["type"] == "status"


def test_explain_cash_intent():
    p = portfolio("green")
    rr = rules_result("green")
    ans = chat("What is the cash position?", p, MANDATE, rr)
    assert ans.intent == "explain_cash"
    assert "%" in ans.answer


def test_what_if_trade_intent():
    p = portfolio("green")
    rr = rules_result("green")
    ans = chat("What if I sell 5 TLT?", p, MANDATE, rr)
    assert ans.intent == "what_if_trade"
    assert "TLT" in ans.answer
    assert ans.citations[0]["type"] == "what_if"


def test_grounded_answer_includes_citations():
    p = portfolio("red")
    rr = rules_result("red")
    ans = chat("Why is it breaching?", p, MANDATE, rr)
    assert ans.grounded is True
    assert any(c["type"] == "breach" for c in ans.citations)


def test_suggested_followups_for_red():
    p = portfolio("red")
    rr = rules_result("red")
    ans = chat("Hi", p, MANDATE, rr)
    assert "Why is it red?" in ans.suggested_followups
