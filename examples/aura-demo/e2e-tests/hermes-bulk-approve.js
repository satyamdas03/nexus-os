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

  // Accept all confirm dialogs
  page.on('dialog', async dialog => {
    console.log('DIALOG:', dialog.type(), dialog.message());
    await dialog.accept();
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
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(out, '26-hermes-bulk-ready.png'), fullPage: false });

  // Click bulk "Approve all verified" button
  const bulkBtn = page.locator('button').filter({ hasText: /Approve all verified/i }).first();
  await bulkBtn.scrollIntoViewIfNeeded();
  await bulkBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(out, '27-hermes-bulk-approved.png'), fullPage: false });

  // Check that queue is now empty and first few portfolios are green
  const queue = await fetch(`${API}/hermes/queue?cursor=0&limit=10`).then(r => r.json());
  console.log('queue size after bulk approve:', queue.rows.length);

  for (const cid of ['c12253', 'c32947', 'c14021']) {
    const p = await fetch(`${API}/portfolio/${cid}`).then(r => r.json());
    console.log(cid, 'status:', p.rules_result.status, 'breaches:', p.rules_result.breaches.length);
  }

  await context.close();
  await browser.close();
})();
