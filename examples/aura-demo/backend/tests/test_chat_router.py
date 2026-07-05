"""Tests for the chat router."""

import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_chat_endpoint_unknown_portfolio():
    r = client.post("/portfolio/missing-client/chat", json={"query": "Why red?"})
    assert r.status_code == 404


def test_chat_generic_requires_fields():
    r = client.post("/chat", json={"query": "summary"})
    assert r.status_code == 422


def test_chat_generic_returns_grounded_answer():
    portfolio = {
        "client_id": "C-TEST",
        "client_name": "Test",
        "adviser": "A-1",
        "cash": 50_000,
        "holdings": [
            {"ticker": "SPY", "asset_class": "Equity", "sector": "Broad", "units": 10, "price": 500, "market_value": 5000},
            {"ticker": "TLT", "asset_class": "Bonds", "sector": "Broad", "units": 100, "price": 95, "market_value": 9500},
        ],
        "fum": 64_500,
    }
    mandate = {
        "rules": [
            {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0}}},
            {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
            {"type": "min_cash", "parameters": {"min_weight": 0.05}},
        ]
    }
    rules_result = {
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
    r = client.post("/chat", json={
        "query": "summarize",
        "portfolio": portfolio,
        "mandate": mandate,
        "rules_result": rules_result,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "summarize"
    assert data["grounded"] is True
    assert len(data["citations"]) >= 1


def test_voice_status_unconfigured():
    r = client.get("/voice/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False


def test_voice_token_unconfigured():
    r = client.post("/voice/token/C-001")
    assert r.status_code == 503


def test_voice_status_configured(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    r = client.get("/voice/status")
    assert r.status_code == 200
    assert r.json()["configured"] is True


def test_voice_token_configured(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    r = client.post("/voice/token/C-001")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["room"] == "assure-C-001"
    assert data["token"]
    assert data["url"] == "wss://test.livekit.cloud"
