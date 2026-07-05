import os
import sys
import json
import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

FRONT = os.environ.get("FRONT_URL", "http://127.0.0.1:3000")
API = os.environ.get("API_URL", "http://127.0.0.1:8000")
OUT = Path("screenshots-evidence-regression")
OUT.mkdir(exist_ok=True)

errors = []
console_logs = []
network_failures = []


def screenshot(page, name):
    p = OUT / f"{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"  Screenshot {name}")
    return p


def record_events(page):
    page.on("console", lambda msg: console_logs.append((msg.type, msg.text)))
    page.on("requestfailed", lambda req: network_failures.append((req.url, req.failure)))


def check_page_console(label):
    bad_console = [m for m in console_logs if m[0] in ("error", "assert")]
    if bad_console:
        for t, txt in bad_console:
            print(f"  Console {label} [{t}]: {txt[:200]}")
        errors.append(f"{label}: {len(bad_console)} console error(s)")
    # Next.js RSC prefetch aborts are expected when navigating; ignore them.
    bad_network = [
        n for n in network_failures
        if n[1] and "_rsc=" not in n[0] and "favicon" not in n[0].lower()
    ]
    if bad_network:
        for url, fail in bad_network:
            print(f"  Network {label} failed: {url} -> {fail}")
        errors.append(f"{label}: {len(bad_network)} network failure(s)")


def find_sample_portfolios():
    r = requests.get(f"{API}/portfolios?limit=200&offset=0", timeout=30)
    r.raise_for_status()
    rows = r.json()
    by_status = {"red": None, "orange": None, "green": None}
    for row in rows:
        s = row.get("status")
        if s in by_status and by_status[s] is None:
            by_status[s] = row
    print("Sample portfolios:", {k: (v["client_id"], v["status"]) if v else None for k, v in by_status.items()})
    return by_status


def goto(page, path, label, wait_selector=None):
    print(f"\nClick-through: {label} ({path})")
    console_logs.clear()
    network_failures.clear()
    try:
        page.goto(f"{FRONT}{path}", wait_until="networkidle", timeout=20000)
        if wait_selector:
            page.wait_for_selector(wait_selector, state="visible", timeout=15000)
        page.wait_for_timeout(1200)
    except PlaywrightTimeout as e:
        errors.append(f"{label}: navigation timeout ({e})")
        print(f"  ERROR timeout: {e}")


def verify_evidence_html(client_id, status):
    print(f"\nEvidence HTML: {client_id} ({status})")
    url = f"{API}/evidence/portfolio/{client_id}/html"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        errors.append(f"Evidence HTML {client_id}: HTTP {r.status_code}")
        print(f"  ERROR HTTP {r.status_code}")
        return
    html = r.text
    for must in ["ASSURE Evidence Pack", client_id, "Deterministic Summary", "Control Statement"]:
        if must not in html:
            errors.append(f"Evidence HTML {client_id}: missing '{must}'")
            print(f"  ERROR missing '{must}'")
    (OUT / f"evidence-{status}-{client_id}.html").write_text(html, encoding="utf-8")
    print(f"  HTML saved ({len(html)} chars)")


def verify_evidence_json(client_id):
    print(f"\nEvidence JSON: {client_id}")
    url = f"{API}/evidence/portfolio/{client_id}"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        errors.append(f"Evidence JSON {client_id}: HTTP {r.status_code}")
        return
    data = r.json()
    if "_html" in data:
        errors.append("Evidence JSON should not include _html key")
    for key in ["header", "current_attestation", "deterministic_summary", "alignment_history", "remediation_evidence", "control_statement"]:
        if key not in data:
            errors.append(f"Evidence JSON {client_id}: missing {key}")
    print(f"  JSON keys ok")


def main():
    print(f"Regression target: FRONT={FRONT} API={API}")
    samples = find_sample_portfolios()
    if not any(samples.values()):
        errors.append("Could not find any sample portfolios")
        print("No sample portfolios found")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        record_events(page)

        # 1. Command Centre cold load
        goto(page, "/", "Command Centre", wait_selector="text=Global Portfolio Assurance")
        body = page.locator("body").inner_text()
        if "Global Portfolio Assurance" not in body:
            errors.append("Command Centre: main heading missing")
        screenshot(page, "01-command-centre")
        check_page_console("Command Centre")

        # 2. Portfolio detail (first available)
        chosen = samples.get("red") or samples.get("orange") or samples.get("green")
        cid = chosen["client_id"]
        goto(page, f"/portfolio/{cid}", f"Portfolio {cid}", wait_selector="text=Generate Evidence Pack")
        page.wait_for_timeout(800)
        body = page.locator("body").inner_text()
        if not page.locator("a, button").filter(has_text="Remediation").count():
            errors.append(f"Portfolio {cid}: Open Remediation button missing")
        if "Generate Evidence Pack" not in body:
            errors.append(f"Portfolio {cid}: Evidence Pack button missing")
        screenshot(page, f"02-portfolio-{cid}")
        check_page_console(f"Portfolio {cid}")

        # 3. Workbench
        goto(page, f"/portfolio/{cid}/workbench", f"Workbench {cid}", wait_selector="text=Workbench")
        body = page.locator("body").inner_text()
        if "Workbench" not in body:
            errors.append(f"Workbench {cid}: heading missing")
        screenshot(page, f"03-workbench-{cid}")
        check_page_console(f"Workbench {cid}")

        # 4. Hermes Engine
        goto(page, "/hermes", "Hermes Engine", wait_selector="text=Hermes Engine")
        body = page.locator("body").inner_text()
        if "Hermes Engine" not in body:
            errors.append("Hermes: heading missing")
        screenshot(page, "04-hermes")
        check_page_console("Hermes")

        context.close()
        browser.close()

    # Evidence API checks (outside browser)
    for status, row in samples.items():
        if row:
            verify_evidence_json(row["client_id"])
            verify_evidence_html(row["client_id"], status)

    # Evidence 404 check
    print("\nEvidence 404 check")
    r = requests.get(f"{API}/evidence/portfolio/NONEXISTENT_000000/html", timeout=30)
    if r.status_code != 404:
        errors.append(f"Evidence 404 returned {r.status_code}")
    print(f"  /evidence/portfolio/NONEXISTENT_000000/html -> {r.status_code}")

    (OUT / "errors.json").write_text(json.dumps(errors, indent=2))
    (OUT / "console.json").write_text(json.dumps(console_logs, indent=2))
    (OUT / "network.json").write_text(json.dumps([{"url": u, "error": str(f)} for u, f in network_failures], indent=2))

    print(f"\nDone. Errors: {len(errors)}")
    for e in errors:
        print(f" - {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
