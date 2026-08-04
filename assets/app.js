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
import {
  buildApplicationGuide,
  buildCalendarFile,
  getJobAlerts,
} from './application.mjs';
import {
  exportWorkspace,
  importWorkspace,
  mergeWorkspaces,
  normalizeWorkspace,
  toggleCheck,
  toggleSaved,
  updateNote,
} from './favorites.mjs';

const STORAGE = {
  saved: 'job-radar:saved',
  workspace: 'job-radar:workspace',
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
  workspaceButton: document.querySelector('#workspaceButton'),
  workspaceDialog: document.querySelector('#workspaceDialog'),
  workspaceClose: document.querySelector('#workspaceClose'),
  workspaceList: document.querySelector('#workspaceList'),
  workspaceExport: document.querySelector('#workspaceExport'),
  workspaceImport: document.querySelector('#workspaceImport'),
  workspaceImportFile: document.querySelector('#workspaceImportFile'),
  workspaceStatus: document.querySelector('#workspaceStatus'),
  applicationDialog: document.querySelector('#applicationDialog'),
  applicationClose: document.querySelector('#applicationClose'),
  applicationTitle: document.querySelector('#applicationTitle'),
  applicationOfficialLink: document.querySelector('#applicationOfficialLink'),
  applicationAlerts: document.querySelector('#applicationAlerts'),
  applicationSteps: document.querySelector('#applicationSteps'),
  materialChecklist: document.querySelector('#materialChecklist'),
  materialsNote: document.querySelector('#materialsNote'),
  applicationEvidence: document.querySelector('#applicationEvidence'),
  jobNote: document.querySelector('#jobNote'),
  noteCounter: document.querySelector('#noteCounter'),
  noteSave: document.querySelector('#noteSave'),
  applicationStatus: document.querySelector('#applicationStatus'),
  calendarExport: document.querySelector('#calendarExport'),
};

let payload = { generatedAt: null, jobs: [], sourceStatus: [] };
let profile = normalizeProfile(readJson(STORAGE.profile, DEFAULT_PROFILE));
let workspace = normalizeWorkspace(
  readJson(STORAGE.workspace, null),
  readJson(STORAGE.saved, []),
);
let activeJobId = null;
let state = {
  ...stateFromSearchParams(new URLSearchParams(location.search)),
  savedOnly: false,
  savedIds: workspace.savedIds,
};

function readJson(key, fallback) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key));
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function persistWorkspace(nextWorkspace, { rerender = true } = {}) {
  workspace = normalizeWorkspace(nextWorkspace);
  localStorage.setItem(STORAGE.workspace, JSON.stringify(workspace));
  localStorage.setItem(STORAGE.saved, JSON.stringify(workspace.savedIds));
  state = { ...state, savedIds: workspace.savedIds };
  syncControls();
  renderWorkspaceList();
  if (rerender) render();
}

function downloadText(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function evaluatedJob(jobId) {
  const job = payload.jobs.find((item) => item.id === jobId);
  return job ? filterByMatchMode([job], 'all', profile)[0] : null;
}

function ensureFavorite(jobId) {
  if (!workspace.savedIds.includes(jobId)) {
    workspace = toggleSaved(workspace, jobId);
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
  els.workspaceButton.textContent = state.savedIds.length
    ? `收藏备份 ${state.savedIds.length}`
    : '收藏备份';
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
  const alertList = fragment.querySelector('.job-alerts');
  const alerts = getJobAlerts(job, match);
  alertList.hidden = alerts.length === 0;
  alertList.replaceChildren(...alerts.map((alert) => {
    const chip = document.createElement('span');
    chip.className = `job-alert ${alert.type}`;
    chip.textContent = alert.label;
    chip.title = alert.detail;
    return chip;
  }));
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
  const applicationButton = fragment.querySelector('.application-button');
  applicationButton.dataset.application = job.id;
  applicationButton.setAttribute('aria-label', `打开报名助手：${job.title}`);
  applicationButton.textContent = workspace.notes[job.id] ? '报名助手 · 有备注' : '报名助手';
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

function applicationCheckRow(item, group, selected) {
  const label = document.createElement('label');
  label.className = 'application-check';
  const input = document.createElement('input');
  const copy = document.createElement('span');
  const title = document.createElement('strong');
  input.type = 'checkbox';
  input.dataset.applicationGroup = group;
  input.dataset.applicationKey = item.id || item.key;
  input.checked = selected.has(item.id || item.key);
  title.textContent = item.label;
  copy.append(title);
  if (item.detail) {
    const detail = document.createElement('small');
    detail.textContent = item.detail;
    copy.append(detail);
  }
  label.append(input, copy);
  return label;
}

function renderApplicationAlerts(job) {
  const alerts = getJobAlerts(job, job._match);
  els.applicationAlerts.replaceChildren(...alerts.map((alert) => {
    const item = document.createElement('span');
    item.className = `job-alert ${alert.type}`;
    item.textContent = alert.label;
    item.title = alert.detail;
    return item;
  }));
  els.applicationAlerts.hidden = alerts.length === 0;
}

function openApplicationDialog(jobId) {
  const job = evaluatedJob(jobId);
  if (!job) return;
  activeJobId = job.id;
  const guide = buildApplicationGuide(job);
  const progress = workspace.progress[job.id] || { steps: [], materials: [] };
  els.applicationTitle.textContent = job.title;
  els.applicationOfficialLink.href = job.url;
  renderApplicationAlerts(job);
  els.applicationSteps.replaceChildren(...guide.steps.map((step) => (
    applicationCheckRow(step, 'steps', new Set(progress.steps))
  )));
  els.materialChecklist.replaceChildren(...guide.materials.map((material) => (
    applicationCheckRow(material, 'materials', new Set(progress.materials))
  )));
  els.materialsNote.textContent = guide.materialsAreGeneric
    ? '未从正文提取到完整材料清单，以下为通用核对项，必须再看原公告和职位表。'
    : `从官方正文提取到 ${guide.materials.length} 项材料线索；仍请逐项对照原文。`;
  const evidenceItems = Object.entries(guide.evidence)
    .filter(([, value]) => value)
    .slice(0, 12)
    .map(([key, value]) => buildMetaItem(`${key}：${value}`));
  els.applicationEvidence.hidden = evidenceItems.length === 0;
  els.applicationEvidence.querySelector('ul').replaceChildren(...evidenceItems);
  els.jobNote.value = workspace.notes[job.id] || '';
  els.noteCounter.textContent = `${els.jobNote.value.length}/500`;
  els.applicationStatus.textContent = workspace.savedIds.includes(job.id)
    ? '该岗位已加入收藏工作区。'
    : '填写备注或勾选进度后会自动收藏。';
  const calendar = buildCalendarFile(job);
  els.calendarExport.disabled = !calendar;
  els.calendarExport.textContent = calendar ? '导出截止日历' : '截止日待确认';
  els.calendarExport.dataset.jobId = job.id;
  els.applicationDialog.showModal();
}

function saveActiveNote() {
  if (!activeJobId) return;
  const note = els.jobNote.value.slice(0, 500);
  workspace = updateNote(workspace, activeJobId, note);
  if (note.trim()) ensureFavorite(activeJobId);
  persistWorkspace(workspace);
  els.applicationStatus.textContent = note.trim()
    ? '备注已保存在当前浏览器，并已加入收藏。'
    : '空备注已清除；原有收藏和清单进度保持不变。';
}

function renderWorkspaceList() {
  if (!els.workspaceList) return;
  if (!workspace.savedIds.length) {
    const empty = document.createElement('li');
    empty.className = 'workspace-empty';
    empty.textContent = '还没有收藏岗位。收藏后可以在这里统一备份备注和报名进度。';
    els.workspaceList.replaceChildren(empty);
    return;
  }
  const items = workspace.savedIds.map((id) => {
    const job = payload.jobs.find((item) => item.id === id);
    const item = document.createElement('li');
    const copy = document.createElement('div');
    const title = document.createElement('strong');
    const meta = document.createElement('small');
    const note = document.createElement('p');
    title.textContent = job?.title || `暂未收录的历史收藏（${id}）`;
    meta.textContent = job
      ? `${job.source} · ${job.deadline ? `${job.deadline}截止` : '截止时间待确认'}`
      : '仍会保留本地备注和进度';
    note.textContent = workspace.notes[id] || '暂无备注';
    copy.append(title, meta, note);
    item.append(copy);
    if (job) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.workspaceOpen = id;
      button.textContent = '打开报名助手';
      item.append(button);
    }
    return item;
  });
  els.workspaceList.replaceChildren(...items);
}

function openWorkspaceDialog() {
  renderWorkspaceList();
  els.workspaceStatus.textContent = '备份文件只包含收藏岗位、备注和清单进度。';
  els.workspaceDialog.showModal();
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
    status.textContent = source.status === 'ok'
      ? `正常 · ${source.count} 条`
      : source.status === 'empty'
        ? '正常 · 暂无新公告'
        : source.status === 'disabled'
          ? '合规停用'
          : '暂时不可用';
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
  const applicationId = event.target.closest('[data-application]')?.dataset.application;
  if (applicationId) {
    openApplicationDialog(applicationId);
    return;
  }
  const id = event.target.closest('[data-save]')?.dataset.save;
  if (!id) return;
  persistWorkspace(toggleSaved(workspace, id));
});
els.settingsButton.addEventListener('click', () => els.settingsDialog.showModal());
els.sourceButton.addEventListener('click', () => els.sourceDialog.showModal());
els.workspaceButton.addEventListener('click', openWorkspaceDialog);
els.workspaceClose.addEventListener('click', () => els.workspaceDialog.close());
els.workspaceList.addEventListener('click', (event) => {
  const id = event.target.closest('[data-workspace-open]')?.dataset.workspaceOpen;
  if (!id) return;
  els.workspaceDialog.close();
  openApplicationDialog(id);
});
els.workspaceExport.addEventListener('click', () => {
  const backup = exportWorkspace(workspace, payload.jobs);
  downloadText(
    `招考雷达收藏备份-${new Date().toISOString().slice(0, 10)}.json`,
    `${JSON.stringify(backup, null, 2)}\n`,
    'application/json;charset=utf-8',
  );
  els.workspaceStatus.textContent = `已导出 ${workspace.savedIds.length} 个收藏岗位的本地备份。`;
});
els.workspaceImport.addEventListener('click', () => els.workspaceImportFile.click());
els.workspaceImportFile.addEventListener('change', async () => {
  const [file] = els.workspaceImportFile.files;
  els.workspaceImportFile.value = '';
  if (!file) return;
  if (file.size > 1_000_000) {
    els.workspaceStatus.textContent = '导入失败：备份文件不能超过 1 MB。';
    return;
  }
  try {
    const incoming = importWorkspace(await file.text());
    persistWorkspace(mergeWorkspaces(workspace, incoming));
    els.workspaceStatus.textContent = `导入成功，当前共有 ${workspace.savedIds.length} 个收藏岗位。`;
  } catch (error) {
    els.workspaceStatus.textContent = `导入失败：${error.message}`;
  }
});
els.applicationClose.addEventListener('click', () => {
  saveActiveNote();
  activeJobId = null;
  els.applicationDialog.close();
});
els.applicationDialog.addEventListener('cancel', (event) => {
  event.preventDefault();
  saveActiveNote();
  activeJobId = null;
  els.applicationDialog.close();
});
els.noteSave.addEventListener('click', saveActiveNote);
els.jobNote.addEventListener('input', () => {
  if (els.jobNote.value.length > 500) els.jobNote.value = els.jobNote.value.slice(0, 500);
  els.noteCounter.textContent = `${els.jobNote.value.length}/500`;
});
els.applicationDialog.addEventListener('change', (event) => {
  const input = event.target.closest('[data-application-group]');
  if (!input || !activeJobId) return;
  ensureFavorite(activeJobId);
  workspace = toggleCheck(
    workspace,
    activeJobId,
    input.dataset.applicationGroup,
    input.dataset.applicationKey,
    input.checked,
  );
  persistWorkspace(workspace);
  els.applicationStatus.textContent = '清单进度已保存在当前浏览器，并已加入收藏。';
});
els.calendarExport.addEventListener('click', () => {
  const job = payload.jobs.find((item) => item.id === els.calendarExport.dataset.jobId);
  const file = buildCalendarFile(job);
  if (!file) return;
  downloadText(file.filename, file.content, 'text/calendar;charset=utf-8');
  els.applicationStatus.textContent = '日历文件已导出；导入日历后请再次核对官方截止时刻。';
});
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
persistWorkspace(workspace, { rerender: false });
renderProfileSummary();
syncControls();
loadData();
