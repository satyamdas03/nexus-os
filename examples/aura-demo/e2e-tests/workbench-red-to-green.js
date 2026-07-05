const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.URL || 'http://localhost:3000';
const API = process.env.API_URL || 'http://127.0.0.1:8000';
const ID = 'c00011';
const out = path.resolve(__dirname, '../frontend/screenshots-deep-dive');
if (!fs.existsSync(out)) fs.mkdirSync(out, { recursive: true });

async function screenshot(page, name, fullPage = true) {
  const p = path.join(out, `${name}.png`);
  await page.screenshot({ path: p, fullPage });
  console.log(`Captured ${name}`);
  return p;
}

async function waitForData(page) {
  await page.waitForFunction(() => {
    const txt = document.body.innerText || '';
    return !txt.includes('LOADING') && !txt.includes('BACKEND_UNREACHABLE') && txt.trim().length > 200;
  }, { timeout: 60000 });
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];

  try {
    // Reset
    await fetch(`${API}/admin/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });

    // Workbench initial
    await page.goto(`${BASE}/portfolio/${ID}/workbench`, { waitUntil: 'networkidle' });
    await waitForData(page);
    await page.waitForTimeout(1000);
    await screenshot(page, 'workbench-red-initial');

    // Propose
    const proposeBtn = page.locator('button').filter({ hasText: /Propose a fix/i }).first();
    if (await proposeBtn.count() && await proposeBtn.isEnabled().catch(() => false)) {
      await proposeBtn.click();
      await page.waitForTimeout(3000);
      await screenshot(page, 'workbench-proposed');
    } else {
      errors.push('Propose button not found/enabled');
    }

    // Verify (click if a separate Verify button exists)
    const verifyBtn = page.locator('button').filter({ hasText: /^Verify/i }).first();
    if (await verifyBtn.count() && await verifyBtn.isEnabled().catch(() => false)) {
      await verifyBtn.click();
      await page.waitForTimeout(2000);
      await screenshot(page, 'workbench-verified');
    }

    // Approve
    const approveBtn = page.locator('button').filter({ hasText: /Approve \& Log/i }).first();
    if (await approveBtn.count() && await approveBtn.isEnabled().catch(() => false)) {
      await approveBtn.click();
      await page.waitForTimeout(2500);
      await screenshot(page, 'workbench-approved-green');
    } else {
      errors.push('Approve button not found/enabled');
    }

    // Scroll lower to show audit trail
    await page.evaluate(() => window.scrollTo(0, 900));
    await page.waitForTimeout(500);
    await screenshot(page, 'workbench-approved-lower');

    // Check effective state via API
    const check = await fetch(`${API}/portfolio/${ID}/check`).then(r => r.json());
    fs.writeFileSync(path.join(out, 'workbench-final-check.json'), JSON.stringify(check, null, 2));
    console.log('Final check status:', check.status, 'breaches:', check.breaches.length);
  } catch (e) {
    errors.push(e.message);
    console.error(e);
  }

  await context.close();
  await browser.close();
  fs.writeFileSync(path.join(out, 'workbench-errors.json'), JSON.stringify(errors, null, 2));
  console.log(`Done. Errors: ${errors.length}`);
})();
