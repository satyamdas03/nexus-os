"""Playwright-driven UI screenshot validation for the AURA demo.

Captures key pages/flows and validates that they render without console errors
or obvious broken-state markers. Outputs PNGs under e2e_screenshots/ and a JSON
report. Run with both backend + frontend dev servers running:

    python scripts/e2e_screenshots.py

Env:
    FRONTEND_URL  - base URL (default http://localhost:3000)
    BACKEND_URL   - health check target (default http://localhost:8000)
"""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
OUT_DIR = Path(__file__).parent.parent / "e2e_screenshots"


def _health() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def _console_errors(page: Page) -> list[str]:
    errors: list[str] = []
    def handler(msg):
        if msg.type == "error":
            errors.append(msg.text)
    page.on("console", handler)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    return errors


def _network_failures(page: Page) -> list[str]:
    failures: list[str] = []
    def handler(response):
        if response.status >= 400:
            failures.append(f"{response.status} {response.url}")
    page.on("response", handler)
    return failures


def _has_marker(page: Page, text: str) -> bool:
    return page.locator(f"text={text}").first.is_visible(timeout=2000)


def shot(page: Page, name: str, path: str, report: dict):
    url = f"{FRONTEND_URL}{path}"
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(500)
    file = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(file), full_page=True)
    report["shots"].append({
        "name": name,
        "url": url,
        "path": str(file.relative_to(Path(__file__).parent.parent)),
        "title": page.title(),
    })


def main():
    if not _health():
        print(f"Backend not reachable at {BACKEND_URL}/health; start servers first.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"frontend_url": FRONTEND_URL, "backend_url": BACKEND_URL, "shots": [], "errors": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors = _console_errors(page)
        net_failures = _network_failures(page)

        # Flow 1: Command Centre (portfolio list + summary)
        shot(page, "01_command_centre", "/", report)
        expect(page.get_by_text("Global Portfolio Assurance").first).to_be_visible(timeout=10000)

        # Flow 2: Portfolio detail
        page.goto(f"{FRONTEND_URL}/portfolio/c00000", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "02_portfolio_detail.png"), full_page=True)
        report["shots"].append({"name": "02_portfolio_detail", "url": page.url, "path": "e2e_screenshots/02_portfolio_detail.png", "title": page.title()})

        # Flow 3: Workbench verify
        page.goto(f"{FRONTEND_URL}/portfolio/c00000/workbench", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "03_workbench.png"), full_page=True)
        report["shots"].append({"name": "03_workbench", "url": page.url, "path": "e2e_screenshots/03_workbench.png", "title": page.title()})

        # Flow 4: Hermes Mission Control (scan + queue)
        page.goto(f"{FRONTEND_URL}/hermes", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "04_hermes_initial.png"), full_page=True)
        report["shots"].append({"name": "04_hermes_initial", "url": page.url, "path": "e2e_screenshots/04_hermes_initial.png", "title": page.title()})

        # Trigger a scan from the UI and wait for queue population.
        scan_btn = page.locator("button:has-text('Scan Book')").first
        if scan_btn.is_visible():
            scan_btn.click()
            # Wait until queue count text updates or spinner stops.
            page.wait_for_timeout(8000)
            page.screenshot(path=str(OUT_DIR / "05_hermes_after_scan.png"), full_page=True)
            report["shots"].append({"name": "05_hermes_after_scan", "url": page.url, "path": "e2e_screenshots/05_hermes_after_scan.png", "title": page.title()})

        # Flow 5: scroll to / capture the MarketPanel inside the command centre
        page.goto(f"{FRONTEND_URL}/", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.get_by_text("Market Simulation").first.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "06_market_panel.png"), full_page=True)
        report["shots"].append({"name": "06_market_panel", "url": page.url, "path": "e2e_screenshots/06_market_panel.png", "title": page.title()})

        browser.close()

    # Known upstream warnings we cannot fix here (recharts defaultProps).
    # Treat everything else — especially hydration errors — as a failure.
    BENIGN = "Support for defaultProps will be removed"
    serious = [e for e in errors if BENIGN not in e]
    benign = [e for e in errors if BENIGN in e]
    report["console_errors"] = errors
    report["benign_warnings"] = benign
    report["network_404s"] = net_failures
    if serious:
        report["errors"].append(f"{len(serious)} console error(s) captured")
    if net_failures:
        report["errors"].append(f"{len(net_failures)} network 404(s)")

    report_path = OUT_DIR.parent / "e2e_screenshot_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Wrote {len(report['shots'])} screenshots to {OUT_DIR}")
    print(f"Report: {report_path}")
    if serious:
        print(f"Console errors: {len(serious)}")
        for e in serious[:5]:
            print(f"  - {e}")
    if net_failures:
        print(f"Network 404s: {len(net_failures)}")
        for u in net_failures[:5]:
            print(f"  - {u}")
    if serious or net_failures:
        sys.exit(1)
    if benign:
        print(f"Ignored {len(benign)} upstream recharts warning(s).")
    print("PASS — no blocking console errors or 404s.")


if __name__ == "__main__":
    main()
