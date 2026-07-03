import json
import sys
import time
from urllib import request, error

BASE = "https://aura-demo-rho.vercel.app/api"
CID = "c00003"  # orange status, has top_reason

def call(method, path, body=None, params=None):
    url = BASE + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += "?" + qs
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            status = resp.status
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            return status, parsed, ""
    except error.HTTPError as e:
        body = e.read().decode()
        return e.code, body, str(e)
    except Exception as e:
        return 0, str(e), str(e)


def has(obj, keys):
    if not isinstance(obj, dict):
        return False
    return all(k in obj for k in keys)


def check_schema(kind, data, keys):
    if not isinstance(data, dict):
        return False, f"expected dict, got {type(data).__name__}"
    missing = [k for k in keys if k not in data]
    if missing:
        return False, f"missing keys: {missing}"
    return True, ""


results = []

def record(endpoint, method, status, passed, note=""):
    results.append({
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "result": "PASS" if passed else "FAIL",
        "note": note,
    })

# Health
status, data, err = call("GET", "/health")
record("/health", "GET", status, has(data, ["status"]), err)

# Portfolios
status, data, err = call("GET", "/portfolios", params={"limit": "5"})
record("/portfolios", "GET", status, isinstance(data, list) and len(data) > 0 and has(data[0], ["client_id", "client_name", "status"]), err)

# Portfolio detail
status, data, err = call("GET", f"/portfolio/{CID}")
record(f"/portfolio/{CID}", "GET", status, has(data, ["client_id", "mandate", "holdings", "rules_result"]), err)

# Portfolio check
status, data, err = call("GET", f"/portfolio/{CID}/check")
record(f"/portfolio/{CID}/check", "GET", status, has(data, ["status", "breaches", "watches"]), err)

# Portfolios summary
status, data, err = call("GET", "/portfolios/summary")
record("/portfolios/summary", "GET", status, has(data, ["total", "counts", "breach_count"]), err)

# Portfolios summary AI
status, data, err = call("GET", "/portfolios/summary_ai")
note = ""
passed = False
if isinstance(data, dict):
    passed, note = check_schema("summary_ai", data, ["narrative", "aggregate"])
else:
    note = f"expected dict, got {type(data).__name__}: {str(data)[:100]}"
record("/portfolios/summary_ai", "GET", status, passed, note or err)

# Portfolios top
status, data, err = call("GET", "/portfolios/top", params={"limit": "10"})
passed = has(data, ["top", "rest"]) and isinstance(data.get("top"), list)
record("/portfolios/top", "GET", status, passed, err)

# Audit
status, data, err = call("GET", "/audit", params={"limit": "5"})
record("/audit", "GET", status, isinstance(data, list), err)

# Explain
status, data, err = call("POST", f"/portfolio/{CID}/explain", body={"metric": "equity"})
passed = has(data, ["narrative", "breach_summaries", "watch_summaries"]) if isinstance(data, dict) else False
record(f"/portfolio/{CID}/explain", "POST", status, passed, err)

# Verify
sample_trade = [{"isin": "US0378331005", "qty": 1, "price": 100}]
status, data, err = call("POST", f"/portfolio/{CID}/verify", body={"trades": sample_trade})
passed = has(data, ["status", "breaches", "watches"])
record(f"/portfolio/{CID}/verify", "POST", status, passed, err)

# Remediate
status, data, err = call("POST", f"/portfolio/{CID}/remediate")
passed = has(data, ["trades", "verification"])
record(f"/portfolio/{CID}/remediate", "POST", status, passed, err)

# Approve
status, data, err = call("POST", f"/portfolio/{CID}/approve", body={"trades": [], "rationale": "test"})
passed = has(data, ["ok", "prior_status", "new_status", "rules_result"])
record(f"/portfolio/{CID}/approve", "POST", status, passed, err)

# Reflect
status, data, err = call("POST", f"/portfolio/{CID}/reflect")
passed = has(data, ["suggestion"])
record(f"/portfolio/{CID}/reflect", "POST", status, passed, err)

# Preferences adopt
status, data, err = call("POST", "/preferences/adopt", body={"breach_type": "equity", "preference": "sell_first", "rationale": "test"})
passed = has(data, ["ok", "version"])
record("/preferences/adopt", "POST", status, passed, err)

# Admin reset
status, data, err = call("POST", "/admin/reset")
passed = has(data, ["ok", "cleared", "day", "summary"])
record("/admin/reset", "POST", status, passed, err)

# Hermes strategy
status, data, err = call("GET", "/hermes/strategy")
passed = has(data, ["variables", "version"])
record("/hermes/strategy", "GET", status, passed, err)

# Hermes reflect fallback
status, data, err = call("POST", "/hermes/reflect", body={"mode": "fallback"})
passed = has(data, ["variable", "to", "rationale", "mode"])
record("/hermes/reflect", "POST", status, passed, err)

# Hermes heartbeat
status, data, err = call("GET", "/hermes/heartbeat")
passed = has(data, ["counts", "queue_size", "miss_count"]) or has(data, ["stale", "message"])
record("/hermes/heartbeat", "GET", status, passed, err)

# Hermes history
status, data, err = call("GET", "/hermes/history")
record("/hermes/history", "GET", status, isinstance(data, list), err)

# Hermes queue
status, data, err = call("GET", "/hermes/queue", params={"limit": "5"})
passed = has(data, ["day", "rows", "next_cursor"])
record("/hermes/queue", "GET", status, passed, err)

# Hermes scan
status, data, err = call("POST", "/hermes/scan")
scan_job = None
if status in (200, 202) and isinstance(data, dict) and "job_id" in data:
    scan_job = data["job_id"]
    passed = True
else:
    passed = False
record("/hermes/scan", "POST", status, passed, err)

if scan_job:
    time.sleep(2)
    status, data, err = call("GET", f"/hermes/scan/{scan_job}")
    passed = has(data, ["job_id", "status"])
    record(f"/hermes/scan/{scan_job}", "GET", status, passed, err)

# Hermes adopt - use current strategy variable
status, strat, _ = call("GET", "/hermes/strategy")
if isinstance(strat, dict) and strat.get("variables"):
    var = list(strat["variables"].keys())[0]
    current = strat["variables"][var]
    status, data, err = call("POST", "/hermes/adopt", body={"variable": var, "to": current, "rationale": "test"})
    passed = has(data, ["ok", "version"]) or has(data, ["version"])
    record("/hermes/adopt", "POST", status, passed, err)
else:
    record("/hermes/adopt", "POST", 0, False, "could not read strategy variables")

# Hermes approve-batch
status, data, err = call("POST", "/hermes/approve-batch", body={"items": []})
passed = has(data, ["results", "applied", "failed"])
record("/hermes/approve-batch", "POST", status, passed, err)

# Hermes rollback - try version 1
status, data, err = call("POST", "/hermes/rollback", body={"version": 1})
passed = status == 200 and has(data, ["from_version", "to_version", "restored"])
if status == 404:
    record("/hermes/rollback", "POST", status, True, "no history v1 available (expected)")
else:
    record("/hermes/rollback", "POST", status, passed, err)

# Market clock
status, data, err = call("GET", "/market/clock")
passed = has(data, ["day", "running", "auto_interval_sec"])
record("/market/clock", "GET", status, passed, err)

# Market tick
status, data, err = call("POST", "/market/tick")
passed = has(data, ["day", "running", "auto_interval_sec"])
record("/market/tick", "POST", status, passed, err)

# Market advance
status, data, err = call("POST", "/market/advance", params={"days": "3"})
passed = has(data, ["day", "running", "auto_interval_sec"])
record("/market/advance?days=3", "POST", status, passed, err)

# Market auto-run
status, data, err = call("POST", "/market/auto-run", body={"on": False})
passed = has(data, ["day", "running"])
record("/market/auto-run", "POST", status, passed, err)

# Market auto-fix
status, data, err = call("POST", "/market/auto-fix", body={"on": False})
passed = has(data, ["auto_fix"])
record("/market/auto-fix", "POST", status, passed, err)

# Market prices
status, data, err = call("GET", "/market/prices")
passed = isinstance(data, dict) and len(data) > 0
record("/market/prices", "GET", status, passed, err)

# Market history
status, data, err = call("GET", "/market/history", params={"from_day": "0", "to_day": "5"})
passed = isinstance(data, list)
record("/market/history", "GET", status, passed, err)

# Market status
status, data, err = call("GET", "/market/status")
passed = has(data, ["clock", "summary"])
record("/market/status", "GET", status, passed, err)

# 404 check
status, data, err = call("GET", "/portfolio/doesnotexist")
record("/portfolio/doesnotexist", "GET", status, status == 404, err if status != 404 else "")

# Print table
print(f"\n{'Endpoint':<45} {'Method':<6} {'HTTP':<5} {'Result':<6} {'Notes'}")
print("-" * 100)
for r in results:
    print(f"{r['endpoint']:<45} {r['method']:<6} {r['status']:<5} {r['result']:<6} {r['note']}")

passes = sum(1 for r in results if r["result"] == "PASS")
fails = sum(1 for r in results if r["result"] == "FAIL")
print(f"\nTotal: {len(results)}  PASS: {passes}  FAIL: {fails}")

if fails > 0:
    sys.exit(1)
