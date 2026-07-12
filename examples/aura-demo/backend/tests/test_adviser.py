"""Tests for the AI Investment Manager adviser endpoints."""

import pytest

from core import data_loader


def _client(n=100):
    from tests.helpers import auth_client, build_db

    conn = build_db(n=n)
    return auth_client(conn), conn


@pytest.fixture
def admin_client(monkeypatch):
    """Authenticated admin client with auth env fully isolated via monkeypatch."""
    monkeypatch.setenv("AUTH_ENFORCE", "1")
    monkeypatch.setenv("AUTH_SECRET", "test-secret-32-bytes-long-ok")
    monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "adminpass")
    c, conn = _client(n=100)
    try:
        yield c
    finally:
        data_loader.set_conn(None)


def test_whiteboard_returns_structured_payload(admin_client):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = admin_client.post(f"/adviser/whiteboard/{client_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["client_id"] == client_id
    assert "current_status" in body
    assert "breaches" in body
    assert "proposed_trades" in body
    assert "post_status" in body
    assert body["impact"]["trades_count"] == len(body["proposed_trades"])


def test_chat_refuses_trade_execution(admin_client):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = admin_client.post(
        "/adviser/chat",
        json={"client_id": client_id, "query": "Execute the trade now"},
    )
    assert r.status_code == 200, r.text
    answer = r.json()["answer"].lower()
    assert "cannot execute" in answer or "workbench" in answer or "advisory" in answer


def test_session_returns_livekit_status(admin_client):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = admin_client.post("/adviser/session", json={"client_id": client_id})
    # LiveKit is not configured in CI/dev test runs; expect a graceful 503.
    assert r.status_code in (200, 503)
