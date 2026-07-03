const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.URL || 'http://localhost:3000';
const API = process.env.API_URL || 'http://localhost:8000';
const out = path.resolve(__dirname, '../frontend/screenshots-deep-dive');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Capture all console logs and network requests
  page.on('console', msg => console.log('CONSOLE:', msg.type(), msg.text()));
  page.on('requestfinished', async req => {
    const url = req.url();
    if (url.includes('/approve')) {
      const post = req.postData();
      const resp = await req.response().catch(() => null);
      const status = resp ? resp.status() : 'no response';
      console.log('NETWORK APPROVE:', url, 'status:', status, 'body:', post);
    }
  });

  // Reset and scan
  await fetch(`${API}/admin/reset`, { method: 'POST' });
  const scan = await fetch(`${API}/hermes/scan`, { method: 'POST' }).then(r => r.json());
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const job = await fetch(`${API}/hermes/scan/${scan.job_id}`).then(r => r.json());
    if (job.status === 'done') break;
  }

  await page.goto(`${BASE}/hermes`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Expand first row
  const rows = page.locator('button[aria-expanded]');
  await rows.first().click();
  await page.waitForTimeout(1500);

  // Click Approve
  const approveBtn = page.locator('button').filter({ hasText: /Approve/i }).first();
  await approveBtn.scrollIntoViewIfNeeded();
  console.log('Approve button text:', await approveBtn.innerText());
  await approveBtn.click();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: path.join(out, '25-hermes-approve-debug.png'), fullPage: false });

  // Check backend state
  const pCheck = await fetch(`${API}/portfolio/c12253`).then(r => r.json());
  console.log('c12253 status after frontend approve:', pCheck.rules_result.status);

  await context.close();
  await browser.close();
})();
