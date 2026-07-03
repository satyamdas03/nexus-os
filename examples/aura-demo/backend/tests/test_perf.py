# backend/tests/test_perf.py
import os, sqlite3, tempfile, time
import pytest
from core import storage, data_loader, market
from generators import generate_data


@pytest.fixture(scope="module")
def big_book():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=34000, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    market.set_auto_fix(False)  # benchmark re-check only
    yield conn
    conn.close(); os.remove(path)


def test_generation_under_60s(big_book):
    # build_book already ran in the fixture; re-time a fresh build to assert
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    t0 = time.perf_counter()
    generate_data.build_book(conn, n=34000, seed=42, market_seed=42)
    dt = time.perf_counter() - t0
    conn.close(); os.remove(path)
    assert dt < 60.0, f"generation took {dt:.1f}s (>60s)"


def test_tick_monitor_under_10s(big_book):
    t0 = time.perf_counter()
    market.tick(run_monitor=True)
    dt = time.perf_counter() - t0
    assert dt < 10.0, f"tick+monitor took {dt:.1f}s (>10s)"


def test_delta_scan_under_5s(big_book):
    from agents.hermes.loop import delta_scan
    # advance a few days to create drift, then delta-scan the newly-non-green
    market.advance(5, run_monitor=True)
    conn = data_loader.get_conn_cached()
    rows = conn.execute(
        "SELECT client_id FROM status_history WHERE day=? AND status!='green' "
        "AND client_id IN (SELECT client_id FROM status_history WHERE day=? AND status='green')",
        (market.get_clock()["day"], market.get_clock()["day"] - 1),
    ).fetchall()
    ids = [r["client_id"] for r in rows][:500]
    t0 = time.perf_counter()
    if ids:
        delta_scan(ids, market.get_clock()["day"])
    dt = time.perf_counter() - t0
    assert dt < 5.0, f"delta scan took {dt:.1f}s (>5s)"


def test_portfolio_lookup_under_100ms(big_book):
    t0 = time.perf_counter()
    p = data_loader.get_portfolio("c00000")
    dt = time.perf_counter() - t0
    assert p is not None
    assert dt < 0.100, f"get_portfolio took {dt*1000:.0f}ms (>100ms)"


def test_summary_under_50ms(big_book):
    t0 = time.perf_counter()
    s = data_loader.summary()
    dt = time.perf_counter() - t0
    assert s["total"] == 34000
    assert dt < 0.050, f"summary took {dt*1000:.0f}ms (>50ms)"


def test_paged_portfolios_under_200ms(big_book):
    t0 = time.perf_counter()
    page = data_loader.list_portfolios(limit=500, offset=0)
    dt = time.perf_counter() - t0
    assert len(page) == 500
    assert dt < 0.200, f"paged list took {dt*1000:.0f}ms (>200ms)"