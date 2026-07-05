# backend/tests/test_routers_market.py
import os, sqlite3, tempfile
from fastapi.testclient import TestClient
from core import storage, data_loader
from generators import generate_data


def _client():
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=300, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    from main import app
    return TestClient(app)


def test_clock_endpoint():
    c = _client()
    r = c.get("/market/clock")
    assert r.status_code == 200
    body = r.json()
    assert body["day"] == 0 and body["running"] == 0


def test_tick_endpoint_advances_day():
    c = _client()
    r = c.post("/market/tick")
    assert r.status_code == 200
    assert r.json()["day"] == 1
    assert c.get("/market/clock").json()["day"] == 1


def test_advance_endpoint():
    c = _client()
    r = c.post("/market/advance?days=3")
    assert r.status_code == 200
    assert r.json()["day"] == 3


def test_prices_endpoint_covers_tickers():
    c = _client()
    r = c.get("/market/prices")
    assert r.status_code == 200
    ps = r.json()
    assert "SPY" in ps and len(ps) >= 30


def test_auto_fix_toggle():
    c = _client()
    r = c.post("/market/auto-fix", json={"on": True})
    assert r.status_code == 200
    assert r.json()["auto_fix"] == 1
    assert c.get("/market/clock").json()["auto_fix"] == 1


def test_auto_run_toggle_sets_running():
    c = _client()
    r = c.post("/market/auto-run", json={"on": True, "interval_sec": 60})
    assert r.status_code == 200
    assert r.json()["running"] == 1
    # turn off immediately so no background tick fires in the test process
    c.post("/market/auto-run", json={"on": False})
    assert c.get("/market/clock").json()["running"] == 0


def test_history_endpoint_seeded_day0():
    # build_book seeds a day-0 status_history baseline (so /portfolios/top works
    # before any tick). history() passes that through; only post-tick days are
    # added by the monitor. Verify shape + that no future day appears.
    c = _client()
    r = c.get("/market/history?from_day=0&to_day=10")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert all({"day", "green", "orange", "red"} <= set(row) for row in rows)
    assert all(row["day"] == 0 for row in rows)  # no tick has run yet


def test_status_endpoint():
    c = _client()
    r = c.get("/market/status")
    assert r.status_code == 200
    body = r.json()
    assert "clock" in body and "summary" in body
    assert body["summary"]["total"] == 300


def test_start_autorun_loop_is_idempotent_and_creates_task():
    """start_autorun_loop() creates a single asyncio task and is idempotent:
    a second call while the first is alive returns None and does NOT spawn a
    second task. Does not actually run the loop (mocked) so the test is fast
    and non-hanging.
    """
    import asyncio
    import routers.market as rm

    # Reset module state from any prior test.
    if rm._autorun_task is not None and not rm._autorun_task.done():
        rm._autorun_task.cancel()
    rm._autorun_task = None

    async def _fake_loop():
        await asyncio.sleep(60)  # never completes during the test

    created = []

    async def _driver():
        # Patch _autorun_loop to our no-op so no real tick/sleep-loop runs.
        rm._autorun_loop = _fake_loop
        t1 = rm.start_autorun_loop()
        assert t1 is not None, "first call should create a task"
        created.append(t1)
        t2 = rm.start_autorun_loop()
        assert t2 is None, "second call while first alive must be idempotent (no new task)"
        assert rm._autorun_task is t1
        # stop_autorun_loop cancels and clears.
        rm.stop_autorun_loop()
        assert rm._autorun_task is None

    asyncio.run(_driver())
    # Cleanup any stray task.
    for t in created:
        if not t.done():
            t.cancel()


def test_startup_handler_launches_only_when_env_truthy(monkeypatch):
    """main.py's startup handler calls market.start_autorun_loop() only when
    MARKET_AUTO_RUN is truthy. Verifies the wiring without running the loop or
    generating the book (ensure_book is stubbed).
    """
    import main as mainmod
    import routers.market as rm
    import core.data_loader as dl

    # Ensure clean state.
    if rm._autorun_task is not None and not rm._autorun_task.done():
        rm._autorun_task.cancel()
    rm._autorun_task = None

    called = {"n": 0}

    def _fake_start():
        called["n"] += 1
        return None  # pretend we launched

    original = rm.start_autorun_loop
    rm.start_autorun_loop = _fake_start
    orig_ensure = dl.ensure_book
    dl.ensure_book = lambda *a, **k: False  # stub: don't touch the db in this wiring test
    try:
        # Env unset -> no call.
        monkeypatch.delenv("MARKET_AUTO_RUN", raising=False)
        import asyncio
        asyncio.run(mainmod._ensure_book_then_autorun())
        assert called["n"] == 0, "should NOT launch when env unset"

        # Env truthy -> one call.
        monkeypatch.setenv("MARKET_AUTO_RUN", "1")
        asyncio.run(mainmod._ensure_book_then_autorun())
        assert called["n"] == 1, "should launch once when env truthy"

        # Env false-y -> no further call.
        monkeypatch.setenv("MARKET_AUTO_RUN", "false")
        asyncio.run(mainmod._ensure_book_then_autorun())
        assert called["n"] == 1, "should NOT launch when env=false"

        # "on" also counts as truthy.
        monkeypatch.setenv("MARKET_AUTO_RUN", "on")
        asyncio.run(mainmod._ensure_book_then_autorun())
        assert called["n"] == 2, "should launch for 'on'"
    finally:
        rm.start_autorun_loop = original
        dl.ensure_book = orig_ensure


def test_apply_env_defaults_accepts_on(monkeypatch):
    """_apply_env_defaults must treat MARKET_AUTO_RUN=on the same as 1/true
    (aligned with main.py's startup handler truthy set). Otherwise the autorun
    loop spawns but its first iteration sees running=0 and breaks immediately.
    """
    import routers.market as rm

    captured = {}

    def _fake_set_running(value, interval_sec=None):
        captured["value"] = value
        captured["interval"] = interval_sec
        return {"running": 1 if value else 0}

    monkeypatch.setenv("MARKET_AUTO_RUN", "on")
    monkeypatch.setenv("MARKET_AUTO_INTERVAL_SEC", "7")
    original = rm.M.set_running
    rm.M.set_running = _fake_set_running
    try:
        rm._apply_env_defaults()
        assert captured.get("value") is True, "MARKET_AUTO_RUN=on should call set_running(True)"
        assert captured.get("interval") == 7
    finally:
        rm.M.set_running = original