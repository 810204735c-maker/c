import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildApplicationGuide,
  buildCalendarFile,
  getJobAlerts,
} from '../assets/application.mjs';

const NOW = new Date('2026-08-04T12:00:00+08:00');

test('three-day deadline and unresolved major produce reminders', () => {
  const alerts = getJobAlerts(
    { deadline: '2026-08-07' },
    { tier: 'writing' },
    NOW,
  );

  assert.deepEqual(alerts.map((item) => item.type), ['deadline', 'major']);
  assert.equal(alerts[0].label, '3天内截止');
  assert.equal(alerts[1].label, '专业待确认');
});

test('expired, invalid, and exact-major jobs avoid false reminders', () => {
  assert.deepEqual(
    getJobAlerts({ deadline: '2026-08-03' }, { tier: 'exact' }, NOW),
    [],
  );
  assert.deepEqual(
    getJobAlerts({ deadline: null }, { tier: 'exact' }, NOW),
    [],
  );
});

test('application guide uses official methods and material hints', () => {
  const guide = buildApplicationGuide({
    url: 'https://example.gov.cn/a',
    applicationHints: {
      methods: ['网上报名'],
      materialTags: ['报名表', '身份证'],
      evidence: { 网上报名: '登录报名系统进行网上报名' },
    },
  });

  assert.equal(guide.steps.length, 5);
  assert.deepEqual(guide.methods, ['网上报名']);
  assert.deepEqual(guide.materials.map((item) => item.label), ['报名表', '身份证']);
  assert.equal(guide.materialsAreGeneric, false);
});

test('application guide supplies a clearly marked generic checklist when evidence is absent', () => {
  const guide = buildApplicationGuide({});

  assert.equal(guide.materialsAreGeneric, true);
  assert.ok(guide.materials.length >= 4);
  assert.match(guide.steps[2].detail, /公告未提取到完整清单/);
});

test('calendar file includes deadline alarm and official URL', () => {
  const file = buildCalendarFile({
    id: 'a',
    title: '某单位招聘公告',
    deadline: '2026-08-07',
    url: 'https://example.gov.cn/a',
  }, NOW);

  assert.equal(file.filename, '招考雷达-2026-08-07-某单位招聘公告.ics');
  assert.match(file.content, /BEGIN:VCALENDAR/);
  assert.match(file.content, /DTSTART;VALUE=DATE:20260807/);
  assert.match(file.content, /TRIGGER:-P3D/);
  assert.match(file.content, /URL:https:\/\/example.gov.cn\/a/);
  assert.match(file.content, /END:VCALENDAR/);
});

test('calendar export is unavailable without a valid deadline', () => {
  assert.equal(buildCalendarFile({ title: '公告', deadline: null }), null);
  assert.equal(buildCalendarFile({ title: '公告', deadline: '待确认' }), null);
});

test('foreign guide keeps stable step ids and uses application wording', () => {
  const guide = buildApplicationGuide({
    channel: 'foreign',
    official: false,
    applicationHints: {},
  });

  assert.deepEqual(guide.steps.map((item) => item.id), [
    'read', 'qualify', 'materials', 'submit', 'retain',
  ]);
  assert.match(guide.steps[1].detail, /学历.*2027届.*语言.*工作地点/);
  assert.ok(guide.materials.some((item) => item.label === '中英文简历'));
  assert.equal(guide.materialsAreGeneric, true);
});

test('foreign calendar uses application wording', () => {
  const file = buildCalendarFile({
    id: 'foreign_a',
    channel: 'foreign',
    title: '2027 Graduate Programme',
    deadline: '2026-10-18',
    url: 'https://example.com/graduate',
  }, NOW);
  assert.match(file.content, /SUMMARY:申请截止：2027 Graduate Programme/);
  assert.match(file.content, /DESCRIPTION:申请截止前三天提醒/);
});

test('foreign third-party record produces source and condition verification alerts', () => {
  const alerts = getJobAlerts(
    { channel: 'foreign', official: false, deadline: null },
    { tier: 'verify' },
    NOW,
  );

  assert.ok(alerts.some((item) => item.type === 'source'));
  assert.ok(alerts.some((item) => item.label.includes('第三方')));
  assert.ok(alerts.some((item) => item.label === '申请条件待核对'));
});

test('foreign guide uses extracted materials when reliable hints exist', () => {
  const guide = buildApplicationGuide({
    channel: 'foreign',
    applicationHints: {
      methods: ['网上报名'],
      materialTags: ['中英文简历', '成绩单'],
      evidence: { '中英文简历': 'Please upload your Chinese and English resumes.' },
    },
  });

  assert.equal(guide.materialsAreGeneric, false);
  assert.deepEqual(guide.materials.map((item) => item.label), ['中英文简历', '成绩单']);
  assert.match(guide.steps[3].detail, /招聘页.*网上报名/);
});
