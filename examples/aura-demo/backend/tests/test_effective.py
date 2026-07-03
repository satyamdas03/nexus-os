# backend/tests/test_effective.py
import os, sqlite3, tempfile
from core import storage, data_loader, effective, rules_engine
from generators import generate_data


def _setup(n=300):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    return conn


def _first_holding_ticker(p):
    return p["holdings"][0]["ticker"]


def test_effective_equals_seed_when_no_state():
    _setup()
    p = data_loader.get_portfolio("c00000")
    eff = effective.effective_portfolio(p)
    assert eff["holdings"] == p["holdings"]


def test_record_trades_then_effective_applies_them():
    conn = _setup()
    p = data_loader.get_portfolio("c00000")
    tk = _first_holding_ticker(p)
    before = next(h for h in p["holdings"] if h["ticker"] == tk)["units"]
    effective.record_trades("c00000", [{"ticker": tk, "action": "sell", "units": before * 0.5, "value": 0}], rationale="trim")
    # state persisted
    rows = conn.execute("SELECT count(*) FROM state WHERE client_id='c00000'").fetchone()[0]
    assert rows == 1
    eff = effective.effective_portfolio(p)
    after = next(h for h in eff["holdings"] if h["ticker"] == tk)["units"]
    assert after < before


def test_effective_flips_red_to_green_when_fix_applied():
    """Find a red portfolio, apply a fix that the rules engine confirms green,
    and assert effective status flips and persists across a fresh load."""
    _setup(n=1500)
    conn = data_loader.get_conn_cached()
    # locate a red portfolio
    reds = []
    for cid in [r["client_id"] for r in conn.execute("SELECT client_id FROM portfolios LIMIT 1500")]:
        p = data_loader.get_portfolio(cid)
        if rules_engine.check(p, p["mandate"])["status"] == "red":
            reds.append(p)
        if len(reds) >= 10:
            break
    assert reds, "expected at least one red portfolio in the seed book"
    # Pick a red whose first breach has offending_holdings AND liquidating them
    # actually flips the portfolio out of red (robustness: some first-breaches
    # like min_cash have no offenders; liquidating others can trip min_liquid_pct).
    p = None
    for r in reds:
        b0 = rules_engine.check(r, r["mandate"])["breaches"][0]
        offenders = b0.get("offending_holdings") or []
        if not offenders:
            continue
        candidate_trades = []
        for tk in offenders:
            h = next((x for x in r["holdings"] if x["ticker"] == tk), None)
            if h:
                candidate_trades.append({"ticker": tk, "action": "sell", "units": h["units"], "value": 0})
        if not candidate_trades:
            continue
        from core.trades import apply_trades
        sim = apply_trades(r, candidate_trades, price_lookup=lambda t: data_loader.current_prices().get(t))
        if rules_engine.check(sim, r["mandate"])["status"] in ("green", "orange"):
            p = r
            break
    assert p is not None, "expected at least one red portfolio fixable by liquidating first-breach offenders"
    # fix = liquidate every offending holding from the first breach into cash
    res = rules_engine.check(p, p["mandate"])
    b = res["breaches"][0]
    trades = []
    for tk in b.get("offending_holdings", []):
        h = next((x for x in p["holdings"] if x["ticker"] == tk), None)
        if h:
            trades.append({"ticker": tk, "action": "sell", "units": h["units"], "value": 0})
    effective.record_trades(p["client_id"], trades, rationale="liquidate offenders")
    eff = effective.get_effective(p["client_id"])
    post = rules_engine.check(eff, p["mandate"])
    # liquidating offenders removes the breach; status should no longer be red
    # (may be orange via drift, but never red from that breach)
    assert post["status"] in ("green", "orange")
    # persists across a fresh load
    eff2 = effective.get_effective(p["client_id"])
    assert rules_engine.check(eff2, p["mandate"])["status"] == post["status"]


def test_reset_state_clears_and_returns_cleared_ids():
    _setup()
    p = data_loader.get_portfolio("c00000")
    effective.record_trades("c00000", [{"ticker": _first_holding_ticker(p), "action": "sell", "units": 1, "value": 0}], rationale="x")
    cleared = effective.reset_state()
    assert "c00000" in cleared
    eff = effective.effective_portfolio(p)
    assert eff["holdings"] == p["holdings"]  # back to seed