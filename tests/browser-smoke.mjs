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
assert.equal(await page.locator('#loadError').isVisible(), false, 'load error should stay hidden after data loads');
assert.match(await page.locator('.job-item h3 a').first().getAttribute('href'), /^https?:\/\//);

await page.locator('#search').fill('电信');
assert.ok(await page.locator('.job-item').count() >= 1, 'search should find the seeded telecom listing');
await page.locator('[data-category="央国企"]').click();
assert.ok(await page.locator('.job-item').count() >= 1, 'category and search should combine');

const saveButton = page.locator('.save-button').first();
const savedId = await saveButton.getAttribute('data-save');
await saveButton.click();
assert.equal(await saveButton.getAttribute('aria-pressed'), 'true');
await page.reload({ waitUntil: 'networkidle' });
await page.locator('.job-item').first().waitFor();
assert.equal(
  await page.locator(`[data-save="${savedId}"]`).getAttribute('aria-pressed'),
  'true',
  'favorite should survive reload',
);

await page.locator('.application-button').first().click();
assert.equal(await page.locator('#applicationDialog').getAttribute('open'), '');
assert.equal(await page.locator('#applicationSteps .application-check').count(), 5);
await page.locator('#jobNote').fill('优先准备写作样本；确认专业代码');
await page.locator('#applicationSteps input[type="checkbox"]').first().check();
await page.locator('#noteSave').click();
assert.match(await page.locator('#applicationStatus').textContent(), /备注已保存/);
await page.locator('#applicationClose').click();

await page.reload({ waitUntil: 'networkidle' });
await page.locator('.job-item').first().waitFor();
await page.locator('.application-button').first().click();
assert.equal(await page.locator('#jobNote').inputValue(), '优先准备写作样本；确认专业代码');
assert.equal(await page.locator('#applicationSteps input[type="checkbox"]').first().isChecked(), true);
await page.locator('#applicationClose').click();

await page.locator('#workspaceButton').click();
assert.ok(await page.locator('#workspaceList li').count() >= 1, 'workspace should list favorites');
const downloadPromise = page.waitForEvent('download');
await page.locator('#workspaceExport').click();
const download = await downloadPromise;
assert.match(download.suggestedFilename(), /^招考雷达收藏备份-\d{4}-\d{2}-\d{2}\.json$/);
await page.locator('#workspaceImportFile').setInputFiles({
  name: 'backup.json',
  mimeType: 'application/json',
  buffer: Buffer.from(JSON.stringify({
    schema: 'job-radar-backup', version: 1,
    workspace: { savedIds: ['imported'], notes: { imported: '导入备注' }, progress: {} },
  })),
});
assert.match(await page.locator('#workspaceStatus').textContent(), /导入成功/);
await page.locator('#workspaceClose').click();

await page.locator('#settingsButton').click();
await page.locator('input[name="view"][value="terminal"]').check();
assert.equal(await page.locator('body').getAttribute('class'), 'view-terminal');
await page.locator('#settingsDialog .dialog-close').click();

await page.locator('#profileButton').click();
assert.equal(await page.locator('#profileMajor').inputValue(), '中国语言文学');
await page.locator('#profileDirection').fill('中国现当代文学');
await page.locator('#profileGraduationYear').fill('2027');
await page.locator('#profilePolitical').selectOption('中共党员');
await page.locator('#profileLocations').fill('北京、湖北');
await page.locator('input[name="profileCertificate"][value="教师资格证"]').check();
await page.locator('#profileForm .primary-action').click();
assert.equal(await page.locator('#profileDialog').getAttribute('open'), null, 'saving should close the profile dialog');
assert.match(await page.locator('#profileSummary').textContent(), /中国现当代文学.*2027届.*中共党员/);
assert.equal(await page.locator('[data-match="recommended"]').getAttribute('aria-pressed'), 'true');
const storedProfile = await page.evaluate(() => JSON.parse(localStorage.getItem('job-radar:profile')));
assert.equal(storedProfile.major, '中国语言文学');
assert.equal(storedProfile.graduationYear, '2027');
assert.deepEqual(storedProfile.preferredLocations, ['北京', '湖北']);

await page.reload({ waitUntil: 'networkidle' });
assert.match(await page.locator('#profileSummary').textContent(), /中国现当代文学.*2027届/);
await page.locator('[data-match="all"]').click();
await page.locator('.job-item').first().waitFor();

await page.setViewportSize({ width: 390, height: 844 });
const dimensions = await page.evaluate(() => ({
  viewport: document.documentElement.clientWidth,
  content: document.documentElement.scrollWidth,
  searchHeight: document.querySelector('#search').getBoundingClientRect().height,
  profileButtonHeight: document.querySelector('#profileButton').getBoundingClientRect().height,
  workspaceButtonHeight: document.querySelector('#workspaceButton').getBoundingClientRect().height,
  matchButtonHeight: document.querySelector('[data-match="recommended"]').getBoundingClientRect().height,
  applicationButtonHeight: document.querySelector('.application-button').getBoundingClientRect().height,
}));
assert.ok(dimensions.content <= dimensions.viewport, `mobile overflow: ${JSON.stringify(dimensions)}`);
assert.ok(dimensions.searchHeight >= 44, 'mobile search target should remain at least 44px high');
assert.ok(dimensions.profileButtonHeight >= 44, 'profile button should remain at least 44px high');
assert.ok(dimensions.workspaceButtonHeight >= 44, 'workspace button should remain at least 44px high');
assert.ok(dimensions.matchButtonHeight >= 44, 'match target should remain at least 44px high');
assert.ok(dimensions.applicationButtonHeight >= 44, 'application button should remain at least 44px high');
assert.deepEqual(errors, [], `browser console should be clean: ${errors.join('\n')}`);

await browser.close();
console.log('browser smoke test passed');
