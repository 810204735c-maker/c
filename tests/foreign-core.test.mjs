import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_FOREIGN_STATE,
  filterForeignCampaigns,
  foreignSearchParamsFromState,
  foreignStateFromSearchParams,
  normalizeDailySummaries,
  normalizeForeignCampaign,
  sortForeignCampaigns,
} from '../assets/foreign-core.mjs';
import {
  CHANNELS,
  channelFromSearchParams,
  searchParamsForChannel,
} from '../assets/channels.mjs';

const NOW = new Date('2026-08-22T12:00:00+08:00');
const CAMPAIGNS = [
  {
    id: 'foreign_a',
    channel: 'foreign',
    company: {
      id: 'deloitte', name: '德勤', nameEn: 'Deloitte', industryTags: ['咨询/专业服务'],
    },
    title: 'Deloitte China 2027 Graduate Program - Marketing',
    url: 'https://example.com/a',
    source: { name: '企业官网', tier: 'official_verified' },
    official: true,
    publishedAt: '2026-08-21',
    graduateYears: ['2027'],
    campaignType: 'graduate_program',
    cities: ['上海', '北京'],
    jobFunctions: ['市场/品牌', '咨询'],
    educationLevels: ['本科', '硕士'],
    industryTags: ['咨询/专业服务'],
    englishRequirements: ['英语六级'],
    deadline: '2026-10-18',
    status: 'open',
    summary: 'Marketing and consulting opportunities in China.',
  },
  {
    id: 'foreign_unknown',
    channel: 'foreign',
    company: { id: 'bosch', name: '博世', nameEn: 'Bosch', industryTags: ['工业/制造'] },
    title: 'Bosch China 2027 Campus Recruitment',
    url: 'https://example.com/unknown',
    source: { name: '企业官网', tier: 'official_verified' },
    official: true,
    publishedAt: '2026-08-20',
    graduateYears: ['2027'],
    campaignType: 'campus_recruitment',
    cities: ['苏州'],
    jobFunctions: ['技术/研发'],
    educationLevels: ['本科'],
    industryTags: ['工业/制造'],
    deadline: null,
    status: 'deadline_unknown',
  },
  {
    id: 'foreign_expired',
    channel: 'foreign',
    company: { id: 'apple', name: '苹果', nameEn: 'Apple', industryTags: ['科技/互联网'] },
    title: 'Apple China 2027 Graduate Hiring',
    url: 'https://example.com/expired',
    source: { name: '第三方', tier: 'third_party_only' },
    official: false,
    publishedAt: '2026-08-10',
    graduateYears: ['2027'],
    campaignType: 'campus_recruitment',
    cities: ['上海'],
    jobFunctions: ['产品'],
    educationLevels: ['本科'],
    industryTags: ['科技/互联网'],
    deadline: '2026-08-21',
    status: 'expired',
  },
  {
    id: 'foreign_stale',
    channel: 'foreign',
    company: { id: 'old', name: '待核企业', nameEn: '', industryTags: [] },
    title: '2027 Campus Recruitment',
    url: 'https://example.com/stale',
    source: { name: '第三方', tier: 'third_party_only' },
    official: false,
    publishedAt: '2026-06-01',
    graduateYears: ['2027'],
    campaignType: 'campus_recruitment',
    cities: [],
    jobFunctions: [],
    educationLevels: [],
    industryTags: [],
    deadline: null,
    status: 'stale',
  },
];

test('foreign filters combine without splitting a company campaign', () => {
  const result = filterForeignCampaigns(CAMPAIGNS, {
    ...DEFAULT_FOREIGN_STATE,
    q: 'marketing',
    company: 'deloitte',
    jobFunction: '市场/品牌',
    city: '上海',
    graduationYear: '2027',
    degree: '硕士',
    recruitmentType: 'graduate_program',
  }, NOW);

  assert.deepEqual(result.map((item) => item.id), ['foreign_a']);
  assert.deepEqual(result[0].cities, ['上海', '北京']);
  assert.deepEqual(result[0].jobFunctions, ['市场/品牌', '咨询']);
});

test('open is the default and saved mode reveals retained inactive records', () => {
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, DEFAULT_FOREIGN_STATE, NOW).map((item) => item.id),
    ['foreign_a', 'foreign_unknown'],
  );
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, {
      ...DEFAULT_FOREIGN_STATE,
      savedOnly: true,
      savedIds: ['foreign_expired', 'foreign_stale'],
    }, NOW).map((item) => item.id),
    ['foreign_expired', 'foreign_stale'],
  );
});

test('deadline and freshness filters use calendar dates and safe unknown states', () => {
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, { ...DEFAULT_FOREIGN_STATE, deadline: 'unknown' }, NOW)
      .map((item) => item.id),
    ['foreign_unknown'],
  );
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, { ...DEFAULT_FOREIGN_STATE, deadline: 'expired' }, NOW)
      .map((item) => item.id),
    ['foreign_expired', 'foreign_stale'],
  );
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, { ...DEFAULT_FOREIGN_STATE, freshness: '1' }, NOW)
      .map((item) => item.id),
    ['foreign_a'],
  );
});

test('foreign sorts support company deadline and explained match score', () => {
  const matched = CAMPAIGNS.map((item, index) => ({ ...item, _match: { score: index * 10 } }));
  assert.deepEqual(sortForeignCampaigns(matched, 'company', NOW).map((item) => item.id), [
    'foreign_unknown', 'foreign_stale', 'foreign_a', 'foreign_expired',
  ]);
  assert.equal(sortForeignCampaigns(matched, 'deadline', NOW)[0].id, 'foreign_a');
  assert.equal(sortForeignCampaigns(matched, 'match', NOW)[0].id, 'foreign_stale');
});

test('foreign URL state round-trips supported values and rejects unsupported enums', () => {
  const state = foreignStateFromSearchParams(new URLSearchParams(
    'channel=foreign&company=deloitte&function=%E5%B8%82%E5%9C%BA%2F%E5%93%81%E7%89%8C&degree=invalid&deadline=expired&sort=match',
  ));
  assert.equal(state.company, 'deloitte');
  assert.equal(state.jobFunction, '市场/品牌');
  assert.equal(state.degree, '全部');
  assert.equal(state.deadline, 'expired');
  assert.equal(state.sort, 'match');

  const params = foreignSearchParamsFromState({
    ...state, degree: '硕士', city: '上海', graduationYear: '全部',
  });
  const restored = foreignStateFromSearchParams(params);
  assert.equal(restored.company, 'deloitte');
  assert.equal(restored.jobFunction, '市场/品牌');
  assert.equal(restored.degree, '硕士');
  assert.equal(restored.city, '上海');
  assert.equal(restored.graduationYear, '全部');
});

test('channel state defaults old links to public and adds channel only for foreign URLs', () => {
  assert.equal(channelFromSearchParams(new URLSearchParams('q=武汉')), 'public');
  assert.equal(channelFromSearchParams(new URLSearchParams('channel=foreign')), 'foreign');
  assert.equal(CHANNELS.foreign.dataUrl, './data/foreign-campus.json');

  const publicParams = searchParamsForChannel('public', {
    q: '武汉', category: '全部', location: '全部', audience: '全部', freshness: 'all',
    sort: 'newest', match: 'all',
  });
  assert.equal(publicParams.get('q'), '武汉');
  assert.equal(publicParams.has('channel'), false);
  assert.equal(searchParamsForChannel('public').toString(), '');

  const foreignParams = searchParamsForChannel('foreign', DEFAULT_FOREIGN_STATE);
  assert.equal(foreignParams.get('channel'), 'foreign');
});

test('campaign and seven-day summary normalization are bounded and safe', () => {
  const normalized = normalizeForeignCampaign({
    ...CAMPAIGNS[0],
    company: {
      ...CAMPAIGNS[0].company,
      ownership: 'foreign_controlled',
      homeCountryOrRegion: 'United Kingdom',
    },
    cities: ['上海', '上海', '', null],
    source: { id: 'deloitte-2027', name: '企业官网', tier: 'official_verified' },
  });
  assert.deepEqual(normalized.cities, ['上海']);
  assert.equal(normalized.source.id, 'deloitte-2027');
  assert.equal(normalized.company.ownership, 'foreign_controlled');
  assert.equal(normalized.company.homeCountryOrRegion, 'United Kingdom');

  const value = Array.from({ length: 8 }, (_, index) => ({
    date: `2026-08-${String(22 - index).padStart(2, '0')}`,
    bootstrap: false,
    items: [{
      id: index === 0 ? 'foreign_a' : `foreign_${index}`,
      company: '德勤', title: 'Graduate Program', url: 'https://example.com/a', official: true,
    }],
  }));
  value[0].items.push(
    { id: 'foreign_a', company: '重复', title: '重复', url: 'https://example.com/duplicate' },
    { id: 'foreign_bad', company: '不安全', title: '不安全', url: 'javascript:alert(1)' },
  );
  const summaries = normalizeDailySummaries(value);
  assert.equal(summaries.length, 7);
  assert.equal(summaries[0].date, '2026-08-22');
  assert.deepEqual(summaries[0].items.map((item) => item.id), ['foreign_a']);
  assert.equal(summaries[0].addedCount, 1);
});

test('bootstrap summaries retain later same-day discoveries without counting the baseline', () => {
  const summaries = normalizeDailySummaries([{
    date: '2026-08-23',
    bootstrap: true,
    baselineCount: 3,
    addedCount: 999,
    items: [{
      id: 'foreign_new',
      company: '罗氏',
      title: 'StartUp 2027届校园招聘',
      url: 'https://example.com/roche',
      official: true,
    }],
  }]);

  assert.equal(summaries[0].bootstrap, true);
  assert.equal(summaries[0].baselineCount, 3);
  assert.equal(summaries[0].addedCount, 1);
  assert.deepEqual(summaries[0].items.map((item) => item.id), ['foreign_new']);
});
