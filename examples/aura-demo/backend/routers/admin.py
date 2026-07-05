import io
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from core.data_loader import get_conn_cached, list_portfolios
from core import effective
from core.effective import get_effective
from core.rules_engine import check
from core.auth import require_admin as _require_jwt_admin

router = APIRouter()


def _admin_secret():
    secret = os.environ.get("ADMIN_SECRET", "")
    if not secret:
        # When no secret is configured, admin endpoints remain open for local demos.
        return None
    return secret


def require_legacy_admin(secret: str | None = Depends(_admin_secret), x_admin_secret: str | None = None):
    if secret is None:
        return True
    if x_admin_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Secret header",
        )
    return True


@router.post("/admin/reset")
def admin_reset(
    _legacy_ok: bool = Depends(require_legacy_admin),
    _jwt_admin = Depends(_require_jwt_admin),
):
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


# ── Backup / Restore ──────────────────────────────────────────────────────────

STRATEGY_PATH = Path("agents/hermes/strategy.yaml").resolve()
AUDIT_PATH = Path("data/audit.jsonl").resolve()


def _backup_members():
    from core import storage

    db_path = Path(storage.DB_PATH).resolve()
    return {
        db_path.name: db_path,
        STRATEGY_PATH.name: STRATEGY_PATH,
        AUDIT_PATH.name: AUDIT_PATH,
    }


def _close_db() -> bool:
    """Close the cached SQLite connection so the db file can be copied/overwritten.

    Returns True if a global _conn_override was active (test seam), so callers can
    re-pin a fresh connection after a restore.
    """
    from core import data_loader
    from core import storage

    had_override = data_loader._conn_override is not None
    if had_override:
        try:
            data_loader._conn_override.close()
        except Exception:
            pass
        data_loader.set_conn(None)

    local = getattr(data_loader, "_conn_local", None)
    conn = getattr(local, "conn", None)
    if conn is not None:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception:
            pass
        try:
            del local.conn
        except AttributeError:
            pass

    # Remove WAL sidecar files so a direct file copy/overwrite is clean.
    for suffix in ("-wal", "-shm"):
        wal = Path(storage.DB_PATH).with_suffix(Path(storage.DB_PATH).suffix + suffix)
        if wal.exists():
            try:
                wal.unlink()
            except OSError:
                pass
    return had_override


def _reopen_override():
    """Re-pin the global override connection after closing it for a file operation."""
    from core import data_loader, storage

    conn = storage.get_conn(storage.DB_PATH)
    storage.init_schema(conn)
    storage.migrate(conn)
    data_loader.set_conn(conn)


def _ensure_db_dir():
    members = _backup_members()
    members[next(iter(members))].parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)


@router.get("/admin/backup")
def admin_backup(_jwt_admin=Depends(_require_jwt_admin)):
    """Download a zip containing the SQLite book, Hermes strategy, and audit trail."""
    had_override = _close_db()
    members = _backup_members()
    _ensure_db_dir()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in members.items():
            if path.exists():
                zf.write(path, arcname=arcname)
    buf.seek(0)

    if had_override:
        _reopen_override()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=assure-backup-{ts}.zip"},
    )


@router.post("/admin/restore")
def admin_restore(
    file: UploadFile = File(...),
    _jwt_admin=Depends(_require_jwt_admin),
):
    """Restore state from a backup zip produced by /admin/backup. Admin-only.

    Overwrites data/portfolios.db, agents/hermes/strategy.yaml, and data/audit.jsonl.
    The current cached DB connection is closed first. Multi-worker deployments should
    restart the service after restore so every worker opens the new database.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="restore file must be a .zip")

    had_override = _close_db()
    _ensure_db_dir()

    try:
        contents = file.file.read()
        zf = zipfile.ZipFile(io.BytesIO(contents))
        members = _backup_members()
        names = set(zf.namelist())
        if not names.issuperset(members.keys()):
            raise HTTPException(
                status_code=400,
                detail=f"backup zip must contain: {', '.join(members.keys())}",
            )

        for arcname, path in members.items():
            with zf.open(arcname) as src, open(path, "wb") as dst:
                dst.write(src.read())

        # Re-open the new database so the next request does not fail.
        from core import data_loader
        from core import storage

        conn = get_conn_cached()
        conn.execute("SELECT 1")
        data_loader._prices_cache.clear()
        data_loader._mandate_cache.clear()

        # If tests are using the global connection override, re-pin to the
        # restored database so subsequent API calls see the restored state.
        if had_override:
            new_conn = storage.get_conn(storage.DB_PATH)
            storage.init_schema(new_conn)
            storage.migrate(new_conn)
            data_loader.set_conn(new_conn)
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail=f"bad zip file: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"restore failed: {e}")

    return {"ok": True, "restored": list(members.keys())}