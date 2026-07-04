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
from datetime import datetime, timezone
from typing import Optional

from core import data_loader, effective, rules_engine
from core.trades import apply_trades
from core.hermes_store import get_hermes_store, HermesStore

from agents.hermes import HEARTBEAT_PATH
from agents.hermes.proposer import propose
from agents.hermes.strategy_io import load_strategy
from agents.hermes import score as _score

_SEV_WEIGHT = {"red": 3, "orange": 2, "green": 0}
_store_override: Optional[HermesStore] = None


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
        _active_store().clear_queue(day=day)
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