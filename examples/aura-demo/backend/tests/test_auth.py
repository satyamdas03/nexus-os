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
def admin_client():
    """Strict auth mode with a seeded admin user."""
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    c, conn = _client(n=100)
    create_user(conn, "admin", "adminpass", "admin")
    create_user(conn, "viewer", "viewerpass", "viewer")
    create_user(conn, "adviser", "adviserpass", "adviser")
    r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    try:
        yield c
    finally:
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


def test_login_returns_token_and_role():
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    c, conn = _client(n=50)
    create_user(conn, "admin", "adminpass", "admin")
    try:
        r = c.post("/auth/token", json={"username": "admin", "password": "adminpass"})
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "admin"
        assert body["username"] == "admin"
        assert "access_token" in body
    finally:
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


def test_login_bad_password():
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    c, conn = _client(n=50)
    create_user(conn, "admin", "adminpass", "admin")
    try:
        r = c.post("/auth/token", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401
    finally:
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


def test_admin_reset_requires_auth():
    c, _ = _client(n=50)
    r = c.post("/admin/reset")
    # In dev fallback mode, missing credentials still succeed.
    assert r.status_code == 200


def test_enforced_admin_reset_requires_token():
    old_enforce = os.environ.get("AUTH_ENFORCE")
    old_secret = os.environ.get("AUTH_SECRET")
    os.environ["AUTH_ENFORCE"] = "1"
    os.environ["AUTH_SECRET"] = "test-secret-32-bytes-long-ok"
    c, conn = _client(n=50)
    create_user(conn, "admin", "adminpass", "admin")
    create_user(conn, "viewer", "viewerpass", "viewer")
    try:
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
    finally:
        if old_enforce is None:
            os.environ.pop("AUTH_ENFORCE", None)
        else:
            os.environ["AUTH_ENFORCE"] = old_enforce
        if old_secret is None:
            os.environ.pop("AUTH_SECRET", None)
        else:
            os.environ["AUTH_SECRET"] = old_secret


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
