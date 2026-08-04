import test from 'node:test';
import assert from 'node:assert/strict';

import {
  exportWorkspace,
  importWorkspace,
  mergeWorkspaces,
  normalizeWorkspace,
  toggleCheck,
  toggleSaved,
  updateNote,
} from '../assets/favorites.mjs';

test('legacy favorite ids migrate without data loss', () => {
  const workspace = normalizeWorkspace(null, ['a', 'a', 'b']);

  assert.deepEqual(workspace.savedIds, ['a', 'b']);
  assert.deepEqual(workspace.notes, {});
  assert.deepEqual(workspace.progress, {});
});

test('an explicitly empty new workspace does not resurrect legacy favorites', () => {
  const workspace = normalizeWorkspace({ version: 1, savedIds: [] }, ['old']);

  assert.deepEqual(workspace.savedIds, []);
});

test('notes and checklist progress are normalized and bounded', () => {
  let workspace = normalizeWorkspace({ savedIds: ['a'] });
  workspace = updateNote(workspace, 'a', '甲'.repeat(600));
  workspace = toggleCheck(workspace, 'a', 'steps', 'read', true);
  workspace = toggleCheck(workspace, 'a', 'materials', '报名表', true);
  workspace = toggleCheck(workspace, 'a', 'materials', '报名表', false);

  assert.equal(workspace.notes.a.length, 500);
  assert.deepEqual(workspace.progress.a.steps, ['read']);
  assert.deepEqual(workspace.progress.a.materials, []);
});

test('favorite toggling preserves notes against accidental unsave', () => {
  let workspace = updateNote(normalizeWorkspace({ savedIds: ['a'] }), 'a', '准备作品集');
  workspace = toggleSaved(workspace, 'a');

  assert.deepEqual(workspace.savedIds, []);
  assert.equal(workspace.notes.a, '准备作品集');
});

test('backup contains only favorite public job fields and local workspace', () => {
  const workspace = normalizeWorkspace({
    savedIds: ['a'],
    notes: { a: '准备作品集', b: '不应导出' },
    progress: { a: { steps: ['read'], materials: ['报名表'] } },
  });
  const jobs = [
    {
      id: 'a', title: '岗位', url: 'https://example.gov.cn/a', deadline: '2026-08-07',
      source: '官方来源', category: '事业单位', location: '北京', summary: '不导出摘要',
    },
    { id: 'b', title: '未收藏', url: 'https://example.gov.cn/b' },
  ];

  const backup = exportWorkspace(workspace, jobs, '2026-08-04T12:00:00.000Z');

  assert.equal(backup.schema, 'job-radar-backup');
  assert.deepEqual(backup.jobs, [{
    id: 'a', title: '岗位', url: 'https://example.gov.cn/a', deadline: '2026-08-07',
    source: '官方来源', category: '事业单位', location: '北京',
  }]);
  assert.equal(backup.workspace.notes.a, '准备作品集');
  assert.equal(backup.workspace.notes.b, undefined);
  assert.equal(JSON.stringify(backup).includes('不导出摘要'), false);
});

test('backup import validates schema and merges without dropping current data', () => {
  const imported = importWorkspace(JSON.stringify({
    schema: 'job-radar-backup',
    version: 1,
    workspace: { savedIds: ['b'], notes: { b: '导入备注' }, progress: {} },
  }));
  const merged = mergeWorkspaces(
    normalizeWorkspace({ savedIds: ['a'], notes: { a: '现有备注' } }),
    imported,
  );

  assert.deepEqual(merged.savedIds, ['a', 'b']);
  assert.equal(merged.notes.a, '现有备注');
  assert.equal(merged.notes.b, '导入备注');
  assert.throws(() => importWorkspace('{"schema":"other"}'), /无法识别/);
});
