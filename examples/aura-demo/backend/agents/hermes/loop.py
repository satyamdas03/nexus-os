"""Hermes scan loop — book-wide remediation proposer, gated by the rules engine.

34k: paged + async-friendly. scan_book_paged processes one batch at a time and
writes gate-passed rows to the hermes_queue table; scan_book runs the full
paged loop to completion (tests / small books); delta_scan re-scans only a
subset (newly-non-green from the drift monitor). The router (Task 7) wraps a
full scan in a BackgroundTasks job and polls scan_jobs.

Every queue row is gate-green by construction: proposer -> apply_trades ->
rules engine re-check; only rows with zero post-trade breaches survive.
Applying trades stays behind the human gate (approve-batch). Nothing here
touches mandate rules or rules_engine.py.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

from core import data_loader, effective, rules_engine
from core.drift_prediction import suggest_preventive_trades
from core.trades import apply_trades
from core.hermes_store import get_hermes_store, HermesStore, SQLiteHermesStore

from agents.hermes import HEARTBEAT_PATH
from agents.hermes.proposer import propose, strategy_vars
from agents.hermes.strategy_io import load_strategy
from agents.hermes import score as _score

_SEV_WEIGHT = {"red": 3, "orange": 2, "green": 0}
_store_override: Optional[HermesStore] = None

# Prevent-mode defaults if strategy.yaml lacks the Hermes 2.0 variables.
_DEFAULT_HORIZON = 14
_DEFAULT_RISK_THRESHOLD = 0.5


def _severity(rr: dict) -> str:
    return rr.get("status", "green")


def _active_store() -> HermesStore:
    """Return the test-injected store override, or the process-wide store.

    This lets `set_hermes_store` swaps in tests take effect without requiring
    every test to also call loop._set_store."""
    return _store_override if _store_override is not None else get_hermes_store()


def _set_store(store) -> None:
    """Test seam so hermes loop can run against a temp store."""
    global _store_override
    _store_override = store


def _confidence(post_rr: dict) -> float:
    # green after the proposal = high confidence; only watches left = 0.7
    if post_rr.get("breaches"):
        return 0.4
    if post_rr.get("watches"):
        return 0.7
    return 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _score_from_counts(counts: dict, queue: list[dict], total: int) -> dict:
    """Scaled book score from precomputed counts (no O(n) re-check).

    Replaces score.score_book for the paged path: the full book is never held in
    memory at once, so alignment_rate is derived from the green counter and
    breaches_remaining from the orange+red counters accumulated across pages.
    """
    green = counts.get("green", 0)
    alignment = green / total if total else 1.0
    acceptance = _score._acceptance_rate()
    # q["trades"] is a JSON string in DB rows; _trades_obj is the parsed list attached in-memory.
    def _trade_count(q: dict) -> int:
        obj = q.get("_trades_obj")
        if obj is not None:
            return len(obj)
        try:
            return len(json.loads(q.get("trades", "[]")))
        except Exception:
            return 0
    avg_trades = (sum(_trade_count(q) for q in queue) / len(queue)) if queue else 0.0
    breaches_remaining = counts.get("orange", 0) + counts.get("red", 0)
    composite = (0.5 * alignment + 0.3 * acceptance + 0.2 * (1.0 - min(1.0, avg_trades / 4.0))
                 - 0.1 * (breaches_remaining / max(1, total)))
    composite = max(0.0, min(1.0, composite))
    return {"alignment_rate": round(alignment, 3), "avg_trades_per_fix": round(avg_trades, 2),
            "acceptance_rate": round(acceptance, 3), "breaches_remaining": breaches_remaining,
            "composite": round(composite, 3)}


def _scan_ids(ids: list[str], strategy: dict, day, counts: dict,
              misses: list, write: bool) -> list[dict]:
    """Scan a list of client_ids: propose -> gate -> collect queue rows.

    Each NON-green portfolio is proposed (deterministic, no Claude), the trades
    are applied to the effective portfolio, and the rules engine re-checks the
    post-trade state (GATE). Only rows whose post-trade state has zero breaches
    survive (gate-green by construction). Misses (gate-fails) are counted and
    logged, never silently dropped. Survivors are ranked by fum x severity_weight.

    `write` persists gate-passed rows to the hermes_queue table.
    Returns the queue rows (in-memory extras attached for the page view).
    """
    conn = data_loader.get_conn_cached()
    prices = data_loader.current_prices()
    queue_rows: list[dict] = []
    for cid in ids:
        p = data_loader.get_portfolio(cid)
        if p is None:
            continue
        eff = effective.get_effective(cid, seed=p)
        if eff is None:
            continue
        rr = rules_engine.check(eff, p["mandate"])
        counts["scanned"] += 1
        status = _severity(rr)
        if status == "green":
            counts["green"] += 1
            continue
        proposal = propose(eff, rr, strategy)
        trades = proposal["trades"]
        if not trades:
            counts["skipped"] += 1
            continue
        # GATE: rules engine re-checks the post-trade effective portfolio.
        post = apply_trades(eff, trades, price_lookup=lambda t: prices.get(t))
        post_rr = rules_engine.check(post, p["mandate"])
        if post_rr["breaches"]:
            counts["missed"] += 1
            misses.append({"client_id": cid, "prior_status": status,
                           "remaining_breaches": len(post_rr["breaches"]),
                           "rationale": proposal["rationale"]})
            continue
        counts["remediated"] += 1
        rank = p["fum"] * _SEV_WEIGHT[status]
        queue_rows.append({
            "day": day, "client_id": cid, "prior_status": status,
            "post_status": _severity(post_rr), "fum": p["fum"],
            "trades": json.dumps(trades), "rationale": proposal["rationale"],
            "rank_score": rank, "created_ts": _now(),
            # in-memory extras for the returned page (not stored as columns):
            "client_name": p["client_name"], "confidence": _confidence(post_rr),
            "post_rules_result": post_rr, "_trades_obj": trades,
        })
    if write and queue_rows:
        _active_store().insert_queue_rows(queue_rows)
    # Highest fum x severity first (deterministic: rank_score is a float, sort is stable).
    queue_rows.sort(key=lambda q: q["rank_score"], reverse=True)
    return queue_rows


def scan_book_paged(cursor=0, batch=500, subset=None, day=None, clear=False) -> dict:
    """One paged scan batch.

    With `subset` (a client_id list): scans exactly those ids, ignores cursor,
    next_cursor is None (delta scan path). Without subset: scans `batch`
    portfolios in client_id order starting at `cursor`; next_cursor is
    cursor+batch when the page was full, else None (exhausted).

    `clear` wipes hermes_queue first (used by the start of a full scan).
    Returns {queue_page (top 50), next_cursor, counts, misses}.
    """
    if clear:
        _active_store().clear_queue(day=day, mode="remediate")
    if subset is not None:
        ids = list(subset)
        next_cursor = None
    else:
        conn = data_loader.get_conn_cached()
        ids = [r["client_id"] for r in conn.execute(
            "SELECT client_id FROM portfolios ORDER BY client_id LIMIT ? OFFSET ?",
            (batch, cursor))]
        next_cursor = cursor + batch if len(ids) == batch else None
    strategy = load_strategy()
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    misses: list = []
    page = _scan_ids(ids, strategy, day, counts, misses, write=True)
    return {"queue_page": page[:50], "next_cursor": next_cursor,
            "counts": counts, "misses": misses}


def scan_book() -> dict:
    """Full paged scan to completion. Clears the queue, writes heartbeat.

    Back-compat for tests + small books; routers use the async job (Task 7) for
    34k. Returns {heartbeat, queue (top 50), score}.
    """
    conn = data_loader.get_conn_cached()
    total = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    # Tag queue rows with the current clock day so /hermes/queue day-paging works.
    day = data_loader._clock()[0]
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    misses: list = []
    all_queue: list = []
    cursor = 0
    first = True
    while True:
        res = scan_book_paged(cursor=cursor, batch=500, day=day, clear=first)
        first = False
        for k in counts:
            counts[k] += res["counts"][k]
        misses.extend(res["misses"])
        all_queue.extend(res["queue_page"])
        if res["next_cursor"] is None:
            break
        cursor = res["next_cursor"]
    # Re-rank the accumulated top-50 pages by rank_score (pages were individually
    # ranked; merge sort by rank_score for a globally-ordered top 50).
    all_queue.sort(key=lambda q: q["rank_score"], reverse=True)
    score = _score_from_counts(counts, all_queue, total)
    heartbeat = {"counts": counts, "queue_size": counts["remediated"],
                 "miss_count": len(misses), "score": score, "top_misses": misses[:5]}
    _active_store().write_heartbeat(heartbeat)
    # Keep the file heartbeat as a fallback / dev convenience.
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(json.dumps(heartbeat, indent=2))
    return {"heartbeat": heartbeat, "queue": all_queue[:50], "score": score}


def delta_scan(client_ids: list[str], day: int) -> dict:
    """Fast subset scan for newly-non-green portfolios (drift monitor path).

    Appends `day`-tagged gate-passed rows to hermes_queue (does NOT clear).
    Spec §11 target < 5s. Returns {queue_page (top 50), counts, misses}.
    """
    strategy = load_strategy()
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    misses: list = []
    page = _scan_ids(list(client_ids), strategy, day, counts, misses, write=True)
    return {"queue_page": page[:50], "counts": counts, "misses": misses}


def _prevent_thresholds(strategy: dict) -> tuple[int, float]:
    """Read Hermes 2.0 proactive variables from strategy.yaml with safe defaults."""
    vars_ = strategy_vars(strategy)
    horizon = int(vars_.get("prevent_horizon_days", _DEFAULT_HORIZON))
    threshold = float(vars_.get("prevent_risk_threshold", _DEFAULT_RISK_THRESHOLD))
    return max(1, horizon), max(0.0, min(1.0, threshold))


def _scan_prevent_ids(ids: list[str], strategy: dict, day: int,
                      counts: dict, write: bool) -> list[dict]:
    """Scan green portfolios for predicted future breaches.

    Only considers portfolios that are green NOW. For each, project holdings to
    the strategy horizon, run the rules engine, and suggest preventive trades.
    Gating: trades must keep the current portfolio green AND reduce projected
    risk. Surviving rows are queued with mode='prevent'.
    """
    horizon, threshold = _prevent_thresholds(strategy)
    prices = data_loader.current_prices()
    queue_rows: list = []
    for cid in ids:
        p = data_loader.get_portfolio(cid)
        if p is None:
            continue
        eff = effective.get_effective(cid, seed=p)
        if eff is None:
            continue
        rr = rules_engine.check(eff, p["mandate"])
        counts["scanned"] += 1
        if rr["status"] != "green":
            continue
        counts["green"] += 1
        plan = suggest_preventive_trades(eff, p["mandate"], strategy,
                                          horizon_days=horizon)
        if not plan.get("gated") or not plan.get("trades"):
            continue
        if plan["risk_before"] < threshold:
            continue
        counts["remediated"] += 1  # queued preventive action
        rank = p["fum"] * 2  # prevent rows rank below reactive red rows
        prevent_meta = {
            "horizon_days": horizon,
            "risk_before": plan["risk_before"],
            "risk_after": plan["risk_after"],
            "projected_status": plan["projected_unhedged"]["status"],
        }
        queue_rows.append({
            "day": day, "client_id": cid, "prior_status": "green",
            "post_status": "green", "fum": p["fum"],
            "trades": json.dumps(plan["trades"]),
            "rationale": plan["rationale"],
            "rank_score": rank, "created_ts": _now(),
            "mode": "prevent",
            "prevent_meta": json.dumps(prevent_meta),
            # in-memory extras
            "client_name": p["client_name"], "confidence": 1.0 - plan["risk_after"],
            "post_rules_result": plan["current_after_hedge"],
            "_trades_obj": plan["trades"],
        })
    if write and queue_rows:
        _active_store().insert_queue_rows(queue_rows)
    queue_rows.sort(key=lambda q: q["rank_score"], reverse=True)
    return queue_rows


def prevent_scan_paged(cursor=0, batch=500, subset=None, day=None,
                       clear=False, strategy: Optional[dict] = None) -> dict:
    """One paged prevent-scan batch.

    Scans currently-green portfolios, projects them forward, and queues
    preventive trades that reduce projected breach risk.
    """
    if clear:
        _active_store().clear_queue(day=day, mode="prevent")
    if subset is not None:
        ids = list(subset)
        next_cursor = None
    else:
        conn = data_loader.get_conn_cached()
        ids = [r["client_id"] for r in conn.execute(
            "SELECT client_id FROM portfolios ORDER BY client_id LIMIT ? OFFSET ?",
            (batch, cursor))]
        next_cursor = cursor + batch if len(ids) == batch else None
    strategy = strategy if strategy is not None else load_strategy()
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    page = _scan_prevent_ids(ids, strategy, day, counts, write=True)
    return {"queue_page": page[:50], "next_cursor": next_cursor,
            "counts": counts}


def prevent_scan(strategy: Optional[dict] = None) -> dict:
    """Full paged prevent scan to completion. Clears prevent queue, returns top 50."""
    conn = data_loader.get_conn_cached()
    total = conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]
    day = data_loader._clock()[0]
    counts = {"scanned": 0, "green": 0, "remediated": 0, "missed": 0, "skipped": 0}
    all_queue: list = []
    cursor = 0
    first = True
    while True:
        res = prevent_scan_paged(cursor=cursor, batch=500, day=day, clear=first, strategy=strategy)
        first = False
        for k in counts:
            counts[k] += res["counts"][k]
        all_queue.extend(res["queue_page"])
        if res["next_cursor"] is None:
            break
        cursor = res["next_cursor"]
    all_queue.sort(key=lambda q: q["rank_score"], reverse=True)
    return {"queue": all_queue[:50], "counts": counts, "total": total}


def simulate_book(days: int = 100, mode: str = "reactive",
                  seed: Optional[int] = None,
                  strategy: Optional[dict] = None) -> dict:
    """Run a virtual 100-day simulation on a cloned book without mutating prod state.

    Modes:
      reactive — only the drift monitor runs; no Hermes intervention.
      prevent  — each day starts with a prevent scan + auto-approval of gated
                 preventive trades, then the market ticks.

    Returns a daily time series plus aggregate breach-incidence comparison.
    """
    import shutil
    import tempfile
    from core import storage, market as mkt
    from agents.hermes import monitor

    if mode not in ("reactive", "prevent"):
        raise ValueError("mode must be 'reactive' or 'prevent'")

    orig_conn = data_loader.get_conn_cached()
    orig_store = _active_store()

    # Clone current DB to a temp file so the simulation is isolated.
    src_path = storage.DB_PATH
    if orig_conn is not None:
        # Checkpoint WAL so the main db file is complete before copying.
        orig_conn.execute("PRAGMA wal_checkpoint(FULL)")
        row = orig_conn.execute("PRAGMA database_list").fetchone()
        if row:
            src_path = row["file"]
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copyfile(src_path, tmp_path)

    try:
        sim_conn = storage.get_conn(tmp_path)
        storage.init_schema(sim_conn)
        storage.migrate(sim_conn)
        data_loader.set_conn(sim_conn)
        sim_store = SQLiteHermesStore(sim_conn)
        sim_store.init()
        _set_store(sim_store)

        # Reset simulation state to day 0.
        sim_conn.execute("DELETE FROM state")
        sim_conn.execute("DELETE FROM hermes_queue")
        sim_conn.execute("DELETE FROM hermes_heartbeat")
        sim_conn.execute("DELETE FROM status_history")
        sim_conn.execute("DELETE FROM drift_events")
        sim_conn.execute("DELETE FROM scan_jobs")
        if seed is not None:
            sim_conn.execute("UPDATE clock SET day=0, running=0, auto_fix=0, seed=? WHERE id=1", (seed,))
        else:
            sim_conn.execute("UPDATE clock SET day=0, running=0, auto_fix=0 WHERE id=1")
        sim_conn.commit()

        # Seed day-0 status_history.
        monitor.run(0)

        series: list[dict] = []
        prevented_breaches = 0
        approved_prevent_trades = 0

        for d in range(1, days + 1):
            if mode == "prevent":
                # Proactive: scan green portfolios and auto-approve low-risk trades.
                res = prevent_scan(strategy=strategy)
                for row in res.get("queue", []):
                    trades = row.get("_trades_obj") or json.loads(row["trades"])
                    if _low_risk_trades(trades, sim_conn):
                        effective.record_trades(row["client_id"], trades,
                                                 rationale=row.get("rationale", "hermes prevent auto-approve"))
                        approved_prevent_trades += len(trades)
                        sim_store.mark_queue_processed([row["client_id"]], row["day"], _now(), mode="prevent")

            # Reactive step: market tick + monitor.
            before_counts = _book_counts(sim_conn)
            mkt.tick(run_monitor=True)
            after_counts = _book_counts(sim_conn)
            if mode == "prevent":
                # Crude prevention metric: green count increased or stayed higher.
                if after_counts["red"] + after_counts["orange"] < before_counts["red"] + before_counts["orange"]:
                    prevented_breaches += 1
            series.append({"day": d, "counts": after_counts,
                           "prevent_approved": approved_prevent_trades if mode == "prevent" else 0})

        # Aggregate breach incidence: sum of (red+orange) portfolios across days.
        reactive_incidence = sum(d["counts"]["red"] + d["counts"]["orange"] for d in series) if mode == "reactive" else None
        prevent_incidence = sum(d["counts"]["red"] + d["counts"]["orange"] for d in series) if mode == "prevent" else None

        return {
            "mode": mode,
            "days": days,
            "seed": seed,
            "series": series,
            "prevented_breaches": prevented_breaches,
            "approved_prevent_trades": approved_prevent_trades,
            "reactive_incidence": reactive_incidence,
            "prevent_incidence": prevent_incidence,
        }
    finally:
        data_loader.set_conn(orig_conn)
        _set_store(orig_store)
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _book_counts(conn) -> dict:
    row = conn.execute("SELECT green, orange, red FROM book_summary WHERE id=1").fetchone()
    if row:
        return {"green": row["green"], "orange": row["orange"], "red": row["red"]}
    return {"green": 0, "orange": 0, "red": 0}


def _low_risk_trades(trades: list[dict], conn) -> bool:
    """Placeholder policy: all gated preventive trades are considered low-risk
    for simulation purposes. A real policy would inspect weight deltas vs a band."""
    return True