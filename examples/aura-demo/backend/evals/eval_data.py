"""Evaluation dataset for ASSURE Conversational Assurance.

This module contains 50 test cases (30 synthetic + 20 real-book) designed to
regression-test the grounded chat agent. Each case declares the expected intent,
the required citation types, and tokens that must appear in the final answer so
that LLM polish can be verified not to hallucinate or drop engine facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class EvalCase:
    """A single evaluation case for the conversational agent."""

    id: str
    query: str
    source: Literal["synthetic", "real-book"]
    expected_intent: str
    expected_citation_types: list[str]
    required_substrings: list[str] = field(default_factory=list)
    portfolio: dict | None = None
    mandate: dict | None = None
    rules_result: dict | None = None
    client_id: str | None = None
    description: str = ""
    paraphrases: list[str] = field(default_factory=list)


# Shared deterministic mandate used by synthetic fixtures.
MANDATE = {
    "max_asset_class_weight": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0},
    "max_sector_weight": {"Technology": 0.35, "Financials": 0.25},
    "approved_universe": ["SPY", "TLT", "AAPL", "MSFT", "JPM", "XLK"],
    "max_single_holding": 0.4,
    "min_cash": 0.05,
    "target_allocation": {"Equity": 0.55, "Bonds": 0.35, "Cash": 0.1},
    "drift_tolerance": 0.08,
}


def _portfolio_red_concentrated() -> dict:
    return {
        "client_id": "C-EVAL-RED",
        "client_name": "Red Demo Client",
        "adviser": "A-1",
        "cash": 10_000,
        "holdings": [
            {
                "ticker": "SPY",
                "name": "SPDR S&P 500",
                "asset_class": "Equity",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 1000,
                "price": 500,
                "market_value": 500_000,
            },
        ],
        "fum": 510_000,
    }


def _portfolio_green_balanced() -> dict:
    return {
        "client_id": "C-EVAL-GREEN",
        "client_name": "Green Demo Client",
        "adviser": "A-2",
        "cash": 50_000,
        "holdings": [
            {
                "ticker": "TLT",
                "name": "iShares 20+ Year Treasury",
                "asset_class": "Bonds",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 100,
                "price": 95,
                "market_value": 9500,
            },
            {
                "ticker": "SPY",
                "name": "SPDR S&P 500",
                "asset_class": "Equity",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 10,
                "price": 500,
                "market_value": 5000,
            },
        ],
        "fum": 64_500,
    }


def _portfolio_orange_drift() -> dict:
    return {
        "client_id": "C-EVAL-ORANGE",
        "client_name": "Orange Demo Client",
        "adviser": "A-3",
        "cash": 20_000,
        "holdings": [
            {
                "ticker": "SPY",
                "name": "SPDR S&P 500",
                "asset_class": "Equity",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 85,
                "price": 500,
                "market_value": 42_500,
            },
            {
                "ticker": "TLT",
                "name": "iShares 20+ Year Treasury",
                "asset_class": "Bonds",
                "sector": "Broad",
                "region": "US",
                "liquidity_tier": 1,
                "units": 20,
                "price": 95,
                "market_value": 1900,
            },
        ],
        "fum": 64_400,
    }


RR_RED = {
    "status": "red",
    "breaches": [
        {
            "rule": "max_asset_class_weight:Equity",
            "current": 0.98,
            "limit": 0.6,
            "offending_holdings": ["SPY"],
            "severity": "red",
            "plain": "Equity 98.0% exceeds 60.0% cap",
        },
        {
            "rule": "max_single_holding",
            "current": 0.98,
            "limit": 0.4,
            "offending_holdings": ["SPY"],
            "severity": "red",
            "plain": "Single holding 98.0% exceeds 40.0% cap",
        },
        {
            "rule": "min_cash",
            "current": 0.02,
            "limit": 0.05,
            "offending_holdings": [],
            "severity": "red",
            "plain": "Cash 2.0% is below 5.0% minimum",
        },
    ],
    "watches": [],
    "per_rule": [
        {
            "rule": "max_asset_class_weight:Equity",
            "pass": False,
            "current": 0.98,
            "limit": 0.6,
            "offending_holdings": ["SPY"],
            "severity": "red",
        },
        {
            "rule": "max_single_holding",
            "pass": False,
            "current": 0.98,
            "limit": 0.4,
            "offending_holdings": ["SPY"],
            "severity": "red",
        },
        {
            "rule": "min_cash",
            "pass": False,
            "current": 0.02,
            "limit": 0.05,
            "offending_holdings": [],
            "severity": "red",
        },
    ],
}


RR_GREEN = {
    "status": "green",
    "breaches": [],
    "watches": [],
    "per_rule": [
        {
            "rule": "max_asset_class_weight:Equity",
            "pass": True,
            "current": 0.08,
            "limit": 0.6,
            "offending_holdings": [],
            "severity": "green",
        },
        {
            "rule": "min_cash",
            "pass": True,
            "current": 0.77,
            "limit": 0.05,
            "offending_holdings": [],
            "severity": "green",
        },
        {
            "rule": "max_single_holding",
            "pass": True,
            "current": 0.08,
            "limit": 0.4,
            "offending_holdings": [],
            "severity": "green",
        },
    ],
}


RR_ORANGE = {
    "status": "orange",
    "breaches": [],
    "watches": [
        {
            "rule": "max_asset_class_weight:Equity",
            "current": 0.66,
            "limit": 0.6,
            "offending_holdings": ["SPY"],
            "severity": "orange",
            "plain": "Equity 66.0% is near the 60.0% cap; target 55.0% (tolerance 8.0%)",
        },
        {
            "rule": "max_single_holding",
            "current": 0.66,
            "limit": 0.4,
            "offending_holdings": ["SPY"],
            "severity": "orange",
            "plain": "Single holding SPY 66.0% is near the 40.0% cap",
        }
    ],
    "per_rule": [
        {
            "rule": "max_asset_class_weight:Equity",
            "pass": True,
            "current": 0.66,
            "limit": 0.6,
            "offending_holdings": ["SPY"],
            "severity": "orange",
        },
        {
            "rule": "min_cash",
            "pass": True,
            "current": 0.31,
            "limit": 0.05,
            "offending_holdings": [],
            "severity": "green",
        },
        {
            "rule": "max_single_holding",
            "pass": True,
            "current": 0.66,
            "limit": 0.4,
            "offending_holdings": ["SPY"],
            "severity": "orange",
        },
    ],
}


SYNTHETIC_CASES: list[EvalCase] = [
    # ---------- explain_breaches (6 cases) ----------
    EvalCase(
        id="breach-why-red",
        query="Why is this portfolio red?",
        source="synthetic",
        expected_intent="explain_breaches",
        expected_citation_types=["breach"],
        required_substrings=["98", "Equity", "60.0%", "40.0%"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="User asks for breach explanation on a red portfolio.",
        paraphrases=[
            "why is the portfolio breaching?",
            "what violations are there?",
            "tell me about the red flags",
        ],
    ),
    EvalCase(
        id="breach-list",
        query="List the breaches.",
        source="synthetic",
        expected_intent="explain_breaches",
        expected_citation_types=["breach"],
        required_substrings=["max_asset_class_weight:Equity", "max_single_holding"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Explicit request for breach list.",
        paraphrases=["which rules are breached", "show me the violations"],
    ),
    EvalCase(
        id="breach-none",
        query="Are there any breaches?",
        source="synthetic",
        expected_intent="explain_breaches",
        expected_citation_types=[],
        required_substrings=["no breaches", "aligned"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Green portfolio should report no breaches.",
        paraphrases=["is the portfolio in breach", "any violations"],
    ),
    EvalCase(
        id="breach-equity-cap",
        query="Which breach is the equity cap?",
        source="synthetic",
        expected_intent="explain_breaches",
        expected_citation_types=["breach"],
        required_substrings=["Equity", "98.0%", "60.0%", "breach"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Breach answer should quote equity concentration numbers.",
        paraphrases=["explain the equity breach"],
    ),
    EvalCase(
        id="breach-min-cash",
        query="Why is cash in breach?",
        source="synthetic",
        expected_intent="explain_breaches",
        expected_citation_types=["breach"],
        required_substrings=["min_cash", "2.0%", "5.0%"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Catch the min_cash breach row in the response.",
        paraphrases=["cash is too low and breaching", "minimum cash rule is breached"],
    ),
    EvalCase(
        id="breach-multi",
        query="How many breaches are there?",
        source="synthetic",
        expected_intent="explain_breaches",
        expected_citation_types=["breach"],
        required_substrings=["3", "breach"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Answer should report exactly two breaches.",
        paraphrases=["count the breaches"],
    ),
    # ---------- explain_watches (6 cases) ----------
    EvalCase(
        id="watch-list",
        query="What are the watches?",
        source="synthetic",
        expected_intent="explain_watches",
        expected_citation_types=["watch"],
        required_substrings=["Equity", "66.0%", "55.0%"],
        portfolio=_portfolio_orange_drift(),
        mandate=MANDATE,
        rules_result=RR_ORANGE,
        description="Orange portfolio should list the drift watch.",
        paraphrases=["show me watches", "any drift warnings"],
    ),
    EvalCase(
        id="watch-orange",
        query="Why is the portfolio orange?",
        source="synthetic",
        expected_intent="explain_watches",
        expected_citation_types=["watch"],
        required_substrings=["watch", "target"],
        portfolio=_portfolio_orange_drift(),
        mandate=MANDATE,
        rules_result=RR_ORANGE,
        description="Status orange maps to drift watches.",
        paraphrases=["portfolio is under watch", "drift attention orange"],
    ),
    EvalCase(
        id="watch-none",
        query="Are there any watches?",
        source="synthetic",
        expected_intent="explain_watches",
        expected_citation_types=[],
        required_substrings=["no drift watches"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Green portfolio has no watches.",
        paraphrases=["any drift"],
    ),
    EvalCase(
        id="watch-close-to-breach",
        query="How close to a breach is the watch?",
        source="synthetic",
        expected_intent="explain_watches",
        expected_citation_types=["watch"],
        required_substrings=["66.0%", "60.0%"],
        portfolio=_portfolio_orange_drift(),
        mandate=MANDATE,
        rules_result=RR_ORANGE,
        description="Watch answer should quote current vs limit.",
        paraphrases=["watch near a breach"],
    ),
    EvalCase(
        id="watch-single-holding-drift",
        query="Is the single holding watch drifting?",
        source="synthetic",
        expected_intent="explain_watches",
        expected_citation_types=["watch"],
        required_substrings=["66.0%", "40.0%"],
        portfolio=_portfolio_orange_drift(),
        mandate=MANDATE,
        rules_result=RR_ORANGE,
        description="Watch answer should surface single-holding drift.",
        paraphrases=["single holding watch"],
    ),
    EvalCase(
        id="watch-asset-class",
        query="Tell me about the asset class watch.",
        source="synthetic",
        expected_intent="explain_watches",
        expected_citation_types=["watch"],
        required_substrings=["Equity", "target"],
        portfolio=_portfolio_orange_drift(),
        mandate=MANDATE,
        rules_result=RR_ORANGE,
        description="Named asset-class watch query.",
        paraphrases=["asset class drift"],
    ),
    # ---------- explain_rule (6 cases) ----------
    EvalCase(
        id="rule-equity",
        query="Explain the equity rule.",
        source="synthetic",
        expected_intent="explain_rule",
        expected_citation_types=["per_rule"],
        required_substrings=["max_asset_class_weight:Equity", "0.6"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Rule explanation should cite the exact per_rule row.",
        paraphrases=["explain the equity cap rule", "what is the equity limit"],
    ),
    EvalCase(
        id="rule-single-holding",
        query="Tell me about the single holding rule.",
        source="synthetic",
        expected_intent="explain_rule",
        expected_citation_types=["per_rule"],
        required_substrings=["max_single_holding", "0.4"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Rule explanation for single holding cap.",
        paraphrases=["explain the single holding rule", "what is the one holding cap"],
    ),
    EvalCase(
        id="rule-cash",
        query="What does the cash rule say?",
        source="synthetic",
        expected_intent="explain_rule",
        expected_citation_types=["per_rule"],
        required_substrings=["min_cash", "0.05"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Cash rule explanation.",
        paraphrases=["explain the minimum cash rule", "what does the cash rule say"],
    ),
    EvalCase(
        id="rule-unknown",
        query="What is the cryptocurrency rule?",
        source="synthetic",
        expected_intent="explain_rule",
        expected_citation_types=["per_rule"],
        required_substrings=["couldn't match", "rules"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Unknown rule should fall back to listing all checked rules.",
        paraphrases=["explain the crypto rule", "what is the cryptocurrency rule"],
    ),
    EvalCase(
        id="rule-pass",
        query="Does the min cash rule pass?",
        source="synthetic",
        expected_intent="explain_rule",
        expected_citation_types=["per_rule"],
        required_substrings=["PASS", "77", "0.05"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Rule question on a passing check.",
        paraphrases=["does the minimum cash rule pass", "is the minimum cash rule ok"],
    ),
    EvalCase(
        id="rule-token-match",
        query="Tell me about the technology rule.",
        source="synthetic",
        expected_intent="explain_rule",
        expected_citation_types=["per_rule"],
        required_substrings=["couldn't match"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Sector token not in per_rule should not false-match.",
        paraphrases=["explain the technology sector rule", "what is the technology rule"],
    ),
    # ---------- what_if_trade (6 cases) ----------
    EvalCase(
        id="whatif-buy-equity",
        query="What if I buy 10 SPY?",
        source="synthetic",
        expected_intent="what_if_trade",
        expected_citation_types=["what_if"],
        required_substrings=["buy", "10", "SPY"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="What-if buy increases equity exposure.",
        paraphrases=["what if I purchase 10 SPY", "if I buy ten SPY"],
    ),
    EvalCase(
        id="whatif-sell-bonds",
        query="What if I sell 50 TLT?",
        source="synthetic",
        expected_intent="what_if_trade",
        expected_citation_types=["what_if"],
        required_substrings=["sell", "50", "TLT"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="What-if sell should reference TLT.",
        paraphrases=["what if I sell 50 TLT", "if I sell fifty TLT"],
    ),
    EvalCase(
        id="whatif-fix-breach",
        query="What if I sell 900 SPY?",
        source="synthetic",
        expected_intent="what_if_trade",
        expected_citation_types=["what_if"],
        required_substrings=["sell", "900", "SPY", "red", "green"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="What-if trade that fixes the breach.",
        paraphrases=["what if I sell 900 SPY", "if I sell nine hundred SPY"],
    ),
    EvalCase(
        id="whatif-missing-ticker",
        query="What if I buy 10 NVDA?",
        source="synthetic",
        expected_intent="what_if_trade",
        expected_citation_types=[],
        required_substrings=["price", "NVDA"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Ticker not in portfolio should ask for price.",
        paraphrases=["what if I purchase 10 NVDA", "if I buy 10 NVDA"],
    ),
    EvalCase(
        id="whatif-no-trade",
        query="What happens if I move to cash?",
        source="synthetic",
        expected_intent="what_if_trade",
        expected_citation_types=[],
        required_substrings=["buy 50 SPY", "sell 100 AAPL"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Unparsable trade should ask for clarification.",
        paraphrases=["what if I move to cash", "if I go to cash"],
    ),
    EvalCase(
        id="whatif-introduces-breach",
        query="What if I buy 1000 SPY?",
        source="synthetic",
        expected_intent="what_if_trade",
        expected_citation_types=["what_if"],
        required_substrings=["buy", "1000", "SPY", "breach"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="What-if trade that creates a breach.",
        paraphrases=["what if I buy 1000 SPY", "if I buy a thousand SPY"],
    ),
    # ---------- explain_cash (4 cases) ----------
    EvalCase(
        id="cash-position",
        query="What is the cash position?",
        source="synthetic",
        expected_intent="explain_cash",
        expected_citation_types=["per_rule"],
        required_substrings=["77.5%", "5.0%", "PASS"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Cash question on green portfolio.",
        paraphrases=["how much cash", "cash percentage"],
    ),
    EvalCase(
        id="cash-low",
        query="Is cash too low?",
        source="synthetic",
        expected_intent="explain_cash",
        expected_citation_types=["per_rule"],
        required_substrings=["2.0%", "5.0%", "FAIL"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Cash question on breaching portfolio.",
        paraphrases=["cash below minimum"],
    ),
    EvalCase(
        id="cash-liquid",
        query="How liquid is the portfolio?",
        source="synthetic",
        expected_intent="explain_cash",
        expected_citation_types=["per_rule"],
        required_substrings=["77.5%"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Liquidity phrasing should still route to cash.",
        paraphrases=["liquidity position"],
    ),
    EvalCase(
        id="cash-rule-none",
        query="How much cash do we hold?",
        source="synthetic",
        expected_intent="explain_cash",
        expected_citation_types=["cash"],
        required_substrings=["77.5%"],
        portfolio=_portfolio_green_balanced(),
        mandate={k: v for k, v in MANDATE.items() if k != "min_cash"},
        rules_result={
            "status": "green",
            "breaches": [],
            "watches": [],
            "per_rule": [
                {
                    "rule": "max_asset_class_weight:Equity",
                    "pass": True,
                    "current": 0.08,
                    "limit": 0.6,
                    "offending_holdings": [],
                    "severity": "green",
                },
            ],
        },
        description="Cash question when no min_cash rule applies.",
        paraphrases=["cash amount"],
    ),
    # ---------- summarize / status (2 cases) ----------
    EvalCase(
        id="summary-green",
        query="Summarize the portfolio.",
        source="synthetic",
        expected_intent="summarize",
        expected_citation_types=["status"],
        required_substrings=["Green Demo Client", "green", "TLT", "77.5%"],
        portfolio=_portfolio_green_balanced(),
        mandate=MANDATE,
        rules_result=RR_GREEN,
        description="Summary of green portfolio.",
        paraphrases=["give me an overview", "portfolio status"],
    ),
    EvalCase(
        id="summary-red",
        query="How is the portfolio doing?",
        source="synthetic",
        expected_intent="summarize",
        expected_citation_types=["status"],
        required_substrings=["Red Demo Client", "red", "SPY", "Breaches: 3"],
        portfolio=_portfolio_red_concentrated(),
        mandate=MANDATE,
        rules_result=RR_RED,
        description="Summary of red portfolio.",
        paraphrases=["portfolio health", "tell me about this client"],
    ),
]


# Real-book cases: sample client_ids from the seeded book.
# These are tolerant assertions handled by the runner.
REAL_BOOK_CLIENT_IDS: list[str] = [
    "c00000",  # green expected
    "c00003",  # orange expected
    "c00004",  # varied
    "c00010",
    "c00020",
    "c00030",
    "c00100",
    "c00500",
    "c01000",
    "c02000",
    "c03000",
    "c04000",
    "c05000",
    "c06000",
    "c07000",
    "c08000",
    "c09000",
    "c10000",
    "c20000",
    "c30000",
]

REAL_BOOK_QUERIES: list[tuple[str, str]] = [
    ("summarize", "summarize"),
    ("why is this portfolio red", "explain_breaches"),
    ("what are the watches", "explain_watches"),
    ("what is the cash position", "explain_cash"),
    ("what if I sell 10 SPY", "what_if_trade"),
    ("explain the equity rule", "explain_rule"),
]

REAL_BOOK_CASES: list[EvalCase] = [
    EvalCase(
        id=f"real-{client_id}-{intent}",
        query=query,
        source="real-book",
        expected_intent=intent,
        expected_citation_types=[],
        required_substrings=[],
        client_id=client_id,
        description=f"Real book client {client_id} asked: {query!r}",
    )
    for client_id in REAL_BOOK_CLIENT_IDS
    for query, intent in REAL_BOOK_QUERIES
]


ALL_EVAL_CASES: list[EvalCase] = SYNTHETIC_CASES + REAL_BOOK_CASES

EVAL_CATEGORIES: dict[str, list[EvalCase]] = {
    "explain_breaches": [c for c in SYNTHETIC_CASES if c.expected_intent == "explain_breaches"],
    "explain_watches": [c for c in SYNTHETIC_CASES if c.expected_intent == "explain_watches"],
    "explain_rule": [c for c in SYNTHETIC_CASES if c.expected_intent == "explain_rule"],
    "what_if_trade": [c for c in SYNTHETIC_CASES if c.expected_intent == "what_if_trade"],
    "explain_cash": [c for c in SYNTHETIC_CASES if c.expected_intent == "explain_cash"],
    "summarize": [c for c in SYNTHETIC_CASES if c.expected_intent == "summarize"],
    "real-book": REAL_BOOK_CASES,
}
