const CATEGORIES = new Set(['全部', '公务员', '事业单位', '央国企']);
const FRESHNESS = new Set(['all', '1', '3', '7', '30', '90']);
const SORTS = new Set(['newest', 'deadline', 'source']);

function localDate(value) {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function ageInDays(value, now) {
  const parsed = localDate(value);
  if (!parsed) return Number.POSITIVE_INFINITY;
  return Math.floor((startOfDay(now) - parsed) / 86_400_000);
}

function searchableText(job) {
  return [job.title, job.source, job.location, job.summary, job.audience, job.category]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase('zh-CN');
}

export function filterJobs(jobs, filters, now = new Date()) {
  const q = (filters.q || '').trim().toLocaleLowerCase('zh-CN');
  const saved = new Set(filters.savedIds || []);
  const freshness = filters.freshness || 'all';
  return jobs.filter((job) => {
    if (q && !searchableText(job).includes(q)) return false;
    if (filters.category && filters.category !== '全部' && job.category !== filters.category) return false;
    if (filters.location && filters.location !== '全部' && job.location !== filters.location) return false;
    if (filters.audience && filters.audience !== '全部' && ![filters.audience, '不限'].includes(job.audience)) return false;
    if (freshness !== 'all' && ageInDays(job.publishedAt, now) > Number(freshness)) return false;
    if (filters.savedOnly && !saved.has(job.id)) return false;
    return true;
  });
}

export function sortJobs(jobs, mode = 'newest', now = new Date()) {
  const copy = [...jobs];
  const dateValue = (value) => localDate(value)?.getTime() ?? 0;
  if (mode === 'deadline') {
    const today = startOfDay(now).getTime();
    return copy.sort((a, b) => {
      const aTime = dateValue(a.deadline);
      const bTime = dateValue(b.deadline);
      const aRank = aTime >= today ? 0 : aTime === 0 ? 1 : 2;
      const bRank = bTime >= today ? 0 : bTime === 0 ? 1 : 2;
      return aRank - bRank || (aRank === 0 ? aTime - bTime : bTime - aTime) || dateValue(b.publishedAt) - dateValue(a.publishedAt);
    });
  }
  if (mode === 'source') {
    return copy.sort((a, b) => (a.source || '').localeCompare(b.source || '', 'zh-CN') || dateValue(b.publishedAt) - dateValue(a.publishedAt));
  }
  return copy.sort((a, b) => dateValue(b.publishedAt) - dateValue(a.publishedAt) || (a.title || '').localeCompare(b.title || '', 'zh-CN'));
}

export function formatRelativeDate(value, now = new Date()) {
  const days = ageInDays(value, now);
  if (!Number.isFinite(days)) return '日期待核';
  if (days <= 0) return '今天';
  if (days === 1) return '昨天';
  if (days < 7) return `${days}天前`;
  return value.slice(5).replace('-', '.');
}

export function deadlineState(value, now = new Date()) {
  const parsed = localDate(value);
  if (!parsed) return { label: '截止时间见公告', tone: 'neutral' };
  const days = Math.ceil((parsed - startOfDay(now)) / 86_400_000);
  if (days < 0) return { label: '报名或已截止', tone: 'muted' };
  if (days === 0) return { label: '今天截止', tone: 'urgent' };
  if (days <= 3) return { label: `${days}天后截止`, tone: 'urgent' };
  return { label: `${value.slice(5).replace('-', '.')} 截止`, tone: 'active' };
}

export function stateFromSearchParams(params) {
  const category = params.get('category') || '全部';
  const freshness = params.get('freshness') || 'all';
  const sort = params.get('sort') || 'newest';
  return {
    q: params.get('q') || '',
    category: CATEGORIES.has(category) ? category : '全部',
    location: params.get('location') || '全部',
    audience: ['全部', '应届', '社会'].includes(params.get('audience')) ? params.get('audience') : '全部',
    freshness: FRESHNESS.has(freshness) ? freshness : 'all',
    sort: SORTS.has(sort) ? sort : 'newest',
  };
}

export function searchParamsFromState(state) {
  const params = new URLSearchParams();
  if (state.q) params.set('q', state.q);
  if (state.category !== '全部') params.set('category', state.category);
  if (state.location !== '全部') params.set('location', state.location);
  if (state.audience !== '全部') params.set('audience', state.audience);
  if (state.freshness !== 'all') params.set('freshness', state.freshness);
  if (state.sort !== 'newest') params.set('sort', state.sort);
  return params;
}
