const { chromium, devices } = require('playwright');
const fs = require('fs');

const BASE = process.env.URL || 'https://prototyping-steel.vercel.app';
const ID = 'c000';
const out = './screenshots';
if (!fs.existsSync(out)) fs.mkdirSync(out, { recursive: true });

const pages = [
  { name: 'home', path: '/' },
  { name: 'diagnosis', path: `/portfolio/${ID}` },
  { name: 'workbench', path: `/portfolio/${ID}/workbench` },
];

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  for (const { name, path } of pages) {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: `${out}/${name}-desktop.png`, fullPage: true });
    console.log(`Captured ${name} desktop`);
  }

  await context.close();

  const mobileContext = await browser.newContext({ ...devices['iPhone 12 Pro'] });
  const mobilePage = await mobileContext.newPage();
  for (const { name, path } of pages) {
    await mobilePage.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
    await mobilePage.screenshot({ path: `${out}/${name}-mobile.png`, fullPage: true });
    console.log(`Captured ${name} mobile`);
  }
  await mobileContext.close();
  await browser.close();
})();
