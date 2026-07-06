"""Tests for Hermes synthetic-reality strategy diff + generated tests."""
import os
import tempfile
import time

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


def _poll_generate(client: TestClient, job_id: str, timeout: int = 90) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/hermes/generate/{job_id}")
        assert r.status_code == 200, r.text
        body = r.json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.5)
    raise AssertionError("generate job did not complete in time")


def test_generate_returns_diff_or_no_improvement(admin_client):
    r = admin_client.post("/hermes/generate", json={"days": 7, "seed": 42})
    assert r.status_code == 200, r.text
    init = r.json()
    assert "job_id" in init
    body = _poll_generate(admin_client, init["job_id"])
    result = body["result"]
    assert result["ok"] is True
    assert "diff" in result
    assert "simulation" in result


def test_run_generated_test(admin_client):
    r = admin_client.post("/hermes/generate", json={"days": 7, "seed": 42})
    assert r.status_code == 200
    init = r.json()
    body = _poll_generate(admin_client, init["job_id"])
    result = body["result"]
    if result["diff"] is None:
        pytest.skip("no improvement found in this seed")
    r2 = admin_client.post("/hermes/run-test", json={"source": result["test"]["source"]})
    assert r2.status_code == 200, r2.text
    assert r2.json()["ok"] is True
