export const FOREIGN_GRADUATION_YEARS = Object.freeze(['全部', '2027']);
export const FOREIGN_DEGREES = Object.freeze(['全部', '本科', '硕士', '博士']);
export const FOREIGN_RECRUITMENT_TYPES = Object.freeze([
  '全部',
  'campus_recruitment',
  'graduate_program',
  'management_trainee',
  'supplemental',
]);
export const FOREIGN_DEADLINE_FILTERS = Object.freeze([
  'open', '7days', '30days', 'unknown', 'expired', 'all',
]);
export const FOREIGN_SORTS = Object.freeze(['newest', 'deadline', 'company', 'match']);
export const FOREIGN_MATCH_MODES = Object.freeze([
  'all', 'recommended', 'function', 'location', 'verify',
]);
export const FOREIGN_FRESHNESS = Object.freeze(['all', '1', '3', '7', '30', '90']);

const GRADUATION_YEAR_SET = new Set(FOREIGN_GRADUATION_YEARS);
const DEGREE_SET = new Set(FOREIGN_DEGREES);
const RECRUITMENT_TYPE_SET = new Set(FOREIGN_RECRUITMENT_TYPES);
const DEADLINE_SET = new Set(FOREIGN_DEADLINE_FILTERS);
const SORT_SET = new Set(FOREIGN_SORTS);
const MATCH_MODE_SET = new Set(FOREIGN_MATCH_MODES);
const FRESHNESS_SET = new Set(FOREIGN_FRESHNESS);
const CAMPAIGN_TYPES = new Set(FOREIGN_RECRUITMENT_TYPES.filter((value) => value !== '全部'));
const CAMPAIGN_STATUSES = new Set(['open', 'deadline_unknown', 'expired', 'stale']);

export const DEFAULT_FOREIGN_STATE = Object.freeze({
  q: '',
  company: '全部',
  jobFunction: '全部',
  city: '全部',
  graduationYear: '2027',
  degree: '全部',
  recruitmentType: '全部',
  freshness: 'all',
  deadline: 'open',
  sort: 'newest',
  match: 'all',
  savedOnly: false,
  savedIds: Object.freeze([]),
});

function cleanText(value, limit = 200) {
  return String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

function cleanFilterValue(value, fallback = '全部') {
  return cleanText(value, 100) || fallback;
}

function cleanList(value, limit = 30) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map((item) => cleanText(item, 80)).filter(Boolean))].slice(0, limit);
}

function safeHttpUrl(value) {
  const url = cleanText(value, 2_000);
  return /^https?:\/\//i.test(url) ? url : '';
}

function localDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year
    || parsed.getMonth() !== month - 1
    || parsed.getDate() !== day
  ) return null;
  return parsed;
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function ageInDays(value, now) {
  const parsed = localDate(value);
  if (!parsed || Number.isNaN(now?.getTime?.())) return Number.POSITIVE_INFINITY;
  return Math.floor((startOfDay(now) - parsed) / 86_400_000);
}

function daysUntil(value, now) {
  const parsed = localDate(value);
  if (!parsed || Number.isNaN(now?.getTime?.())) return null;
  return Math.ceil((parsed - startOfDay(now)) / 86_400_000);
}

function normalizeCompany(value, fallbackIndustries = []) {
  const source = value && typeof value === 'object' && !Array.isArray(value)
    ? value
    : { name: value };
  return {
    id: cleanText(source.id, 80),
    name: cleanText(source.name, 100),
    nameEn: cleanText(source.nameEn, 100),
    ownership: cleanText(source.ownership, 80),
    homeCountryOrRegion: cleanText(source.homeCountryOrRegion, 80),
    industryTags: cleanList(source.industryTags?.length ? source.industryTags : fallbackIndustries, 16),
  };
}

function normalizeSource(value) {
  const source = value && typeof value === 'object' && !Array.isArray(value)
    ? value
    : { name: value };
  return {
    id: cleanText(source.id, 100),
    name: cleanText(source.name, 100),
    tier: cleanText(source.tier, 40),
  };
}

function normalizeAlternateSources(value) {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 8).map((item) => ({
    name: cleanText(item?.name, 100),
    tier: cleanText(item?.tier, 40),
    url: safeHttpUrl(item?.url),
  })).filter((item) => item.url);
}

export function normalizeForeignCampaign(value = {}) {
  const candidate = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const industryTags = cleanList(candidate.industryTags, 16);
  const company = normalizeCompany(candidate.company, industryTags);
  const deadline = localDate(candidate.deadline) ? candidate.deadline : null;
  const status = CAMPAIGN_STATUSES.has(candidate.status)
    ? candidate.status
    : deadline
      ? 'open'
      : 'deadline_unknown';
  return {
    ...candidate,
    id: cleanText(candidate.id, 100),
    campaignKey: cleanText(candidate.campaignKey, 240),
    channel: 'foreign',
    company,
    title: cleanText(candidate.title, 300),
    titleLanguage: ['zh', 'en'].includes(candidate.titleLanguage) ? candidate.titleLanguage : '',
    url: safeHttpUrl(candidate.url),
    source: normalizeSource(candidate.source),
    alternateSources: normalizeAlternateSources(candidate.alternateSources),
    official: candidate.official === true,
    publishedAt: localDate(candidate.publishedAt) ? candidate.publishedAt : '',
    dateEstimated: candidate.dateEstimated === true,
    firstSeenAt: cleanText(candidate.firstSeenAt, 40),
    lastSeenAt: cleanText(candidate.lastSeenAt, 40),
    graduateYears: cleanList(candidate.graduateYears, 8)
      .filter((item) => /^20\d{2}$/.test(item)),
    campaignType: CAMPAIGN_TYPES.has(candidate.campaignType)
      ? candidate.campaignType
      : 'campus_recruitment',
    season: cleanText(candidate.season, 30),
    employmentType: cleanText(candidate.employmentType, 30) || 'full_time',
    cities: cleanList(candidate.cities),
    jobFunctions: cleanList(candidate.jobFunctions),
    educationLevels: cleanList(candidate.educationLevels, 10),
    industryTags: industryTags.length ? industryTags : [...company.industryTags],
    englishRequirements: cleanList(candidate.englishRequirements, 10),
    deadline,
    deadlineConfidence: cleanText(candidate.deadlineConfidence, 20),
    deadlineEvidence: cleanText(candidate.deadlineEvidence, 160),
    summary: cleanText(candidate.summary, 1_000),
    status,
    foreignHints: candidate.foreignHints && typeof candidate.foreignHints === 'object'
      ? { ...candidate.foreignHints }
      : {},
    applicationHints: candidate.applicationHints && typeof candidate.applicationHints === 'object'
      ? { ...candidate.applicationHints }
      : {},
    _match: candidate._match && typeof candidate._match === 'object'
      ? { ...candidate._match }
      : undefined,
  };
}

function lifecycleState(campaign, now) {
  if (campaign.status === 'stale') return 'stale';
  const remaining = daysUntil(campaign.deadline, now);
  if (campaign.status === 'expired' || (remaining !== null && remaining < 0)) return 'expired';
  if (remaining === null) return 'deadline_unknown';
  return 'open';
}

function deadlineMatches(campaign, mode, now) {
  const selected = DEADLINE_SET.has(mode) ? mode : 'open';
  if (selected === 'all') return true;
  const state = lifecycleState(campaign, now);
  if (selected === 'open') return ['open', 'deadline_unknown'].includes(state);
  if (selected === 'unknown') return state === 'deadline_unknown';
  if (selected === 'expired') return ['expired', 'stale'].includes(state);
  const remaining = daysUntil(campaign.deadline, now);
  if (state !== 'open' || remaining === null || remaining < 0) return false;
  return remaining <= (selected === '7days' ? 7 : 30);
}

function freshnessMatches(value, freshness, now) {
  const selected = FRESHNESS_SET.has(freshness) ? freshness : 'all';
  if (selected === 'all') return true;
  return ageInDays(value, now) <= Number(selected);
}

function searchableText(campaign) {
  return [
    campaign.title,
    campaign.company.name,
    campaign.company.nameEn,
    campaign.source.name,
    campaign.summary,
    ...campaign.cities,
    ...campaign.jobFunctions,
    ...campaign.industryTags,
    ...campaign.educationLevels,
    ...campaign.englishRequirements,
  ].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN');
}

export function filterForeignCampaigns(campaigns, filters = DEFAULT_FOREIGN_STATE, now = new Date()) {
  const selected = { ...DEFAULT_FOREIGN_STATE, ...(filters || {}) };
  const query = cleanText(selected.q, 200).toLocaleLowerCase('zh-CN');
  const saved = new Set(Array.isArray(selected.savedIds) ? selected.savedIds : []);
  const deadline = selected.savedOnly ? 'all' : selected.deadline;
  const source = Array.isArray(campaigns) ? campaigns : [];
  return source.map(normalizeForeignCampaign).filter((campaign) => {
    if (query && !searchableText(campaign).includes(query)) return false;
    if (selected.company !== '全部' && campaign.company.id !== selected.company) return false;
    if (selected.jobFunction !== '全部' && !campaign.jobFunctions.includes(selected.jobFunction)) return false;
    if (selected.city !== '全部' && !campaign.cities.includes(selected.city)) return false;
    if (selected.graduationYear !== '全部' && !campaign.graduateYears.includes(selected.graduationYear)) return false;
    if (selected.degree !== '全部' && !campaign.educationLevels.includes(selected.degree)) return false;
    if (selected.recruitmentType !== '全部' && campaign.campaignType !== selected.recruitmentType) return false;
    if (!deadlineMatches(campaign, deadline, now)) return false;
    if (!freshnessMatches(campaign.publishedAt, selected.freshness, now)) return false;
    if (selected.savedOnly && !saved.has(campaign.id)) return false;
    return true;
  });
}

export function sortForeignCampaigns(campaigns, mode = 'newest', now = new Date()) {
  const selected = SORT_SET.has(mode) ? mode : 'newest';
  const records = (Array.isArray(campaigns) ? campaigns : []).map(normalizeForeignCampaign);
  const dateValue = (value) => localDate(value)?.getTime() ?? 0;
  const byNewest = (a, b) => (
    dateValue(b.publishedAt) - dateValue(a.publishedAt)
    || a.company.name.localeCompare(b.company.name, 'zh-CN')
    || a.title.localeCompare(b.title, 'zh-CN')
  );
  if (selected === 'match') {
    return records.sort((a, b) => (
      (b._match?.score || 0) - (a._match?.score || 0) || byNewest(a, b)
    ));
  }
  if (selected === 'company') {
    return records.sort((a, b) => (
      a.company.name.localeCompare(b.company.name, 'zh-CN') || byNewest(a, b)
    ));
  }
  if (selected === 'deadline') {
    return records.sort((a, b) => {
      const aState = lifecycleState(a, now);
      const bState = lifecycleState(b, now);
      const rank = { open: 0, deadline_unknown: 1, expired: 2, stale: 3 };
      const stateDifference = rank[aState] - rank[bState];
      if (stateDifference) return stateDifference;
      if (aState === 'open') return dateValue(a.deadline) - dateValue(b.deadline) || byNewest(a, b);
      return byNewest(a, b);
    });
  }
  return records.sort(byNewest);
}

export function foreignStateFromSearchParams(params = new URLSearchParams()) {
  const get = (key) => params?.get?.(key);
  const graduationYear = get('graduationYear') || DEFAULT_FOREIGN_STATE.graduationYear;
  const degree = get('degree') || DEFAULT_FOREIGN_STATE.degree;
  const recruitmentType = get('recruitmentType') || DEFAULT_FOREIGN_STATE.recruitmentType;
  const freshness = get('freshness') || DEFAULT_FOREIGN_STATE.freshness;
  const deadline = get('deadline') || DEFAULT_FOREIGN_STATE.deadline;
  const sort = get('sort') || DEFAULT_FOREIGN_STATE.sort;
  const match = get('match') || DEFAULT_FOREIGN_STATE.match;
  return {
    q: cleanText(get('q'), 200),
    company: cleanFilterValue(get('company')),
    jobFunction: cleanFilterValue(get('function') || get('jobFunction')),
    city: cleanFilterValue(get('city')),
    graduationYear: GRADUATION_YEAR_SET.has(graduationYear) ? graduationYear : DEFAULT_FOREIGN_STATE.graduationYear,
    degree: DEGREE_SET.has(degree) ? degree : DEFAULT_FOREIGN_STATE.degree,
    recruitmentType: RECRUITMENT_TYPE_SET.has(recruitmentType) ? recruitmentType : DEFAULT_FOREIGN_STATE.recruitmentType,
    freshness: FRESHNESS_SET.has(freshness) ? freshness : DEFAULT_FOREIGN_STATE.freshness,
    deadline: DEADLINE_SET.has(deadline) ? deadline : DEFAULT_FOREIGN_STATE.deadline,
    sort: SORT_SET.has(sort) ? sort : DEFAULT_FOREIGN_STATE.sort,
    match: MATCH_MODE_SET.has(match) ? match : DEFAULT_FOREIGN_STATE.match,
    savedOnly: false,
    savedIds: [],
  };
}

export function foreignSearchParamsFromState(state = DEFAULT_FOREIGN_STATE) {
  const selected = { ...DEFAULT_FOREIGN_STATE, ...(state || {}) };
  const params = new URLSearchParams();
  if (selected.q) params.set('q', cleanText(selected.q, 200));
  if (selected.company !== '全部') params.set('company', cleanFilterValue(selected.company));
  if (selected.jobFunction !== '全部') params.set('function', cleanFilterValue(selected.jobFunction));
  if (selected.city !== '全部') params.set('city', cleanFilterValue(selected.city));
  if (selected.graduationYear !== DEFAULT_FOREIGN_STATE.graduationYear) params.set('graduationYear', selected.graduationYear);
  if (selected.degree !== '全部') params.set('degree', selected.degree);
  if (selected.recruitmentType !== '全部') params.set('recruitmentType', selected.recruitmentType);
  if (selected.freshness !== 'all') params.set('freshness', selected.freshness);
  if (selected.deadline !== 'open') params.set('deadline', selected.deadline);
  if (selected.sort !== 'newest') params.set('sort', selected.sort);
  if (selected.match !== 'all') params.set('match', selected.match);
  return params;
}

function validDateKey(value) {
  return localDate(value) ? value : '';
}

function normalizeSummaryItem(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const id = cleanText(value.id, 100);
  const url = safeHttpUrl(value.url);
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(id) || !url) return null;
  return {
    id,
    company: cleanText(value.company, 100),
    title: cleanText(value.title, 300),
    url,
    official: value.official === true,
  };
}

export function normalizeDailySummaries(value) {
  if (!Array.isArray(value)) return [];
  const byDate = new Map();
  for (const candidate of value) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) continue;
    const date = validDateKey(candidate.date);
    if (!date) continue;
    const current = byDate.get(date) || {
      date,
      bootstrap: false,
      baselineCount: 0,
      itemMap: new Map(),
    };
    current.bootstrap ||= candidate.bootstrap === true;
    const baselineCount = Number.isSafeInteger(candidate.baselineCount) && candidate.baselineCount >= 0
      ? candidate.baselineCount
      : 0;
    current.baselineCount = Math.max(current.baselineCount, baselineCount);
    for (const rawItem of Array.isArray(candidate.items) ? candidate.items : []) {
      const item = normalizeSummaryItem(rawItem);
      if (item && !current.itemMap.has(item.id)) current.itemMap.set(item.id, item);
    }
    byDate.set(date, current);
  }
  return [...byDate.values()]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 7)
    .map((entry) => {
      const items = [...entry.itemMap.values()];
      return {
        date: entry.date,
        bootstrap: entry.bootstrap,
        // A bootstrap day can still receive genuinely new campaigns after the
        // initial baseline snapshot. Its items array contains only those later
        // discoveries, so keep that count visible.
        addedCount: items.length,
        baselineCount: entry.baselineCount,
        items,
      };
    });
}

export function campaignTypeLabel(value) {
  return {
    campus_recruitment: '校园招聘',
    graduate_program: 'Graduate Program',
    management_trainee: '管培生',
    supplemental: '补录',
  }[value] || '校园招聘';
}
