"""Tests for the chat and voice routers."""

import pytest
from fastapi.testclient import TestClient

from agents import voice as voice_mod
from main import app
from tests.helpers import auth_client, build_db


def _fake_voice_token(client_id, room_name=None, identity=None, ttl_seconds=3600):
    return voice_mod.VoiceToken(
        token="fake-token",
        url="wss://test.livekit.cloud",
        room=room_name or f"assure-{client_id}",
        identity=identity or f"user-{client_id}",
    )


def _configure_voice(monkeypatch):
    """Patch the voice adapter so configured-token tests work offline without
    the LiveKit SDK or real credentials."""
    import routers.voice as router_voice

    monkeypatch.setattr(voice_mod, "is_configured", lambda: True)
    monkeypatch.setattr(voice_mod, "create_token", _fake_voice_token)
    monkeypatch.setattr(router_voice, "is_configured", lambda: True)
    monkeypatch.setattr(router_voice, "create_token", _fake_voice_token)


@pytest.fixture
def client():
    """Authenticated admin client backed by a small temp book."""
    conn = build_db(n=10)
    c = auth_client(conn)
    yield c


def test_chat_endpoint_unknown_portfolio(client):
    r = client.post("/portfolio/missing-client/chat", json={"query": "Why red?"})
    assert r.status_code == 404


def test_chat_generic_requires_fields(client):
    r = client.post("/chat", json={"query": "summary"})
    assert r.status_code == 422


def test_chat_generic_returns_grounded_answer(client):
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


def test_voice_status_unconfigured(client):
    r = client.get("/voice/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False


def test_voice_token_unconfigured(client):
    r = client.post("/voice/token/C-001")
    assert r.status_code == 503


def test_voice_status_configured(monkeypatch, client):
    _configure_voice(monkeypatch)
    r = client.get("/voice/status")
    assert r.status_code == 200
    assert r.json()["configured"] is True


def test_voice_token_configured(monkeypatch, client):
    _configure_voice(monkeypatch)
    r = client.post("/voice/token/C-001")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["room"] == "assure-C-001"
    assert data["token"]
    assert data["url"] == "wss://test.livekit.cloud"
