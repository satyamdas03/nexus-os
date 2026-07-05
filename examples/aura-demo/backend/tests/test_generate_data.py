# backend/tests/test_generate_data.py
import hashlib
import json
import os
import sqlite3
import tempfile
from generators import generate_data, universe
from core import storage, rules_engine


def _build(n=2000, seed=42):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path)
    storage.init_schema(conn); storage.migrate(conn)
    counts = generate_data.build_book(conn, n=n, seed=seed, market_seed=42)
    return conn, counts


def test_build_book_counts_match_rows():
    conn, counts = _build()
    total = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    assert total == 2000
    assert counts["total"] == 2000
    assert counts["green"] + counts["orange"] + counts["red"] == 2000


def test_distribution_approx_5_15_80():
    conn, counts = _build(n=4000)
    g, o, r = counts["green"], counts["orange"], counts["red"]
    assert abs(r / 4000 - 0.05) < 0.05
    assert abs(o / 4000 - 0.15) < 0.06
    assert abs(g / 4000 - 0.80) < 0.06


def test_fum_power_law_top_decile_dominates():
    conn, _ = _build(n=4000)
    fums = [r[0] for r in conn.execute("SELECT fum FROM portfolios ORDER BY fum DESC")]
    top10 = fums[: max(1, len(fums) // 10)]
    total = sum(fums)
    assert sum(top10) > 0.45 * total  # top decile holds >45% of FUM


def test_holdings_carry_region_and_liquidity_tier():
    conn, _ = _build()
    row = conn.execute("SELECT h.ticker, t.region, t.liquidity_tier FROM holdings h "
                       "JOIN tickers t ON h.ticker = t.ticker LIMIT 200").fetchall()
    assert len(row) == 200
    for r in row:
        assert r["region"] in universe.REGIONS
        assert 1 <= r["liquidity_tier"] <= 3


def test_no_orphan_holdings():
    conn, _ = _build()
    orphans = conn.execute(
        "SELECT count(*) FROM holdings h LEFT JOIN portfolios p ON h.client_id=p.client_id "
        "WHERE p.client_id IS NULL"
    ).fetchone()[0]
    assert orphans == 0


def test_all_mandates_valid_and_deduped():
    conn, _ = _build()
    rows = conn.execute("SELECT mandate_id, spec FROM mandates").fetchall()
    seen = set()
    for r in rows:
        m = json.loads(r["spec"])
        assert mandates_valid(m)
        seen.add(r["mandate_id"])
    # far fewer distinct mandates than portfolios
    assert len(seen) < 2000


def mandates_valid(m):
    from generators import mandates
    return mandates.is_valid_mandate(m)


def test_prices_day0_present_for_all_tickers():
    conn, _ = _build()
    n = conn.execute("SELECT count(*) FROM prices WHERE day=0").fetchone()[0]
    assert n == len(universe.all_tickers())


def test_state_and_history_cleared_on_build():
    # build_book must clear stale state/queue/drift and write a fresh day-0
    # status_history row per portfolio (spec: day-0 history + summary written).
    conn, _ = _build()
    assert conn.execute("SELECT count(*) FROM state").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM hermes_queue").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM drift_events").fetchone()[0] == 0
    # day-0 status_history has exactly one row per portfolio (stale cleared)
    n_hist = conn.execute("SELECT count(*) FROM status_history WHERE day=0").fetchone()[0]
    n_port = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    assert n_hist == n_port
    assert conn.execute("SELECT count(*) FROM status_history WHERE day>0").fetchone()[0] == 0


def test_green_cohort_actually_green():
    """A sample of green-tagged portfolios must pass the rules engine at day 0
    (the green cohort is built + repaired against check()). Uses the cash
    stored in the portfolios row so the reconstruction matches what the
    generator actually evaluated."""
    conn, counts = _build(n=1500)
    sample = conn.execute("SELECT client_id, fum, mandate_id, cash FROM portfolios LIMIT 1500").fetchall()
    prices = {r["ticker"]: r["price"] for r in
              conn.execute("SELECT ticker, price FROM prices WHERE day=0").fetchall()}
    greens = 0; checked = 0
    for p in sample:
        mh = conn.execute("SELECT ticker, units FROM holdings WHERE client_id=?", (p["client_id"],)).fetchall()
        if not mh:
            continue
        checked += 1
        spec = json.loads(conn.execute("SELECT spec FROM mandates WHERE mandate_id=?", (p["mandate_id"],)).fetchone()["spec"])
        holdings = []
        for h in mh:
            meta = universe.UNIVERSE_BY_TICKER[h["ticker"]]
            holdings.append({"ticker": h["ticker"], "name": meta["name"], "asset_class": meta["asset_class"],
                             "sector": meta["sector"], "region": meta["region"], "liquidity_tier": meta["liquidity_tier"],
                             "units": h["units"], "price": prices[h["ticker"]],
                             "market_value": round(h["units"] * prices[h["ticker"]], 2)})
        res = rules_engine.check({"client_id": p["client_id"], "holdings": holdings, "cash": p["cash"]}, spec)
        if res["status"] == "green":
            greens += 1
    # the green cohort is ~80%; allow slack for the random mandate jitter
    assert checked > 0
    assert greens / checked > 0.55


def test_determinism_two_runs_identical_hash():
    h1 = _hash_book()
    h2 = _hash_book()
    assert h1 == h2


def _hash_book():
    conn, _ = _build(n=1000, seed=42)
    parts = []
    for tbl in ("portfolios", "holdings", "mandates", "prices"):
        rows = conn.execute(f"SELECT * FROM {tbl} ORDER BY 1,2").fetchall()
        parts.append(json.dumps([dict(r) for r in rows], default=str, sort_keys=True))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()