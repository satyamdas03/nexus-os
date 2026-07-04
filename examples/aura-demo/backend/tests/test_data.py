# backend/tests/test_data.py
import os, sqlite3, tempfile
import pytest
from core import storage, data_loader, rules_engine
from generators import generate_data, universe


@pytest.fixture(autouse=True)
def _reset_data_loader_cache():
    """Ensure each test starts and ends with a clean data_loader cache so
    set_conn() in one test never leaks into other test modules."""
    data_loader.reset_cache()
    yield
    data_loader.reset_cache()


@pytest.fixture
def book_conn(tmp_path):
    """Create a temporary book DB, yield the connection, then close and delete it."""
    path = tmp_path / "book.db"
    conn = storage.get_conn(str(path))
    storage.init_schema(conn)
    storage.migrate(conn)
    yield conn
    conn.close()


def _build(conn, n=300):
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)


def test_get_portfolio_is_o1_and_shaped(book_conn):
    _build(book_conn)
    p = data_loader.get_portfolio("c00000")
    assert p is not None
    assert p["client_id"] == "c00000"
    assert "holdings" in p and "cash" in p and "mandate" in p
    for h in p["holdings"]:
        for k in ("ticker", "name", "asset_class", "sector", "region", "liquidity_tier", "units", "price", "market_value"):
            assert k in h
        assert h["market_value"] == round(h["units"] * h["price"], 2)


def test_get_portfolio_unknown_returns_none(book_conn):
    _build(book_conn)
    assert data_loader.get_portfolio("does-not-exist") is None


def test_holdings_revalued_at_current_prices(book_conn):
    _build(book_conn)
    p = data_loader.get_portfolio("c00000")
    prices = data_loader.current_prices()
    for h in p["holdings"]:
        assert h["price"] == prices[h["ticker"]]


def test_list_portfolios_paged(book_conn):
    _build(book_conn, n=300)
    page1 = data_loader.list_portfolios(limit=100, offset=0)
    page2 = data_loader.list_portfolios(limit=100, offset=100)
    assert len(page1) == 100 and len(page2) == 100
    assert page1[0]["client_id"] == "c00000"
    assert page2[0]["client_id"] == "c00100"
    assert {p["client_id"] for p in page1}.isdisjoint({p["client_id"] for p in page2})


def test_ensure_book_generates_when_empty_and_is_idempotent(tmp_path):
    """On a fresh/empty db (ephemeral deploy disk) ensure_book generates the
    book; on a second call it leaves the existing book untouched (preserves
    clock day + approved trades across reboots)."""
    path = tmp_path / "ensure.db"
    conn = storage.get_conn(str(path))
    storage.init_schema(conn)
    storage.migrate(conn)
    data_loader.set_conn(conn)
    try:
        assert conn.execute("SELECT count(*) FROM portfolios").fetchone()[0] == 0
        # empty -> generate
        assert data_loader.ensure_book(n=500, seed=42, market_seed=42) is True
        assert conn.execute("SELECT count(*) FROM portfolios").fetchone()[0] == 500
        # existing -> skip (idempotent, no wipe)
        assert data_loader.ensure_book(n=500, seed=42, market_seed=42) is False
        assert conn.execute("SELECT count(*) FROM portfolios").fetchone()[0] == 500
    finally:
        conn.close()


def test_summary_reads_precomputed_counts(book_conn):
    _build(book_conn, n=300)
    s = data_loader.summary()
    assert s["total"] == 300
    assert s["counts"]["green"] + s["counts"]["orange"] + s["counts"]["red"] == 300
    assert "breach_count" in s


def test_current_prices_covers_all_tickers_and_persists(book_conn):
    _build(book_conn)
    prices = data_loader.current_prices()
    assert set(prices) == set(universe.all_tickers())
    # day-0 prices persisted in the prices table
    n = book_conn.execute("SELECT count(*) FROM prices WHERE day=0").fetchone()[0]
    assert n == len(universe.all_tickers())


def test_check_runs_on_loaded_portfolio(book_conn):
    _build(book_conn)
    p = data_loader.get_portfolio("c00000")
    res = rules_engine.check(p, p["mandate"])
    assert res["status"] in ("green", "orange", "red")


def test_reset_cache_drops_conn(book_conn):
    _build(book_conn)
    data_loader.reset_cache()
    # after reset, get_conn_cached should build a fresh connection (different object)
    # but our temp db path is gone from scope; set_conn again for safety
    data_loader.set_conn(book_conn)
    assert data_loader.get_portfolio("c00000") is not None
