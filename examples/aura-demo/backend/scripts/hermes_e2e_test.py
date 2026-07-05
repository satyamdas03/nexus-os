#!/usr/bin/env python3
"""End-to-end Hermes Mission Control smoke test against the deployed demo API."""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://aura-demo-rho.vercel.app/api"
TIMEOUT = 25  # seconds for any single request
SCAN_TIMEOUT = 600  # seconds to wait for the background scan
POLL_INTERVAL = 5


def now():
    return datetime.now(timezone.utc).isoformat()


def _req(method, path, payload=None, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        status = e.code
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {"raw": body}
    return status, parsed


def get(path, params=None):
    return _req("GET", path, params=params)


def post(path, payload=None):
    return _req("POST", path, payload=payload)


def fetch_all_queue(day=None):
    """Return every queue row by paging through /hermes/queue."""
    all_rows = []
    cursor = 0
    limit = 500
    while True:
        params = {"cursor": cursor, "limit": limit}
        if day is not None:
            params["day"] = day
        status, data = get("/hermes/queue", params=params)
        if status != 200:
            return status, data, all_rows
        rows = data.get("rows", [])
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        cursor = data.get("next_cursor", cursor + len(rows))
    return 200, {"rows": all_rows, "day": (data.get("day") if data else None)}, all_rows


def main():
    findings = {
        "started_at": now(),
        "base_url": BASE,
        "steps": [],
    }

    # 1. Heartbeat
    status, heartbeat = get("/hermes/heartbeat")
    findings["steps"].append({
        "step": 1,
        "endpoint": "GET /hermes/heartbeat",
        "status": status,
        "ok": status == 200,
        "response": heartbeat,
    })

    # 2. Trigger scan
    status, scan_resp = post("/hermes/scan")
    job_id = scan_resp.get("job_id") if status == 200 else None
    findings["steps"].append({
        "step": 2,
        "endpoint": "POST /hermes/scan",
        "status": status,
        "ok": status == 200 and bool(job_id),
        "job_id": job_id,
        "response": scan_resp,
    })

    if not job_id:
        findings["completed_at"] = now()
        print(json.dumps(findings, indent=2, default=str))
        sys.exit(1)

    # 3. Poll scan status + queue population
    scan_done = False
    queue_populated = False
    deadline = time.time() + SCAN_TIMEOUT
    last_queue_len = 0
    scan_status_resp = None
    while time.time() < deadline:
        s_status, s_data = get(f"/hermes/scan/{job_id}")
        scan_status_resp = s_data
        if s_status == 200 and s_data.get("status") in ("done", "failed"):
            scan_done = True
        # Also poll queue size to show progress
        q_status, q_meta, q_rows = fetch_all_queue()
        if q_status == 200 and len(q_rows) > 0:
            queue_populated = True
            last_queue_len = len(q_rows)
        if scan_done and queue_populated:
            break
        time.sleep(POLL_INTERVAL)

    findings["steps"].append({
        "step": 3,
        "endpoint": f"GET /hermes/scan/{job_id} + queue polling",
        "scan_status": scan_status_resp,
        "queue_len": last_queue_len,
        "ok": scan_done and queue_populated,
        "message": "scan completed and queue populated" if (scan_done and queue_populated)
                   else ("scan failed" if scan_status_resp and scan_status_resp.get("status") == "failed" else "timeout"),
    })

    # Refresh heartbeat after scan
    hb_status, heartbeat_after = get("/hermes/heartbeat")

    # Fetch full queue for the current day
    q_status, q_meta, all_rows = fetch_all_queue()
    findings["steps"].append({
        "step": 3.5,
        "endpoint": "GET /hermes/queue (paged)",
        "status": q_status,
        "ok": q_status == 200,
        "queue_meta": q_meta,
        "row_count": len(all_rows),
    })

    # 4. Approve one individual queue item
    one_approved = False
    one_result = None
    if all_rows:
        first = all_rows[0]
        trades = first.get("trades")
        if isinstance(trades, str):
            try:
                trades = json.loads(trades)
            except json.JSONDecodeError:
                trades = []
        payload = {
            "items": [{
                "client_id": first["client_id"],
                "trades": trades,
                "rationale": first.get("rationale", "hermes single approve"),
            }]
        }
        s, one_result = post("/hermes/approve-batch", payload)
        one_approved = s == 200 and one_result.get("applied", 0) >= 1
        findings["steps"].append({
            "step": 4,
            "endpoint": "POST /hermes/approve-batch (single)",
            "status": s,
            "ok": one_approved,
            "client_id": first["client_id"],
            "response": one_result,
        })
    else:
        findings["steps"].append({
            "step": 4,
            "endpoint": "POST /hermes/approve-batch (single)",
            "ok": False,
            "message": "no queue rows to approve",
        })

    # 5. Approve all verified (all queue rows) in batches to avoid huge request
    bulk_approved = False
    bulk_result = None
    batch_size = 100
    if all_rows:
        batches = [
            all_rows[i:i + batch_size]
            for i in range(0, len(all_rows), batch_size)
        ]
        total_applied = 0
        total_failed = 0
        per_batch = []
        for idx, batch in enumerate(batches):
            items = []
            for r in batch:
                trades = r.get("trades")
                if isinstance(trades, str):
                    try:
                        trades = json.loads(trades)
                    except json.JSONDecodeError:
                        trades = []
                items.append({
                    "client_id": r["client_id"],
                    "trades": trades,
                    "rationale": r.get("rationale", "hermes bulk approve"),
                })
            s, resp = post("/hermes/approve-batch", {"items": items})
            applied = resp.get("applied", 0) if s == 200 else 0
            failed = resp.get("failed", 0) if s == 200 else len(items)
            total_applied += applied
            total_failed += failed
            per_batch.append({"batch": idx + 1, "status": s, "applied": applied, "failed": failed})
            # Avoid hammering the server
            if idx < len(batches) - 1:
                time.sleep(0.5)
        bulk_approved = total_applied > 0 and total_failed == 0
        bulk_result = {
            "batches": len(batches),
            "total_applied": total_applied,
            "total_failed": total_failed,
            "per_batch": per_batch[:5],  # summarise first few
        }
        findings["steps"].append({
            "step": 5,
            "endpoint": "POST /hermes/approve-batch (bulk)",
            "status": 200,
            "ok": bulk_approved,
            "response": bulk_result,
        })
    else:
        findings["steps"].append({
            "step": 5,
            "endpoint": "POST /hermes/approve-batch (bulk)",
            "ok": False,
            "message": "no queue rows to bulk approve",
        })

    # 6. Queue refresh / processed counts
    q_status2, q_meta2, all_rows2 = fetch_all_queue()
    hb_status2, heartbeat_after2 = get("/hermes/heartbeat")
    findings["steps"].append({
        "step": 6,
        "endpoint": "GET /hermes/queue + /hermes/heartbeat after approvals",
        "queue_status": q_status2,
        "queue_len_before": len(all_rows),
        "queue_len_after": len(all_rows2),
        "heartbeat_before": heartbeat_after,
        "heartbeat_after": heartbeat_after2,
        # Queue rows are not deleted by approval; there is no processed counter in the queue endpoint.
        "ok": q_status2 == 200 and hb_status2 == 200,
        "note": "Hermes queue rows are a snapshot and are not removed by approval; processed counts are not exposed by this endpoint.",
    })

    # 7. Strategy + reflection
    s_status, strategy = get("/hermes/strategy")
    findings["steps"].append({
        "step": 7,
        "endpoint": "GET /hermes/strategy",
        "status": s_status,
        "ok": s_status == 200,
        "response": strategy,
    })
    r_status, reflect_resp = post("/hermes/reflect", {"mode": "hermes"})
    findings["steps"].append({
        "step": 7.5,
        "endpoint": "POST /hermes/reflect",
        "status": r_status,
        "ok": r_status == 200,
        "response": reflect_resp,
    })

    # 8. Audit logs
    a_status, audit = get("/audit", {"limit": 200})
    hermes_audit = [e for e in audit if isinstance(e, dict) and "hermes" in str(e.get("action_type", "")).lower()]
    approve_audit = [e for e in audit if isinstance(e, dict) and e.get("action_type") == "approve" and e.get("actor") == "hermes_bulk"]
    findings["steps"].append({
        "step": 8,
        "endpoint": "GET /audit",
        "status": a_status,
        "ok": a_status == 200,
        "audit_total_returned": len(audit),
        "hermes_action_records": len(hermes_audit),
        "approve_records_from_hermes_bulk": len(approve_audit),
        "last_few_hermes_records": hermes_audit[-5:] if hermes_audit else [],
    })

    findings["completed_at"] = now()
    findings["overall_ok"] = all(step.get("ok", False) for step in findings["steps"])
    print(json.dumps(findings, indent=2, default=str))


if __name__ == "__main__":
    main()
