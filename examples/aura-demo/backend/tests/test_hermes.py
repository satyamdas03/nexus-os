"""Hermes core tests: proposer strategy-sensitivity, reflection mandate-guard,
scan-loop gating. Hermes never touches mandate rules or rules_engine.py."""
import json
import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

from core import storage, data_loader
from core.hermes_store import SQLiteHermesStore, set_hermes_store
from generators import generate_data
from core.rules_engine import check
from core.trades import apply_trades
from agents.hermes.proposer import propose, strategy_vars
from agents.hermes.strategy_io import load_strategy, _guard, adopt_proposal
from agents.hermes import STRATEGY_PATH, HISTORY_DIR


def _client(n=400):
    """SQLite fixture: temp DB with n portfolios, wired into data_loader.
    Mirrors tests/test_routers.py::_client so hermes endpoint tests run against
    the real SQLite book instead of the removed file-based state."""
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    # Pin Hermes store to the same temp DB so scan/approve endpoints are isolated.
    set_hermes_store(SQLiteHermesStore(conn))
    # Reset any loop-level store override left by loop tests; use the global store.
    from agents.hermes import loop
    loop._set_store(None)
    from main import app
    return TestClient(app), conn

# A red portfolio the proportional trim can fix: Technology over its 25% cap.
PORTFOLIO = {
    "client_id": "ctest", "client_name": "Test", "adviser": "Pat", "fum": 100_000,
    "holdings": [
        {"ticker": "NVDA", "name": "Nvidia", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 500, "market_value": 50000},
        {"ticker": "MSFT", "name": "Microsoft", "asset_class": "Equity", "sector": "Technology", "units": 100, "price": 400, "market_value": 40000},
        {"ticker": "SPY", "name": "S&P 500", "asset_class": "Equity", "sector": "Broad", "units": 10, "price": 500, "market_value": 5000},
    ], "cash": 5000,
}
MANDATE = {
    "max_asset_class_weight": {"Equity": 1.0, "Bonds": 0.40, "Crypto": 0.0, "Cash": 0.30},
    "max_sector_weight": {"Technology": 0.25, "Broad": 1.0},
    "approved_universe": ["SPY", "TLT", "QQQ", "NVDA", "MSFT"],
    "max_single_holding": 1.0, "min_cash": 0.0,
    "target_allocation": {}, "drift_tolerance": 0.10,
}


def _strategy_with(trim_method: str) -> dict:
    s = load_strategy()
    s["variables"]["preferred_trim_method"]["value"] = trim_method
    return s


def test_proposer_is_strategy_sensitive():
    """A strategy-variable change MUST change the proposer output."""
    rr = check(PORTFOLIO, MANDATE)
    assert rr["breaches"], "fixture must be red"
    prop_p = propose(PORTFOLIO, rr, _strategy_with("proportional"))
    prop_l = propose(PORTFOLIO, rr, _strategy_with("liquidate"))
    # Both propose trades to fix the Technology cap breach.
    assert prop_p["trades"] and prop_l["trades"]
    # Different trim method => different units sold on at least one holding.
    sells_p = {t["ticker"]: t["units"] for t in prop_p["trades"] if t["action"] == "sell"}
    sells_l = {t["ticker"]: t["units"] for t in prop_l["trades"] if t["action"] == "sell"}
    assert sells_p != sells_l, "strategy var change must change output"


def test_proposer_output_gates_green():
    """The rules engine — not the proposer — disposes. Post-trade must be green."""
    rr = check(PORTFOLIO, MANDATE)
    prop = propose(PORTFOLIO, rr, _strategy_with("proportional"))
    post = apply_trades(PORTFOLIO, prop["trades"])
    post_rr = check(post, MANDATE)
    assert not post_rr["breaches"], f"proposal left breaches: {post_rr['breaches']}"


def test_reflect_never_proposes_mandate_rule():
    """Reflection only ever names a strategy.yaml variable — never a mandate rule
    or anything in rules_engine.py."""
    from agents.hermes.reflect import reflect
    allowed = set(strategy_vars(load_strategy()).keys())
    for mode in ("fallback", "hermes"):
        prop = reflect(mode=mode)
        assert prop["variable"] in allowed, f"{mode} proposed {prop['variable']} outside strategy"


def test_strategy_guard_refuses_mandate_and_engine_paths():
    """The sole strategy writer must refuse paths outside strategy.yaml/history/."""
    from pathlib import Path
    with pytest.raises(PermissionError):
        _guard(Path("data/portfolios.json"))  # mandate rules
    with pytest.raises(PermissionError):
        _guard(Path("core/rules_engine.py"))  # the law itself
    # Allowed: strategy.yaml + history/ archives.
    _guard(STRATEGY_PATH)
    _guard(HISTORY_DIR / "v99.json")


def test_scan_book_gates_queue_and_writes_heartbeat():
    """scan_book over the SQLite book: gates every queue row green/orange,
    writes heartbeat with composite score. Wired to the SQLite fixture because
    the old file-based 40-portfolio fixture was removed in Task 4b."""
    c, _ = _client(n=400)
    from agents.hermes.loop import scan_book
    from agents.hermes import HEARTBEAT_PATH
    res = scan_book()
    hb = res["heartbeat"]
    counts = hb["counts"]
    assert counts["scanned"] == 400
    assert counts["green"] + counts["remediated"] + counts["missed"] + counts["skipped"] == counts["scanned"]
    # Every queue entry cleared its breaches (the gate) — post_status green or orange only.
    for q in res["queue"]:
        assert q["post_status"] in ("green", "orange")
        assert not q["post_rules_result"]["breaches"], "gate must drop still-red proposals"
    assert HEARTBEAT_PATH.exists()
    assert "score" in hb and "composite" in hb["score"]


def test_adopt_bumps_version_and_archives(tmp_path, monkeypatch):
    """Adopt mutates strategy.yaml, bumps version, archives the prior snapshot.
    Restores the seed after so other tests stay deterministic."""
    import shutil, json
    # Snapshot + restore the real strategy.yaml so this test is hermetic.
    original = STRATEGY_PATH.read_text()
    hist = HISTORY_DIR
    try:
        before_version = load_strategy()["version"]
        result = adopt_proposal("cash_buffer_target", 0.05, "test bump")
        after = load_strategy()
        assert result["version"] == before_version + 1
        assert after["version"] == before_version + 1
        assert after["variables"]["cash_buffer_target"]["value"] == 0.05
        # Prior snapshot archived under the OLD version number.
        assert (hist / f"v{before_version}.json").exists()
    finally:
        STRATEGY_PATH.write_text(original)
        if hist.exists():
            shutil.rmtree(hist)


# --- strategy + audit redirection helpers for the two new endpoint tests ---

def _redirect_strategy(monkeypatch, tmp_path):
    """Redirect strategy.yaml + history/ to tmp_path so strategy mutation tests
    never touch the real shipped strategy.yaml. Patches both the package exports
    and the strategy_io module bindings (which were bound at import time)."""
    import agents.hermes as hermes_pkg
    import agents.hermes.strategy_io as sio
    strat = tmp_path / "strategy.yaml"
    hist = tmp_path / "history"
    strat.write_text(hermes_pkg.STRATEGY_PATH.read_text())
    monkeypatch.setattr(hermes_pkg, "STRATEGY_PATH", strat)
    monkeypatch.setattr(hermes_pkg, "HISTORY_DIR", hist)
    monkeypatch.setattr(sio, "STRATEGY_PATH", strat)
    monkeypatch.setattr(sio, "HISTORY_DIR", hist)
    monkeypatch.setattr(sio, "_ALLOWED_WRITE_PREFIXES",
                        (strat.resolve(), hist.resolve()))
    return strat, hist


def _redirect_audit(monkeypatch, tmp_path):
    """Redirect the audit log to tmp_path; returns the audit file."""
    import routers.audit as audit
    audit_file = tmp_path / "audit.jsonl"
    audit_file.write_text("")
    monkeypatch.setattr(audit, "_AUDIT", audit_file)
    return audit_file


def test_approve_batch_applies_trades_flips_status_and_audits(tmp_path, monkeypatch):
    """POST /hermes/approve-batch: applies trades, re-checks via rules engine,
    flips a red portfolio to green, and writes a hermes_bulk audit record.

    Wired to the SQLite fixture (Task 4b removed the file-based _STATE_PATH the
    old test redirected). Audit is redirected to tmp_path; effective state lives
    in the temp DB so it stays isolated."""
    c, _ = _client(n=400)
    _redirect_audit(monkeypatch, tmp_path)

    # Run a full scan to produce gate-green queue rows with trades.
    r = c.post("/hermes/scan")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    import time
    for _ in range(60):
        st = c.get(f"/hermes/scan/{job_id}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", f"scan job did not complete: {st}"

    # Pick a queue row whose post-trade state is green (gate passed cleanly).
    rows = c.get("/hermes/queue?limit=200").json()["rows"]
    targets = [row for row in rows if row.get("trades") and row["post_status"] == "green"]
    assert targets, "expected at least one gate-green queue row with trades"
    item = targets[0]
    cid = item["client_id"]
    # queue stores trades as a JSON string; approve-batch expects list[dict]
    trades = json.loads(item["trades"]) if isinstance(item["trades"], str) else item["trades"]

    prior = c.get(f"/portfolio/{cid}/check").json()
    assert prior["status"] != "green", "queued portfolio must start non-green"

    r = c.post("/hermes/approve-batch",
               json={"items": [{"client_id": cid, "trades": trades,
                                "rationale": "bulk approve test"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] == 1
    assert body["failed"] == 0
    res = body["results"][0]
    assert res["client_id"] == cid
    assert res["prior_status"] != "green"
    assert res["new_status"] == "green"
    assert not res["rules_result"]["breaches"]

    # Audit recorded with actor "hermes_bulk".
    tail = c.get("/audit").json()
    assert any(e["client_id"] == cid and e["actor"] == "hermes_bulk"
               and e["action_type"] == "approve" for e in tail), \
        "hermes_bulk approve audit record missing"

    # Effective portfolio now green on re-read.
    new = c.get(f"/portfolio/{cid}/check").json()
    assert new["status"] == "green", "approved trades must persist into effective state"


def test_approve_batch_404_unknown_client(tmp_path, monkeypatch):
    """An unknown client_id is reported per-item failed; the batch still returns 200.

    Wired to the SQLite fixture; no state redirect needed (state lives in the
    temp DB). The old test redirected core.effective._STATE_PATH which was
    removed in Task 4b's SQLite rewrite."""
    c, _ = _client(n=400)
    _redirect_audit(monkeypatch, tmp_path)
    r = c.post("/hermes/approve-batch",
               json={"items": [{"client_id": "nope_not_real", "trades": [],
                                "rationale": ""}]})
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] == 0
    assert body["failed"] == 1
    assert "error" in body["results"][0]


def test_rollback_restores_prior_version_archives_current_and_audits(tmp_path, monkeypatch):
    """POST /hermes/rollback: restores history/v{version}.json, archives the
    current strategy first (reversible), bumps version forward, audits."""
    from fastapi.testclient import TestClient
    from main import app
    import agents.hermes.strategy_io as sio

    strat, hist = _redirect_strategy(monkeypatch, tmp_path)
    _redirect_audit(monkeypatch, tmp_path)
    client = TestClient(app)

    # Seed: v0 strategy. Adopt once -> archives v0, bumps to v1, changes a var.
    before = sio.load_strategy()
    v0 = before["version"]
    sio.adopt_proposal("cash_buffer_target", 0.05, "first change")
    after_first = sio.load_strategy()
    assert after_first["version"] == v0 + 1
    assert (hist / f"v{v0}.json").exists()

    # Now rollback to v0: should restore the v0 snapshot, archive current (v1)
    # as v1.json, and bump version to v2.
    r = client.post("/hermes/rollback", json={"version": v0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["from_version"] == v0 + 1
    assert body["to_version"] == v0 + 2
    # The restored strategy's variable matches the v0 snapshot (rolled back).
    v0_snapshot = __import__("json").loads((hist / f"v{v0}.json").read_text())
    assert (body["restored"]["variables"]["cash_buffer_target"]["value"]
            == v0_snapshot["variables"]["cash_buffer_target"]["value"])
    # Current pre-rollback strategy was archived as v{v0+1}.json (reversible).
    assert (hist / f"v{v0 + 1}.json").exists()
    # strategy.yaml on disk now holds the restored + bumped strategy.
    on_disk = sio.load_strategy()
    assert on_disk["version"] == v0 + 2
    assert (on_disk["variables"]["cash_buffer_target"]["value"]
            == v0_snapshot["variables"]["cash_buffer_target"]["value"])

    # Audit recorded.
    tail = client.get("/audit").json()
    assert any(e["action_type"] == "hermes_rollback" and e["actor"] == "human"
               and e["payload"].get("restored_version") == v0 for e in tail), \
        "hermes_rollback audit record missing"


def test_rollback_404_unknown_version(tmp_path, monkeypatch):
    """Rollback to a version with no archived snapshot returns 404."""
    from fastapi.testclient import TestClient
    from main import app
    _redirect_strategy(monkeypatch, tmp_path)
    _redirect_audit(monkeypatch, tmp_path)
    client = TestClient(app)
    r = client.post("/hermes/rollback", json={"version": 999})
    assert r.status_code == 404


# --- Hermes 2.0 proactive drift prevention (Sprint 6) ---

def test_prevent_scan_queues_green_portfolios_with_meta():
    """POST /hermes/prevent-scan: async job scans green portfolios, queues
    preventive trades with mode='prevent' and prevent_meta in the row."""
    c, _ = _client(n=400)
    r = c.post("/hermes/prevent-scan")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    import time
    for _ in range(80):
        st = c.get(f"/hermes/scan/{job_id}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", f"prevent scan job failed: {st}"

    rows = c.get("/hermes/queue?mode=prevent&limit=200").json()["rows"]
    for row in rows:
        assert row.get("mode") == "prevent", f"expected mode=prevent, got {row.get('mode')}"
        meta = json.loads(row["prevent_meta"]) if isinstance(row.get("prevent_meta"), str) else row.get("prevent_meta")
        assert meta and "horizon_days" in meta and "risk_before" in meta and "risk_after" in meta
        assert meta["risk_after"] < meta["risk_before"], "preventive trade must reduce projected risk"


def test_simulate_book_prevent_reduces_breach_incidence():
    """simulate_book('prevent') must reduce aggregate breach incidence by ≥50%
    versus the reactive baseline on the same cloned book and seed."""
    c, _ = _client(n=400)
    from agents.hermes.loop import simulate_book
    reactive = simulate_book(days=100, mode="reactive", seed=42)
    prevent = simulate_book(days=100, mode="prevent", seed=42)
    assert reactive["mode"] == "reactive"
    assert prevent["mode"] == "prevent"
    assert len(reactive["series"]) == 100
    assert len(prevent["series"]) == 100
    assert reactive["reactive_incidence"] is not None
    assert prevent["prevent_incidence"] is not None
    reduction = (reactive["reactive_incidence"] - prevent["prevent_incidence"]) / reactive["reactive_incidence"]
    assert reduction >= 0.50, (
        f"expected ≥50% breach-incidence reduction, got {reduction:.2%} "
        f"(reactive={reactive['reactive_incidence']}, prevent={prevent['prevent_incidence']})"
    )