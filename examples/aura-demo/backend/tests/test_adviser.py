"""Tests for the AI Investment Manager adviser endpoints."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core import data_loader, storage
from core.auth import create_user
from generators import generate_data


def _client(n=100):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    from main import app
    return TestClient(app), conn


@pytest.fixture
def admin_client():
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    c, conn = _client(n=100)
    create_user(conn, "admin", "adminpass", "admin")
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    try:
        yield c
    finally:
        data_loader.set_conn(None)
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


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
