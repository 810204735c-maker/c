import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:4173';
const executablePath = process.env.BROWSER_EXECUTABLE;

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('console', (message) => {
  if (message.type() === 'error') errors.push(`console: ${message.text()}`);
});
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));

await page.goto(baseUrl, { waitUntil: 'networkidle' });
await page.locator('.job-item').first().waitFor();
const dataResponse = await page.request.get(`${baseUrl}/data/jobs.json`);
const data = await dataResponse.json();
assert.equal(await page.locator('.job-item').count(), data.total, 'every snapshot record should render');
assert.match(await page.locator('.job-item h3 a').first().getAttribute('href'), /^https?:\/\//);

await page.locator('#search').fill('电信');
assert.ok(await page.locator('.job-item').count() >= 1, 'search should find the seeded telecom listing');
await page.locator('[data-category="央国企"]').click();
assert.ok(await page.locator('.job-item').count() >= 1, 'category and search should combine');

await page.locator('.save-button').click();
assert.equal(await page.locator('.save-button').getAttribute('aria-pressed'), 'true');
await page.reload({ waitUntil: 'networkidle' });
await page.locator('.job-item').first().waitFor();
assert.equal(await page.locator('.save-button').getAttribute('aria-pressed'), 'true', 'favorite should survive reload');

await page.locator('#settingsButton').click();
await page.locator('input[name="view"][value="terminal"]').check();
assert.equal(await page.locator('body').getAttribute('class'), 'view-terminal');
await page.locator('#settingsDialog .dialog-close').click();

await page.setViewportSize({ width: 390, height: 844 });
const dimensions = await page.evaluate(() => ({
  viewport: document.documentElement.clientWidth,
  content: document.documentElement.scrollWidth,
  searchHeight: document.querySelector('#search').getBoundingClientRect().height,
}));
assert.ok(dimensions.content <= dimensions.viewport, `mobile overflow: ${JSON.stringify(dimensions)}`);
assert.ok(dimensions.searchHeight >= 44, 'mobile search target should remain at least 44px high');
assert.deepEqual(errors, [], `browser console should be clean: ${errors.join('\n')}`);

await browser.close();
console.log('browser smoke test passed');
