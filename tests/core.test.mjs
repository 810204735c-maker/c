import test from 'node:test';
import assert from 'node:assert/strict';

import {
  filterJobs,
  formatRelativeDate,
  sortJobs,
  stateFromSearchParams,
} from '../assets/core.mjs';

const NOW = new Date('2026-07-20T12:00:00+08:00');
const JOBS = [
  {
    id: 'a', title: '湖北省省直事业单位公开招聘', source: '湖北省人社厅',
    category: '事业单位', location: '湖北', audience: '社会',
    publishedAt: '2026-07-18', deadline: null, summary: '武汉等地岗位',
  },
  {
    id: 'b', title: '中国电信2027届校园招聘', source: '国务院国资委',
    category: '央国企', location: '全国', audience: '应届',
    publishedAt: '2026-07-19', deadline: '2026-07-25', summary: '面向高校毕业生',
  },
];

const EMPTY = {
  q: '', category: '全部', location: '全部', audience: '全部', freshness: 'all',
  savedOnly: false, savedIds: [],
};

test('search matches title, source, location and summary', () => {
  assert.equal(filterJobs(JOBS, { ...EMPTY, q: '湖北' }, NOW).length, 1);
  assert.equal(filterJobs(JOBS, { ...EMPTY, q: '高校毕业生' }, NOW).length, 1);
});

test('filters combine across category, location and audience', () => {
  const result = filterJobs(JOBS, {
    ...EMPTY, category: '央国企', location: '全国', audience: '应届',
  }, NOW);
  assert.deepEqual(result.map((job) => job.id), ['b']);
});

test('favorites mode only returns saved ids', () => {
  const result = filterJobs(JOBS, { ...EMPTY, savedOnly: true, savedIds: ['b'] }, NOW);
  assert.deepEqual(result.map((job) => job.id), ['b']);
});

test('freshness uses calendar-day distance', () => {
  assert.deepEqual(filterJobs(JOBS, { ...EMPTY, freshness: '1' }, NOW).map((job) => job.id), ['b']);
  assert.equal(filterJobs(JOBS, { ...EMPTY, freshness: '7' }, NOW).length, 2);
});

test('deadline sort puts known upcoming deadlines first', () => {
  assert.deepEqual(sortJobs(JOBS, 'deadline', NOW).map((job) => job.id), ['b', 'a']);
});

test('relative date is concise', () => {
  assert.equal(formatRelativeDate('2026-07-20', NOW), '今天');
  assert.equal(formatRelativeDate('2026-07-19', NOW), '昨天');
  assert.equal(formatRelativeDate('2026-07-16', NOW), '4天前');
});

test('URL state only accepts supported values', () => {
  const state = stateFromSearchParams(new URLSearchParams('q=%E6%AD%A6%E6%B1%89&category=%E5%A4%AE%E5%9B%BD%E4%BC%81&freshness=bad&sort=deadline'));
  assert.equal(state.q, '武汉');
  assert.equal(state.category, '央国企');
  assert.equal(state.freshness, 'all');
  assert.equal(state.sort, 'deadline');
});
