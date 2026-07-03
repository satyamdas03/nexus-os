const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.URL || 'http://localhost:3000';
const API = process.env.API_URL || 'http://localhost:8000';
const out = path.resolve(__dirname, '../frontend/screenshots-deep-dive');
if (!fs.existsSync(out)) fs.mkdirSync(out, { recursive: true });

async function screenshot(page, name) {
  const p = path.join(out, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  console.log(`Captured ${name}`);
  return p;
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Reset and scan
  await fetch(`${API}/admin/reset`, { method: 'POST' });
  const scan = await fetch(`${API}/hermes/scan`, { method: 'POST' }).then(r => r.json());
  console.log('scan job:', scan.job_id);
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const job = await fetch(`${API}/hermes/scan/${scan.job_id}`).then(r => r.json());
    if (job.status === 'done') { console.log('scan done'); break; }
  }

  // Load /hermes page
  await page.goto(`${BASE}/hermes`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await screenshot(page, '22-hermes-queue-ready');

  // Expand first queue row (click the row button)
  const rows = page.locator('button[aria-expanded]');
  const firstRow = rows.first();
  await firstRow.click();
  await page.waitForTimeout(1500);
  await screenshot(page, '23-hermes-row-expanded');

  // Click Approve
  const approveBtn = page.locator('button').filter({ hasText: /Approve/i }).first();
  await approveBtn.scrollIntoViewIfNeeded();
  await approveBtn.click();
  await page.waitForTimeout(2500);
  await screenshot(page, '24-hermes-row-approved');

  // Verify the portfolio is now green via API
  const pCheck = await fetch(`${API}/portfolio/c12253`).then(r => r.json());
  console.log('c12253 after approve:', pCheck.rules_result.status, 'breaches:', pCheck.rules_result.breaches.length);

  await context.close();
  await browser.close();
})();
