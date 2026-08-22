import test from 'node:test';
import assert from 'node:assert/strict';

import {
  analyzeJob,
  DEFAULT_PROFILE,
  filterByMatchMode,
  normalizeProfile,
} from '../assets/matching.mjs';


test('Chinese major evidence creates a professional result without claiming eligibility', () => {
  const match = analyzeJob({
    location: '全国',
    profileHints: {
      majorTags: ['中国语言文学'],
      roleTags: ['综合文字'],
      qualificationTags: ['硕士'],
      graduateYears: [],
      evidence: { 中国语言文学: '专业要求：中国语言文学。' },
    },
  }, DEFAULT_PROFILE);

  assert.equal(match.tier, 'exact');
  assert.equal(match.label, '专业相关');
  assert.ok(match.reasons.includes('公告原文提到中国语言文学'));
  assert.ok(match.cautions.includes('仍需核对职位表中的具体专业范围'));
  assert.doesNotMatch(match.label, /能报|通过|符合资格/);
});

test('writing duties without a major signal stay in the writing tier', () => {
  const match = analyzeJob({
    profileHints: {
      majorTags: [],
      roleTags: ['宣传文化', '新媒体'],
      qualificationTags: [],
      graduateYears: [],
      evidence: {},
    },
  }, DEFAULT_PROFILE);

  assert.equal(match.tier, 'writing');
  assert.equal(match.label, '文字岗位');
  assert.ok(match.score >= 36);
});

test('missing hints are safe and require verification', () => {
  const match = analyzeJob({}, DEFAULT_PROFILE);

  assert.equal(match.tier, 'verify');
  assert.equal(match.label, '需要核对');
  assert.ok(match.cautions.includes('详情页尚未提取到足够的专业或职责线索'));
});

test('party membership, experience and certificate clues create cautions', () => {
  const profile = normalizeProfile({
    ...DEFAULT_PROFILE,
    politicalStatus: '群众',
    certificates: [],
  });
  const match = analyzeJob({
    profileHints: {
      majorTags: ['中国语言文学'],
      roleTags: [],
      qualificationTags: ['中共党员', '工作经历', '教师资格证'],
      graduateYears: [],
      evidence: {},
    },
  }, profile);

  assert.ok(match.cautions.some((item) => item.includes('党员')));
  assert.ok(match.cautions.some((item) => item.includes('工作经历')));
  assert.ok(match.cautions.some((item) => item.includes('教师资格证')));
});

test('graduation cohort evidence is compared when the profile has a year', () => {
  const match = analyzeJob({
    profileHints: {
      majorTags: [], roleTags: ['综合文字'], qualificationTags: ['应届'],
      graduateYears: ['2026'], evidence: {},
    },
  }, normalizeProfile({ ...DEFAULT_PROFILE, graduationYear: '2027' }));

  assert.ok(match.cautions.some((item) => item.includes('2026届')));
});

test('match modes annotate jobs and select the requested tiers', () => {
  const jobs = [
    { id: 'a', profileHints: { majorTags: ['中国语言文学'], roleTags: [], qualificationTags: [], graduateYears: [], evidence: {} } },
    { id: 'b', profileHints: { majorTags: [], roleTags: ['编辑出版'], qualificationTags: [], graduateYears: [], evidence: {} } },
    { id: 'c' },
  ];

  assert.deepEqual(filterByMatchMode(jobs, 'recommended', DEFAULT_PROFILE).map((job) => job.id), ['a', 'b']);
  assert.deepEqual(filterByMatchMode(jobs, 'exact', DEFAULT_PROFILE).map((job) => job.id), ['a']);
  assert.deepEqual(filterByMatchMode(jobs, 'writing', DEFAULT_PROFILE).map((job) => job.id), ['b']);
  assert.deepEqual(filterByMatchMode(jobs, 'verify', DEFAULT_PROFILE).map((job) => job.id), ['c']);
});

test('profile normalization keeps only supported roles and clean values', () => {
  const profile = normalizeProfile({
    major: '  中国现当代文学  ',
    graduationYear: '2027年',
    preferredLocations: ['北京', '北京', '', '湖北'],
    roleInterests: ['综合文字', '不存在的方向'],
  });

  assert.equal(profile.major, '中国现当代文学');
  assert.equal(profile.graduationYear, '2027');
  assert.deepEqual(profile.preferredLocations, ['北京', '湖北']);
  assert.deepEqual(profile.roleInterests, ['综合文字']);
});

test('legacy profiles gain safe foreign defaults without changing public fields', () => {
  const profile = normalizeProfile({ major: '中国语言文学', graduationYear: '2027' });

  assert.deepEqual(profile.targetFunctions, []);
  assert.deepEqual(profile.preferredIndustries, []);
  assert.equal(profile.englishLevel, '未设置');
  assert.equal(profile.major, '中国语言文学');
  assert.equal(profile.graduationYear, '2027');
  assert.deepEqual(profile.roleInterests, DEFAULT_PROFILE.roleInterests);
});
