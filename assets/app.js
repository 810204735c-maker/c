import {
  deadlineState,
  filterJobs,
  formatRelativeDate,
  searchParamsFromState,
  sortJobs,
  stateFromSearchParams,
} from './core.mjs';
import {
  DEFAULT_PROFILE,
  filterByMatchMode,
  normalizeProfile,
} from './matching.mjs';

const STORAGE = {
  saved: 'job-radar:saved',
  view: 'job-radar:view',
  profile: 'job-radar:profile',
};
const VALID_VIEWS = new Set(['editorial', 'terminal', 'calm']);

const els = {
  filters: document.querySelector('#filters'),
  search: document.querySelector('#search'),
  location: document.querySelector('#location'),
  audience: document.querySelector('#audience'),
  freshness: document.querySelector('#freshness'),
  sort: document.querySelector('#sort'),
  matchTabs: document.querySelector('#matchTabs'),
  categoryTabs: document.querySelector('#categoryTabs'),
  savedOnly: document.querySelector('#savedOnly'),
  savedCount: document.querySelector('#savedCount'),
  clearFilters: document.querySelector('#clearFilters'),
  results: document.querySelector('#results'),
  resultSummary: document.querySelector('#resultSummary'),
  emptyState: document.querySelector('#emptyState'),
  emptyReset: document.querySelector('#emptyReset'),
  loadError: document.querySelector('#loadError'),
  retryButton: document.querySelector('#retryButton'),
  updateStatus: document.querySelector('#updateStatus'),
  totalCount: document.querySelector('#totalCount'),
  weekCount: document.querySelector('#weekCount'),
  sourceCount: document.querySelector('#sourceCount'),
  jobTemplate: document.querySelector('#jobTemplate'),
  settingsButton: document.querySelector('#settingsButton'),
  settingsDialog: document.querySelector('#settingsDialog'),
  viewOptions: document.querySelector('#viewOptions'),
  sourceButton: document.querySelector('#sourceButton'),
  sourceDialog: document.querySelector('#sourceDialog'),
  sourceList: document.querySelector('#sourceList'),
  profileButton: document.querySelector('#profileButton'),
  profileEdit: document.querySelector('#profileEdit'),
  profileSummary: document.querySelector('#profileSummary'),
  profileDialog: document.querySelector('#profileDialog'),
  profileForm: document.querySelector('#profileForm'),
  profileClose: document.querySelector('#profileClose'),
  profileReset: document.querySelector('#profileReset'),
  profileMajor: document.querySelector('#profileMajor'),
  profileDirection: document.querySelector('#profileDirection'),
  profileGraduationYear: document.querySelector('#profileGraduationYear'),
  profilePolitical: document.querySelector('#profilePolitical'),
  profileLocations: document.querySelector('#profileLocations'),
  feedTitle: document.querySelector('#feedTitle'),
};

let payload = { generatedAt: null, jobs: [], sourceStatus: [] };
let profile = normalizeProfile(readJson(STORAGE.profile, DEFAULT_PROFILE));
let state = {
  ...stateFromSearchParams(new URLSearchParams(location.search)),
  savedOnly: false,
  savedIds: readJson(STORAGE.saved, []),
};

function readJson(key, fallback) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key));
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function applyView(value) {
  const view = VALID_VIEWS.has(value) ? value : 'editorial';
  document.body.classList.remove('view-editorial', 'view-terminal', 'view-calm');
  document.body.classList.add(`view-${view}`);
  const radio = els.viewOptions.querySelector(`input[value="${view}"]`);
  if (radio) radio.checked = true;
  localStorage.setItem(STORAGE.view, view);
}

function syncControls() {
  els.search.value = state.q;
  els.location.value = [...els.location.options].some((option) => option.value === state.location) ? state.location : '全部';
  els.audience.value = state.audience;
  els.freshness.value = state.freshness;
  els.sort.value = state.sort;
  for (const tab of els.categoryTabs.querySelectorAll('[data-category]')) {
    tab.classList.toggle('is-active', tab.dataset.category === state.category);
  }
  for (const tab of els.matchTabs.querySelectorAll('[data-match]')) {
    const active = tab.dataset.match === state.match;
    tab.classList.toggle('is-active', active);
    tab.setAttribute('aria-pressed', String(active));
  }
  els.savedOnly.setAttribute('aria-pressed', String(state.savedOnly));
  els.savedCount.textContent = String(state.savedIds.length);
}

function updateUrl() {
  const params = searchParamsFromState(state);
  const next = params.size ? `${location.pathname}?${params}` : location.pathname;
  history.replaceState(null, '', next);
}

function setState(patch, { updateQuery = true } = {}) {
  state = { ...state, ...patch };
  syncControls();
  render();
  if (updateQuery) updateUrl();
}

function buildMetaItem(text, className = '') {
  const item = document.createElement('li');
  item.textContent = text;
  if (className) item.className = className;
  return item;
}

function renderJob(job) {
  const fragment = els.jobTemplate.content.cloneNode(true);
  const item = fragment.querySelector('.job-item');
  const time = fragment.querySelector('time');
  const titleLink = fragment.querySelector('h3 a');
  const summary = fragment.querySelector('.job-summary');
  const saveButton = fragment.querySelector('.save-button');
  const openLink = fragment.querySelector('.open-link');
  const deadline = deadlineState(job.deadline);
  const saved = state.savedIds.includes(job.id);
  const match = job._match;

  item.dataset.id = job.id;
  time.dateTime = job.publishedAt;
  time.textContent = job.dateEstimated ? '日期待核' : job.publishedAt;
  fragment.querySelector('.relative-date').textContent = job.dateEstimated ? '以原文为准' : formatRelativeDate(job.publishedAt);
  fragment.querySelector('.category-badge').textContent = job.category;
  fragment.querySelector('.source-name').textContent = job.source;
  fragment.querySelector('.official-badge').hidden = !job.official;
  titleLink.href = job.url;
  titleLink.textContent = job.title;
  summary.textContent = job.summary || '';
  fragment.querySelector('.job-meta').append(
    buildMetaItem(job.location || '全国'),
    buildMetaItem(job.audience === '不限' ? '对象见公告' : job.audience),
    buildMetaItem(deadline.label, deadline.tone),
  );
  const matchExplain = fragment.querySelector('.match-explain');
  const matchLabel = fragment.querySelector('.match-label');
  const matchReasons = fragment.querySelector('.match-reasons');
  const matchCaution = fragment.querySelector('.match-caution');
  const matchEvidence = fragment.querySelector('.match-evidence');
  matchExplain.classList.add(`tier-${match.tier}`);
  matchLabel.textContent = match.label;
  const reasons = match.reasons.length
    ? match.reasons.slice(0, 2)
    : ['暂未发现明确的专业或文字职责线索'];
  matchReasons.replaceChildren(...reasons.map((reason) => buildMetaItem(reason)));
  matchCaution.textContent = match.cautions[0] || '';
  matchCaution.hidden = !match.cautions.length;
  const evidenceKeys = new Set([...match.majorTags, ...match.roleTags]);
  const evidenceItems = Object.entries(match.evidence)
    .filter(([key, value]) => evidenceKeys.has(key) && value)
    .slice(0, 3)
    .map(([key, value]) => buildMetaItem(`${key}：${value}`));
  matchEvidence.hidden = evidenceItems.length === 0;
  matchEvidence.querySelector('ul').replaceChildren(...evidenceItems);
  saveButton.dataset.save = job.id;
  saveButton.setAttribute('aria-pressed', String(saved));
  saveButton.setAttribute('aria-label', `${saved ? '取消收藏' : '收藏'}：${job.title}`);
  saveButton.textContent = saved ? '已收藏' : '收藏';
  openLink.href = job.url;
  return fragment;
}

function render() {
  const matched = filterByMatchMode(payload.jobs, state.match, profile);
  const filtered = filterJobs(matched, state);
  const jobs = sortJobs(filtered, state.sort);
  els.results.replaceChildren(...jobs.map(renderJob));
  els.results.setAttribute('aria-busy', 'false');
  const matchLabels = {
    all: '全部公告', recommended: '适合我的', exact: '专业相关', writing: '文字岗位', verify: '需要核对',
  };
  els.feedTitle.textContent = matchLabels[state.match] || '最新公告';
  els.resultSummary.textContent = state.savedOnly
    ? `收藏中有 ${jobs.length} 条符合条件`
    : `${matchLabels[state.match] || '当前范围'}共 ${jobs.length} 条 · 匹配不代替资格审核`;
  els.emptyState.hidden = jobs.length !== 0 || payload.jobs.length === 0;
  document.title = jobs.length === payload.jobs.length
    ? '招考雷达｜公开招考信息聚合'
    : `${jobs.length} 条结果｜招考雷达`;
}

function renderProfileSummary() {
  const parts = [profile.degree, profile.major];
  if (profile.researchDirection) parts.push(profile.researchDirection);
  parts.push(profile.graduationYear ? `${profile.graduationYear}届` : '毕业年份待设置');
  if (profile.politicalStatus !== '未设置') parts.push(profile.politicalStatus);
  if (profile.preferredLocations.length) parts.push(`偏好：${profile.preferredLocations.join('、')}`);
  els.profileSummary.textContent = parts.join(' · ');
}

function fillProfileForm(value = profile) {
  els.profileMajor.value = value.major;
  els.profileDirection.value = value.researchDirection;
  els.profileGraduationYear.value = value.graduationYear;
  els.profilePolitical.value = value.politicalStatus;
  els.profileLocations.value = value.preferredLocations.join('、');
  const roles = new Set(value.roleInterests);
  const certificates = new Set(value.certificates);
  for (const input of els.profileForm.querySelectorAll('input[name="profileRole"]')) {
    input.checked = roles.has(input.value);
  }
  for (const input of els.profileForm.querySelectorAll('input[name="profileCertificate"]')) {
    input.checked = certificates.has(input.value);
  }
}

function openProfileDialog() {
  fillProfileForm();
  els.profileDialog.showModal();
}

function renderCounts() {
  const jobs = payload.jobs;
  const weekJobs = filterJobs(jobs.filter((job) => !job.dateEstimated), {
    q: '', category: '全部', location: '全部', audience: '全部', freshness: '7',
    savedOnly: false, savedIds: [],
  });
  const sourceStatuses = payload.sourceStatus || [];
  const availableSources = sourceStatuses.filter((source) => source.status === 'ok').length;
  const fallbackSources = new Set(jobs.map((job) => job.source)).size;
  els.totalCount.textContent = String(jobs.length);
  els.weekCount.textContent = String(weekJobs.length);
  els.sourceCount.textContent = String(availableSources || fallbackSources);
  for (const category of ['全部', '公务员', '事业单位', '央国企']) {
    const count = category === '全部' ? jobs.length : jobs.filter((job) => job.category === category).length;
    const node = document.querySelector(`[data-count="${category}"]`);
    if (node) node.textContent = String(count);
  }
}

function renderLocations() {
  const preferredOrder = ['全国', '北京', '上海', '广东', '江苏', '浙江', '山东', '河南', '湖北', '湖南', '四川', '重庆'];
  const locations = [...new Set(payload.jobs.map((job) => job.location).filter(Boolean))]
    .sort((a, b) => {
      const aIndex = preferredOrder.indexOf(a);
      const bIndex = preferredOrder.indexOf(b);
      if (aIndex !== -1 || bIndex !== -1) return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
      return a.localeCompare(b, 'zh-CN');
    });
  const options = [new Option('全部地区', '全部'), ...locations.map((value) => new Option(value, value))];
  els.location.replaceChildren(...options);
}

function renderSourceStatus() {
  const statuses = payload.sourceStatus || [];
  if (!statuses.length) {
    const item = document.createElement('li');
    item.textContent = '当前为初始数据快照；首次自动更新后会显示各来源状态。';
    els.sourceList.replaceChildren(item);
    return;
  }
  const items = statuses.map((source) => {
    const item = document.createElement('li');
    const name = document.createElement('strong');
    const status = document.createElement('span');
    name.textContent = source.name;
    status.className = `source-state ${source.status}`;
    status.textContent = source.status === 'ok' ? `正常 · ${source.count} 条` : '暂时不可用';
    item.append(name, status);
    if (source.error) {
      const detail = document.createElement('small');
      detail.textContent = source.error;
      item.append(detail);
    }
    return item;
  });
  els.sourceList.replaceChildren(...items);
}

function formatUpdatedAt(value) {
  if (!value) return '更新时间待确认';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '更新时间待确认';
  return `更新于 ${new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date)}`;
}

async function loadData() {
  els.results.setAttribute('aria-busy', 'true');
  els.loadError.hidden = true;
  try {
    const response = await fetch('./data/jobs.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const nextPayload = await response.json();
    if (!Array.isArray(nextPayload.jobs)) throw new Error('invalid jobs payload');
    payload = nextPayload;
    renderLocations();
    renderCounts();
    renderSourceStatus();
    els.updateStatus.textContent = `${formatUpdatedAt(payload.generatedAt)} · 每日自动检查`;
    syncControls();
    render();
  } catch (error) {
    console.error('Failed to load recruitment data:', error);
    els.results.setAttribute('aria-busy', 'false');
    els.loadError.hidden = false;
    els.resultSummary.textContent = '数据读取失败';
  }
}

function resetFilters() {
  setState({
    q: '', category: '全部', location: '全部', audience: '全部', freshness: 'all',
    sort: 'newest', match: 'all', savedOnly: false,
  });
  els.search.focus();
}

els.filters.addEventListener('submit', (event) => event.preventDefault());
els.search.addEventListener('input', () => setState({ q: els.search.value }));
els.location.addEventListener('change', () => setState({ location: els.location.value }));
els.audience.addEventListener('change', () => setState({ audience: els.audience.value }));
els.freshness.addEventListener('change', () => setState({ freshness: els.freshness.value }));
els.sort.addEventListener('change', () => setState({ sort: els.sort.value }));
els.categoryTabs.addEventListener('click', (event) => {
  const category = event.target.closest('[data-category]')?.dataset.category;
  if (category) setState({ category, savedOnly: false });
});
els.matchTabs.addEventListener('click', (event) => {
  const match = event.target.closest('[data-match]')?.dataset.match;
  if (!match) return;
  setState({ match, sort: match === 'all' ? state.sort : 'match', savedOnly: false });
});
els.savedOnly.addEventListener('click', () => setState({ savedOnly: !state.savedOnly }));
els.clearFilters.addEventListener('click', resetFilters);
els.emptyReset.addEventListener('click', resetFilters);
els.retryButton.addEventListener('click', loadData);
els.results.addEventListener('click', (event) => {
  const id = event.target.closest('[data-save]')?.dataset.save;
  if (!id) return;
  const saved = new Set(state.savedIds);
  if (saved.has(id)) saved.delete(id); else saved.add(id);
  const savedIds = [...saved];
  localStorage.setItem(STORAGE.saved, JSON.stringify(savedIds));
  setState({ savedIds }, { updateQuery: false });
});
els.settingsButton.addEventListener('click', () => els.settingsDialog.showModal());
els.sourceButton.addEventListener('click', () => els.sourceDialog.showModal());
els.profileButton.addEventListener('click', openProfileDialog);
els.profileEdit.addEventListener('click', openProfileDialog);
els.profileClose.addEventListener('click', () => els.profileDialog.close());
els.profileReset.addEventListener('click', () => fillProfileForm(normalizeProfile(DEFAULT_PROFILE)));
els.profileForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!els.profileForm.reportValidity()) return;
  const data = new FormData(els.profileForm);
  profile = normalizeProfile({
    degree: '硕士',
    major: data.get('major'),
    researchDirection: data.get('researchDirection'),
    graduationYear: data.get('graduationYear'),
    graduateStatus: '应届',
    politicalStatus: data.get('politicalStatus'),
    preferredLocations: data.get('preferredLocations'),
    roleInterests: data.getAll('profileRole'),
    certificates: data.getAll('profileCertificate'),
  });
  localStorage.setItem(STORAGE.profile, JSON.stringify(profile));
  renderProfileSummary();
  els.profileDialog.close();
  setState({ match: 'recommended', sort: 'match', savedOnly: false });
});
els.viewOptions.addEventListener('change', (event) => applyView(event.target.value));
document.addEventListener('keydown', (event) => {
  const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
  if (event.key === '/' && !isTyping) {
    event.preventDefault();
    els.search.focus();
  }
});

applyView(localStorage.getItem(STORAGE.view) || 'editorial');
renderProfileSummary();
syncControls();
loadData();
