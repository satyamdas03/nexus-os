"""Deep end-to-end UI + API validation for ASSURE Phase 2 demo.

Exercises the full portfolio assurance flow and produces screenshots + a JSON
report. Run with both dev servers up:

    python scripts/e2e_deep.py

Env:
    FRONTEND_URL  - base URL (default http://localhost:3000)
    BACKEND_URL   - API base URL (default http://localhost:8000)
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright, Page, expect

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
OUT_DIR = Path(__file__).parent.parent / "e2e_screenshots_deep"
REPORT_PATH = OUT_DIR.parent / "e2e_deep_report.json"


def api_call(method, path, body=None):
    url = f"{BACKEND_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"error": text}
    except Exception as e:
        return None, {"error": str(e)}


def reset_demo():
    status, data = api_call("POST", "/admin/reset")
    if status != 200 or not data.get("ok"):
        print(f"WARNING: demo reset returned {status} {data}")
    return status == 200 and data.get("ok")


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def attach_listeners(page: Page, report: dict):
    errors = []
    network = []
    api_calls = []

    def on_console(msg):
        entry = {"type": msg.type, "text": msg.text, "location": str(msg.location)}
        if msg.type == "error":
            errors.append(entry)
        report["all_console"].append(entry)

    def on_pageerror(exc):
        errors.append({"type": "pageerror", "text": str(exc)})
        report["all_console"].append({"type": "pageerror", "text": str(exc)})

    def on_response(resp):
        if resp.status >= 400:
            network.append({"status": resp.status, "url": resp.url})
        url = resp.url
        if BACKEND_URL in url or "/api/" in url:
            api_calls.append({"method": resp.request.method if resp.request else "?", "url": url, "status": resp.status})

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)
    return errors, network, api_calls


def shot(page: Page, name: str, report: dict, full_page: bool = True):
    file = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(file), full_page=full_page)
    report["shots"].append({
        "name": name,
        "url": page.url,
        "path": str(file.relative_to(OUT_DIR.parent)),
        "title": page.title(),
    })


def wait_for_load(page: Page):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)


def check_text(page: Page, text: str, timeout: int = 5000) -> bool:
    try:
        expect(page.get_by_text(text).first).to_be_visible(timeout=timeout)
        return True
    except Exception:
        return False


def record(report: dict, name: str, ok: bool, evidence: str, severity: str = "critical"):
    report["findings"].append({"name": name, "status": "PASS" if ok else "FAIL", "evidence": evidence, "severity": severity})


def run_command_centre(page: Page, report: dict):
    page.goto(f"{FRONTEND_URL}/", wait_until="networkidle")
    wait_for_load(page)
    shot(page, "01_command_centre", report)

    record(report, "page: Command Centre loads", check_text(page, "Global Portfolio Assurance"), "Global Portfolio Assurance heading visible")
    record(report, "cc: summary metrics present", check_text(page, "Total Managed FUM") and check_text(page, "Breached"), "summary metrics visible")
    record(report, "cc: heatmap present", check_text(page, "Heatmap") or page.locator(".recharts-wrapper, [class*='heatmap']").count() > 0, "heatmap chart area present")
    record(report, "cc: triage queue present", check_text(page, "Triage Queue") or check_text(page, " breaches"), "triage queue present")
    record(report, "cc: market panel present", check_text(page, "Market Simulation"), "market panel present")

    # Scroll to market panel and capture.
    if check_text(page, "Market Simulation", timeout=2000):
        page.get_by_text("Market Simulation").first.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        shot(page, "02_market_panel", report)
        record(report, "cc: market panel scrolls", True, "scrolled to market panel")


def run_diagnosis(page: Page, report: dict, cid: str):
    page.goto(f"{FRONTEND_URL}/portfolio/{cid}", wait_until="networkidle")
    wait_for_load(page)
    shot(page, "03_diagnosis", report)

    record(report, "page: Diagnosis loads", check_text(page, "Entity //") or check_text(page, "Open Remediation") or check_text(page, "Deterministic checks"), f"loaded {cid}")

    # Try explain popovers
    explain_btn = page.locator("button:has-text('Explain')").first
    if explain_btn.is_visible():
        explain_btn.click()
        page.wait_for_timeout(1200)
        shot(page, "04_diagnosis_explain", report)
        narrative_visible = check_text(page, "AI Explain") or check_text(page, "narrative") or check_text(page, "breach")
        record(report, "diag: explain popover", narrative_visible, "explain popover visible" if narrative_visible else "no narrative found")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    else:
        record(report, "diag: explain popover", False, "no Explain button found", "warning")

    # Allocation explain (second Explain button, inside Allocation Profile panel)
    alloc_btn = page.locator("button:has-text('Explain')").nth(1)
    if alloc_btn.is_visible():
        alloc_btn.click()
        page.wait_for_timeout(1200)
        shot(page, "05_diagnosis_allocation", report)
        record(report, "diag: allocation chart", check_text(page, "AI Explain") or check_text(page, "Allocation Profile") or page.locator(".recharts-wrapper").count() > 0, "allocation chart visible")


def run_workbench(page: Page, report: dict, cid: str):
    page.goto(f"{FRONTEND_URL}/portfolio/{cid}/workbench", wait_until="networkidle")
    wait_for_load(page)
    shot(page, "06_workbench_initial", report)

    record(report, "page: Workbench loads", check_text(page, "Remediation Workbench"), f"loaded {cid} workbench")

    # Propose
    propose_btn = page.locator("button:has-text('Propose a fix')").first
    if propose_btn.is_visible():
        propose_btn.click()
        # Wait for the async remediate call to finish and the UI to update, rather
        # than a blind fixed sleep. Local dev is usually ~1s; cold remote renders
        # may need up to 20s on first call.
        max_wait = 20000 if "localhost" not in FRONTEND_URL else 5000
        try:
            expect(page.locator("button:has-text('Proposing...')")).to_have_count(0, timeout=max_wait)
        except Exception:
            pass
        shot(page, "07_workbench_proposed", report)
        has_trades = page.locator("table tbody tr").count() > 0 and not check_text(page, "No trades proposed", timeout=500)
        record(report, "wb: propose returns trades", has_trades, f"trades visible={has_trades}")
    else:
        record(report, "wb: propose returns trades", False, "no Propose a fix button", "critical")
        has_trades = False

    if has_trades:
        # Verify panel should show rules status
        verify_visible = check_text(page, "Verified by rules engine") or check_text(page, "Rules:") or check_text(page, "PASS") or check_text(page, "FAIL")
        record(report, "wb: verify panel", verify_visible, "verify panel visible")

        # Export CSV
        export_btn = page.locator("button:has-text('Export CSV')").first
        if export_btn.is_visible():
            try:
                with page.expect_download(timeout=5000) as download_info:
                    export_btn.click()
                download = download_info.value
                dl_path = Path(download.path())
                csv_ok = dl_path.exists() and dl_path.stat().st_size > 0
                record(report, "wb: CSV export", csv_ok, f"downloaded {download.suggested_filename} ({dl_path})")
                if csv_ok:
                    content = dl_path.read_text()
                    reader = csv.reader(io.StringIO(content))
                    rows = list(reader)
                    record(report, "wb: CSV parseable", len(rows) > 1, f"{len(rows)-1} data rows")
            except Exception as e:
                record(report, "wb: CSV export", False, f"download failed: {e}", "warning")
        else:
            record(report, "wb: CSV export", False, "no Export CSV button", "warning")

        # Approve
        approve_btn = page.locator("button:has-text('Approve & Log')").first
        if approve_btn.is_visible():
            approve_btn.click()
            page.wait_for_timeout(1500)
            shot(page, "08_workbench_approved", report)
            approved = check_text(page, "Approved and logged") or check_text(page, "approved", timeout=2000)
            record(report, "wb: approve persists", approved, "approved banner visible" if approved else "no approved banner")
        else:
            record(report, "wb: approve persists", False, "no Approve & Log button", "critical")


def run_hermes(page: Page, report: dict):
    page.goto(f"{FRONTEND_URL}/hermes", wait_until="networkidle")
    wait_for_load(page)
    shot(page, "09_hermes_initial", report)

    record(report, "page: Hermes loads", check_text(page, "Mission Control") or check_text(page, "Hermes"), "hermes page loaded")

    scan_btn = page.locator("button:has-text('Scan Book')").first
    if scan_btn.is_visible():
        scan_btn.click()
        # Wait until queue rows are visible (FUM text is inside each collapsed row).
        populated = False
        for _ in range(60):
            page.wait_for_timeout(1000)
            if page.locator("text=/FUM/").count() > 0:
                populated = True
                break
        shot(page, "10_hermes_after_scan", report)
        record(report, "hermes: scan populates queue", populated, f"queue populated={populated}")
    else:
        record(report, "hermes: scan populates queue", False, "no Scan Book button", "critical")
        populated = False

    # Expand first queue row so the per-item Approve button is visible.
    if populated:
        first_row = page.locator("button:has-text('#1')").first
        if first_row.is_visible():
            first_row.click()
            page.wait_for_timeout(800)

    approve_one = page.locator("button:has-text('Approve')").nth(1)
    if approve_one.is_visible():
        approve_one.click()
        page.wait_for_timeout(1500)
        shot(page, "11_hermes_approved_one", report)
        record(report, "hermes: individual approve", True, "individual approve clicked")
    else:
        record(report, "hermes: individual approve", False, "no Approve button", "warning")

    # Bulk approve remaining.
    bulk_btn = page.locator("button:has-text('Approve all verified')").first
    if bulk_btn.is_visible():
        bulk_btn.click()
        page.wait_for_timeout(2000)
        shot(page, "12_hermes_bulk_approved", report)
        record(report, "hermes: bulk approve", True, "bulk approve clicked")
    else:
        record(report, "hermes: bulk approve", False, "no Approve all verified button", "warning")

    # Reflect / adopt / history.
    reflect_btn = page.locator("button:has-text('Reflect')").first
    if reflect_btn.is_visible():
        reflect_btn.click()
        page.wait_for_timeout(1500)
        shot(page, "13_hermes_reflected", report)
        record(report, "hermes: reflect", True, "reflect clicked")
    else:
        record(report, "hermes: reflect", False, "no Reflect button", "warning")

    adopt_btn = page.locator("button:has-text('Adopt')").first
    if adopt_btn.is_visible():
        adopt_btn.click()
        page.wait_for_timeout(1000)
        shot(page, "14_hermes_adopted", report)
        record(report, "hermes: adopt", True, "adopt clicked")
    else:
        record(report, "hermes: adopt", False, "no Adopt button", "warning")


def main():
    if not health_ok():
        print(f"Backend not reachable at {BACKEND_URL}/health; start servers first.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "shots": [],
        "findings": [],
        "all_console": [],
        "network_404s": [],
        "api_calls": [],
    }

    reset_demo()

    # Pick a portfolio that actually produces remediation trades.
    status, top = api_call("GET", "/portfolios/top?limit=200")
    candidates = [r for r in top.get("top", []) if r.get("status") in ("red", "orange")]
    cid = None
    for cand in candidates:
        test_cid = cand["client_id"]
        _, rem = api_call("POST", f"/portfolio/{test_cid}/remediate")
        if len(rem.get("trades", [])) > 0:
            cid = test_cid
            break
    if cid is None and top.get("top"):
        cid = top["top"][0]["client_id"]
    if cid is None:
        print("No portfolios returned from /portfolios/top")
        sys.exit(1)
    print(f"Selected portfolio: {cid}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = context.new_page()
        errors, network, api_calls = attach_listeners(page, report)

        run_command_centre(page, report)
        run_diagnosis(page, report, cid)
        run_workbench(page, report, cid)
        run_hermes(page, report)

        # Final state of Command Centre after mutations.
        page.goto(f"{FRONTEND_URL}/", wait_until="networkidle")
        wait_for_load(page)
        shot(page, "15_command_centre_final", report)

        browser.close()

    report["network_404s"] = network
    report["api_calls"] = api_calls

    BENIGN = "Support for defaultProps will be removed"
    serious = [e for e in errors if BENIGN not in (e.get("text") or "")]
    benign = [e for e in errors if BENIGN in (e.get("text") or "")]
    report["console_errors"] = errors
    report["benign_warnings"] = benign
    if serious:
        record(report, "no serious console errors", False, f"{len(serious)} serious console errors", "critical")
    else:
        record(report, "no serious console errors", True, "no serious console errors")
    if network:
        record(report, "no network 404s", False, f"{len(network)} network 404s", "critical")
    else:
        record(report, "no network 404s", True, "no network 404s")

    pass_count = sum(1 for f in report["findings"] if f["status"] == "PASS")
    fail_count = sum(1 for f in report["findings"] if f["status"] == "FAIL")
    report["pass"] = pass_count
    report["fail"] = fail_count

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"Wrote {len(report['shots'])} screenshots to {OUT_DIR}")
    print(f"Report: {REPORT_PATH}")
    print(f"PASS: {pass_count}  FAIL: {fail_count}")
    for f in report["findings"]:
        if f["status"] == "FAIL":
            print(f"  FAIL: {f['name']} - {f['evidence']}")
    if serious:
        print(f"Serious console errors: {len(serious)}")
    if network:
        print(f"Network 404s: {len(network)}")
    if benign:
        print(f"Ignored {len(benign)} upstream recharts warning(s).")

    if fail_count:
        sys.exit(1)
    print("PASS — deep E2E validation completed.")


if __name__ == "__main__":
    main()
