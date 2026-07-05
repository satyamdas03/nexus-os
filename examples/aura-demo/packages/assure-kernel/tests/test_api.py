"""Tests for the Kernel-as-a-Service HTTP API."""
import pytest
from fastapi.testclient import TestClient

from assure_kernel.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_portfolio():
    return {
        "client_id": "test-001",
        "cash": 10_000.0,
        "holdings": [
            {"ticker": "SPY", "units": 10.0, "price": 500.0, "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1},
            {"ticker": "TLT", "units": 20.0, "price": 95.0, "asset_class": "Bonds", "sector": "Broad", "region": "US", "liquidity_tier": 1},
        ],
    }


@pytest.fixture
def sample_mandate():
    return {
        "id": "test-mandate",
        "name": "Test Mandate",
        "version": "1.0.0",
        "rules": [
            {"type": "max_asset_class_weight", "parameters": {"max_weights": {"Equity": 0.6, "Bonds": 0.5, "Cash": 1.0}}},
            {"type": "max_single_holding", "parameters": {"max_weight": 0.4}},
            {"type": "min_cash", "parameters": {"min_weight": 0.05}},
        ],
    }


def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "assure-kernel"
    assert body["kernel_version"] == "0.1.0"


def test_evaluate_green(client, sample_portfolio, sample_mandate):
    r = client.post("/v1/evaluate", json={"portfolio": sample_portfolio, "mandate": sample_mandate})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "green"
    assert body["breaches"] == []
    assert len(body["per_rule"]) >= 3


def test_evaluate_breach(client, sample_portfolio, sample_mandate):
    # Overweight SPY so it breaches the single-holding cap.
    sample_portfolio["holdings"][0]["units"] = 100.0
    r = client.post("/v1/evaluate", json={"portfolio": sample_portfolio, "mandate": sample_mandate})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "red"
    assert any(b["rule"] == "max_single_holding" for b in body["breaches"])


def test_verify_buy_gate_passes(client, sample_portfolio, sample_mandate):
    # Sell some SPY to reduce concentration.
    trades = [{"ticker": "SPY", "action": "sell", "units": 5.0}]
    r = client.post("/v1/verify", json={"portfolio": sample_portfolio, "mandate": sample_mandate, "trades": trades})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("green", "orange")


def test_explain_mandate(client, sample_mandate):
    r = client.post("/v1/explain", json={"mandate": sample_mandate})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "test-mandate"
    assert body["rule_count"] == 3
    assert body["enabled_rule_count"] == 3
    assert all(r["type"] for r in body["rules"])


def test_explain_legacy_mandate(client):
    legacy = {
        "id": "legacy",
        "max_asset_class_weight": {"Equity": 0.6},
        "max_single_holding": 0.4,
        "min_cash": 0.05,
        "target_allocation": {"Equity": 0.5},
        "drift_tolerance": 0.05,
        "approved_universe": ["SPY", "TLT"],
        "excluded_tickers": [],
        "max_region_weight": {},
        "max_sector_weight": {},
        "max_top_n_concentration": {"n": 5, "limit": 1.0},
        "min_liquid_pct": 0.0,
    }
    r = client.post("/v1/explain", json={"mandate": legacy})
    assert r.status_code == 200
    body = r.json()
    assert body["rule_count"] >= 3


def test_evidence_pack(client, sample_portfolio, sample_mandate):
    r = client.post("/v1/evidence", json={
        "portfolio": sample_portfolio,
        "mandate": sample_mandate,
        "client_name": "Test Client",
        "adviser": "Test Adviser",
        "fum": 15_000.0,
        "day": 7,
        "alignment_history": [{"day": 0, "status": "green", "breach_count": 0, "watch_count": 0}],
        "remediation_evidence": [
            {"timestamp": "2026-07-05T10:00:00+00:00", "actor": "adviser", "action_type": "explain", "tier": "advisory", "rationale": "review", "payload_summary": "explanation narrative", "rules_status": "green"}
        ],
    })
    assert r.status_code == 200
    body = r.json()
    evidence = body["evidence"]
    assert evidence["header"]["client_id"] == "test-001"
    assert evidence["header"]["day"] == 7
    assert evidence["current_attestation"]["status"] == "green"
    assert evidence["mandate_documentation"]["rule_count"] == 3
    assert "_html" not in evidence
    assert "html" not in body


def test_evidence_pack_with_html(client, sample_portfolio, sample_mandate):
    r = client.post("/v1/evidence", json={
        "portfolio": sample_portfolio,
        "mandate": sample_mandate,
        "include_html": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert "html" in body
    assert body["html"].startswith("<!DOCTYPE html")
    assert "ASSURE" in body["html"]


def test_evidence_pack_breach(client, sample_mandate):
    portfolio = {
        "client_id": "test-breach",
        "cash": 10_000.0,
        "holdings": [
            {"ticker": "SPY", "units": 100.0, "price": 500.0, "asset_class": "Equity", "sector": "Broad", "region": "US", "liquidity_tier": 1},
            {"ticker": "TLT", "units": 20.0, "price": 95.0, "asset_class": "Bonds", "sector": "Broad", "region": "US", "liquidity_tier": 1},
        ],
    }
    r = client.post("/v1/evidence", json={"portfolio": portfolio, "mandate": sample_mandate})
    assert r.status_code == 200
    evidence = r.json()["evidence"]
    assert evidence["current_attestation"]["status"] == "red"
    assert "BREACH" in evidence["deterministic_summary"]
