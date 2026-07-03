"""End-to-end API audit of the deployed AURA demo.

Run:
    cd backend && .venv/Scripts/python.exe ../scripts/e2e_audit.py
"""
import json
import sys
import time
import urllib.request
from urllib.error import HTTPError
from pathlib import Path

BASE = "https://aura-demo-rho.vercel.app"
API = f"{BASE}/api"


def call(method, path, body=None, retries=1):
    url = f"{API}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.status, json.loads(resp.read().decode())
        except HTTPError as e:
            text = e.read().decode()
            try:
                return e.code, json.loads(text)
            except json.JSONDecodeError:
                return e.code, {"error": text}
        except Exception as e:
            if attempt == retries:
                return None, {"error": str(e)}
            time.sleep(2)


def html_fetch(path):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode(errors="ignore")
    except HTTPError as e:
        return e.code, e.read().decode(errors="ignore")
    except Exception as e:
        return None, str(e)


def check(name, status, evidence, ok_condition, findings):
    ok = ok_condition(status)
    findings.append({"name": name, "status": "PASS" if ok else "FAIL", "evidence": evidence, "severity": "critical" if not ok else "note"})
    return ok


def main():
    findings = []
    print("=== AURA Phase 2 E2E Audit ===")

    # 1. Health
    status, data = call("GET", "/health")
    print("health:", status, data)
    check("/api/health", status, str(data), lambda s: s == 200 and data.get("status") == "ok", findings)

    # 2. Summary
    status, data = call("GET", "/portfolios/summary")
    print("summary:", status, data)
    check("/api/portfolios/summary", status, str(data), lambda s: s == 200 and data.get("total", 0) >= 30000, findings)

    # 3. Reset demo state
    status, data = call("POST", "/admin/reset")
    print("reset:", status, data)
    check("/api/admin/reset", status, str(data), lambda s: s == 200 and data.get("ok"), findings)

    # 4. Top portfolios
    status, data = call("GET", "/portfolios/top?limit=50")
    print("top:", status, len(data.get("top", [])))
    check("/api/portfolios/top", status, f"{len(data.get('top', []))} rows", lambda s: s == 200 and len(data.get("top", [])) > 0, findings)

    # 5. Find a red/orange portfolio
    red_orange = [r for r in data.get("top", []) if r.get("status") in ("red", "orange")]
    if not red_orange:
        findings.append({"name": "find red/orange portfolio", "status": "FAIL", "evidence": "no breached/orange portfolios in top 50", "severity": "warning"})
        cid = data["top"][0]["client_id"] if data.get("top") else None
    else:
        cid = red_orange[0]["client_id"]
        findings.append({"name": "find red/orange portfolio", "status": "PASS", "evidence": f"using {cid} ({red_orange[0].get('status')})", "severity": "note"})
    print("selected portfolio:", cid)

    if cid:
        # 6. Portfolio detail
        status, detail = call("GET", f"/portfolio/{cid}")
        print("detail:", status, detail.get("client_name"), detail.get("rules_result", {}).get("status"))
        check("/api/portfolio/{id}", status, f"status={detail.get('rules_result',{}).get('status')}", lambda s: s == 200 and "holdings" in detail, findings)

        # 7. Explain full
        status, explain = call("POST", f"/portfolio/{cid}/explain")
        print("explain:", status, explain.get("narrative", "")[:120])
        check("/api/portfolio/{id}/explain (full)", status, explain.get("narrative", "")[:200], lambda s: s == 200 and len(explain.get("narrative", "")) > 50 and "[MOCK LLM]" not in explain.get("narrative", ""), findings)

        # 8. Explain per-metric
        rr = detail.get("rules_result", {})
        first_rule = None
        if rr.get("per_rule"):
            first_rule = rr["per_rule"][0].get("rule")
        if first_rule:
            status, mexplain = call("POST", f"/portfolio/{cid}/explain", {"metric": first_rule})
            print("metric explain:", status, mexplain.get("narrative", "")[:120])
            check("/api/portfolio/{id}/explain (metric)", status, mexplain.get("narrative", "")[:200], lambda s: s == 200 and len(mexplain.get("narrative", "")) > 20 and "[MOCK LLM]" not in mexplain.get("narrative", ""), findings)

        # 9. Remediate
        status, rem = call("POST", f"/portfolio/{cid}/remediate")
        print("remediate:", status, len(rem.get("trades", [])))
        trades = rem.get("trades", [])
        check("/api/portfolio/{id}/remediate", status, f"{len(trades)} trades, post_status={rem.get('verification',{}).get('status')}", lambda s: s == 200 and rem.get("verification", {}).get("status") in ("green", "orange"), findings)

        # 10. Verify trades
        if trades:
            status, vr = call("POST", f"/portfolio/{cid}/verify", {"trades": trades})
            print("verify:", status, vr.get("status"))
            check("/api/portfolio/{id}/verify", status, f"status={vr.get('status')}", lambda s: s == 200 and vr.get("status") in ("green", "orange"), findings)

            # 11. Approve
            status, app = call("POST", f"/portfolio/{cid}/approve", {"trades": trades, "rationale": "e2e audit approval"})
            print("approve:", status, app.get("new_status"))
            check("/api/portfolio/{id}/approve", status, f"prior={app.get('prior_status')} new={app.get('new_status')}", lambda s: s == 200 and app.get("new_status") in ("green", "orange"), findings)

            # 12. Confirm persists
            status, detail2 = call("GET", f"/portfolio/{cid}")
            new_status = detail2.get("rules_result", {}).get("status")
            print("post-approve detail:", status, new_status)
            check("post-approve status persists", status, f"status={new_status}", lambda s: s == 200 and new_status == app.get("new_status"), findings)

    # 13. Summary AI
    status, sdata = call("GET", "/portfolios/summary_ai")
    print("summary_ai:", status, sdata.get("narrative", "")[:120])
    check("/api/portfolios/summary_ai", status, sdata.get("narrative", "")[:200], lambda s: s == 200 and len(sdata.get("narrative", "")) > 30, findings)

    # 14. Audit trail
    status, audit = call("GET", "/audit")
    print("audit:", status, len(audit))
    check("/api/audit", status, f"{len(audit)} entries", lambda s: s == 200 and len(audit) > 0, findings)

    # 15. Hermes heartbeat
    status, hb = call("GET", "/hermes/heartbeat")
    print("hermes heartbeat:", status, hb)
    # It's ok if no scan yet
    findings.append({"name": "/api/hermes/heartbeat", "status": "PASS" if status == 200 else "FAIL", "evidence": str(hb), "severity": "warning"})

    # 16. Hermes scan
    status, scan = call("POST", "/hermes/scan")
    print("hermes scan:", status, scan)
    job_id = scan.get("job_id")
    check("/api/hermes/scan", status, f"job_id={job_id}", lambda s: s == 200 and bool(job_id), findings)

    # Poll queue for up to 90s
    queue_items = []
    if job_id:
        for _ in range(18):
            status, q = call("GET", "/hermes/queue?limit=100")
            queue_items = q.get("rows", [])
            if queue_items:
                break
            status, sj = call("GET", f"/hermes/scan/{job_id}")
            if sj.get("status") == "failed":
                findings.append({"name": "hermes scan completes", "status": "FAIL", "evidence": str(sj), "severity": "critical"})
                break
            time.sleep(5)
        print("queue items:", len(queue_items))
        check("/api/hermes/queue populates", status if queue_items else 500, f"{len(queue_items)} items", lambda s: len(queue_items) > 0, findings)

        # 17. Hermes approve-batch
        if queue_items:
            batch = [{"client_id": r["client_id"], "trades": json.loads(r["trades"]) if isinstance(r["trades"], str) else r["trades"], "rationale": "e2e bulk approve"} for r in queue_items[:5]]
            status, batch_res = call("POST", "/hermes/approve-batch", {"items": batch})
            print("approve-batch:", status, batch_res.get("applied"), batch_res.get("failed"))
            check("/api/hermes/approve-batch", status, f"applied={batch_res.get('applied')} failed={batch_res.get('failed')}", lambda s: s == 200 and batch_res.get("failed", 0) == 0, findings)

    # 18. HTML pages load
    for path in ["/", "/portfolio/c00011", "/portfolio/c00011/workbench", "/hermes"]:
        status, html = html_fetch(path)
        print(f"html {path}:", status, len(html))
        check(f"page loads: {path}", status, f"status={status}, len={len(html)}", lambda s, h=html: s == 200 and len(h) > 1000 and "</html>" in h.lower(), findings)

    # 19. Frontend build local (if running from repo)
    fe_root = Path(__file__).resolve().parents[1] / "frontend"
    if (fe_root / "package.json").exists():
        findings.append({"name": "frontend build", "status": "SKIP", "evidence": "run npm run build manually if needed", "severity": "note"})

    # 20. Backend tests local (if running from repo)
    be_root = Path(__file__).resolve().parents[1] / "backend"
    if (be_root / ".venv").exists():
        findings.append({"name": "backend tests", "status": "SKIP", "evidence": "run pytest manually if needed", "severity": "note"})

    # Write report
    out = Path("e2e_audit_report.json")
    out.write_text(json.dumps({"base": BASE, "findings": findings, "pass": sum(1 for f in findings if f["status"] == "PASS"), "fail": sum(1 for f in findings if f["status"] == "FAIL")}, indent=2))
    print(f"\n=== Report: {out.absolute()} ===")
    print(f"PASS: {sum(1 for f in findings if f['status'] == 'PASS')}")
    print(f"FAIL: {sum(1 for f in findings if f['status'] == 'FAIL')}")
    for f in findings:
        if f["status"] == "FAIL":
            print("FAIL:", f["name"], "-", f["evidence"])

    return findings


if __name__ == "__main__":
    main()
