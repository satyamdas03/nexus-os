"""Tests for the Hermes shared storage abstraction.

Covers both SQLite (default) and Postgres (if HERMES_STORE_URL is set) stores
with the same contract tests.
"""
import os
import pytest
from core.hermes_store import SQLiteHermesStore, PostgresHermesStore, get_hermes_store, set_hermes_store


def _contract_test(store):
    store.init()

    # scan_jobs
    store.insert_scan_job("job-1", "full", "running", "2026-06-20T00:00:00Z")
    job = store.get_scan_job("job-1")
    assert job is not None
    assert job["status"] == "running"

    store.update_scan_job_done("job-1", "2026-06-20T00:01:00Z", 100, 10, 5)
    job = store.get_scan_job("job-1")
    assert job["status"] == "done"
    assert job["scanned"] == 100
    assert job["remediated"] == 10
    assert job["missed"] == 5

    # heartbeat
    assert store.read_heartbeat() is None
    hb = {"counts": {"scanned": 100}, "queue_size": 10}
    store.write_heartbeat(hb)
    assert store.read_heartbeat() == hb

    # queue
    store.clear_queue()
    rows = [
        {"day": 0, "client_id": "c00001", "prior_status": "red", "post_status": "green",
         "fum": 1e6, "trades": "[]", "rationale": "r1", "rank_score": 100.0,
         "created_ts": "2026-06-20T00:00:00Z"},
        {"day": 0, "client_id": "c00002", "prior_status": "orange", "post_status": "green",
         "fum": 2e6, "trades": "[]", "rationale": "r2", "rank_score": 200.0,
         "created_ts": "2026-06-20T00:00:00Z"},
    ]
    store.insert_queue_rows(rows)
    assert store.get_latest_queue_day() == 0
    assert store.count_unprocessed_queue(0) == 2

    q = store.get_queue(0, 0, 10)
    assert len(q) == 2
    assert q[0]["client_id"] == "c00002"  # higher rank_score first

    # mark processed
    n = store.mark_queue_processed(["c00002"], 0, "2026-06-20T00:02:00Z")
    assert n == 1
    assert store.count_unprocessed_queue(0) == 1
    q = store.get_queue(0, 0, 10)
    assert len(q) == 1
    assert q[0]["client_id"] == "c00001"

    store.clear_queue()
    assert store.count_unprocessed_queue(0) == 0


def test_sqlite_store(tmp_path):
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "hermes_test.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    from core import storage
    storage.init_schema(conn)
    store = SQLiteHermesStore(conn)
    _contract_test(store)


@pytest.mark.skipif(not os.environ.get("HERMES_STORE_URL", "").startswith("postgres"),
                    reason="requires HERMES_STORE_URL")
def test_postgres_store():
    store = PostgresHermesStore(os.environ["HERMES_STORE_URL"])
    _contract_test(store)


def test_get_hermes_store_singleton():
    old = get_hermes_store()
    new = SQLiteHermesStore()
    set_hermes_store(new)
    assert get_hermes_store() is new
    set_hermes_store(old)
