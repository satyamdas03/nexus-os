#!/usr/bin/env python3
"""Hermes approval + audit end-to-end test (assumes a populated queue)."""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://aura-demo-rho.vercel.app/api"
TIMEOUT = 25


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


def fetch_all_queue():
    all_rows = []
    cursor = 0
    limit = 500
    day = None
    while True:
        params = {"cursor": cursor, "limit": limit}
        if day is not None:
            params["day"] = day
        status, data = get("/hermes/queue", params=params)
        if status != 200:
            return status, data, []
        rows = data.get("rows", [])
        if not rows:
            break
        day = data.get("day", day)
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        cursor = data.get("next_cursor", cursor + len(rows))
    return 200, {"rows": all_rows, "day": day}, all_rows


def main():
    results = {"started_at": now(), "base_url": BASE, "steps": []}

    # Pre-state
    hb_status, heartbeat_before = get("/hermes/heartbeat")
    q_status, q_meta, rows = fetch_all_queue()
    results["steps"].append({
        "step": "pre",
        "endpoint": "GET /hermes/heartbeat + /hermes/queue",
        "heartbeat_status": hb_status,
        "queue_status": q_status,
        "queue_len": len(rows),
        "heartbeat": heartbeat_before,
    })

    # Approve one
    one_result = None
    if rows:
        first = rows[0]
        trades = first.get("trades")
        if isinstance(trades, str):
            trades = json.loads(trades)
        one_payload = {
            "items": [{
                "client_id": first["client_id"],
                "trades": trades,
                "rationale": first.get("rationale", "hermes single approve"),
            }]
        }
        s, one_result = post("/hermes/approve-batch", one_payload)
        results["steps"].append({
            "step": 4,
            "endpoint": "POST /hermes/approve-batch (single)",
            "status": s,
            "ok": s == 200 and one_result.get("applied", 0) >= 1,
            "client_id": first["client_id"],
            "response": one_result,
        })
    else:
        results["steps"].append({"step": 4, "ok": False, "message": "no queue rows"})

    # Bulk approve all in batches of 25 to avoid huge request bodies
    bulk_result = None
    if rows:
        batch_size = 25
        batches = [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]
        total_applied = 0
        total_failed = 0
        per_batch = []
        for idx, batch in enumerate(batches):
            items = []
            for r in batch:
                trades = r.get("trades")
                if isinstance(trades, str):
                    trades = json.loads(trades)
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
            per_batch.append({"batch": idx + 1, "status": s, "sent": len(items), "applied": applied, "failed": failed})
            if idx < len(batches) - 1:
                time.sleep(0.3)
        bulk_result = {
            "batches": len(batches),
            "total_applied": total_applied,
            "total_failed": total_failed,
            "per_batch": per_batch,
        }
        results["steps"].append({
            "step": 5,
            "endpoint": "POST /hermes/approve-batch (bulk)",
            "ok": total_applied == len(rows) and total_failed == 0,
            "response": bulk_result,
        })
    else:
        results["steps"].append({"step": 5, "ok": False, "message": "no queue rows"})

    # Post-state
    hb_status2, heartbeat_after = get("/hermes/heartbeat")
    q_status2, q_meta2, rows_after = fetch_all_queue()
    results["steps"].append({
        "step": 6,
        "endpoint": "GET /hermes/heartbeat + /hermes/queue after approvals",
        "queue_len_before": len(rows),
        "queue_len_after": len(rows_after),
        "heartbeat_before": heartbeat_before,
        "heartbeat_after": heartbeat_after,
        "note": "queue rows are not removed by approval; processed counters are not exposed",
    })

    # Audit
    a_status, audit = get("/audit", {"limit": 200})
    approve_records = [e for e in audit if isinstance(e, dict) and e.get("action_type") == "approve" and e.get("actor") == "hermes_bulk"]
    results["steps"].append({
        "step": 8,
        "endpoint": "GET /audit",
        "status": a_status,
        "ok": a_status == 200 and len(approve_records) >= (one_result.get("applied", 0) if one_result else 0) + (bulk_result.get("total_applied", 0) if bulk_result else 0),
        "audit_total_returned": len(audit),
        "approve_records_from_hermes_bulk": len(approve_records),
        "last_few_approve_records": approve_records[-5:] if approve_records else [],
    })

    results["completed_at"] = now()
    results["overall_ok"] = all(step.get("ok", True) for step in results["steps"] if "ok" in step)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
