#!/usr/bin/env node
/** Capture a small, repeatable set of visual review states. Requires Playwright and Chromium. */
import fs from 'node:fs';
import path from 'node:path';

const arg = (name, fallback) => {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
};
const baseUrl = arg('--url', 'http://localhost:3000').replace(/\/$/, '');
const outDir = path.resolve(arg('--out', 'artifacts/visual-review'));
let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  console.error('Playwright is not installed. Run `npm install --save-dev playwright` and `npx playwright install chromium`.');
  process.exit(2);
}

fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const waitForScene = async (page) => {
  await page.evaluate(async () => { await document.fonts?.ready; return true; });
  await page.waitForTimeout(900);
};
const capture = async (page, name) => {
  const file = path.join(outDir, `${name}.png`);
  await page.screenshot({ path: file, animations: 'disabled' });
  console.log(file);
};

try {
  for (const device of [
    { name: 'desktop', viewport: { width: 1440, height: 1000 }, isMobile: false, hasTouch: false },
    { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
  ]) {
    const { name, ...contextOptions } = device;
    const context = await browser.newContext({ ...contextOptions, deviceScaleFactor: 1, reducedMotion: 'reduce' });
    const page = await context.newPage();

    await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
    await waitForScene(page);
    await page.evaluate(() => window.scrollTo(0, 0));
    await capture(page, `${name}-home-hero`);
    for (const [label, fraction] of [['mid', 0.52], ['bottom', 1]]) {
      await page.evaluate((f) => window.scrollTo(0, f * (document.documentElement.scrollHeight - innerHeight)), fraction);
      await waitForScene(page);
      await capture(page, `${name}-home-${label}`);
    }

    await page.goto(`${baseUrl}/viewer`, { waitUntil: 'domcontentloaded' });
    await waitForScene(page);
    await capture(page, `${name}-viewer-three-quarter`);
    const front = page.getByRole('button', { name: 'Front', exact: true });
    if (await front.count() && await front.isEnabled()) {
      await front.click();
      await waitForScene(page);
      await capture(page, `${name}-viewer-front`);
    }
    const hotspot = page.getByRole('button', { name: 'Show head detail' });
    if (await hotspot.count() && await hotspot.isEnabled()) {
      await hotspot.click();
      await waitForScene(page);
      await capture(page, `${name}-viewer-detail`);
    }
    await context.close();
  }
} finally {
  await browser.close();
}
