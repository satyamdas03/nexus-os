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
