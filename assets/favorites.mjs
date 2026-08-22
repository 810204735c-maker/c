export const EMPTY_WORKSPACE = Object.freeze({
  version: 1,
  savedIds: [],
  notes: {},
  progress: {},
});

const RESERVED_KEYS = new Set(['__proto__', 'prototype', 'constructor']);

function cleanId(value) {
  const id = String(value || '').trim();
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(id) || RESERVED_KEYS.has(id)) return '';
  return id;
}

function cleanIds(value, limit = 500) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map(cleanId).filter(Boolean))].slice(0, limit);
}

function cleanChecklistKeys(value, limit = 100) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value
    .map((item) => String(item || '').replace(/\s+/g, ' ').trim().slice(0, 80))
    .filter((item) => item && !RESERVED_KEYS.has(item)))]
    .slice(0, limit);
}

function cleanNotes(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const entries = [];
  for (const [rawId, rawNote] of Object.entries(value).slice(0, 500)) {
    const id = cleanId(rawId);
    if (!id) continue;
    const note = String(rawNote ?? '').replace(/\r\n/g, '\n').slice(0, 500);
    if (note.trim()) entries.push([id, note]);
  }
  return Object.fromEntries(entries);
}

function cleanProgress(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const entries = [];
  for (const [rawId, rawProgress] of Object.entries(value).slice(0, 500)) {
    const id = cleanId(rawId);
    if (!id || !rawProgress || typeof rawProgress !== 'object' || Array.isArray(rawProgress)) continue;
    entries.push([id, {
      steps: cleanChecklistKeys(rawProgress.steps),
      materials: cleanChecklistKeys(rawProgress.materials),
    }]);
  }
  return Object.fromEntries(entries);
}

export function normalizeWorkspace(value, legacySavedIds = []) {
  const source = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const savedSource = Object.hasOwn(source, 'savedIds') ? source.savedIds : legacySavedIds;
  return {
    version: 1,
    savedIds: cleanIds(savedSource),
    notes: cleanNotes(source.notes),
    progress: cleanProgress(source.progress),
  };
}

export function toggleSaved(value, rawId) {
  const workspace = normalizeWorkspace(value);
  const id = cleanId(rawId);
  if (!id) return workspace;
  const saved = new Set(workspace.savedIds);
  if (saved.has(id)) saved.delete(id); else saved.add(id);
  return { ...workspace, savedIds: [...saved] };
}

export function updateNote(value, rawId, rawNote) {
  const workspace = normalizeWorkspace(value);
  const id = cleanId(rawId);
  if (!id) return workspace;
  const note = String(rawNote ?? '').replace(/\r\n/g, '\n').slice(0, 500);
  const notes = { ...workspace.notes };
  if (note.trim()) notes[id] = note; else delete notes[id];
  return { ...workspace, notes };
}

export function toggleCheck(value, rawId, group, rawKey, checked = undefined) {
  const workspace = normalizeWorkspace(value);
  const id = cleanId(rawId);
  const key = cleanChecklistKeys([rawKey], 1)[0];
  if (!id || !key || !['steps', 'materials'].includes(group)) return workspace;
  const current = workspace.progress[id] || { steps: [], materials: [] };
  const selected = new Set(current[group]);
  const shouldSelect = typeof checked === 'boolean' ? checked : !selected.has(key);
  if (shouldSelect) selected.add(key); else selected.delete(key);
  return {
    ...workspace,
    progress: {
      ...workspace.progress,
      [id]: { ...current, [group]: [...selected] },
    },
  };
}

function subsetMap(value, ids) {
  return Object.fromEntries(Object.entries(value).filter(([id]) => ids.has(id)));
}

function publicJob(job) {
  const isForeign = job?.channel === 'foreign';
  const common = {
    id: cleanId(job.id),
    title: String(job.title || '').slice(0, 200),
    url: /^https?:\/\//.test(String(job.url || '')) ? String(job.url) : '',
    deadline: /^\d{4}-\d{2}-\d{2}$/.test(String(job.deadline || '')) ? job.deadline : null,
    source: String(job.source?.name || job.source || '').slice(0, 100),
    category: String(job.category || '').slice(0, 30),
    location: String(job.location || (isForeign ? job.cities?.join('、') : '') || '')
      .slice(0, isForeign ? 100 : 30),
  };
  if (!isForeign) return common;
  return {
    id: common.id,
    channel: 'foreign',
    company: String(job.company?.name || job.company || '').slice(0, 100),
    title: common.title,
    url: common.url,
    deadline: common.deadline,
    source: common.source,
    category: common.category,
    location: common.location,
  };
}

export function exportWorkspace(value, jobs = [], exportedAt = new Date().toISOString()) {
  const workspace = normalizeWorkspace(value);
  const saved = new Set(workspace.savedIds);
  const selectedJobs = Array.isArray(jobs)
    ? jobs.filter((job) => saved.has(cleanId(job?.id))).map(publicJob)
    : [];
  return {
    schema: 'job-radar-backup',
    version: 1,
    exportedAt: String(exportedAt || new Date().toISOString()),
    workspace: {
      ...workspace,
      notes: subsetMap(workspace.notes, saved),
      progress: subsetMap(workspace.progress, saved),
    },
    jobs: selectedJobs,
  };
}

export function importWorkspace(value) {
  let document = value;
  if (typeof value === 'string') {
    try {
      document = JSON.parse(value);
    } catch {
      throw new Error('备份文件不是有效的 JSON');
    }
  }
  if (
    !document
    || typeof document !== 'object'
    || document.schema !== 'job-radar-backup'
    || document.version !== 1
    || !document.workspace
  ) {
    throw new Error('无法识别该招考雷达备份');
  }
  return normalizeWorkspace(document.workspace);
}

export function mergeWorkspaces(currentValue, incomingValue) {
  const current = normalizeWorkspace(currentValue);
  const incoming = normalizeWorkspace(incomingValue);
  const progress = { ...current.progress };
  for (const [id, entry] of Object.entries(incoming.progress)) {
    const existing = progress[id] || { steps: [], materials: [] };
    progress[id] = {
      steps: [...new Set([...existing.steps, ...entry.steps])],
      materials: [...new Set([...existing.materials, ...entry.materials])],
    };
  }
  return normalizeWorkspace({
    savedIds: [...current.savedIds, ...incoming.savedIds],
    notes: { ...current.notes, ...incoming.notes },
    progress,
  });
}
