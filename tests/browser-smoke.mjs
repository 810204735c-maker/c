import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:4173';
const executablePath = process.env.BROWSER_EXECUTABLE;

const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const FOREIGN_OFFICIAL_ID = 'foreign_aaaaaaaaaaaaaaaaaaaa';
const FOREIGN_THIRD_ID = 'foreign_bbbbbbbbbbbbbbbbbbbb';
const FOREIGN_EXPIRED_ID = 'foreign_cccccccccccccccccccc';
const today = new Date().toISOString().slice(0, 10);
const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
const futureDeadline = new Date(Date.now() + 45 * 86_400_000).toISOString().slice(0, 10);
const foreignCampaign = ({
  id, company, companyEn, companyId, title, official, source, publishedAt,
  cities, jobFunctions, industryTags, deadline, status, campaignType = 'campus_recruitment',
}) => ({
  id,
  campaignKey: `${companyId}|2027|${campaignType}|autumn|general`,
  channel: 'foreign-campus',
  company: { id: companyId, name: company, nameEn: companyEn, industryTags },
  title,
  titleLanguage: title.includes('Program') ? 'en' : 'zh',
  url: `https://example.com/${id}`,
  source: { name: source, tier: official ? 'official_verified' : 'third_party_only' },
  alternateSources: [],
  official,
  publishedAt,
  dateEstimated: false,
  firstSeenAt: `${today}T08:00:00+08:00`,
  lastSeenAt: `${today}T08:00:00+08:00`,
  graduateYears: ['2027'],
  campaignType,
  season: 'autumn',
  employmentType: 'full_time',
  cities,
  jobFunctions,
  educationLevels: ['本科', '硕士'],
  industryTags,
  englishRequirements: official ? ['英语六级'] : [],
  deadline,
  deadlineConfidence: deadline ? 'high' : '',
  deadlineEvidence: deadline ? `申请截止 ${deadline}` : '',
  summary: `${company}面向 2027 届毕业生的正式全职校园招聘活动。`,
  status,
  applicationHints: { methods: ['企业招聘网站'], materialTags: [], evidence: {} },
});
const foreignFixture = {
  schemaVersion: 1,
  channel: 'foreign',
  generatedAt: `${today}T08:00:00+08:00`,
  targetGraduateYear: '2027',
  total: 3,
  campaigns: [
    foreignCampaign({
      id: FOREIGN_OFFICIAL_ID,
      company: '德勤',
      companyEn: 'Deloitte',
      companyId: 'deloitte',
      title: 'Deloitte China 2027 Graduate Program',
      official: true,
      source: '德勤招聘官网',
      publishedAt: today,
      cities: ['上海', '北京'],
      jobFunctions: ['市场/品牌', '咨询'],
      industryTags: ['咨询/专业服务'],
      deadline: futureDeadline,
      status: 'open',
      campaignType: 'graduate_program',
    }),
    foreignCampaign({
      id: FOREIGN_THIRD_ID,
      company: '宝洁',
      companyEn: 'P&G',
      companyId: 'pg',
      title: '宝洁中国 2027 届校园招聘',
      official: false,
      source: '应届生求职网',
      publishedAt: yesterday,
      cities: ['广州'],
      jobFunctions: ['人力资源'],
      industryTags: ['消费品'],
      deadline: null,
      status: 'deadline_unknown',
    }),
    foreignCampaign({
      id: FOREIGN_EXPIRED_ID,
      company: '微软',
      companyEn: 'Microsoft',
      companyId: 'microsoft',
      title: 'Microsoft China 2027 Campus Recruitment',
      official: true,
      source: '微软招聘官网',
      publishedAt: yesterday,
      cities: ['苏州'],
      jobFunctions: ['技术/研发'],
      industryTags: ['科技/互联网'],
      deadline: '2000-01-01',
      status: 'expired',
    }),
  ],
  todaySummary: {
    date: today,
    bootstrap: true,
    baselineCount: 1,
    addedCount: 2,
    items: [
      { id: FOREIGN_OFFICIAL_ID, company: '德勤', title: 'Deloitte China 2027 Graduate Program', url: `https://example.com/${FOREIGN_OFFICIAL_ID}`, official: true },
      { id: FOREIGN_THIRD_ID, company: '宝洁', title: '宝洁中国 2027 届校园招聘', url: `https://example.com/${FOREIGN_THIRD_ID}`, official: false },
    ],
  },
  summaryHistory: [
    {
      date: today,
      bootstrap: true,
      baselineCount: 1,
      addedCount: 2,
      items: [
        { id: FOREIGN_OFFICIAL_ID, company: '德勤', title: 'Deloitte China 2027 Graduate Program', url: `https://example.com/${FOREIGN_OFFICIAL_ID}`, official: true },
        { id: FOREIGN_THIRD_ID, company: '宝洁', title: '宝洁中国 2027 届校园招聘', url: `https://example.com/${FOREIGN_THIRD_ID}`, official: false },
      ],
    },
  ],
  sourceStatus: [
    { id: 'deloitte-official', name: '德勤招聘官网', status: 'ok', count: 1 },
    { id: 'yingjiesheng', name: '应届生求职网', status: 'ok', count: 1 },
  ],
};
await page.route('**/data/foreign-campus.json', (route) => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(foreignFixture),
}));
await page.route('**/data/foreign-health.json', (route) => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ status: 'healthy', sources: foreignFixture.sourceStatus }),
}));
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
await page.locator('input[name="foreignFunction"][value="市场/品牌"]').check();
await page.locator('input[name="foreignIndustry"][value="咨询/专业服务"]').check();
await page.locator('#profileEnglish').selectOption('英语六级');
await page.locator('#profileForm .primary-action').click();
assert.equal(await page.locator('#profileDialog').getAttribute('open'), null, 'saving should close the profile dialog');
assert.match(await page.locator('#profileSummary').textContent(), /中国现当代文学.*2027届.*中共党员/);
assert.equal(await page.locator('[data-match="recommended"]').getAttribute('aria-pressed'), 'true');
const storedProfile = await page.evaluate(() => JSON.parse(localStorage.getItem('job-radar:profile')));
assert.equal(storedProfile.major, '中国语言文学');
assert.equal(storedProfile.graduationYear, '2027');
assert.deepEqual(storedProfile.preferredLocations, ['北京', '湖北']);
assert.deepEqual(storedProfile.targetFunctions, ['市场/品牌']);
assert.deepEqual(storedProfile.preferredIndustries, ['咨询/专业服务']);
assert.equal(storedProfile.englishLevel, '英语六级');

await page.reload({ waitUntil: 'networkidle' });
assert.match(await page.locator('#profileSummary').textContent(), /中国现当代文学.*2027届/);
await page.locator('[data-match="all"]').click();
await page.locator('.job-item').first().waitFor();

await page.goto(`${baseUrl}/?channel=foreign`, { waitUntil: 'networkidle' });
await page.locator('.job-item').first().waitFor();
assert.equal(await page.locator('#foreignChannelLink').getAttribute('aria-current'), 'page');
assert.equal(await page.locator('#publicChannelLink').getAttribute('aria-current'), null);
assert.match(await page.locator('#pageTitle').textContent(), /外企 2027 校招/);
assert.equal(await page.locator('.job-item').count(), 2, 'expired foreign campaigns should be hidden by default');
assert.match(await page.locator('#foreignTodaySummary').textContent(), /今日新增 2 场/);
assert.match(await page.locator('#foreignTodaySummary').textContent(), /首批建库基线为 1 场/);
assert.match(await page.locator(`[data-id="${FOREIGN_THIRD_ID}"]`).textContent(), /第三方信息，请核验/);
assert.equal(await page.locator('#foreignFilters').isVisible(), true);
assert.equal(await page.locator('[data-channel-fields="public"].filter-row').isVisible(), false);

await page.locator('#foreignCompany').selectOption('deloitte');
assert.equal(await page.locator('.job-item').count(), 1);
await page.locator('#foreignSort').selectOption('company');
assert.match(page.url(), /sort=company/);
await page.locator('#publicChannelLink').click();
assert.equal(await page.locator('#publicChannelLink').getAttribute('aria-current'), 'page');
await page.locator('#foreignChannelLink').click();
assert.equal(await page.locator('#foreignCompany').inputValue(), 'deloitte', 'foreign filters should survive channel switches');
assert.equal(await page.locator('#foreignSort').inputValue(), 'company');
await page.goBack();
assert.equal(await page.locator('#publicChannelLink').getAttribute('aria-current'), 'page');
await page.goForward();
assert.equal(await page.locator('#foreignChannelLink').getAttribute('aria-current'), 'page');
assert.equal(await page.locator('#foreignCompany').inputValue(), 'deloitte');
await page.locator('#foreignClearFilters').click();
assert.equal(await page.locator('.job-item').count(), 2);

await page.locator('#foreignTodayOnly').click();
assert.equal(await page.locator('#foreignTodayOnly').getAttribute('aria-pressed'), 'true');
assert.equal(await page.locator('.job-item').count(), 2);
await page.locator('#foreignTodayOnly').click();

const foreignSave = page.locator(`[data-save="${FOREIGN_OFFICIAL_ID}"]`);
await foreignSave.click();
assert.equal(await foreignSave.getAttribute('aria-pressed'), 'true');
await page.locator(`[data-application="${FOREIGN_OFFICIAL_ID}"]`).click();
assert.equal(await page.locator('#applicationSteps .application-check').count(), 5);
assert.equal(await page.locator('#applicationFlowTitle').textContent(), '五步申请核对');
assert.match(await page.locator('#materialChecklist').textContent(), /中英文简历/);
await page.locator('#jobNote').fill('准备英文简历；核对网申截止时间');
await page.locator('#applicationSteps input[type="checkbox"]').first().check();
await page.locator('#noteSave').click();
await page.locator('#applicationClose').click();

await page.locator('#publicChannelLink').click();
await page.locator('#workspaceButton').click();
assert.ok(await page.locator(`[data-workspace-open="${FOREIGN_OFFICIAL_ID}"]`).isVisible(), 'public workspace should resolve foreign favorites');
await page.locator(`[data-workspace-open="${FOREIGN_OFFICIAL_ID}"]`).click();
assert.equal(await page.locator('#jobNote').inputValue(), '准备英文简历；核对网申截止时间');
assert.equal(await page.locator('#applicationSteps input[type="checkbox"]').first().isChecked(), true);
await page.locator('#applicationClose').click();

await page.reload({ waitUntil: 'networkidle' });
await page.locator('.job-item').first().waitFor();
await page.locator('#workspaceButton').click();
await page.locator(`[data-workspace-open="${FOREIGN_OFFICIAL_ID}"]`).click();
assert.equal(await page.locator('#jobNote').inputValue(), '准备英文简历；核对网申截止时间');
assert.equal(await page.locator('#applicationSteps input[type="checkbox"]').first().isChecked(), true);
await page.locator('#applicationClose').click();

await page.locator('#workspaceButton').click();
const crossChannelDownloadPromise = page.waitForEvent('download');
await page.locator('#workspaceExport').click();
const crossChannelDownload = await crossChannelDownloadPromise;
const stream = await crossChannelDownload.createReadStream();
let backupText = '';
for await (const chunk of stream) backupText += chunk.toString('utf8');
const crossChannelBackup = JSON.parse(backupText);
assert.ok(crossChannelBackup.jobs.some((job) => job.id === savedId), 'backup should retain a public favorite');
assert.ok(crossChannelBackup.jobs.some((job) => job.id === FOREIGN_OFFICIAL_ID && job.channel === 'foreign'), 'backup should include foreign identity');
await page.locator('#workspaceClose').click();

await page.locator('#foreignChannelLink').click();
await page.locator('.job-item').first().waitFor();

await page.setViewportSize({ width: 390, height: 844 });
const dimensions = await page.evaluate(() => ({
  viewport: document.documentElement.clientWidth,
  content: document.documentElement.scrollWidth,
  searchHeight: document.querySelector('#search').getBoundingClientRect().height,
  profileButtonHeight: document.querySelector('#profileButton').getBoundingClientRect().height,
  workspaceButtonHeight: document.querySelector('#workspaceButton').getBoundingClientRect().height,
  channelLinkHeight: document.querySelector('#foreignChannelLink').getBoundingClientRect().height,
  foreignSortHeight: document.querySelector('#foreignSort').getBoundingClientRect().height,
  matchButtonHeight: document.querySelector('[data-match="recommended"]').getBoundingClientRect().height,
  applicationButtonHeight: document.querySelector('.application-button').getBoundingClientRect().height,
}));
assert.ok(dimensions.content <= dimensions.viewport, `mobile overflow: ${JSON.stringify(dimensions)}`);
assert.ok(dimensions.searchHeight >= 44, 'mobile search target should remain at least 44px high');
assert.ok(dimensions.profileButtonHeight >= 44, 'profile button should remain at least 44px high');
assert.ok(dimensions.workspaceButtonHeight >= 44, 'workspace button should remain at least 44px high');
assert.ok(dimensions.channelLinkHeight >= 44, 'channel link should remain at least 44px high');
assert.ok(dimensions.foreignSortHeight >= 44, 'foreign sort target should remain at least 44px high');
assert.ok(dimensions.matchButtonHeight >= 44, 'match target should remain at least 44px high');
assert.ok(dimensions.applicationButtonHeight >= 44, 'application button should remain at least 44px high');
assert.deepEqual(errors, [], `browser console should be clean: ${errors.join('\n')}`);

await page.unroute('**/data/foreign-campus.json');
await page.unroute('**/data/foreign-health.json');
await page.setViewportSize({ width: 1440, height: 1000 });
await page.goto(`${baseUrl}/?channel=foreign`, { waitUntil: 'networkidle' });
const liveForeignResponse = await page.request.get(`${baseUrl}/data/foreign-campus.json`);
assert.equal(liveForeignResponse.ok(), true, 'real foreign snapshot should be readable');
const liveForeign = await liveForeignResponse.json();
const liveActive = liveForeign.campaigns.filter((campaign) => ['open', 'deadline_unknown'].includes(campaign.status));
if (liveActive.length) await page.locator('.job-item').first().waitFor();
assert.equal(
  await page.locator('.job-item').count(),
  liveActive.length,
  'real foreign channel should render every active campaign and hide retained inactive records',
);
if (liveForeign.todaySummary?.addedCount > 0) {
  assert.match(
    await page.locator('#foreignTodaySummary').textContent(),
    new RegExp(`今日新增 ${liveForeign.todaySummary.addedCount} 场`),
    'real daily summary should match the snapshot',
  );
}
assert.deepEqual(errors, [], `real-data browser console should be clean: ${errors.join('\n')}`);

await browser.close();
console.log(`browser smoke test passed (real foreign active=${liveActive.length})`);
