# backend/core/storage.py
"""SQLite storage layer for the 34k synthetic book.

Single source of truth replacing the JSON-file data loader. WAL mode for
tick/scan/approve concurrency. All other modules go through get_conn(); no
module opens the db file directly.

Schema lives here (spec §6). init_schema is idempotent (CREATE IF NOT EXISTS);
migrate seeds the clock + book_summary singletons once.
"""
import os
import sqlite3
from typing import Optional

DB_PATH = os.environ.get("PORTFOLIOS_DB", os.path.join("data", "portfolios.db"))
SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
  client_id TEXT PRIMARY KEY,
  client_name TEXT, adviser TEXT, fum REAL, mandate_id INTEGER, cash REAL
);
CREATE TABLE IF NOT EXISTS mandates (
  mandate_id INTEGER PRIMARY KEY,
  spec TEXT,
  version TEXT DEFAULT '1.0.0',
  dsl TEXT,
  source_path TEXT,
  created_ts TEXT,
  spec_hash TEXT
);
CREATE TABLE IF NOT EXISTS holdings (
  client_id TEXT, ticker TEXT, units REAL,
  FOREIGN KEY(client_id) REFERENCES portfolios(client_id)
);
CREATE INDEX IF NOT EXISTS idx_holdings_client ON holdings(client_id);
CREATE TABLE IF NOT EXISTS prices (
  ticker TEXT, day INTEGER, price REAL,
  PRIMARY KEY(ticker, day)
);
CREATE TABLE IF NOT EXISTS state (
  client_id TEXT, ts TEXT, ticker TEXT, action TEXT, units REAL, value REAL, rationale TEXT
);
CREATE INDEX IF NOT EXISTS idx_state_client ON state(client_id);
CREATE TABLE IF NOT EXISTS status_history (
  day INTEGER, client_id TEXT, status TEXT, breach_count INTEGER, watch_count INTEGER,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX IF NOT EXISTS idx_status_day ON status_history(day);
CREATE TABLE IF NOT EXISTS book_summary (
  id INTEGER PRIMARY KEY CHECK(id=1),
  day INTEGER, total INTEGER, green INTEGER, orange INTEGER, red INTEGER,
  breach_count INTEGER, updated_ts TEXT
);
CREATE TABLE IF NOT EXISTS hermes_queue (
  day INTEGER, client_id TEXT, prior_status TEXT, post_status TEXT,
  fum REAL, trades TEXT, rationale TEXT, rank_score REAL, created_ts TEXT,
  processed_at TEXT,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX IF NOT EXISTS idx_queue_day ON hermes_queue(day);
CREATE TABLE IF NOT EXISTS scan_jobs (
  job_id TEXT PRIMARY KEY, kind TEXT, status TEXT, started_ts TEXT, done_ts TEXT,
  scanned INTEGER, remediated INTEGER, missed INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS clock (
  id INTEGER PRIMARY KEY CHECK(id=1),
  day INTEGER, running INTEGER, auto_interval_sec INTEGER, auto_fix INTEGER, seed INTEGER
);
CREATE TABLE IF NOT EXISTS drift_events (
  day INTEGER, client_id TEXT, from_status TEXT, to_status TEXT, ts TEXT,
  PRIMARY KEY(day, client_id)
);
CREATE INDEX IF NOT EXISTS idx_drift_day ON drift_events(day);
CREATE TABLE IF NOT EXISTS tickers (
  ticker TEXT PRIMARY KEY, name TEXT, asset_class TEXT, sector TEXT,
  region TEXT, liquidity_tier INTEGER, base_price REAL, mu REAL, sigma REAL
);
"""


def get_conn(path: Optional[str] = None) -> sqlite3.Connection:
    p = path or DB_PATH
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_mandates_table(conn: sqlite3.Connection) -> None:
    """Idempotent migration from v1 mandates table to v2 schema."""
    cols = _columns(conn, "mandates")
    if "version" not in cols:
        conn.execute("ALTER TABLE mandates ADD COLUMN version TEXT DEFAULT '1.0.0'")
    if "dsl" not in cols:
        conn.execute("ALTER TABLE mandates ADD COLUMN dsl TEXT")
    if "source_path" not in cols:
        conn.execute("ALTER TABLE mandates ADD COLUMN source_path TEXT")
    if "created_ts" not in cols:
        conn.execute("ALTER TABLE mandates ADD COLUMN created_ts TEXT")
    if "spec_hash" not in cols:
        conn.execute("ALTER TABLE mandates ADD COLUMN spec_hash TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mandates_hash ON mandates(spec_hash)")
    conn.execute(
        "UPDATE mandates SET version = COALESCE(version, '1.0.0'), "
        "created_ts = COALESCE(created_ts, datetime('now')) WHERE version IS NULL OR created_ts IS NULL"
    )


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    _migrate_mandates_table(conn)
    conn.commit()


def migrate(conn: sqlite3.Connection) -> None:
    init_schema(conn)
    seed = int(os.environ.get("MARKET_SEED", "42"))
    # Seed singletons only if absent — never clobber an existing clock day.
    if conn.execute("SELECT count(*) FROM clock WHERE id=1").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO clock (id, day, running, auto_interval_sec, auto_fix, seed) "
            "VALUES (1, 0, 0, 5, 0, ?)",
            (seed,),
        )
    if conn.execute("SELECT count(*) FROM book_summary WHERE id=1").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO book_summary (id, day, total, green, orange, red, breach_count, updated_ts) "
            "VALUES (1, 0, 0, 0, 0, 0, 0, '')"
        )
    conn.commit()