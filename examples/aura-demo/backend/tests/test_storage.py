# backend/tests/test_storage.py
import sqlite3
from core import storage


def _mem():
    """In-memory conn with Row factory (matches get_conn's row_factory)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_init_schema_creates_all_tables():
    conn = _mem()
    storage.init_schema(conn)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    names = {r[0] for r in rows}
    for t in ("portfolios", "mandates", "holdings", "prices", "state",
              "status_history", "book_summary", "hermes_queue", "scan_jobs",
              "clock", "drift_events", "tickers"):
        assert t in names, f"missing table {t}"


def test_init_schema_idempotent():
    conn = _mem()
    storage.init_schema(conn)
    storage.init_schema(conn)  # no error
    assert conn.execute("SELECT count(*) FROM portfolios").fetchone()[0] == 0


def test_migrate_seeds_clock_and_summary_singletons():
    conn = _mem()
    storage.init_schema(conn)
    storage.migrate(conn)
    clock = conn.execute("SELECT * FROM clock WHERE id=1").fetchone()
    assert clock is not None
    assert clock["day"] == 0
    assert clock["running"] == 0
    assert clock["auto_fix"] == 0
    summary = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    assert summary is not None
    assert summary["total"] == 0


def test_migrate_idempotent_does_not_reset_day():
    conn = _mem()
    storage.init_schema(conn)
    storage.migrate(conn)
    conn.execute("UPDATE clock SET day=7 WHERE id=1")
    storage.migrate(conn)  # must not clobber an existing clock row
    assert conn.execute("SELECT day FROM clock WHERE id=1").fetchone()[0] == 7


def test_get_conn_uses_wal_and_row_factory(tmp_path):
    p = str(tmp_path / "t.db")
    conn = storage.get_conn(p)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    conn.execute("CREATE TABLE x(a INTEGER)")
    conn.execute("INSERT INTO x VALUES (1)")
    row = conn.execute("SELECT a FROM x").fetchone()
    assert row["a"] == 1  # Row factory supports column access
    conn.close()