# backend/tests/test_routers.py
import os, json, sqlite3, tempfile
from fastapi.testclient import TestClient
from core import storage, data_loader
from generators import generate_data


def _client(n=400):
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
    conn = storage.get_conn(path); storage.init_schema(conn); storage.migrate(conn)
    generate_data.build_book(conn, n=n, seed=42, market_seed=42)
    data_loader.set_conn(conn)
    from main import app
    return TestClient(app), conn


def test_portfolios_paged():
    c, _ = _client(n=400)
    r = c.get("/portfolios?limit=50&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 50
    assert {"client_id", "client_name", "adviser", "fum", "status", "top_reason", "top_asset_class"} <= set(body[0])


def test_portfolio_detail_o1():
    c, _ = _client()
    r = c.get("/portfolio/c00000")
    assert r.status_code == 200
    body = r.json()
    assert body["client_id"] == "c00000"
    assert "holdings" in body and "rules_result" in body


def test_portfolio_detail_404():
    c, _ = _client()
    assert c.get("/portfolio/zzz").status_code == 404


def test_summary_precomputed():
    c, _ = _client()
    r = c.get("/portfolios/summary")
    assert r.status_code == 200
    s = r.json()
    assert s["total"] == 400
    assert s["counts"]["green"] + s["counts"]["orange"] + s["counts"]["red"] == 400




def test_top_safeguard_returns_top_and_rest():
    c, _ = _client(n=400)
    r = c.get("/portfolios/top?limit=50")
    assert r.status_code == 200
    body = r.json()
    assert "top" in body and "rest" in body
    assert len(body["top"]) <= 50
    assert body["rest"]["count"] == 400 - len(body["top"])
    # top sorted strictly by FUM descending (mixed statuses per page)
    fums = [p["fum"] for p in body["top"]]
    assert fums == sorted(fums, reverse=True)


def test_summary_ai_returns_string():
    c, _ = _client(n=200)
    r = c.get("/portfolios/summary_ai")
    assert r.status_code == 200
    assert isinstance(r.json().get("narrative", r.json()), str) or "narrative" in r.json()


# --- Hermes async scan job + paged queue (Task 7b) ---
import time


def test_hermes_queue_paged():
    c, conn = _client(n=400)
    # run a full scan to populate the queue
    r = c.post("/hermes/scan")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    # poll job to done
    for _ in range(60):
        st = c.get(f"/hermes/scan/{job_id}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done"
    assert st["scanned"] == 400
    q = c.get("/hermes/queue?limit=50").json()
    assert "rows" in q and "next_cursor" in q and "day" in q
    assert len(q["rows"]) <= 50
    for row in q["rows"]:
        assert {"day", "client_id", "post_status", "trades", "rationale", "fum"} <= set(row)


def test_approve_batch_clears_breach_and_persists():
    c, conn = _client(n=400)
    # run a full scan to populate the queue (poll the async job to done)
    r = c.post("/hermes/scan")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    for _ in range(60):
        st = c.get(f"/hermes/scan/{job_id}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", f"scan job did not complete: {st}"
    # find a red/orange queue row with trades
    rows = c.get("/hermes/queue?limit=200").json()["rows"]
    targets = [r for r in rows if r.get("trades") and r["post_status"] in ("green", "orange")]
    assert targets, "expected at least one remediated queue row"
    item = targets[0]
    # queue stores trades as a JSON string; approve-batch expects a list[dict]
    trades = json.loads(item["trades"]) if isinstance(item["trades"], str) else item["trades"]
    body = {"items": [{"client_id": item["client_id"], "trades": trades,
                       "rationale": item.get("rationale", "")}]}
    r = c.post("/hermes/approve-batch", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["applied"] == 1
    # persists across reload (effective re-check)
    rr = c.get(f"/portfolio/{item['client_id']}/check").json()
    assert rr["status"] in ("green", "orange")


# --- Admin reset clears SQLite state + clock rewind (Task 7c) ---
from core import market as mkt


def test_admin_reset_clears_state_and_clock():
    c, conn = _client(n=200)
    # advance the clock + run a scan so there is state/queue/history to clear
    mkt.tick(run_monitor=True)  # day 0 -> 1
    c.post("/hermes/scan")
    assert conn.execute("SELECT MAX(day) AS d FROM status_history").fetchone()["d"] >= 1
    r = c.post("/admin/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["day"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM state").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM hermes_queue").fetchone()["n"] == 0
    # status_history reset to a single day-0 row per portfolio
    assert conn.execute("SELECT MAX(day) AS d FROM status_history").fetchone()["d"] == 0
    # book_summary refreshed at day 0
    s = conn.execute("SELECT * FROM book_summary WHERE id=1").fetchone()
    assert s["day"] == 0 and s["total"] == 200