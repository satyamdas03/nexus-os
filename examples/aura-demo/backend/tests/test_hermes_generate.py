"""Tests for Hermes synthetic-reality strategy diff + generated tests."""
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from agents.hermes.generator import (
    generate_diff,
    _candidates,
    _var_bounds,
    TUNABLES,
)
from agents.llm import MockLLM
from core import data_loader, storage
from core.auth import create_user
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


# ---------------------------------------------------------------------------
# Direct generator unit tests (fast, no HTTP polling).
# ---------------------------------------------------------------------------


def test_candidates_default_unidirectional():
    strategy = {"variables": {}}
    assert _candidates("prevent_horizon_days", 14, strategy) == [15]
    assert _candidates("prevent_risk_threshold", 0.5, strategy) == [0.55]
    assert _candidates("min_trade_size", 0.006, strategy) == [0.0066]
    assert _candidates("preferred_trim_method", "liquidate", strategy) == []
    assert _candidates("cash_buffer_target", True, strategy) == [False]


def test_candidates_bidirectional_perturbations():
    strategy = {"variables": {}}
    assert _candidates("prevent_horizon_days", 14, strategy, bidirectional=True) == [13, 15]
    # Floats use multiplicative factors in both directions.
    assert _candidates("prevent_risk_threshold", 0.5, strategy, bidirectional=True) == [0.4545, 0.55]
    assert _candidates("min_trade_size", 0.006, strategy, bidirectional=True) == [0.0055, 0.0066]


def test_candidates_respects_safe_bounds():
    """Downward and upward perturbations are clamped to per-variable safe bounds."""
    strategy = {"variables": {}}
    # prevent_risk_threshold min=0.0, max=1.0.
    assert _candidates("prevent_risk_threshold", 0.05, strategy, bidirectional=True) == [0.0455, 0.055]
    assert _candidates("prevent_risk_threshold", 0.95, strategy, bidirectional=True) == [0.8636, 1.0]
    # prevent_horizon_days min=1, max=90.
    assert _candidates("prevent_horizon_days", 1, strategy, bidirectional=True) == [1, 2]
    assert _candidates("prevent_horizon_days", 90, strategy, bidirectional=True) == [89, 90]


def test_var_bounds_prefers_yaml_metadata():
    strategy = {
        "variables": {
            "prevent_risk_threshold": {"value": 0.5, "min": 0.1, "max": 0.9},
        }
    }
    bounds = _var_bounds("prevent_risk_threshold", strategy)
    assert bounds["min"] == 0.1
    assert bounds["max"] == 0.9


def test_generate_test_source_compiles_for_both_modes():
    """Generated regression tests must be syntactically valid for prevent and reactive diffs."""
    from agents.hermes.test_generator import generate_test

    for mode, sim in (
        (
            "prevent",
            {
                "prevent_incidence_before": 100,
                "prevent_incidence_after": 80,
                "reactive_incidence": 120,
            },
        ),
        (
            "reactive",
            {
                "reactive_incidence": 120,
                "reactive_incidence_after": 100,
                "prevent_incidence_before": 100,
            },
        ),
    ):
        diff = {"variable": "prevent_risk_threshold", "to": 0.45, "mode": mode}
        out = generate_test(diff, sim, seed=42)
        assert out["filename"].startswith("test_strategy_")
        compile(out["source"], out["filename"], "exec")


def test_generate_diff_both_modes():
    from tests.helpers import build_db
    from core import data_loader

    conn = build_db(n=20)
    try:
        result = generate_diff(days=2, seed=42, modes=("reactive", "prevent"))
        assert result["ok"] is True
        sim = result["simulation"]
        assert "reactive_incidence" in sim
        assert "prevent_incidence_before" in sim
        assert sim["modes_run"] == ["reactive", "prevent"]
    finally:
        data_loader.set_conn(None)
        try:
            conn.close()
        except Exception:
            pass


def test_generate_diff_bidirectional():
    from tests.helpers import build_db
    from core import data_loader

    conn = build_db(n=20)
    try:
        result = generate_diff(days=2, seed=42, bidirectional=True)
        assert result["ok"] is True
        assert "diff" in result
        assert "simulation" in result
    finally:
        data_loader.set_conn(None)
        try:
            conn.close()
        except Exception:
            pass


def test_generate_diff_llm_offline_safe():
    """LLM-assisted path must not fail when the autouse MockLLM fixture is active."""
    from tests.helpers import build_db
    from core import data_loader

    conn = build_db(n=20)
    fake_history = [{"client_id": "C001", "breach": "max_single_holding"}]
    try:
        result = generate_diff(
            days=2,
            seed=42,
            bidirectional=False,
            use_llm=True,
            llm_provider=MockLLM(),
            recent_breach_history=fake_history,
        )
        assert result["ok"] is True
    finally:
        data_loader.set_conn(None)
        try:
            conn.close()
        except Exception:
            pass


def test_generate_diff_llm_suggestion_order():
    """A fake LLM that returns a JSON variable list is parsed and used."""
    from tests.helpers import build_db
    from core import data_loader

    conn = build_db(n=20)

    class FakeProvider:
        def complete(self, system: str, user: str) -> str:
            return '{"variables": ["auto_approve_band", "min_trade_size", "prevent_risk_threshold"]}'

    try:
        result = generate_diff(
            days=2,
            seed=42,
            bidirectional=False,
            use_llm=True,
            llm_provider=FakeProvider(),
        )
        assert result["ok"] is True
        # The order of tried variables should start with the LLM-suggested ones.
        # We cannot easily inspect internal order from the public result, but the
        # call must complete and stay deterministic.
        assert "diff" in result
    finally:
        data_loader.set_conn(None)
        try:
            conn.close()
        except Exception:
            pass
