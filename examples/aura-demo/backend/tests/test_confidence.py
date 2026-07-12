"""Tests for the confidence / confirmation prediction endpoint."""
import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core import data_loader, storage
from core.auth import create_user
from core.confidence import _historical_score, score_confidence
from generators import generate_data


def _client(n=100):
    from tests.helpers import auth_client, build_db

    conn = build_db(n=n)
    return auth_client(conn), conn


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


def _fake_simulate(prevent_incidence: int = 0):
    def inner(**kwargs):
        return {"prevent_incidence": prevent_incidence, "reactive_incidence": prevent_incidence + 50}

    return inner


def test_confidence_returns_scores(admin_client, monkeypatch):
    import routers.confidence as rc

    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    # Avoid running a real 30-day book simulation in the router test.
    fake = _fake_simulate(prevent_incidence=100)
    monkeypatch.setattr(rc, "simulate_book", fake)
    r = admin_client.post(f"/confidence/{client_id}", json={"trades": []})
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["confidence"] <= 1
    assert "human_review_recommended" in body
    assert len(body["factors"]) == 3
    assert body["data_freshness"] == 1.0
    assert body["simulation_baseline"] == 0.8


def test_simulate_fn_is_used(admin_client):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    result = score_confidence(client_id, [], simulate_fn=_fake_simulate(prevent_incidence=250))
    assert result.simulation_baseline == 0.5


def test_historical_score_returns_half_with_no_history(admin_client, monkeypatch, tmp_path):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    monkeypatch.setattr("core.confidence._AUDIT_PATH", tmp_path / "no_audit.jsonl")
    assert _historical_score(client_id, []) == 0.5


def test_historical_score_computes_success_rate(admin_client, monkeypatch, tmp_path):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    audit_file = tmp_path / "audit.jsonl"
    entries = [
        {
            "client_id": client_id,
            "action_type": "approve",
            "payload": {"trades": [], "day": 1, "new_status": "green"},
        },
        {
            "client_id": client_id,
            "action_type": "approve",
            "payload": {"trades": [], "day": 2, "new_status": "green"},
        },
        {
            "client_id": client_id,
            "action_type": "approve",
            "payload": {"trades": [], "day": 3, "new_status": "red"},
        },
    ]
    audit_file.write_text("\n".join(json.dumps(e) for e in entries))
    monkeypatch.setattr("core.confidence._AUDIT_PATH", audit_file)

    conn = data_loader.get_conn_cached()
    conn.execute(
        "INSERT OR REPLACE INTO status_history "
        "(day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        (2, client_id, "green", 0, 0),
    )
    conn.execute(
        "INSERT OR REPLACE INTO status_history "
        "(day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        (3, client_id, "green", 0, 0),
    )
    conn.execute(
        "INSERT OR REPLACE INTO status_history "
        "(day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        (4, client_id, "red", 1, 0),
    )
    conn.commit()

    result = score_confidence(client_id, [], simulate_fn=_fake_simulate(prevent_incidence=0))
    assert result.historical_approval_success == 2 / 3


def test_historical_score_filters_by_ticker_action(admin_client, monkeypatch, tmp_path):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    audit_file = tmp_path / "audit.jsonl"
    entries = [
        {
            "client_id": client_id,
            "action_type": "approve",
            "payload": {"trades": [{"ticker": "AAPL", "action": "buy"}], "day": 1, "new_status": "green"},
        },
        {
            "client_id": client_id,
            "action_type": "approve",
            "payload": {"trades": [{"ticker": "TSLA", "action": "sell"}], "day": 2, "new_status": "red"},
        },
    ]
    audit_file.write_text("\n".join(json.dumps(e) for e in entries))
    monkeypatch.setattr("core.confidence._AUDIT_PATH", audit_file)

    conn = data_loader.get_conn_cached()
    conn.execute(
        "INSERT OR REPLACE INTO status_history "
        "(day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
        (2, client_id, "green", 0, 0),
    )
    conn.commit()

    # Only the AAPL buy record matches the current proposed trade.
    result = score_confidence(
        client_id,
        [{"ticker": "AAPL", "action": "buy", "units": 1}],
        simulate_fn=_fake_simulate(prevent_incidence=0),
    )
    assert result.historical_approval_success == 1.0
