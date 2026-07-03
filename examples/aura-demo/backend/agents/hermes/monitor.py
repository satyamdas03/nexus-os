"""Drift monitor — runs on each market tick.

Batched full-book re-check (500 portfolios/batch): for each effective
portfolio (revalued with live prices + applied trades), check() -> status +
breach/watch counts. Upsert status_history(day, client, ...) and the
precomputed book_summary. Detect transitions vs status_history(day-1) and log
drift_events. If clock.auto_fix is on and portfolios went green->orange/red or
orange->red (newly non-green), hand the set to hermes.delta_scan for
autonomous propose+gate+queue. Applying trades still stays behind the human gate.

Deterministic given the DB state + day. No clock mutation (reads clock.auto_fix;
does NOT advance day). stdlib only.
"""
from datetime import datetime, timezone

from core import data_loader, effective, rules_engine
from core import market as mkt

_BATCH = 1000


def run(day: int) -> dict:
    conn = data_loader.get_conn_cached()
    counts = {"green": 0, "orange": 0, "red": 0}
    breach_total = 0
    total = 0
    statuses: list[tuple[str, str]] = []  # (client_id, status) for drift detection

    # 1. Batched full-book re-check (500/batch) with per-batch executemany upsert.
    offset = 0
    while True:
        page = data_loader.list_portfolios(limit=_BATCH, offset=offset)
        if not page:
            break
        total += len(page)
        history_rows = []
        for p in page:
            eff = effective.get_effective(p["client_id"], seed=p)
            rr = rules_engine.check(eff, p["mandate"])
            status = rr["status"]
            bc = len(rr["breaches"])
            wc = len(rr["watches"])
            counts[status] += 1
            breach_total += bc
            history_rows.append((day, p["client_id"], status, bc, wc))
            statuses.append((p["client_id"], status))
        conn.executemany(
            "INSERT OR REPLACE INTO status_history "
            "(day, client_id, status, breach_count, watch_count) VALUES (?,?,?,?,?)",
            history_rows,
        )
        offset += _BATCH
    conn.commit()

    # 3. Recompute + upsert book_summary(id=1).
    conn.execute(
        "INSERT OR REPLACE INTO book_summary "
        "(id, day, total, green, orange, red, breach_count, updated_ts) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        (day, total, counts["green"], counts["orange"], counts["red"],
         breach_total, datetime.now(timezone.utc).isoformat()),
    )

    # 4. Drift events vs status_history(day-1). DELETE first so a re-run of the
    # same day is idempotent (PK day,client_id -> INSERT OR REPLACE).
    conn.execute("DELETE FROM drift_events WHERE day=?", (day,))
    prev = {
        r["client_id"]: r["status"]
        for r in conn.execute(
            "SELECT client_id, status FROM status_history WHERE day=?", (day - 1,)
        )
    }
    newly_non_green: list[str] = []
    drift_rows = []
    ts = datetime.now(timezone.utc).isoformat()
    for cid, status in statuses:
        ps = prev.get(cid)
        if ps is None or ps == status:
            continue
        drift_rows.append((day, cid, ps, status, ts))
        # newly non-green = green->orange/red or orange->red (status worsened)
        if ps in ("green", "orange") and status in ("orange", "red") and status > ps:
            newly_non_green.append(cid)
    if drift_rows:
        conn.executemany(
            "INSERT OR REPLACE INTO drift_events "
            "(day, client_id, from_status, to_status, ts) VALUES (?,?,?,?,?)",
            drift_rows,
        )
    conn.commit()

    # 5. auto-fix: hand newly-non-green set to Hermes delta scan (Task 6c).
    # Narrow guard: only the import is guarded (ImportError/AttributeError) so a
    # not-yet-wired delta_scan doesn't crash the monitor. Once delta_scan exists
    # the CALL is outside the guard — real runtime errors propagate, never
    # silently swallowed. prices + history still advance regardless.
    auto_fix = mkt.get_clock().get("auto_fix", 0)
    if auto_fix and newly_non_green:
        delta_scan = None
        try:
            from agents.hermes.loop import delta_scan as _ds
            delta_scan = _ds
        except (ImportError, AttributeError):
            delta_scan = None
        if delta_scan is not None:
            delta_scan(newly_non_green, day)

    return {
        "day": day,
        "counts": counts,
        "breach_count": breach_total,
        "drift_count": len(drift_rows),
        "newly_non_green": newly_non_green,
    }