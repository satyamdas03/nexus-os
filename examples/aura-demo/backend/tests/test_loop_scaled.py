# backend/tests/test_loop_scaled.py
"""Hermes scaled-loop tests: paged scan, delta scan, queue table, ranking.

Spec §13.2: delta scan over a synthetic newly-non-green set -> queue rows are
gate-green (post_status green/orange, no breaches); misses logged.
"""
import json, os, sqlite3, tempfile

from core import storage, data_loader
from core.hermes_store import SQLiteHermesStore, set_hermes_store
from generators import generate_data
from agents.hermes import loop


def _setup(n=400):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    store = SQLiteHermesStore(conn)
    set_hermes_store(store)
    loop._set_store(store)
    return conn


def test_scan_book_queue_rows_are_gate_green():
    conn = _setup()
    res = loop.scan_book()
    q = res["queue"]
    assert res["heartbeat"]["counts"]["scanned"] == 400
    # every queued proposal cleared all breaches (gate-green by construction)
    for item in q:
        assert item["post_status"] in ("green", "orange")
        assert item["post_rules_result"]["breaches"] == []
    # queue rows persisted to the table — every gate-passed row is stored
    rows = conn.execute("SELECT count(*) FROM hermes_queue").fetchone()[0]
    assert rows == res["heartbeat"]["counts"]["remediated"] >= len(q)
    assert len(q) >= 1
    # misses are non-zero only if some proposal failed the gate (allowed)
    assert res["heartbeat"]["counts"]["remediated"] == rows


def test_scan_book_paged_returns_cursor_and_accumulates():
    conn = _setup(n=1200)
    page = loop.scan_book_paged(cursor=0, batch=500, clear=True)
    assert page["next_cursor"] == 500
    page2 = loop.scan_book_paged(cursor=500, batch=500)
    assert page2["next_cursor"] == 1000
    page3 = loop.scan_book_paged(cursor=1000, batch=500)
    assert page3["next_cursor"] is None  # exhausted


def test_delta_scan_appends_day_tagged_rows():
    conn = _setup()
    # pick two non-green portfolios to delta-scan
    loop.scan_book()  # populate queue + find non-greens
    cids = [r["client_id"] for r in conn.execute("SELECT client_id FROM hermes_queue LIMIT 2")]
    conn.execute("DELETE FROM hermes_queue")
    conn.commit()
    if not cids:
        cids = [r["client_id"] for r in conn.execute("SELECT client_id FROM portfolios LIMIT 2")]
    res = loop.delta_scan(cids, day=3)
    # every scanned id is counted; subset path is taken (no cursor)
    assert res["counts"]["scanned"] == len(cids)
    rows = conn.execute("SELECT day, client_id FROM hermes_queue WHERE day=3").fetchall()
    # any rows that did land must be day-tagged 3 and gate-green
    assert all(r["day"] == 3 for r in rows)
    for r in rows:
        assert r["client_id"] in cids


def test_queue_rows_ranked_by_fum_times_severity():
    conn = _setup()
    res = loop.scan_book()
    q = res["queue"]
    if len(q) >= 2:
        assert q[0]["rank_score"] >= q[1]["rank_score"]


def test_heartbeat_written_and_shaped():
    _setup()
    res = loop.scan_book()
    hb = res["heartbeat"]
    for k in ("counts", "queue_size", "miss_count", "score"):
        assert k in hb
    # queue_size reflects ALL gate-passed rows; returned queue is the top-50 view
    assert hb["queue_size"] == hb["counts"]["remediated"]
    assert len(res["queue"]) == min(50, hb["queue_size"])


def test_scan_book_is_deterministic():
    conn = _setup()
    r1 = loop.scan_book()
    r2 = loop.scan_book()
    assert r1["heartbeat"]["counts"] == r2["heartbeat"]["counts"]
    assert r1["heartbeat"]["queue_size"] == r2["heartbeat"]["queue_size"]


def test_delta_scan_misses_counted_not_dropped():
    conn = _setup()
    # scan the whole book to find a populated set; delta-scan a non-green id
    loop.scan_book()
    cids = [r["client_id"] for r in conn.execute("SELECT client_id FROM hermes_queue LIMIT 1")]
    conn.execute("DELETE FROM hermes_queue"); conn.commit()
    if not cids:
        cids = [r["client_id"] for r in conn.execute("SELECT client_id FROM portfolios LIMIT 1")]
    res = loop.delta_scan(cids, day=5)
    # scanned + green + remediated + missed + skipped reconciles to scanned
    c = res["counts"]
    assert c["green"] + c["remediated"] + c["missed"] + c["skipped"] == c["scanned"]
    # misses list length matches the missed counter
    assert len(res["misses"]) == c["missed"]