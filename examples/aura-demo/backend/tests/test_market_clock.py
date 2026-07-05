# backend/tests/test_market_clock.py
import os, sqlite3, tempfile
from core import storage, data_loader, market
from generators import generate_data, universe


def _setup(n=300):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def test_get_clock_defaults():
    _setup()
    c = market.get_clock()
    assert c["day"] == 0 and c["running"] == 0 and c["auto_fix"] == 0
    assert c["seed"] == 42


def test_tick_advances_day_and_persists_prices():
    conn = _setup()
    market.tick(run_monitor=False)
    assert market.get_clock()["day"] == 1
    n = conn.execute("SELECT count(*) FROM prices WHERE day=1").fetchone()[0]
    assert n == len(universe.all_tickers())


def test_tick_revalues_on_next_read():
    _setup()
    p0 = data_loader.get_portfolio("c00000")
    market.tick(run_monitor=False)
    p1 = data_loader.get_portfolio("c00000")
    # at least one holding's price changes day 0 -> 1 (sigma > 0 for non-cash)
    changed = any(abs(h0["price"] - h1["price"]) > 1e-9
                  for h0, h1 in zip(p0["holdings"], p1["holdings"]) if h0["ticker"] == h1["ticker"])
    assert changed


def test_advance_loops_n_times():
    conn = _setup()
    market.advance(5, run_monitor=False)
    assert market.get_clock()["day"] == 5
    for d in range(1, 6):
        assert conn.execute("SELECT count(*) FROM prices WHERE day=?", (d,)).fetchone()[0] == len(universe.all_tickers())


def test_set_running_and_auto_fix_toggles():
    _setup()
    market.set_running(True, interval_sec=3)
    assert market.get_clock()["running"] == 1
    assert market.get_clock()["auto_interval_sec"] == 3
    market.set_auto_fix(True)
    assert market.get_clock()["auto_fix"] == 1
    market.set_running(False)
    assert market.get_clock()["running"] == 0


def test_history_returns_status_counts_per_day():
    conn = _setup()
    # generate_data seeds day-0 status_history during build_book; history
    # aggregates those counts per day. No monitor run yet -> only day 0 present.
    hist = market.history(0, 10)
    assert len(hist) == 1 and hist[0]["day"] == 0
    total = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    assert hist[0]["green"] + hist[0]["orange"] + hist[0]["red"] == total
    # days beyond seeded range return empty
    assert market.history(1, 10) == []