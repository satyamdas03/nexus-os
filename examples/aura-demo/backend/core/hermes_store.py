"""Shared storage abstraction for Hermes runtime state.

Hermes needs a single shared source of truth for:
  - scan_jobs     (async scan progress)
  - hermes_queue  (gate-passed remediation proposals)
  - heartbeat     (last scan summary + score)

On local/dev this can stay in SQLite. On Vercel serverless (ephemeral disk)
each function invocation may get a different SQLite file, so scan jobs and
queue rows appear to vanish between requests. This module provides a small
pluggable storage layer:

  - SQLiteHermesStore  : keeps the current SQLite tables (local/dev/tests).
  - PostgresHermesStore: uses a Postgres connection string (production).

Selection is controlled by the HERMES_STORE_URL env var. If unset we fall back
to the main SQLite connection from core.data_loader (current behavior), so
local tests and the Render-style persistent-disk deploy keep working unchanged.

The schema is intentionally narrow and duplicated in both backends so the rest
of the app can keep using the same table/column names.
"""
from __future__ import annotations

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core import storage

HERMES_STORE_URL = os.environ.get("HERMES_STORE_URL", "")
HEARTBEAT_TABLE = "hermes_heartbeat"


class HermesStore(ABC):
    @abstractmethod
    def init(self) -> None: ...

    @abstractmethod
    def get_conn(self): ...

    # ---- scan_jobs ----
    @abstractmethod
    def insert_scan_job(self, job_id: str, kind: str, status: str, started_ts: str) -> None: ...
    @abstractmethod
    def update_scan_job_done(self, job_id: str, done_ts: str, scanned: int, remediated: int,
                             missed: int, error: Optional[str] = None) -> None: ...
    @abstractmethod
    def get_scan_job(self, job_id: str) -> Optional[dict]: ...

    # ---- hermes_queue ----
    @abstractmethod
    def clear_queue(self, day: Optional[int] = None) -> None: ...
    @abstractmethod
    def insert_queue_rows(self, rows: list[dict]) -> None: ...
    @abstractmethod
    def get_queue(self, day: int, cursor: int, limit: int) -> list[dict]: ...
    @abstractmethod
    def get_latest_queue_day(self) -> Optional[int]: ...
    @abstractmethod
    def mark_queue_processed(self, client_ids: list[str], day: int, processed_ts: str) -> int: ...
    @abstractmethod
    def count_unprocessed_queue(self, day: int) -> int: ...

    # ---- heartbeat ----
    @abstractmethod
    def write_heartbeat(self, payload: dict) -> None: ...
    @abstractmethod
    def read_heartbeat(self) -> Optional[dict]: ...


class SQLiteHermesStore(HermesStore):
    """Default store: uses the main SQLite connection from core.data_loader.

    This preserves the existing local-dev and persistent-disk deploy behavior.
    """

    def __init__(self, conn=None):
        # If a connection is provided we derive its file path and open our own
        # connection to that path. This avoids sharing a single sqlite3 connection
        # between the scan loop (heavy writer) and read endpoints, eliminating
        # the "database is locked" 500s seen under concurrent load.
        self._provided_conn = conn
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path: Optional[str] = None

    def _db_file(self) -> str:
        if self._db_path:
            return self._db_path
        # Use the path from the provided connection, or the default DB path.
        if self._provided_conn is not None:
            row = self._provided_conn.execute("PRAGMA database_list").fetchone()
            file_path = row["file"] if row else None
            self._db_path = file_path if file_path else storage.DB_PATH
        else:
            self._db_path = storage.DB_PATH
        return self._db_path

    def _resolve_conn(self):
        # Open a fresh connection each time so we never share the data_loader
        # cached connection with the scan loop.
        if self._conn is None:
            self._conn = storage.get_conn(self._db_file())
            storage.init_schema(self._conn)
            self.init()
        return self._conn

    def get_conn(self):
        return self._resolve_conn()

    def init(self) -> None:
        conn = self._resolve_conn()
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {HEARTBEAT_TABLE} (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT, updated_ts TEXT)"
        )
        # Re-create hermes_queue with the primary key we need for upserts.
        # On a fresh DB core.storage already creates the PK version. On an older
        # dev DB we migrate in place by copying the data.
        pk = conn.execute(
            "SELECT count(*) FROM pragma_table_info('hermes_queue') WHERE pk > 0"
        ).fetchone()[0]
        has_processed = conn.execute(
            "SELECT count(*) FROM pragma_table_info('hermes_queue') WHERE name='processed_at'"
        ).fetchone()[0]
        if pk == 0:
            # Old table without PK: rename, recreate with PK, copy back.
            conn.executescript(
                "ALTER TABLE hermes_queue RENAME TO hermes_queue_old;"
                "CREATE TABLE hermes_queue ("
                "  day INTEGER, client_id TEXT, prior_status TEXT, post_status TEXT,"
                "  fum REAL, trades TEXT, rationale TEXT, rank_score REAL, created_ts TEXT,"
                "  processed_at TEXT, PRIMARY KEY(day, client_id)"
                ");"
                "INSERT INTO hermes_queue (day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts, processed_at)"
                "  SELECT day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts, NULL"
                "  FROM hermes_queue_old;"
                "DROP TABLE hermes_queue_old;"
            )
        elif not has_processed:
            conn.execute("ALTER TABLE hermes_queue ADD COLUMN processed_at TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_processed ON hermes_queue(processed_at)")
        conn.commit()

    def insert_scan_job(self, job_id: str, kind: str, status: str, started_ts: str) -> None:
        conn = self._resolve_conn()
        conn.execute(
            "INSERT INTO scan_jobs(job_id, kind, status, started_ts, scanned, remediated, missed, error) "
            "VALUES (?, ?, ?, ?, 0, 0, 0, NULL)",
            (job_id, kind, status, started_ts),
        )
        conn.commit()

    def update_scan_job_done(self, job_id: str, done_ts: str, scanned: int, remediated: int,
                             missed: int, error: Optional[str] = None) -> None:
        conn = self._resolve_conn()
        status = "failed" if error else "done"
        conn.execute(
            "UPDATE scan_jobs SET status=?, done_ts=?, scanned=?, remediated=?, missed=?, error=? WHERE job_id=?",
            (status, done_ts, scanned, remediated, missed, error, job_id),
        )
        conn.commit()

    def get_scan_job(self, job_id: str) -> Optional[dict]:
        conn = self._resolve_conn()
        row = conn.execute("SELECT * FROM scan_jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def clear_queue(self, day: Optional[int] = None) -> None:
        conn = self._resolve_conn()
        if day is None:
            conn.execute("DELETE FROM hermes_queue")
        else:
            conn.execute("DELETE FROM hermes_queue WHERE day=?", (day,))
        conn.commit()

    def insert_queue_rows(self, rows: list[dict]) -> None:
        if not rows:
            return
        conn = self._resolve_conn()
        # Upsert so a re-scan of the same day does not duplicate rows.
        for r in rows:
            conn.execute(
                "INSERT INTO hermes_queue (day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts, processed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) "
                "ON CONFLICT(day, client_id) DO UPDATE SET "
                "prior_status=excluded.prior_status, post_status=excluded.post_status, fum=excluded.fum, "
                "trades=excluded.trades, rationale=excluded.rationale, rank_score=excluded.rank_score, "
                "created_ts=excluded.created_ts, processed_at=NULL",
                (r["day"], r["client_id"], r["prior_status"], r["post_status"], r["fum"],
                 r["trades"], r["rationale"], r["rank_score"], r["created_ts"]),
            )
        conn.commit()

    def get_queue(self, day: int, cursor: int, limit: int) -> list[dict]:
        conn = self._resolve_conn()
        rows = conn.execute(
            "SELECT day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts, processed_at "
            "FROM hermes_queue WHERE day=? AND processed_at IS NULL ORDER BY rank_score DESC, fum DESC LIMIT ? OFFSET ?",
            (day, limit, cursor),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_queue_day(self) -> Optional[int]:
        conn = self._resolve_conn()
        row = conn.execute("SELECT MAX(day) AS d FROM hermes_queue WHERE processed_at IS NULL").fetchone()
        return row["d"] if row else None

    def mark_queue_processed(self, client_ids: list[str], day: int, processed_ts: str) -> int:
        if not client_ids:
            return 0
        conn = self._resolve_conn()
        placeholders = ",".join("?" for _ in client_ids)
        cur = conn.execute(
            f"UPDATE hermes_queue SET processed_at=? WHERE day=? AND client_id IN ({placeholders}) AND processed_at IS NULL",
            (processed_ts, day, *client_ids),
        )
        conn.commit()
        return cur.rowcount

    def count_unprocessed_queue(self, day: int) -> int:
        conn = self._resolve_conn()
        row = conn.execute(
            "SELECT count(*) AS n FROM hermes_queue WHERE day=? AND processed_at IS NULL",
            (day,),
        ).fetchone()
        return row["n"] if row else 0

    def write_heartbeat(self, payload: dict) -> None:
        conn = self._resolve_conn()
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {HEARTBEAT_TABLE} (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT, updated_ts TEXT)"
        )
        conn.execute(
            f"INSERT OR REPLACE INTO {HEARTBEAT_TABLE}(id, payload, updated_ts) VALUES (1, ?, ?)",
            (json.dumps(payload), ts),
        )
        conn.commit()

    def read_heartbeat(self) -> Optional[dict]:
        conn = self._resolve_conn()
        row = conn.execute(
            f"SELECT payload FROM {HEARTBEAT_TABLE} WHERE id=1"
        ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])


class PostgresHermesStore(HermesStore):
    """Production store for serverless deploys where SQLite is not shared.

    Connection string format: postgresql://user:pass@host:port/dbname
    Uses psycopg 3 (already added to requirements.txt).
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    def get_conn(self):
        if self._conn is None or self._conn.closed:
            import psycopg
            self._conn = psycopg.connect(self.dsn)
            self._conn.autocommit = False
        return self._conn

    def init(self) -> None:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_jobs (
                    job_id TEXT PRIMARY KEY,
                    kind TEXT,
                    status TEXT,
                    started_ts TEXT,
                    done_ts TEXT,
                    scanned INTEGER DEFAULT 0,
                    remediated INTEGER DEFAULT 0,
                    missed INTEGER DEFAULT 0,
                    error TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hermes_queue (
                    day INTEGER,
                    client_id TEXT,
                    prior_status TEXT,
                    post_status TEXT,
                    fum REAL,
                    trades TEXT,
                    rationale TEXT,
                    rank_score REAL,
                    created_ts TEXT,
                    processed_at TEXT,
                    PRIMARY KEY (day, client_id)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {HEARTBEAT_TABLE} (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT,
                    updated_ts TEXT
                )
                """
            )
        conn.commit()

    def insert_scan_job(self, job_id: str, kind: str, status: str, started_ts: str) -> None:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scan_jobs(job_id, kind, status, started_ts, scanned, remediated, missed, error) "
                "VALUES (%s, %s, %s, %s, 0, 0, 0, NULL)",
                (job_id, kind, started_ts),
            )
        conn.commit()

    def update_scan_job_done(self, job_id: str, done_ts: str, scanned: int, remediated: int,
                             missed: int, error: Optional[str] = None) -> None:
        conn = self.get_conn()
        status = "failed" if error else "done"
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE scan_jobs SET status=%s, done_ts=%s, scanned=%s, remediated=%s, missed=%s, error=%s "
                "WHERE job_id=%s",
                (status, done_ts, scanned, remediated, missed, error, job_id),
            )
        conn.commit()

    def get_scan_job(self, job_id: str) -> Optional[dict]:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM scan_jobs WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c.name for c in cur.description]
            return dict(zip(cols, row))

    def clear_queue(self, day: Optional[int] = None) -> None:
        conn = self.get_conn()
        with conn.cursor() as cur:
            if day is None:
                cur.execute("DELETE FROM hermes_queue")
            else:
                cur.execute("DELETE FROM hermes_queue WHERE day=%s", (day,))
        conn.commit()

    def insert_queue_rows(self, rows: list[dict]) -> None:
        if not rows:
            return
        conn = self.get_conn()
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    "INSERT INTO hermes_queue (day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts, processed_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL) "
                    "ON CONFLICT (day, client_id) DO UPDATE SET "
                    "prior_status=EXCLUDED.prior_status, post_status=EXCLUDED.post_status, fum=EXCLUDED.fum, "
                    "trades=EXCLUDED.trades, rationale=EXCLUDED.rationale, rank_score=EXCLUDED.rank_score, "
                    "created_ts=EXCLUDED.created_ts, processed_at=NULL",
                    (r["day"], r["client_id"], r["prior_status"], r["post_status"], r["fum"],
                     r["trades"], r["rationale"], r["rank_score"], r["created_ts"]),
                )
        conn.commit()

    def get_queue(self, day: int, cursor: int, limit: int) -> list[dict]:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT day, client_id, prior_status, post_status, fum, trades, rationale, rank_score, created_ts, processed_at "
                "FROM hermes_queue WHERE day=%s AND processed_at IS NULL "
                "ORDER BY rank_score DESC, fum DESC LIMIT %s OFFSET %s",
                (day, limit, cursor),
            )
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in rows]

    def get_latest_queue_day(self) -> Optional[int]:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(day) AS d FROM hermes_queue WHERE processed_at IS NULL")
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else None

    def mark_queue_processed(self, client_ids: list[str], day: int, processed_ts: str) -> int:
        if not client_ids:
            return 0
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hermes_queue SET processed_at=%s WHERE day=%s AND client_id = ANY(%s) AND processed_at IS NULL",
                (processed_ts, day, client_ids),
            )
            count = cur.rowcount
        conn.commit()
        return count

    def count_unprocessed_queue(self, day: int) -> int:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM hermes_queue WHERE day=%s AND processed_at IS NULL",
                (day,),
            )
            row = cur.fetchone()
            return row[0] if row else 0

    def write_heartbeat(self, payload: dict) -> None:
        conn = self.get_conn()
        ts = datetime.now(timezone.utc).isoformat()
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {HEARTBEAT_TABLE} (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT, updated_ts TEXT)"
            )
            cur.execute(
                f"INSERT INTO {HEARTBEAT_TABLE}(id, payload, updated_ts) VALUES (1, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload, updated_ts=EXCLUDED.updated_ts",
                (json.dumps(payload), ts),
            )
        conn.commit()

    def read_heartbeat(self) -> Optional[dict]:
        conn = self.get_conn()
        with conn.cursor() as cur:
            cur.execute(f"SELECT payload FROM {HEARTBEAT_TABLE} WHERE id=1")
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])


# Singleton selection
_store: Optional[HermesStore] = None


def get_hermes_store() -> HermesStore:
    global _store
    if _store is None:
        if HERMES_STORE_URL.startswith("postgres"):
            _store = PostgresHermesStore(HERMES_STORE_URL)
        else:
            _store = SQLiteHermesStore()
        _store.init()
    return _store


def set_hermes_store(store: HermesStore) -> None:
    global _store
    _store = store
