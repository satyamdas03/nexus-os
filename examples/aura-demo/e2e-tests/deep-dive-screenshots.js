const { chromium, devices } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.URL || 'http://localhost:3000';
const API = process.env.API_URL || 'http://localhost:8000';
const ID = 'c00011';
const out = path.resolve(__dirname, '../frontend/screenshots-deep-dive');
if (!fs.existsSync(out)) fs.mkdirSync(out, { recursive: true });

const apiOut = path.join(out, 'api');
if (!fs.existsSync(apiOut)) fs.mkdirSync(apiOut, { recursive: true });

async function saveApi(name, data) {
  fs.writeFileSync(path.join(apiOut, `${name}.json`), JSON.stringify(data, null, 2));
}

async function fetchApi(path, init) {
  const r = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

async function screenshot(page, name, fullPage = true) {
  const p = path.join(out, `${name}.png`);
  await page.screenshot({ path: p, fullPage });
  console.log(`Captured ${name}`);
  return p;
}

async function waitForData(page) {
  // Wait until the page is no longer showing a loading spinner or skeleton.
  // We use a generous timeout because the backend may be generating data.
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

  // ---- Start from clean state ----
  try {
    await fetchApi('/admin/reset', { method: 'POST' });
  } catch (e) {
    errors.push(`Initial reset: ${e.message}`);
    console.error(e);
  }

  // ---- API baseline ----
  try {
    const health = await fetchApi('/health');
    await saveApi('health', health);
    const summary = await fetchApi('/portfolios/summary');
    await saveApi('summary', summary);
    const clock = await fetchApi('/market/clock');
    await saveApi('market-clock', clock);
    const top = await fetchApi('/portfolios/top?limit=10');
    await saveApi('top-10', top);
    const p0 = await fetchApi(`/portfolio/${ID}`);
    await saveApi(`portfolio-${ID}`, p0);
    const check0 = await fetchApi(`/portfolio/${ID}/check`);
    await saveApi(`check-${ID}`, check0);
    const explain0 = await fetchApi(`/portfolio/${ID}/explain`, { method: 'POST' });
    await saveApi(`explain-${ID}`, explain0);
    const strategy = await fetchApi('/hermes/strategy');
    await saveApi('hermes-strategy', strategy);
    const hb = await fetchApi('/hermes/heartbeat');
    await saveApi('hermes-heartbeat', hb);
  } catch (e) {
    errors.push(`API baseline: ${e.message}`);
    console.error(e);
  }

  // ---- Command Centre ----
  try {
    await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
    await waitForData(page);
    await page.waitForTimeout(1000);
    await screenshot(page, '01-command-centre-initial');

    // Try status filter: Breach only
    const breachChip = page.locator('button, [role="button"]').filter({ hasText: /BREACH/i }).first();
    if (await breachChip.count()) {
      await breachChip.click();
      await page.waitForTimeout(800);
      await screenshot(page, '02-command-centre-filter-breach');
      // clear
      await page.keyboard.press('Escape');
    }

    // Try adviser filter if present
    const adviserFilter = page.locator('select').first();
    if (await adviserFilter.count()) {
      try {
        await adviserFilter.selectOption({ index: 1 });
        await page.waitForTimeout(800);
        await screenshot(page, '03-command-centre-filter-adviser');
      } catch (e) { errors.push(`adviser filter: ${e.message}`); }
    }

    // Search box
    const search = page.locator('input[type="text"], input[placeholder*="Search" i]').first();
    if (await search.count()) {
      await search.fill('Hazel');
      await page.waitForTimeout(800);
      await screenshot(page, '04-command-centre-search');
      await search.fill('');
      await page.waitForTimeout(500);
    }

    // Heatmap pagination next
    const nextBtn = page.locator('button').filter({ hasText: /Next|→|>/ }).first();
    if (await nextBtn.count() && await nextBtn.isEnabled().catch(() => false)) {
      await nextBtn.click();
      await page.waitForTimeout(800);
      await screenshot(page, '05-command-centre-heatmap-page-2');
    }

    // Market panel - click tick
    const tickBtn = page.locator('button').filter({ hasText: /TICK|ADVANCE/i }).first();
    if (await tickBtn.count()) {
      await tickBtn.click();
      await page.waitForTimeout(1200);
      await screenshot(page, '06-command-centre-after-tick');
    }
  } catch (e) {
    errors.push(`Command Centre: ${e.message}`);
    await screenshot(page, '01-command-centre-error');
    console.error(e);
  }

  // ---- Diagnosis ----
  try {
    await page.goto(`${BASE}/portfolio/${ID}`, { waitUntil: 'networkidle' });
    await waitForData(page);
    await page.waitForTimeout(1000);
    await screenshot(page, '07-diagnosis-initial');

    // Click Explain on first breach chip if present
    const explainBtn = page.locator('button').filter({ hasText: /EXPLAIN/i }).first();
    if (await explainBtn.count()) {
      await explainBtn.click();
      await page.waitForTimeout(1200);
      await screenshot(page, '08-diagnosis-after-explain');
    }

    // Scroll to holdings / donut / chart
    await page.evaluate(() => window.scrollTo(0, 800));
    await page.waitForTimeout(500);
    await screenshot(page, '09-diagnosis-lower');

    // Mobile diagnosis
    const mobileContext = await browser.newContext({ ...devices['iPhone 12 Pro'] });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto(`${BASE}/portfolio/${ID}`, { waitUntil: 'networkidle' });
    await waitForData(mobilePage).catch(() => {});
    await mobilePage.waitForTimeout(1500);
    await mobilePage.screenshot({ path: path.join(out, '10-diagnosis-mobile.png'), fullPage: true });
    console.log('Captured 10-diagnosis-mobile');
    await mobileContext.close();
  } catch (e) {
    errors.push(`Diagnosis: ${e.message}`);
    await screenshot(page, '07-diagnosis-error');
    console.error(e);
  }

  // ---- Workbench ----
  try {
    await page.goto(`${BASE}/portfolio/${ID}/workbench`, { waitUntil: 'networkidle' });
    await waitForData(page);
    await page.waitForTimeout(1000);
    await screenshot(page, '11-workbench-initial');

    // Propose
    const proposeBtn = page.locator('button').filter({ hasText: /PROPOSE|REMEDIATE|GENERATE/i }).first();
    if (await proposeBtn.count() && await proposeBtn.isEnabled().catch(() => false)) {
      await proposeBtn.click();
      await page.waitForTimeout(2000);
      await screenshot(page, '12-workbench-proposed');
    }

    // Verify
    const verifyBtn = page.locator('button').filter({ hasText: /VERIFY|SIMULATE/i }).first();
    if (await verifyBtn.count() && await verifyBtn.isEnabled().catch(() => false)) {
      await verifyBtn.click();
      await page.waitForTimeout(1500);
      await screenshot(page, '13-workbench-verified');
    }

    // Approve
    const approveBtn = page.locator('button').filter({ hasText: /APPROVE/i }).first();
    if (await approveBtn.count() && await approveBtn.isEnabled().catch(() => false)) {
      await approveBtn.click();
      await page.waitForTimeout(1500);
      await screenshot(page, '14-workbench-approved');
    }

    // Scroll to audit / suggestions
    await page.evaluate(() => window.scrollTo(0, 800));
    await page.waitForTimeout(500);
    await screenshot(page, '15-workbench-lower');
  } catch (e) {
    errors.push(`Workbench: ${e.message}`);
    await screenshot(page, '11-workbench-error');
    console.error(e);
  }

  // ---- Hermes Mission Control ----
  try {
    await page.goto(`${BASE}/hermes`, { waitUntil: 'networkidle' });
    await waitForData(page);
    await page.waitForTimeout(1000);
    await screenshot(page, '16-hermes-initial');

    // Scan
    const scanBtn = page.locator('button').filter({ hasText: /SCAN/i }).first();
    if (await scanBtn.count() && await scanBtn.isEnabled().catch(() => false)) {
      await scanBtn.click();
      await page.waitForTimeout(3000);
      await screenshot(page, '17-hermes-scanning');
      // Wait for scan to finish (poll up to 60s)
      for (let i = 0; i < 30; i++) {
        const txt = await page.locator('body').innerText().catch(() => '');
        if (txt.includes('done') || txt.includes('complete') || txt.includes('queued')) break;
        await page.waitForTimeout(2000);
        await screenshot(page, `17-hermes-scanning-${i}`);
      }
    }

    // Queue expand first item
    const queueRows = page.locator('[data-testid="hermes-row"], tr, [role="row"]').first();
    if (await queueRows.count()) {
      await queueRows.click();
      await page.waitForTimeout(800);
      await screenshot(page, '18-hermes-queue-expanded');
    }

    // Strategy panel
    await page.evaluate(() => window.scrollTo(0, 600));
    await page.waitForTimeout(500);
    await screenshot(page, '19-hermes-strategy');

    // History panel
    await page.evaluate(() => window.scrollTo(0, 1200));
    await page.waitForTimeout(500);
    await screenshot(page, '20-hermes-history');
  } catch (e) {
    errors.push(`Hermes: ${e.message}`);
    await screenshot(page, '16-hermes-error');
    console.error(e);
  }

  // ---- API after manual flows ----
  try {
    const audit = await fetchApi('/audit');
    await saveApi('audit-after', audit);
    const queue = await fetchApi('/hermes/queue?cursor=0&limit=20');
    await saveApi('hermes-queue-after', queue);
    const hb2 = await fetchApi('/hermes/heartbeat');
    await saveApi('hermes-heartbeat-after', hb2);
  } catch (e) {
    errors.push(`API after flows: ${e.message}`);
    console.error(e);
  }

  // ---- Admin reset ----
  try {
    const reset = await fetchApi('/admin/reset', { method: 'POST' });
    await saveApi('admin-reset', reset);
    await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
    await waitForData(page);
    await page.waitForTimeout(1000);
    await screenshot(page, '21-after-admin-reset');
  } catch (e) {
    errors.push(`Admin reset: ${e.message}`);
    console.error(e);
  }

  await context.close();
  await browser.close();

  fs.writeFileSync(path.join(out, 'errors.json'), JSON.stringify(errors, null, 2));
  console.log(`\nDone. Errors: ${errors.length}`);
  errors.forEach((e) => console.log(` - ${e}`));
})();
