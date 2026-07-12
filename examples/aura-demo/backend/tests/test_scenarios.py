"""Tests for the synthetic stress-scenario router."""
import os
import sqlite3
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from core import storage, data_loader
from core.hermes_store import SQLiteHermesStore, set_hermes_store
from generators import generate_data


def _client(n=400):
    from tests.helpers import auth_client, build_db

    conn = build_db(n=n, with_hermes_store=True)
    return auth_client(conn), conn


def test_scenarios_list():
    c, _ = _client()
    r = c.get("/scenarios")
    assert r.status_code == 200
    body = r.json()
    assert "scenarios" in body
    ids = {s["id"] for s in body["scenarios"]}
    assert "baseline" in ids
    assert "equity_crash_2008" in ids
    for s in body["scenarios"]:
        assert {"id", "name", "description", "severity"} <= set(s)


def test_scenarios_apply():
    c, _ = _client()
    r = c.post("/scenarios/apply", json={"client_id": "c00000", "scenario_id": "equity_crash_2008"})
    assert r.status_code == 200
    body = r.json()
    assert body["client_id"] == "c00000"
    assert body["scenario_id"] == "equity_crash_2008"
    assert body["baseline_status"] in ("green", "orange", "red")
    assert body["stressed_status"] in ("green", "orange", "red")
    assert body["baseline_value"] > 0
    assert body["stressed_value"] > 0
    assert "stressed_rules_result" in body
    assert "baseline_rules_result" in body


def test_scenarios_apply_404():
    c, _ = _client()
    r = c.post("/scenarios/apply", json={"client_id": "zzz", "scenario_id": "baseline"})
    assert r.status_code == 404


def test_scenarios_apply_bad_scenario():
    c, _ = _client()
    r = c.post("/scenarios/apply", json={"client_id": "c00000", "scenario_id": "not-a-scenario"})
    assert r.status_code == 400


def test_scenarios_stress_portfolio():
    c, _ = _client()
    r = c.post("/scenarios/stress-portfolio", json={"client_id": "c00000"})
    assert r.status_code == 200
    body = r.json()
    assert body["client_id"] == "c00000"
    assert body["baseline_status"] in ("green", "orange", "red")
    assert len(body["scenarios"]) >= 6
    for row in body["scenarios"]:
        assert row["scenario_id"]
        assert row["stressed_status"] in ("green", "orange", "red")


def test_scenarios_sweep_async_and_report():
    c, conn = _client(n=200)
    r = c.post("/scenarios/sweep", json={"client_id": "c00000", "scenario_ids": ["baseline"], "n": 50})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Poll until done/failed (background tasks run after TestClient response).
    status = None
    for _ in range(60):
        st = c.get(f"/scenarios/sweep/{job_id}").json()
        status = st["status"]
        if status in ("done", "failed"):
            break
        time.sleep(0.1)
    assert status == "done", f"sweep failed or hung: {st}"

    result = st["result"]
    assert result["total"] == 50
    assert "breach_rate" in result
    assert "scenario_status_counts" in result

    html = c.get(f"/scenarios/sweep/{job_id}/report.html")
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "ASSURE SYNTHETIC REALITY ENGINE" in html.text
