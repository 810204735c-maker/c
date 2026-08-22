import test from 'node:test';
import assert from 'node:assert/strict';

import {
  FOREIGN_ENGLISH_LEVELS,
  FOREIGN_FUNCTIONS,
  FOREIGN_INDUSTRIES,
  normalizeProfile,
} from '../assets/matching.mjs';
import {
  analyzeForeignCampaign,
  filterForeignByMatchMode,
} from '../assets/foreign-matching.mjs';

const CAMPAIGNS = [
  {
    id: 'foreign_a',
    channel: 'foreign',
    official: true,
    company: {
      id: 'deloitte', name: '德勤', nameEn: 'Deloitte', industryTags: ['咨询/专业服务'],
    },
    title: 'Deloitte China 2027 Graduate Program',
    graduateYears: ['2027'],
    campaignType: 'graduate_program',
    cities: ['上海'],
    jobFunctions: ['市场/品牌', '咨询'],
    educationLevels: ['本科', '硕士'],
    industryTags: ['咨询/专业服务'],
    englishRequirements: ['英语六级'],
    foreignHints: { evidence: { '市场/品牌': 'Marketing', '上海': 'Location: Shanghai' } },
  },
  {
    id: 'foreign_b',
    channel: 'foreign',
    official: true,
    company: { id: 'bosch', name: '博世', nameEn: 'Bosch', industryTags: ['工业/制造'] },
    title: 'Bosch China 2027 Campus Recruitment',
    graduateYears: ['2027'],
    campaignType: 'campus_recruitment',
    cities: ['苏州'],
    jobFunctions: ['技术/研发'],
    educationLevels: ['本科'],
    industryTags: ['工业/制造'],
    englishRequirements: [],
  },
  {
    id: 'foreign_conflict',
    channel: 'foreign',
    official: true,
    company: { id: 'legacy', name: '其他公司', nameEn: '', industryTags: [] },
    title: 'Graduate Programme',
    graduateYears: ['2026'],
    campaignType: 'graduate_program',
    cities: [],
    jobFunctions: [],
    educationLevels: [],
    industryTags: [],
    englishRequirements: ['英语流利'],
  },
];

test('foreign profile option exports stay aligned with normalization', () => {
  assert.ok(FOREIGN_FUNCTIONS.includes('市场/品牌'));
  assert.ok(FOREIGN_INDUSTRIES.includes('咨询/专业服务'));
  assert.ok(FOREIGN_INDUSTRIES.includes('化工/材料'));
  assert.ok(FOREIGN_INDUSTRIES.includes('医药/医疗'));
  assert.ok(FOREIGN_INDUSTRIES.includes('汽车'));
  assert.ok(FOREIGN_ENGLISH_LEVELS.includes('英语六级'));
  const profile = normalizeProfile({
    targetFunctions: ['市场/品牌', '不存在'],
    preferredIndustries: ['咨询/专业服务', '不存在'],
    englishLevel: '不存在',
  });
  assert.deepEqual(profile.targetFunctions, ['市场/品牌']);
  assert.deepEqual(profile.preferredIndustries, ['咨询/专业服务']);
  assert.equal(profile.englishLevel, '未设置');
});

test('foreign matching explains function city industry cohort and degree', () => {
  const match = analyzeForeignCampaign(CAMPAIGNS[0], normalizeProfile({
    degree: '硕士',
    graduationYear: '2027',
    preferredLocations: ['上海'],
    targetFunctions: ['市场/品牌'],
    preferredIndustries: ['咨询/专业服务'],
    englishLevel: '英语六级',
  }));

  assert.ok(match.score >= 60);
  assert.ok(match.reasons.some((item) => item.includes('市场/品牌')));
  assert.ok(match.reasons.some((item) => item.includes('上海')));
  assert.ok(match.reasons.some((item) => item.includes('2027')));
  assert.deepEqual(match.matchedFunctions, ['市场/品牌']);
  assert.deepEqual(match.matchedLocations, ['上海']);
  assert.equal(match.cohortConflict, false);
  assert.doesNotMatch(match.label, /保证|录用|符合资格/);
});

test('higher English requirement warns without declaring ineligibility', () => {
  const match = analyzeForeignCampaign(CAMPAIGNS[0], normalizeProfile({
    graduationYear: '2027', englishLevel: '英语四级',
  }));
  assert.ok(match.cautions.some((item) => item.includes('英语六级')));
  assert.doesNotMatch(match.cautions.join(' '), /不符合|不能申请|无资格/);
  assert.deepEqual(
    filterForeignByMatchMode([CAMPAIGNS[0]], 'verify', {
      graduationYear: '2027', englishLevel: '英语四级',
    }).map((item) => item.id),
    ['foreign_a'],
  );
});

test('third-party campaigns stay visible in verify mode even with strong structured signals', () => {
  const thirdParty = { ...CAMPAIGNS[1], official: false };
  assert.deepEqual(
    filterForeignByMatchMode([thirdParty], 'verify', {
      graduationYear: '2027', targetFunctions: ['技术/研发'], preferredLocations: ['苏州'],
    }).map((item) => item.id),
    ['foreign_b'],
  );
});

test('cohort conflicts and missing structured signals stay out of recommendations', () => {
  const profile = normalizeProfile({
    graduationYear: '2027',
    targetFunctions: ['市场/品牌'],
    preferredLocations: ['上海'],
    preferredIndustries: ['咨询/专业服务'],
    englishLevel: '英语六级',
  });
  const conflict = analyzeForeignCampaign(CAMPAIGNS[2], profile);
  assert.equal(conflict.cohortConflict, true);
  assert.equal(conflict.tier, 'verify');
  assert.ok(conflict.cautions.some((item) => item.includes('2026')));
  assert.deepEqual(
    filterForeignByMatchMode(CAMPAIGNS, 'recommended', profile).map((item) => item.id),
    ['foreign_a'],
  );
});

test('foreign match modes select independent function location and verify signals', () => {
  const profile = normalizeProfile({
    graduationYear: '2027',
    targetFunctions: ['市场/品牌'],
    preferredLocations: ['上海'],
    preferredIndustries: ['咨询/专业服务'],
    englishLevel: '英语六级',
  });
  assert.deepEqual(filterForeignByMatchMode(CAMPAIGNS, 'function', profile).map((item) => item.id), ['foreign_a']);
  assert.deepEqual(filterForeignByMatchMode(CAMPAIGNS, 'location', profile).map((item) => item.id), ['foreign_a']);
  assert.deepEqual(filterForeignByMatchMode(CAMPAIGNS, 'verify', profile).map((item) => item.id), ['foreign_conflict']);
  assert.equal(filterForeignByMatchMode(CAMPAIGNS, 'invalid', profile).length, CAMPAIGNS.length);
});
