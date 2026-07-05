import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status

from core.data_loader import get_conn_cached, list_portfolios
from core import effective
from core.effective import get_effective
from core.rules_engine import check

router = APIRouter()


def _admin_secret():
    secret = os.environ.get("ADMIN_SECRET", "")
    if not secret:
        # When no secret is configured, admin endpoints remain open for local demos.
        return None
    return secret


def require_admin(secret: str | None = Depends(_admin_secret), x_admin_secret: str | None = None):
    if secret is None:
        return True
    if x_admin_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Secret header",
        )
    return True


@router.post("/admin/reset")
def admin_reset(_admin_ok: bool = Depends(require_admin)):
    """Clear all post-trade state + scan artefacts and rewind the clock to 0.

    Portfolios, mandates, holdings, prices are NOT touched (the book itself is
    the deterministic seed). Re-writes a fresh day-0 status_history + book_summary.
    """
    conn = get_conn_cached()
    conn.executescript(
        "DELETE FROM state;"
        "DELETE FROM hermes_queue;"
        "DELETE FROM scan_jobs;"
        "DELETE FROM drift_events;"
        "DELETE FROM status_history;"
        "UPDATE clock SET day=0, running=0 WHERE id=1;"
    )
    counts = {"green": 0, "orange": 0, "red": 0}
    breach_total = 0
    hist = []
    for p in list_portfolios(limit=100000, offset=0):
        eff = get_effective(p["client_id"], seed=p)
        rr = check(eff, p["mandate"])
        counts[rr["status"]] = counts.get(rr["status"], 0) + 1
        breach_total += len(rr["breaches"])
        hist.append((0, p["client_id"], rr["status"], len(rr["breaches"]), len(rr["watches"])))
    conn.executemany(
        "INSERT OR REPLACE INTO status_history(day, client_id, status, breach_count, watch_count) "
        "VALUES (?,?,?,?,?)", hist,
    )
    conn.execute(
        "INSERT OR REPLACE INTO book_summary(id, day, total, green, orange, red, breach_count, updated_ts) "
        "VALUES (1, 0, ?, ?, ?, ?, ?, ?)",
        (len(hist), counts.get("green", 0), counts.get("orange", 0), counts.get("red", 0),
         breach_total, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    effective._state_has_rows = False
    return {"ok": True, "cleared": ["state", "hermes_queue", "scan_jobs",
            "drift_events", "status_history"], "day": 0,
            "summary": {"total": len(hist), "counts": counts, "breach_count": breach_total}}