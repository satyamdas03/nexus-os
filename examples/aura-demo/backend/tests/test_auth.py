"""Tests for authentication + RBAC skeleton."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core import storage, data_loader
from core.auth import create_access_token, create_user, hash_password
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
def strict_auth(monkeypatch):
    """Pin auth to enforced mode with a deterministic secret.

    monkeypatch restores the environment after the test, so auth state never
    leaks between tests."""
    monkeypatch.setenv("AUTH_ENFORCE", "1")
    monkeypatch.setenv("AUTH_SECRET", "test-secret-32-bytes-long-ok")
    monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "adminpass")


@pytest.fixture
def admin_client(strict_auth):
    """Authenticated admin client backed by a 100-portfolio temp book."""
    c, conn = _client(n=100)
    create_user(conn, "admin", "adminpass", "admin")
    create_user(conn, "viewer", "viewerpass", "viewer")
    create_user(conn, "adviser", "adviserpass", "adviser")
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    try:
        yield c
    finally:
        data_loader.set_conn(None)


@pytest.fixture
def strict_client(strict_auth):
    """Unauthenticated client in strict-auth mode; tests log in themselves."""
    c, conn = _client(n=50)
    try:
        yield c, conn
    finally:
        data_loader.set_conn(None)


def test_login_returns_token_and_role(strict_client):
    c, conn = strict_client
    create_user(conn, "admin", "adminpass", "admin")
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["username"] == "admin"
    assert "access_token" in body


def test_login_bad_password(strict_client):
    c, conn = strict_client
    create_user(conn, "admin", "adminpass", "admin")
    r = c.post("/auth/token", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_admin_reset_requires_auth():
    # Dev fallback mode (conftest default): missing credentials still succeed.
    c, _ = _client(n=50)
    r = c.post("/admin/reset")
    assert r.status_code == 200


def test_enforced_admin_reset_requires_token(strict_client):
    c, conn = strict_client
    create_user(conn, "admin", "adminpass", "admin")
    create_user(conn, "viewer", "viewerpass", "viewer")
    r = c.post("/admin/reset")
    assert r.status_code == 401
    r = c.post("/auth/token", json={"username": "viewer", "password": "viewerpass"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    r = c.post("/admin/reset")
    assert r.status_code == 403
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    r = c.post("/admin/reset")
    assert r.status_code == 200


def test_viewer_cannot_mutate(admin_client):
    c = admin_client
    r = c.post("/auth/users", json={"username": "v2", "password": "p", "role": "viewer"})
    assert r.status_code == 200
    r = c.post("/auth/token", json={"username": "v2", "password": "p"})
    token = r.json()["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    r = c.post("/market/tick")
    assert r.status_code == 403


def test_admin_can_create_users(admin_client):
    c = admin_client
    r = c.post("/auth/users", json={"username": "adviser2", "password": "p", "role": "adviser"})
    assert r.status_code == 200
    r = c.get("/auth/users")
    assert r.status_code == 200
    usernames = {u["username"] for u in r.json()}
    assert "adviser2" in usernames
    assert "admin" in usernames


def test_me_endpoint(admin_client):
    r = admin_client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "admin"


@pytest.fixture
def scoped_adviser_client(strict_client):
    """Authenticated adviser client scoped to one adviser name."""
    c, conn = strict_client
    create_user(conn, "adviser", "adviserpass", "adviser", assigned_adviser_filter="Pat Quinn")
    r = c.post("/auth/token", json={"username": "adviser", "password": "adviserpass"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c, conn


@pytest.fixture
def unscoped_adviser_client(strict_client):
    """Authenticated adviser client with no assigned filter (backward compat)."""
    c, conn = strict_client
    create_user(conn, "adviser_free", "adviserpass", "adviser")
    r = c.post("/auth/token", json={"username": "adviser_free", "password": "adviserpass"})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c, conn


def _client_ids_for_adviser(conn, adviser_name):
    """Return (matching_id, non_matching_id) portfolio client_ids."""
    rows = conn.execute(
        "SELECT client_id, adviser FROM portfolios ORDER BY client_id"
    ).fetchall()
    matching = [r["client_id"] for r in rows if r["adviser"] == adviser_name]
    non_matching = [r["client_id"] for r in rows if r["adviser"] != adviser_name]
    assert matching, f"no portfolios for adviser {adviser_name}"
    assert non_matching, "no portfolios for other advisers"
    return matching[0], non_matching[0]


def test_admin_can_access_any_client(admin_client):
    rows = admin_client.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = admin_client.post(f"/adviser/whiteboard/{client_id}")
    assert r.status_code == 200, r.text


def test_scoped_adviser_can_access_assigned_client(scoped_adviser_client):
    c, conn = scoped_adviser_client
    matching, _ = _client_ids_for_adviser(conn, "Pat Quinn")
    r = c.post(f"/adviser/whiteboard/{matching}")
    assert r.status_code == 200, r.text


def test_scoped_adviser_denied_for_other_client(scoped_adviser_client):
    c, conn = scoped_adviser_client
    _, non_matching = _client_ids_for_adviser(conn, "Pat Quinn")
    r = c.post(f"/adviser/whiteboard/{non_matching}")
    assert r.status_code == 403, r.text


def test_scoped_adviser_denied_for_other_client_chat(scoped_adviser_client):
    c, conn = scoped_adviser_client
    _, non_matching = _client_ids_for_adviser(conn, "Pat Quinn")
    r = c.post("/adviser/chat", json={"client_id": non_matching, "query": "hello"})
    assert r.status_code == 403, r.text


def test_scoped_adviser_denied_for_other_client_session(scoped_adviser_client):
    c, conn = scoped_adviser_client
    _, non_matching = _client_ids_for_adviser(conn, "Pat Quinn")
    r = c.post("/adviser/session", json={"client_id": non_matching})
    assert r.status_code == 403, r.text


def test_scoped_adviser_denied_for_other_client_voice_token(scoped_adviser_client, monkeypatch):
    c, conn = scoped_adviser_client
    _, non_matching = _client_ids_for_adviser(conn, "Pat Quinn")
    # Patch voice adapter so token creation succeeds if auth passes.
    import routers.voice as router_voice
    from agents import voice as voice_mod

    monkeypatch.setattr(voice_mod, "is_configured", lambda: True)
    monkeypatch.setattr(
        voice_mod,
        "create_token",
        lambda client_id, room_name=None, identity=None, ttl_seconds=3600: voice_mod.VoiceToken(
            token="fake", url="wss://test", room=f"room-{client_id}", identity="i"
        ),
    )
    monkeypatch.setattr(router_voice, "is_configured", lambda: True)
    r = c.post(f"/voice/token/{non_matching}")
    assert r.status_code == 403, r.text


def test_unscoped_adviser_can_access_any_client(unscoped_adviser_client):
    c, conn = unscoped_adviser_client
    rows = c.get("/portfolios?limit=1&offset=0").json()
    client_id = rows[0]["client_id"]
    r = c.post(f"/adviser/whiteboard/{client_id}")
    assert r.status_code == 200, r.text
    r = c.post("/adviser/chat", json={"client_id": client_id, "query": "hello"})
    assert r.status_code == 200, r.text
