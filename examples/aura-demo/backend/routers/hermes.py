"""Hermes Mission Control API.

Endpoints:
  POST /hermes/scan       — scan the effective book; gate proposals via rules engine.
  GET  /hermes/strategy   — current strategy.yaml (variables + version).
  POST /hermes/reflect    — propose ONE strategy change (fallback | hermes). No write.
  POST /hermes/adopt      — human-gated: apply a proposed change, bump version, archive.
  GET  /hermes/heartbeat  — last scan summary + score.
  GET  /hermes/history    — archived strategy snapshots.

Nothing here writes mandate rules or rules_engine.py. Adopt is the sole strategy
writer and strategy_io refuses anything outside strategy.yaml/history/.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from core import data_loader
from core.data_loader import get_portfolio, get_conn_cached
from core.effective import effective_portfolio, record_trades, get_effective
from core.rules_engine import check
from core.hermes_store import get_hermes_store, HERMES_STORE_URL
from agents.hermes import HEARTBEAT_PATH, HISTORY_DIR
from agents.hermes.loop import scan_book
from agents.hermes.reflect import reflect
from agents.hermes.strategy_io import load_strategy, adopt_proposal, restore_version
from routers.audit import append_audit

_hstore = get_hermes_store()

router = APIRouter()


class ReflectBody(BaseModel):
    mode: str = "fallback"  # "fallback" | "hermes"


class AdoptBody(BaseModel):
    variable: str
    to: object
    rationale: str


class BatchItem(BaseModel):
    client_id: str
    trades: list[dict] = []
    rationale: str = ""


class ApproveBatchBody(BaseModel):
    items: list[BatchItem] = []


class RollbackBody(BaseModel):
    version: int


def _log(client_id: str, action_type: str, actor: str, tier: str, payload: dict, rationale: str = ""):
    """Same shape as routers.actions._log — single audit record per event."""
    append_audit({"timestamp": datetime.now(timezone.utc).isoformat(),
                  "client_id": client_id, "action_type": action_type, "actor": actor,
                  "tier": tier, "payload": payload, "rationale": rationale,
                  "rules_check_result": None, "version": "0.1.0"})


@router.post("/hermes/scan")
def hermes_scan(background: BackgroundTasks):
    """Launch an async full-book scan. Returns a job_id immediately; the
    scan writes a scan_jobs row and the paged hermes_queue as it goes.
    Human-applies gate still holds — this only proposes + gates + queues."""
    job_id = uuid.uuid4().hex
    _hstore.insert_scan_job(job_id, "full", "running", datetime.now(timezone.utc).isoformat())
    background.add_task(_run_scan_job, job_id)
    return {"job_id": job_id}


def _run_scan_job(job_id: str):
    try:
        result = scan_book()  # writes heartbeat + paged queue + counts
        counts = result.get("heartbeat", {}).get("counts", {})
        _hstore.update_scan_job_done(
            job_id, datetime.now(timezone.utc).isoformat(),
            counts.get("scanned", 0), counts.get("remediated", 0), counts.get("missed", 0),
        )
    except Exception as e:  # noqa: BLE001 — record failure on the job row
        _hstore.update_scan_job_done(
            job_id, datetime.now(timezone.utc).isoformat(), 0, 0, 0, error=str(e),
        )


@router.get("/hermes/scan/{job_id}")
def hermes_scan_status(job_id: str):
    row = _hstore.get_scan_job(job_id)
    if not row:
        raise HTTPException(404, "scan job not found")
    return row


@router.get("/hermes/strategy")
def hermes_strategy():
    return load_strategy()


@router.post("/hermes/reflect")
def hermes_reflect(body: ReflectBody):
    if body.mode not in ("fallback", "hermes"):
        raise HTTPException(400, "mode must be 'fallback' or 'hermes'")
    return reflect(mode=body.mode)


@router.post("/hermes/adopt")
def hermes_adopt(body: AdoptBody):
    """Human gate. Applies one strategy change, bumps version, archives, audits.
    Never self-adopts — a human must call this."""
    try:
        result = adopt_proposal(body.variable, body.to, body.rationale)
    except KeyError as e:
        raise HTTPException(400, str(e))
    append_audit({"timestamp": datetime.now(timezone.utc).isoformat(),
                  "action_type": "hermes_adopt", "actor": "human",
                  "payload": result, "rationale": body.rationale})
    return result


@router.get("/hermes/heartbeat")
def hermes_heartbeat():
    hb = _hstore.read_heartbeat()
    if hb is None:
        return {"counts": None, "queue_size": 0, "miss_count": 0, "score": None,
                "stale": True, "message": "no scan run yet — POST /hermes/scan"}
    return hb


@router.get("/hermes/history")
def hermes_history():
    if not HISTORY_DIR.exists():
        return []
    out = []
    for f in sorted(HISTORY_DIR.glob("v*.json")):
        try:
            out.append({"file": f.name, "snapshot": json.loads(f.read_text())})
        except json.JSONDecodeError:
            continue
    return out


@router.get("/hermes/queue")
def hermes_queue(day: int | None = None, cursor: int = 0,
                 limit: int = Query(50, ge=1, le=500)):
    """Paged Hermes remediation queue. day defaults to the latest queue day.
    cursor = rowid offset. Returns rows + next_cursor."""
    if day is None:
        d = _hstore.get_latest_queue_day()
        day = d if d is not None else 0
    rows = _hstore.get_queue(day, cursor, limit)
    return {"day": day, "rows": rows, "next_cursor": cursor + len(rows)}


@router.post("/hermes/approve-batch")
def hermes_approve_batch(body: ApproveBatchBody):
    """Bulk-apply human-approved trades for multiple Hermes queue items.

    For each item: record trades against the shadow state, recompute the
    effective portfolio, re-check via the rules engine, and append an audit
    record (actor "hermes_bulk", tier "deterministic"). The rules engine — not
    this endpoint — decides the new status. Reuses core.effective.record_trades
    and core.rules_engine.check; does not duplicate apply logic.

    Returns {results: [...], applied: N, failed: M}.
    """
    results = []
    applied = 0
    failed = 0
    for item in body.items:
        p = get_portfolio(item.client_id)
        if not p:
            failed += 1
            results.append({"client_id": item.client_id, "error": "portfolio not found"})
            continue
        try:
            eff = effective_portfolio(p)
            prior = check(eff, p["mandate"])
            record_trades(item.client_id, item.trades,
                          rationale=item.rationale or "hermes bulk approve")
            new_eff = get_effective(item.client_id, seed=p)
            new_rr = check(new_eff, p["mandate"])
            _log(item.client_id, "approve", "hermes_bulk", "deterministic",
                 {"trades": item.trades,
                  "prior_status": prior["status"],
                  "new_status": new_rr["status"],
                  "rationale": item.rationale},
                 item.rationale or "hermes bulk approve")
            results.append({"client_id": item.client_id,
                            "prior_status": prior["status"],
                            "new_status": new_rr["status"],
                            "rules_result": new_rr})
            applied += 1
        except Exception as e:  # noqa: BLE001 — surface per-item failures, keep going
            failed += 1
            results.append({"client_id": item.client_id, "error": str(e)})
    # Mark approved rows as processed so they vanish from the active queue.
    if applied:
        day = data_loader._clock()[0]
        _hstore.mark_queue_processed(
            [item.client_id for item in body.items],
            day,
            datetime.now(timezone.utc).isoformat(),
        )
    return {"results": results, "applied": applied, "failed": failed}


@router.post("/hermes/rollback")
def hermes_rollback(body: RollbackBody):
    """Human-gated strategy rollback. Restores the snapshot at
    history/v{version}.json. Before overwriting, archives the CURRENT strategy
    so the rollback is itself reversible. Bumps version forward. Appends an
    audit record (actor "human", tier "deterministic", what "hermes_rollback").

    Returns the restored strategy + from/to version metadata.
    """
    try:
        result = restore_version(body.version)
    except FileNotFoundError:
        raise HTTPException(404, f"no archived strategy for version {body.version}")
    _log("global", "hermes_rollback", "human", "deterministic",
         {"from_version": result["from_version"], "to_version": result["to_version"],
          "restored_version": body.version},
         f"rollback to v{body.version}")
    return result