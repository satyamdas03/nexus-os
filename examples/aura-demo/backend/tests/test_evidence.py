# backend/tests/test_evidence.py
"""Tests for the Evidence Pack feature.

The Evidence Pack is read-only assembly of existing data. These tests verify:
- structured output shape for green/orange/red portfolios
- compliance attestation matches rules_engine.check exactly
- no portfolio state mutation occurs
- synthetic-data disclaimer is present
- HTML route returns a themed, print-ready document
- unknown client returns 404
"""

import json
import os
import sqlite3
import tempfile

from fastapi.testclient import TestClient

from agents import evidence
from core import data_loader, effective, rules_engine, storage
from generators import generate_data


def _setup(n=600):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn)
    storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def _find_by_status(target_status: str, n=600):
    conn = data_loader.get_conn_cached()
    for row in conn.execute("SELECT client_id FROM portfolios LIMIT ?", (n,)).fetchall():
        cid = row["client_id"]
        p = data_loader.get_portfolio(cid)
        if rules_engine.check(p, p["mandate"])["status"] == target_status:
            return cid
    raise AssertionError(f"no {target_status} portfolio found in seed book")


def test_green_portfolio_evidence():
    _setup()
    cid = _find_by_status("green")
    pack = evidence.build_portfolio_evidence(cid)

    assert pack["version"] == evidence.EVIDENCE_VERSION
    h = pack["header"]
    assert h["client_id"] == cid
    assert h["synthetic_data"] is True
    assert evidence.SYNTHETIC_DISCLAIMER in h["synthetic_disclaimer"]
    assert "reference_id" in h and len(h["reference_id"]) == 12

    assert pack["current_attestation"]["status"] == "green"
    for r in pack["current_attestation"]["per_rule"]:
        assert r["pass"] is True
        assert r["severity"] == "green"

    assert "fully aligned" in pack["deterministic_summary"].lower()
    assert "no breaches" in pack["deterministic_summary"].lower()

    assert pack["control_statement"] == evidence._CONTROL_STATEMENT
    assert evidence.SYNTHETIC_DISCLAIMER in pack["footer"]["synthetic_disclaimer"]


def test_red_portfolio_evidence():
    _setup()
    cid = _find_by_status("red")
    pack = evidence.build_portfolio_evidence(cid)

    assert pack["current_attestation"]["status"] == "red"
    failing = [r for r in pack["current_attestation"]["per_rule"] if not r["pass"]]
    assert failing, "expected at least one failing rule for a red portfolio"

    assert "breach" in pack["deterministic_summary"].lower()
    assert "human-approved remediation" in pack["deterministic_summary"].lower()


def test_orange_portfolio_evidence():
    _setup()
    cid = _find_by_status("orange")
    pack = evidence.build_portfolio_evidence(cid)

    assert pack["current_attestation"]["status"] == "orange"
    assert "watch" in pack["deterministic_summary"].lower()
    assert "no mandate breaches" in pack["deterministic_summary"].lower()


def test_attestation_matches_rules_engine():
    _setup()
    cid = _find_by_status("red")
    pack = evidence.build_portfolio_evidence(cid)

    p = data_loader.get_portfolio(cid)
    eff = effective.get_effective(cid, seed=p)
    direct = rules_engine.check(eff, p["mandate"])

    assert pack["current_attestation"]["status"] == direct["status"]
    pack_rules = {r["rule"]: r for r in pack["current_attestation"]["per_rule"]}
    for dr in direct["per_rule"]:
        pr = pack_rules[dr["rule"]]
        assert pr["pass"] == bool(dr["pass"])
        assert pr["severity"] == dr["severity"]
        assert pr["current"] == dr["current"]
        assert pr["limit"] == dr["limit"]


def test_no_state_mutation():
    conn = _setup()
    cid = _find_by_status("red")

    # Snapshot before.
    state_before = conn.execute(
        "SELECT count(*) FROM state WHERE client_id=?", (cid,)
    ).fetchone()[0]
    hist_before = conn.execute(
        "SELECT count(*) FROM status_history WHERE client_id=?", (cid,)
    ).fetchone()[0]
    p_before = data_loader.get_portfolio(cid)
    status_before = rules_engine.check(
        effective.get_effective(cid, seed=p_before), p_before["mandate"]
    )["status"]

    # Build pack twice.
    evidence.build_portfolio_evidence(cid)
    evidence.build_portfolio_evidence(cid)

    # Snapshot after.
    state_after = conn.execute(
        "SELECT count(*) FROM state WHERE client_id=?", (cid,)
    ).fetchone()[0]
    hist_after = conn.execute(
        "SELECT count(*) FROM status_history WHERE client_id=?", (cid,)
    ).fetchone()[0]
    p_after = data_loader.get_portfolio(cid)
    status_after = rules_engine.check(
        effective.get_effective(cid, seed=p_after), p_after["mandate"]
    )["status"]

    assert state_before == state_after
    assert hist_before == hist_after
    assert status_before == status_after


def test_synthetic_disclaimer_present():
    _setup()
    cid = _find_by_status("green")
    pack = evidence.build_portfolio_evidence(cid)

    assert evidence.SYNTHETIC_DISCLAIMER in pack["header"]["synthetic_disclaimer"]
    assert evidence.SYNTHETIC_DISCLAIMER in pack["footer"]["synthetic_disclaimer"]
    assert evidence.SYNTHETIC_DISCLAIMER in pack["_html"]
    assert "Synthetic Demonstration Data" in pack["_html"]


def test_html_route_returns_200():
    _setup()
    from main import app

    client = TestClient(app)
    cid = _find_by_status("red")
    r = client.get(f"/evidence/portfolio/{cid}/html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    html = r.text

    p = data_loader.get_portfolio(cid)
    assert p["client_name"] in html
    assert "BREACH" in html or "ATTENTION" in html or "ALIGNED" in html
    assert evidence.SYNTHETIC_DISCLAIMER in html
    assert "ASSURE" in html
    assert "Print / Save as PDF" in html
    assert "@media print" in html


def test_json_route_returns_200_and_strips_html():
    _setup()
    from main import app

    client = TestClient(app)
    cid = _find_by_status("green")
    r = client.get(f"/evidence/portfolio/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert "_html" not in body
    assert body["header"]["client_id"] == cid
    assert body["current_attestation"]["status"] == "green"


def test_404_for_unknown_client():
    _setup()
    from main import app

    client = TestClient(app)
    r = client.get("/evidence/portfolio/zzz")
    assert r.status_code == 404
