# backend/core/data_loader.py
"""SQLite-backed portfolio loader. Replaces the JSON-file loader.

get_portfolio is O(1) (primary-key lookup; holdings via idx_holdings_client).
Holdings are revalued lazily on read: market_value = units * price(current_day).
current_prices() resolves every ticker's price at the current clock day,
computing + persisting any missing (ticker, day) rows via generators.market.price_for.

summary() reads the precomputed book_summary row (written by generate_data and
refreshed by the drift monitor) so /portfolios/summary is O(1).

Holding dicts carry region/liquidity_tier/name/asset_class/sector from the
universe (the holdings table is normalized to client_id, ticker, units only).
rules_engine.check reads h["region"] and h["liquidity_tier"], so those MUST be
attached here — see the Task 3c cross-task contract.
"""
import json
import os
import sqlite3
import threading
from typing import Optional

from generators import universe as U
from generators import market as MK
from core import storage

_conn_local = threading.local()
_conn_lock = threading.Lock()
_conn_override: Optional[sqlite3.Connection] = None  # test seam via set_conn
_prices_cache: dict = {}  # (day, seed) -> {ticker: price}
_mandate_cache: dict = {}  # mandate_id -> full mandates row dict


def get_conn_cached() -> sqlite3.Connection:
    # Tests can pin a single connection globally.
    if _conn_override is not None:
        return _conn_override
    # Each thread gets its own connection so concurrent Uvicorn workers never
    # share a sqlite3 connection (which is unsafe even with check_same_thread=False).
    conn = getattr(_conn_local, "conn", None)
    if conn is None:
        with _conn_lock:
            conn = storage.get_conn()
            storage.init_schema(conn)
            storage.migrate(conn)
            _conn_local.conn = conn
    return conn


def set_conn(conn: sqlite3.Connection) -> None:
    global _conn_override, _prices_cache, _mandate_cache
    _conn_override = conn
    _prices_cache = {}
    _mandate_cache = {}


def set_thread_conn(conn: Optional[sqlite3.Connection]) -> None:
    """Set the connection used by the current thread only.

    This is safer than set_conn for background work because it does not mutate
    the global override used by the main request thread.
    """
    _conn_local.conn = conn


def ensure_book(
    n: int = 34000,
    seed: Optional[int] = None,
    market_seed: Optional[int] = None,
) -> bool:
    """Generate the book if the portfolios table is empty.

    Idempotent: if a book already exists it is left untouched (so a reboot on
    a persistent disk preserves the clock day + any approved trades). Only a
    fresh/empty db (ephemeral Render disk on a new deploy) triggers generation.
    Seeds default to the DATA_SEED / MARKET_SEED env vars (both default 42) so
    the deployed book is deterministic and matches the local seed.
    Returns True iff a book was generated.
    """
    from generators import generate_data

    conn = get_conn_cached()
    count = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    if count and count > 0:
        return False
    generate_data.build_book(
        conn,
        n=n,
        seed=seed if seed is not None else int(os.environ.get("DATA_SEED", "42")),
        market_seed=market_seed if market_seed is not None else int(os.environ.get("MARKET_SEED", "42")),
    )
    return True


def _clock() -> tuple[int, int]:
    row = get_conn_cached().execute("SELECT day, seed FROM clock WHERE id=1").fetchone()
    if row is None:
        return (0, 42)
    day = row["day"]
    return (day if day is not None else 0, row["seed"])


def current_prices() -> dict:
    conn = get_conn_cached()
    day, seed = _clock()
    key = (day, seed)
    if key in _prices_cache:
        return _prices_cache[key]
    have = {r["ticker"]: r["price"]
            for r in conn.execute("SELECT ticker, price FROM prices WHERE day=?", (day,))}
    out = dict(have)
    missing = [t for t in U.all_tickers() if t not in have]
    if missing:
        for t in missing:
            out[t] = MK.price_for(t, day, seed)
            conn.execute("INSERT OR REPLACE INTO prices (ticker, day, price) VALUES (?,?,?)",
                         (t, day, out[t]))
        conn.commit()
    _prices_cache[key] = out
    return out


def _mandate(conn: sqlite3.Connection, mandate_id: int) -> dict:
    row = _mandate_cache.get(mandate_id)
    if row is not None:
        return json.loads(row["spec"])
    row = conn.execute("SELECT * FROM mandates WHERE mandate_id=?", (mandate_id,)).fetchone()
    if row is None:
        return {}
    _mandate_cache[mandate_id] = row
    return json.loads(row["spec"])


def _mandate_full(conn: sqlite3.Connection, mandate_id: int) -> dict:
    """Return mandate metadata including version, DSL YAML, source path and hash."""
    row = conn.execute("SELECT * FROM mandates WHERE mandate_id=?", (mandate_id,)).fetchone()
    if row is None:
        return {}
    return {
        "mandate_id": row["mandate_id"],
        "spec": json.loads(row["spec"]) if row["spec"] else {},
        "version": row["version"] or "1.0.0",
        "dsl": row["dsl"] or "",
        "source_path": row["source_path"] or "",
        "created_ts": row["created_ts"] or "",
        "spec_hash": row["spec_hash"] or "",
    }


def get_portfolio(client_id: str) -> Optional[dict]:
    conn = get_conn_cached()
    p = conn.execute("SELECT * FROM portfolios WHERE client_id=?", (client_id,)).fetchone()
    if p is None:
        return None
    prices = current_prices()
    holdings = []
    for h in conn.execute(
        "SELECT ticker, units FROM holdings WHERE client_id=? AND ticker!='CASH' ORDER BY ticker",
        (client_id,),
    ):
        meta = U.UNIVERSE_BY_TICKER.get(h["ticker"])
        if meta is None:
            continue
        price = prices[h["ticker"]]
        holdings.append({
            "ticker": h["ticker"], "name": meta["name"], "asset_class": meta["asset_class"],
            "sector": meta["sector"], "region": meta["region"], "liquidity_tier": meta["liquidity_tier"],
            "units": h["units"], "price": price, "market_value": round(h["units"] * price, 2),
        })
    return {
        "client_id": p["client_id"], "client_name": p["client_name"], "adviser": p["adviser"],
        "fum": p["fum"], "mandate_id": p["mandate_id"], "holdings": holdings, "cash": p["cash"],
        "mandate": _mandate(conn, p["mandate_id"]),
    }


def list_portfolios(limit: int = 500, offset: int = 0) -> list[dict]:
    """Paged portfolio list. Batch-loads the page in two SQL queries:
    one for the portfolio rows and one for all their holdings, avoiding
    the previous N+1 pattern. Return shape matches get_portfolio exactly."""
    conn = get_conn_cached()
    prices = current_prices()
    portfolio_rows = conn.execute(
        "SELECT * FROM portfolios ORDER BY client_id LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    if not portfolio_rows:
        return []
    client_ids = [p["client_id"] for p in portfolio_rows]
    holdings_by_client: dict[str, list[dict]] = {cid: [] for cid in client_ids}

    # SQLite IN(...) is limited to ~999 variables, so chunk large pages.
    chunk_size = 900
    for i in range(0, len(client_ids), chunk_size):
        chunk = client_ids[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        for h in conn.execute(
            f"SELECT client_id, ticker, units FROM holdings "
            f"WHERE client_id IN ({placeholders}) AND ticker!='CASH' "
            f"ORDER BY client_id, ticker",
            chunk,
        ):
            meta = U.UNIVERSE_BY_TICKER.get(h["ticker"])
            if meta is None:
                continue
            price = prices[h["ticker"]]
            holdings_by_client[h["client_id"]].append({
                "ticker": h["ticker"], "name": meta["name"], "asset_class": meta["asset_class"],
                "sector": meta["sector"], "region": meta["region"], "liquidity_tier": meta["liquidity_tier"],
                "units": h["units"], "price": price, "market_value": round(h["units"] * price, 2),
            })

    mandate_ids = {p["mandate_id"] for p in portfolio_rows}
    mandates = {mid: _mandate(conn, mid) for mid in mandate_ids}

    return [
        {
            "client_id": p["client_id"], "client_name": p["client_name"], "adviser": p["adviser"],
            "fum": p["fum"], "mandate_id": p["mandate_id"],
            "holdings": holdings_by_client[p["client_id"]], "cash": p["cash"],
            "mandate": mandates[p["mandate_id"]],
        }
        for p in portfolio_rows
    ]


def load_portfolios() -> list[dict]:
    """Legacy full-list. Reuses the batched list_portfolios."""
    out: list[dict] = []
    offset = 0
    while True:
        page = list_portfolios(limit=2000, offset=offset)
        if not page:
            break
        out.extend(page)
        offset += len(page)
    return out


def summary() -> dict:
    row = get_conn_cached().execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    if row is None or row["total"] == 0:
        return {"total": 0, "counts": {"green": 0, "orange": 0, "red": 0}, "breach_count": 0}
    return {
        "total": row["total"],
        "counts": {"green": row["green"], "orange": row["orange"], "red": row["red"]},
        "breach_count": row["breach_count"],
    }


def reset_cache() -> None:
    global _conn, _prices_cache
    _conn = None
    _prices_cache = {}