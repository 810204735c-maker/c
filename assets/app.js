import {
  deadlineState,
  filterJobs,
  formatRelativeDate,
  sortJobs,
  stateFromSearchParams,
} from './core.mjs';
import {
  DEFAULT_PROFILE,
  FOREIGN_ENGLISH_LEVELS,
  FOREIGN_FUNCTIONS,
  FOREIGN_INDUSTRIES,
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
import {
  CHANNELS,
  channelFromSearchParams,
  searchParamsForChannel,
} from './channels.mjs';
import {
  DEFAULT_FOREIGN_STATE,
  filterForeignCampaigns,
  foreignStateFromSearchParams,
  normalizeDailySummaries,
  normalizeForeignCampaign,
  sortForeignCampaigns,
} from './foreign-core.mjs';
import { filterForeignByMatchMode } from './foreign-matching.mjs';

const STORAGE = {
  saved: 'job-radar:saved',
  workspace: 'job-radar:workspace',
  view: 'job-radar:view',
  profile: 'job-radar:profile',
};
const VALID_VIEWS = new Set(['editorial', 'terminal', 'calm']);

const CHANNEL_COPY = Object.freeze({
  public: {
    eyebrow: 'PUBLIC RECRUITMENT INTELLIGENCE / 公开招考情报',
    title: ['把分散的招考公告，', '收进一张每日清单。'],
    intro: '聚合考公、考编与央国企招聘信息。只保留可核验来源，点击即可回到原公告。',
    placeholder: '输入单位、岗位、专业或地区',
    profileTitle: '中文硕士求职画像',
    profilePrivacy: '只保存在当前浏览器；匹配结果用于缩小范围，报考资格仍以原职位表为准。',
    totalLabel: '当前收录',
    weekLabel: '近 7 日发布',
    method: [
      ['每日发现', '定时检查国家与地方官方招聘栏目，持续补充新公告。'],
      ['校验去重', '按域名白名单过滤来源，相同公告只保留信息更完整的一条。'],
      ['直达原文', '网站不代替报名系统；资格、时间与岗位要求均以原公告为准。'],
    ],
  },
  foreign: {
    eyebrow: 'FOREIGN CAMPUS RECRUITMENT / 外企校招情报',
    title: ['把外企 2027 校招，', '收进一张每日申请清单。'],
    intro: '每日发现外企在中国大陆发布、面向 2027 届毕业生的正式全职校招；官网优先，第三方信息明确提示核验。',
    placeholder: '输入企业、校招项目、职能、行业或城市',
    profileTitle: '我的外企校招画像',
    profilePrivacy: '画像只保存在当前浏览器；匹配用于发现机会，不代表满足企业申请资格。',
    totalLabel: '当前活动',
    weekLabel: '近 7 日新增',
    method: [
      ['每日发现', '定时检查外企官网、受委托招聘页与公开校招平台，发现面向 2027 届的中国岗位。'],
      ['公司级去重', '同一场招聘活动只展示一张卡片；企业官网或经核验的官方招聘入口优先。'],
      ['申请前核验', '第三方信息会明确标识；申请条件、城市与截止时间均应回到招聘原文复核。'],
    ],
  },
});

const MATCH_UI = Object.freeze({
  public: [
    ['all', '全部公告'], ['recommended', '适合我的'], ['exact', '专业相关'],
    ['writing', '文字岗位'], ['verify', '需要核对'],
  ],
  foreign: [
    ['all', '全部活动'], ['recommended', '适合我的'], ['function', '职能匹配'],
    ['location', '地点匹配'], ['verify', '需要核验'],
  ],
});

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
  foreignClearFilters: document.querySelector('#foreignClearFilters'),
  foreignCompany: document.querySelector('#foreignCompany'),
  foreignFunction: document.querySelector('#foreignFunction'),
  foreignCity: document.querySelector('#foreignCity'),
  foreignGraduationYear: document.querySelector('#foreignGraduationYear'),
  foreignDegree: document.querySelector('#foreignDegree'),
  foreignRecruitmentType: document.querySelector('#foreignRecruitmentType'),
  foreignFreshness: document.querySelector('#foreignFreshness'),
  foreignDeadline: document.querySelector('#foreignDeadline'),
  foreignSort: document.querySelector('#foreignSort'),
  channelNav: document.querySelector('#channelNav'),
  publicChannelLink: document.querySelector('#publicChannelLink'),
  foreignChannelLink: document.querySelector('#foreignChannelLink'),
  pageEyebrow: document.querySelector('#pageEyebrow'),
  pageTitle: document.querySelector('#pageTitle'),
  pageIntro: document.querySelector('#pageIntro'),
  totalLabel: document.querySelector('#totalLabel'),
  weekLabel: document.querySelector('#weekLabel'),
  profileSummaryTitle: document.querySelector('#profileSummaryTitle'),
  profilePrivacy: document.querySelector('#profilePrivacy'),
  methodSteps: document.querySelector('#methodSteps'),
  results: document.querySelector('#results'),
  resultSummary: document.querySelector('#resultSummary'),
  emptyState: document.querySelector('#emptyState'),
  emptyReset: document.querySelector('#emptyReset'),
  loadError: document.querySelector('#loadError'),
  retryButton: document.querySelector('#retryButton'),
  updateStatus: document.querySelector('#updateStatus'),
  totalCount: document.querySelector('#totalCount'),
  totalUnit: document.querySelector('#totalUnit'),
  weekCount: document.querySelector('#weekCount'),
  weekUnit: document.querySelector('#weekUnit'),
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
  profileEnglish: document.querySelector('#profileEnglish'),
  foreignFunctionOptions: document.querySelector('#foreignFunctionOptions'),
  foreignIndustryOptions: document.querySelector('#foreignIndustryOptions'),
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
  applicationFlowIndex: document.querySelector('#applicationFlowIndex'),
  applicationFlowTitle: document.querySelector('#applicationFlowTitle'),
  applicationEvidenceSummary: document.querySelector('#applicationEvidenceSummary'),
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
  foreignTodaySummary: document.querySelector('#foreignTodaySummary'),
  foreignSummaryTitle: document.querySelector('#foreignSummaryTitle'),
  foreignSummaryText: document.querySelector('#foreignSummaryText'),
  foreignSummaryDate: document.querySelector('#foreignSummaryDate'),
  foreignTodayItems: document.querySelector('#foreignTodayItems'),
  foreignTodayOnly: document.querySelector('#foreignTodayOnly'),
  summaryHistoryList: document.querySelector('#summaryHistoryList'),
};

const initialParams = new URLSearchParams(location.search);
let activeChannel = channelFromSearchParams(initialParams);
let profile = normalizeProfile(readJson(STORAGE.profile, DEFAULT_PROFILE));
let workspace = normalizeWorkspace(
  readJson(STORAGE.workspace, null),
  readJson(STORAGE.saved, []),
);
let activeJobId = null;
const payloads = {
  public: { generatedAt: null, jobs: [], sourceStatus: [] },
  foreign: { generatedAt: null, campaigns: [], sourceStatus: [], todaySummary: null, summaryHistory: [] },
};
const loadStates = {
  public: { loaded: false, loading: false, error: null, promise: null },
  foreign: { loaded: false, loading: false, error: null, promise: null },
};
const states = {
  public: {
    ...stateFromSearchParams(activeChannel === 'public' ? initialParams : new URLSearchParams()),
    savedOnly: false,
    savedIds: workspace.savedIds,
  },
  foreign: {
    ...DEFAULT_FOREIGN_STATE,
    ...foreignStateFromSearchParams(activeChannel === 'foreign' ? initialParams : new URLSearchParams()),
    todayOnly: activeChannel === 'foreign' && initialParams.get('today') === '1',
    savedOnly: false,
    savedIds: workspace.savedIds,
  },
};

function readJson(key, fallback) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key));
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function activePayload() {
  return payloads[activeChannel];
}

function activeState() {
  return states[activeChannel];
}

function allRecords() {
  return [...payloads.public.jobs, ...payloads.foreign.campaigns];
}

function findJobById(id) {
  return allRecords().find((item) => item.id === id) || null;
}

function recordSourceName(job) {
  return String(job?.source?.name || job?.source || '来源待核');
}

function recordCompanyName(job) {
  return String(job?.company?.name || job?.company || '');
}

function persistWorkspace(nextWorkspace, { rerender = true } = {}) {
  workspace = normalizeWorkspace(nextWorkspace);
  localStorage.setItem(STORAGE.workspace, JSON.stringify(workspace));
  localStorage.setItem(STORAGE.saved, JSON.stringify(workspace.savedIds));
  for (const channel of Object.keys(states)) {
    states[channel] = { ...states[channel], savedIds: workspace.savedIds };
  }
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
  const job = findJobById(jobId);
  if (!job) return null;
  return job.channel === 'foreign'
    ? filterForeignByMatchMode([job], 'all', profile)[0] || null
    : filterByMatchMode([job], 'all', profile)[0] || null;
}

function ensureFavorite(jobId) {
  if (!workspace.savedIds.includes(jobId)) workspace = toggleSaved(workspace, jobId);
}

function applyView(value) {
  const view = VALID_VIEWS.has(value) ? value : 'editorial';
  document.body.classList.remove('view-editorial', 'view-terminal', 'view-calm');
  document.body.classList.add(`view-${view}`);
  const radio = els.viewOptions.querySelector(`input[value="${view}"]`);
  if (radio) radio.checked = true;
  localStorage.setItem(STORAGE.view, view);
}

function setSelectValue(select, value, fallback) {
  const next = String(value ?? fallback);
  select.value = [...select.options].some((option) => option.value === next) ? next : fallback;
}

function syncMatchTabs() {
  const definitions = MATCH_UI[activeChannel];
  [...els.matchTabs.querySelectorAll('.match-tab')].forEach((tab, index) => {
    const [value, label] = definitions[index];
    tab.dataset.match = value;
    tab.textContent = label;
  });
}

function syncControls() {
  const state = activeState();
  els.search.value = state.q || '';
  syncMatchTabs();
  for (const tab of els.matchTabs.querySelectorAll('[data-match]')) {
    const active = tab.dataset.match === state.match;
    tab.classList.toggle('is-active', active);
    tab.setAttribute('aria-pressed', String(active));
  }
  if (activeChannel === 'public') {
    setSelectValue(els.location, state.location, '全部');
    setSelectValue(els.audience, state.audience, '全部');
    setSelectValue(els.freshness, state.freshness, 'all');
    setSelectValue(els.sort, state.sort, 'newest');
    for (const tab of els.categoryTabs.querySelectorAll('[data-category]')) {
      tab.classList.toggle('is-active', tab.dataset.category === state.category);
    }
  } else {
    setSelectValue(els.foreignCompany, state.company, '全部');
    setSelectValue(els.foreignFunction, state.jobFunction, '全部');
    setSelectValue(els.foreignCity, state.city, '全部');
    setSelectValue(els.foreignGraduationYear, state.graduationYear, '2027');
    setSelectValue(els.foreignDegree, state.degree, '全部');
    setSelectValue(els.foreignRecruitmentType, state.recruitmentType, '全部');
    setSelectValue(els.foreignFreshness, state.freshness, 'all');
    setSelectValue(els.foreignDeadline, state.deadline, 'open');
    setSelectValue(els.foreignSort, state.sort, 'newest');
  }
  els.savedOnly.setAttribute('aria-pressed', String(Boolean(state.savedOnly)));
  els.savedCount.textContent = String(workspace.savedIds.length);
  els.workspaceButton.textContent = workspace.savedIds.length
    ? `收藏备份 ${workspace.savedIds.length}`
    : '收藏备份';
  const todayPressed = activeChannel === 'foreign' && Boolean(state.todayOnly);
  els.foreignTodayOnly.setAttribute('aria-pressed', String(todayPressed));
  els.foreignTodayOnly.textContent = todayPressed ? '查看全部活动' : '只看今日新增';
}

function updateUrl(historyMode = 'replace') {
  const state = activeState();
  const params = searchParamsForChannel(activeChannel, state);
  if (activeChannel === 'foreign' && state.todayOnly) params.set('today', '1');
  else params.delete('today');
  const next = params.size ? `${location.pathname}?${params}` : location.pathname;
  if (historyMode === 'push') history.pushState(null, '', next);
  else history.replaceState(null, '', next);
}

function setState(patch, { updateQuery = true } = {}) {
  states[activeChannel] = { ...states[activeChannel], ...patch, savedIds: workspace.savedIds };
  syncControls();
  render();
  if (updateQuery) updateUrl('replace');
}

function setMultilineTitle(lines) {
  const nodes = [];
  lines.forEach((line, index) => {
    if (index) nodes.push(document.createElement('br'));
    nodes.push(document.createTextNode(line));
  });
  els.pageTitle.replaceChildren(...nodes);
}

function renderChannelShell() {
  const copy = CHANNEL_COPY[activeChannel];
  document.body.dataset.channel = activeChannel;
  for (const link of [els.publicChannelLink, els.foreignChannelLink]) {
    if (link.dataset.channel === activeChannel) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  for (const field of document.querySelectorAll('[data-channel-fields]')) {
    field.hidden = field.dataset.channelFields !== activeChannel;
  }
  els.pageEyebrow.textContent = copy.eyebrow;
  setMultilineTitle(copy.title);
  els.pageIntro.textContent = copy.intro;
  els.search.placeholder = copy.placeholder;
  els.profileSummaryTitle.textContent = copy.profileTitle;
  els.profilePrivacy.textContent = copy.profilePrivacy;
  els.totalLabel.textContent = copy.totalLabel;
  els.weekLabel.textContent = copy.weekLabel;
  els.totalUnit.textContent = activeChannel === 'foreign' ? '场' : '条';
  els.weekUnit.textContent = activeChannel === 'foreign' ? '场' : '条';
  [...els.methodSteps.children].forEach((item, index) => {
    item.querySelector('strong').textContent = copy.method[index][0];
    item.querySelector('p').textContent = copy.method[index][1];
  });
  syncMatchTabs();
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.content = copy.intro;
}

function switchChannel(channel, { historyMode = 'push' } = {}) {
  if (!Object.hasOwn(CHANNELS, channel)) return;
  activeChannel = channel;
  states[channel] = { ...states[channel], savedIds: workspace.savedIds };
  renderChannelShell();
  renderProfileSummary();
  syncControls();
  renderCounts();
  renderSourceStatus();
  renderTodaySummary();
  render();
  if (historyMode !== 'none') updateUrl(historyMode);
  if (!loadStates[channel].loaded && !loadStates[channel].loading) loadChannelData(channel);
}

function buildMetaItem(text, className = '') {
  const item = document.createElement('li');
  item.textContent = text;
  if (className) item.className = className;
  return item;
}

function campaignTypeLabel(value) {
  return {
    campus_recruitment: '校园招聘',
    graduate_program: 'Graduate Program',
    management_trainee: '管培生',
    supplemental: '补录',
  }[value] || '正式校园招聘';
}

function publicCardModel(job) {
  const deadline = deadlineState(job.deadline);
  return {
    date: job.publishedAt,
    dateEstimated: Boolean(job.dateEstimated),
    category: job.category,
    source: recordSourceName(job),
    badge: job.official ? '可核验来源' : '',
    badgeTone: 'official',
    title: job.title,
    url: job.url,
    summary: job.summary || '',
    meta: [
      [job.location || '全国', ''],
      [job.audience === '不限' ? '对象见公告' : job.audience, ''],
      [deadline.label, deadline.tone],
    ],
    actionLabel: '查看原公告',
    matchCaption: '依据官方详情页原文线索',
  };
}

function foreignCardModel(campaign) {
  const deadline = campaign.status === 'stale'
    ? { label: '长期未更新，待复核', tone: 'muted' }
    : campaign.status === 'expired'
      ? { label: '已截止', tone: 'muted' }
      : deadlineState(campaign.deadline);
  const yearLabel = campaign.graduateYears.length
    ? `${campaign.graduateYears.join('、')}届`
    : '届别见公告';
  return {
    date: campaign.publishedAt || String(campaign.firstSeenAt || '').slice(0, 10),
    dateEstimated: Boolean(campaign.dateEstimated),
    category: campaignTypeLabel(campaign.campaignType),
    source: recordSourceName(campaign),
    badge: campaign.official ? '企业官方' : '第三方信息，请核验',
    badgeTone: campaign.official ? 'official' : 'third-party',
    title: campaign.title,
    url: campaign.url,
    summary: campaign.summary || '',
    meta: [
      [campaign.company.name, ''],
      [campaign.cities.length ? campaign.cities.join('、') : '中国多地', ''],
      [yearLabel, ''],
      [campaign.educationLevels.length ? campaign.educationLevels.join('、') : '学历见公告', ''],
      [deadline.label, deadline.tone],
      ...campaign.jobFunctions.map((value) => [value, '']),
    ],
    actionLabel: campaign.official ? '查看企业招聘页' : '查看第三方信息',
    matchCaption: '依据招聘公告与结构化线索',
  };
}

function evidenceText(value) {
  if (Array.isArray(value)) return value.join('、');
  if (value && typeof value === 'object') return Object.values(value).join('、');
  return String(value ?? '');
}

function renderJob(job) {
  const model = job.channel === 'foreign' ? foreignCardModel(job) : publicCardModel(job);
  const fragment = els.jobTemplate.content.cloneNode(true);
  const item = fragment.querySelector('.job-item');
  const time = fragment.querySelector('time');
  const titleLink = fragment.querySelector('h3 a');
  const summary = fragment.querySelector('.job-summary');
  const badge = fragment.querySelector('.official-badge');
  const saveButton = fragment.querySelector('.save-button');
  const openLink = fragment.querySelector('.open-link');
  const saved = workspace.savedIds.includes(job.id);
  const match = job._match || {
    tier: 'verify', label: '需要核对', score: 0, reasons: [], cautions: [], evidence: {},
  };

  item.dataset.id = job.id;
  item.dataset.channel = job.channel || 'public';
  if (model.date) time.dateTime = model.date;
  time.textContent = model.dateEstimated ? '日期待核' : model.date || '日期待核';
  fragment.querySelector('.relative-date').textContent = model.dateEstimated
    ? '以原文为准'
    : formatRelativeDate(model.date);
  fragment.querySelector('.category-badge').textContent = model.category;
  fragment.querySelector('.source-name').textContent = model.source;
  badge.hidden = !model.badge;
  badge.classList.toggle('third-party', model.badgeTone === 'third-party');
  badge.textContent = model.badge;
  titleLink.href = model.url;
  titleLink.textContent = model.title;
  summary.textContent = model.summary;
  fragment.querySelector('.job-meta').append(
    ...model.meta.filter(([text]) => text).map(([text, tone]) => buildMetaItem(text, tone)),
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
  matchExplain.classList.add(`tier-${match.tier || 'verify'}`);
  matchLabel.textContent = match.label || '需要核对';
  fragment.querySelector('.match-caption').textContent = model.matchCaption;
  const reasons = match.reasons?.length
    ? match.reasons.slice(0, 2)
    : [job.channel === 'foreign' ? '请设置目标职能、城市或行业以获得匹配理由' : '暂未发现明确的专业或文字职责线索'];
  matchReasons.replaceChildren(...reasons.map((reason) => buildMetaItem(reason)));
  matchCaution.textContent = match.cautions?.[0] || '';
  matchCaution.hidden = !match.cautions?.length;
  const evidenceKeys = new Set(match.evidenceKeys || [...(match.majorTags || []), ...(match.roleTags || [])]);
  const allEvidence = Object.entries(match.evidence || {});
  const evidenceItems = (evidenceKeys.size
    ? allEvidence.filter(([key]) => evidenceKeys.has(key))
    : allEvidence
  ).filter(([, value]) => value).slice(0, 3)
    .map(([key, value]) => buildMetaItem(`${key}：${evidenceText(value)}`));
  matchEvidence.hidden = evidenceItems.length === 0;
  matchEvidence.querySelector('ul').replaceChildren(...evidenceItems);
  saveButton.dataset.save = job.id;
  saveButton.setAttribute('aria-pressed', String(saved));
  saveButton.setAttribute('aria-label', `${saved ? '取消收藏' : '收藏'}：${job.title}`);
  saveButton.textContent = saved ? '已收藏' : '收藏';
  const applicationButton = fragment.querySelector('.application-button');
  applicationButton.dataset.application = job.id;
  applicationButton.setAttribute('aria-label', `打开申请助手：${job.title}`);
  applicationButton.textContent = workspace.notes[job.id] ? '申请助手 · 有备注' : '申请助手';
  openLink.href = model.url;
  openLink.textContent = `${model.actionLabel} ↗`;
  return fragment;
}

function currentTodaySummary() {
  const payload = payloads.foreign;
  if (payload.todaySummary?.date) return payload.todaySummary;
  return payload.summaryHistory[0] || null;
}

function render() {
  const status = loadStates[activeChannel];
  const source = activeChannel === 'public' ? payloads.public.jobs : payloads.foreign.campaigns;
  els.loadError.hidden = !status.error;
  if (!status.loaded) {
    els.results.replaceChildren();
    els.results.setAttribute('aria-busy', String(status.loading));
    els.resultSummary.textContent = status.error ? '数据读取失败' : '正在加载…';
    els.emptyState.hidden = true;
    return;
  }
  let jobs;
  let labels;
  if (activeChannel === 'public') {
    const state = states.public;
    const matched = filterByMatchMode(source, state.match, profile);
    jobs = sortJobs(filterJobs(matched, state), state.sort);
    labels = {
      all: '全部公告', recommended: '适合我的', exact: '专业相关', writing: '文字岗位', verify: '需要核对',
    };
  } else {
    const state = states.foreign;
    const filtered = filterForeignCampaigns(source, state);
    const matched = filterForeignByMatchMode(filtered, state.match, profile);
    const todayIds = new Set((currentTodaySummary()?.items || []).map((item) => item.id));
    const scoped = state.todayOnly ? matched.filter((item) => todayIds.has(item.id)) : matched;
    jobs = sortForeignCampaigns(scoped, state.sort);
    labels = {
      all: '全部校招', recommended: '适合我的', function: '职能匹配', location: '地点匹配', verify: '需要核验',
    };
  }
  els.results.replaceChildren(...jobs.map(renderJob));
  els.results.setAttribute('aria-busy', 'false');
  const state = activeState();
  els.feedTitle.textContent = state.todayOnly ? '今日新增' : labels[state.match] || '最新招聘';
  const noun = activeChannel === 'public' ? '条' : '场';
  const caution = activeChannel === 'public' ? '匹配不代替资格审核' : '申请条件仍须核对招聘原文';
  els.resultSummary.textContent = state.savedOnly
    ? `收藏中有 ${jobs.length} ${noun}符合条件`
    : `${labels[state.match] || '当前范围'}共 ${jobs.length} ${noun} · ${caution}`;
  els.emptyState.hidden = jobs.length !== 0 || source.length === 0;
  document.title = activeChannel === 'public'
    ? (jobs.length === source.length ? '招考雷达｜公开招考信息聚合' : `${jobs.length} 条结果｜招考雷达`)
    : (jobs.length === source.length ? '外企校招｜招考雷达' : `${jobs.length} 场外企校招｜招考雷达`);
}

function renderProfileSummary() {
  const parts = [profile.degree, profile.major];
  if (profile.researchDirection) parts.push(profile.researchDirection);
  parts.push(profile.graduationYear ? `${profile.graduationYear}届` : '毕业年份待设置');
  if (activeChannel === 'public') {
    if (profile.politicalStatus !== '未设置') parts.push(profile.politicalStatus);
    if (profile.preferredLocations.length) parts.push(`偏好：${profile.preferredLocations.join('、')}`);
  } else {
    if (profile.targetFunctions?.length) parts.push(`职能：${profile.targetFunctions.join('、')}`);
    if (profile.preferredIndustries?.length) parts.push(`行业：${profile.preferredIndustries.join('、')}`);
    if (profile.englishLevel && profile.englishLevel !== '未设置') parts.push(profile.englishLevel);
    if (profile.preferredLocations.length) parts.push(`城市：${profile.preferredLocations.join('、')}`);
  }
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
  const isForeign = job.channel === 'foreign';
  const progress = workspace.progress[job.id] || { steps: [], materials: [] };
  els.applicationTitle.textContent = job.title;
  els.applicationFlowIndex.textContent = isForeign ? '01 / 申请流程' : '01 / 报名流程';
  els.applicationFlowTitle.textContent = isForeign ? '五步申请核对' : '五步报名核对';
  els.applicationEvidenceSummary.textContent = isForeign ? '查看申请原文证据' : '查看报名原文证据';
  els.applicationOfficialLink.href = job.url;
  els.applicationOfficialLink.textContent = job.channel === 'foreign'
    ? (job.official ? '查看企业招聘页 ↗' : '查看第三方信息并核验 ↗')
    : '核对官方原文 ↗';
  renderApplicationAlerts(job);
  els.applicationSteps.replaceChildren(...guide.steps.map((step) => (
    applicationCheckRow(step, 'steps', new Set(progress.steps))
  )));
  els.materialChecklist.replaceChildren(...guide.materials.map((material) => (
    applicationCheckRow(material, 'materials', new Set(progress.materials))
  )));
  if (job.channel === 'foreign') {
    els.materialsNote.textContent = guide.materialsAreGeneric
      ? '尚未提取到完整材料要求，先按通用清单准备，并以企业招聘页为准。'
      : `已识别 ${guide.materials.length} 项申请材料线索，请对照招聘页复核。`;
  } else {
    els.materialsNote.textContent = guide.materialsAreGeneric
      ? '未从正文提取到完整材料清单，以下为通用核对项，必须再看原公告和职位表。'
      : `从官方正文提取到 ${guide.materials.length} 项材料线索；仍请逐项对照原文。`;
  }
  const evidenceItems = Object.entries(guide.evidence || {})
    .filter(([, value]) => value)
    .slice(0, 12)
    .map(([key, value]) => buildMetaItem(`${key}：${evidenceText(value)}`));
  els.applicationEvidence.hidden = evidenceItems.length === 0;
  els.applicationEvidence.querySelector('ul').replaceChildren(...evidenceItems);
  els.jobNote.value = workspace.notes[job.id] || '';
  els.noteCounter.textContent = `${els.jobNote.value.length}/500`;
  els.applicationStatus.textContent = workspace.savedIds.includes(job.id)
    ? '该招聘活动已加入收藏工作区。'
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
  if (!workspace.savedIds.length) {
    const empty = document.createElement('li');
    empty.className = 'workspace-empty';
    empty.textContent = '还没有收藏岗位。收藏后可以在这里统一备份备注和申请进度。';
    els.workspaceList.replaceChildren(empty);
    return;
  }
  const items = workspace.savedIds.map((id) => {
    const job = findJobById(id);
    const item = document.createElement('li');
    const copy = document.createElement('div');
    const title = document.createElement('strong');
    const meta = document.createElement('small');
    const note = document.createElement('p');
    title.textContent = job?.title || `暂未收录的历史收藏（${id}）`;
    meta.textContent = job
      ? [recordCompanyName(job), recordSourceName(job), job.deadline ? `${job.deadline}截止` : '截止时间待确认'].filter(Boolean).join(' · ')
      : '仍会保留本地备注和进度';
    note.textContent = workspace.notes[id] || '暂无备注';
    copy.append(title, meta, note);
    item.append(copy);
    if (job) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.workspaceOpen = id;
      button.textContent = '打开申请助手';
      item.append(button);
    }
    return item;
  });
  els.workspaceList.replaceChildren(...items);
}

async function openWorkspaceDialog() {
  renderWorkspaceList();
  const pending = Object.keys(loadStates).filter((channel) => !loadStates[channel].loaded);
  els.workspaceStatus.textContent = pending.length
    ? '正在补充读取两个频道的收藏信息…'
    : '备份文件只包含收藏岗位、备注和清单进度。';
  els.workspaceDialog.showModal();
  if (pending.length) {
    await Promise.allSettled(pending.map((channel) => loadChannelData(channel)));
    renderWorkspaceList();
    els.workspaceStatus.textContent = '备份文件只包含收藏岗位、备注和清单进度。';
  }
}

function buildProfileCheckbox(value, name) {
  const label = document.createElement('label');
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.name = name;
  input.value = value;
  label.append(input, document.createTextNode(value));
  return label;
}

function populateProfileOptions() {
  const functions = Array.from(FOREIGN_FUNCTIONS || []);
  const industries = Array.from(FOREIGN_INDUSTRIES || []);
  const englishLevels = Array.from(FOREIGN_ENGLISH_LEVELS || []);
  els.foreignFunctionOptions.replaceChildren(...functions.map((value) => buildProfileCheckbox(value, 'foreignFunction')));
  els.foreignIndustryOptions.replaceChildren(...industries.map((value) => buildProfileCheckbox(value, 'foreignIndustry')));
  els.profileEnglish.replaceChildren(...englishLevels.map((value) => new Option(
    value === '未设置' ? '暂不设置' : value,
    value,
  )));
}

function fillProfileForm(value = profile) {
  els.profileMajor.value = value.major;
  els.profileDirection.value = value.researchDirection;
  els.profileGraduationYear.value = value.graduationYear;
  els.profilePolitical.value = value.politicalStatus;
  els.profileLocations.value = value.preferredLocations.join('、');
  setSelectValue(els.profileEnglish, value.englishLevel, '未设置');
  const roles = new Set(value.roleInterests);
  const certificates = new Set(value.certificates);
  const targetFunctions = new Set(value.targetFunctions || []);
  const industries = new Set(value.preferredIndustries || []);
  for (const input of els.profileForm.querySelectorAll('input[name="profileRole"]')) input.checked = roles.has(input.value);
  for (const input of els.profileForm.querySelectorAll('input[name="profileCertificate"]')) input.checked = certificates.has(input.value);
  for (const input of els.profileForm.querySelectorAll('input[name="foreignFunction"]')) input.checked = targetFunctions.has(input.value);
  for (const input of els.profileForm.querySelectorAll('input[name="foreignIndustry"]')) input.checked = industries.has(input.value);
}

function openProfileDialog() {
  fillProfileForm();
  els.profileDialog.showModal();
}

function renderCounts() {
  if (activeChannel === 'public') {
    const jobs = payloads.public.jobs;
    const weekJobs = filterJobs(jobs.filter((job) => !job.dateEstimated), {
      q: '', category: '全部', location: '全部', audience: '全部', freshness: '7',
      savedOnly: false, savedIds: [],
    });
    els.totalCount.textContent = String(jobs.length);
    els.weekCount.textContent = String(weekJobs.length);
    for (const category of ['全部', '公务员', '事业单位', '央国企']) {
      const count = category === '全部' ? jobs.length : jobs.filter((job) => job.category === category).length;
      const node = document.querySelector(`[data-count="${category}"]`);
      if (node) node.textContent = String(count);
    }
  } else {
    const campaigns = payloads.foreign.campaigns;
    const recent = payloads.foreign.summaryHistory.reduce((sum, item) => sum + item.addedCount, 0);
    els.totalCount.textContent = String(campaigns.length);
    els.weekCount.textContent = String(recent);
  }
  const records = activeChannel === 'public' ? payloads.public.jobs : payloads.foreign.campaigns;
  const sourceStatuses = activePayload().sourceStatus || [];
  const availableSources = sourceStatuses.filter((source) => ['ok', 'empty'].includes(source.status)).length;
  const fallbackSources = new Set(records.map(recordSourceName)).size;
  els.sourceCount.textContent = String(availableSources || fallbackSources);
}

function renderLocations() {
  const preferredOrder = ['全国', '北京', '上海', '广东', '江苏', '浙江', '山东', '河南', '湖北', '湖南', '四川', '重庆'];
  const locations = [...new Set(payloads.public.jobs.map((job) => job.location).filter(Boolean))]
    .sort((a, b) => {
      const aIndex = preferredOrder.indexOf(a);
      const bIndex = preferredOrder.indexOf(b);
      if (aIndex !== -1 || bIndex !== -1) return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
      return a.localeCompare(b, 'zh-CN');
    });
  els.location.replaceChildren(new Option('全部地区', '全部'), ...locations.map((value) => new Option(value, value)));
}

function renderForeignOptions() {
  const campaigns = payloads.foreign.campaigns;
  const companies = [...new Map(campaigns.map((item) => [item.company.id, item.company.name])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1], 'zh-CN'));
  const functions = [...new Set(campaigns.flatMap((item) => item.jobFunctions))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const cities = [...new Set(campaigns.flatMap((item) => item.cities))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  els.foreignCompany.replaceChildren(
    new Option('全部企业', '全部'),
    ...companies.map(([id, name]) => new Option(name, id)),
  );
  els.foreignFunction.replaceChildren(
    new Option('全部职能', '全部'),
    ...functions.map((value) => new Option(value, value)),
  );
  els.foreignCity.replaceChildren(
    new Option('全部城市', '全部'),
    ...cities.map((value) => new Option(value, value)),
  );
}

function renderSourceStatus() {
  const statuses = activePayload().sourceStatus || [];
  if (!statuses.length) {
    const item = document.createElement('li');
    item.textContent = activeChannel === 'foreign'
      ? '当前快照未提供来源运行明细；招聘卡片仍会逐条标识官网或第三方来源。'
      : '当前为初始数据快照；首次自动更新后会显示各来源状态。';
    els.sourceList.replaceChildren(item);
    return;
  }
  const items = statuses.map((source) => {
    const item = document.createElement('li');
    const name = document.createElement('strong');
    const status = document.createElement('span');
    name.textContent = source.name || source.id || '未命名来源';
    status.className = `source-state ${source.status}`;
    status.textContent = source.status === 'ok'
      ? `正常 · ${source.count || 0} 条`
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

function normalizeForeignPayload(value) {
  if (!value || !Array.isArray(value.campaigns)) throw new Error('invalid foreign campaigns payload');
  const history = normalizeDailySummaries(value.summaryHistory || []);
  const today = normalizeDailySummaries(value.todaySummary ? [value.todaySummary] : [])[0] || history[0] || null;
  return {
    ...value,
    campaigns: value.campaigns.map((item) => ({ ...normalizeForeignCampaign(item), channel: 'foreign' })),
    sourceStatus: Array.isArray(value.sourceStatus) ? value.sourceStatus : [],
    todaySummary: today,
    summaryHistory: history,
  };
}

async function loadChannelData(channel, { force = false } = {}) {
  const status = loadStates[channel];
  if (status.loading) return status.promise;
  if (status.loaded && !force) return payloads[channel];
  status.loading = true;
  status.error = null;
  if (channel === activeChannel) {
    els.results.setAttribute('aria-busy', 'true');
    els.loadError.hidden = true;
    els.resultSummary.textContent = '正在加载…';
  }
  status.promise = (async () => {
    try {
      const response = await fetch(CHANNELS[channel].dataUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const nextPayload = await response.json();
      if (channel === 'public') {
        if (!Array.isArray(nextPayload.jobs)) throw new Error('invalid jobs payload');
        payloads.public = {
          ...nextPayload,
          jobs: nextPayload.jobs.map((job) => ({ ...job, channel: 'public' })),
          sourceStatus: Array.isArray(nextPayload.sourceStatus) ? nextPayload.sourceStatus : [],
        };
        renderLocations();
      } else {
        payloads.foreign = normalizeForeignPayload(nextPayload);
        renderForeignOptions();
      }
      status.loaded = true;
      status.error = null;
      renderWorkspaceList();
      if (channel === activeChannel) {
        els.updateStatus.textContent = `${formatUpdatedAt(activePayload().generatedAt)} · 每日自动检查`;
        renderCounts();
        renderSourceStatus();
        renderTodaySummary();
        syncControls();
        render();
      }
      return payloads[channel];
    } catch (error) {
      status.loaded = false;
      status.error = error;
      if (channel === activeChannel) {
        els.results.setAttribute('aria-busy', 'false');
        els.loadError.hidden = false;
        els.resultSummary.textContent = '数据读取失败';
        render();
      }
      return null;
    } finally {
      status.loading = false;
      status.promise = null;
    }
  })();
  return status.promise;
}

function createSummaryBadge(official) {
  const badge = document.createElement('span');
  badge.className = `summary-source-badge${official ? '' : ' third-party'}`;
  badge.textContent = official ? '企业官方' : '第三方信息，请核验';
  return badge;
}

function renderTodaySummary() {
  if (activeChannel !== 'foreign') return;
  const summary = currentTodaySummary();
  if (!loadStates.foreign.loaded || !summary) {
    els.foreignSummaryTitle.textContent = '今日新增外企校招';
    els.foreignSummaryText.textContent = loadStates.foreign.error ? '今日摘要暂时无法读取。' : '正在读取今日摘要…';
    els.foreignSummaryDate.textContent = '';
    els.foreignTodayItems.replaceChildren();
    els.summaryHistoryList.replaceChildren();
    els.foreignTodayOnly.disabled = true;
    return;
  }
  els.foreignSummaryDate.dateTime = summary.date;
  els.foreignSummaryDate.textContent = summary.date;
  if (summary.bootstrap && summary.addedCount > 0) {
    els.foreignSummaryTitle.textContent = `今日新增 ${summary.addedCount} 场外企校招`;
    els.foreignSummaryText.textContent = `首批建库基线为 ${summary.baselineCount} 场；这里仅列出基线建立后今天新发现的活动。`;
  } else if (summary.bootstrap) {
    els.foreignSummaryTitle.textContent = `首批收录 ${summary.baselineCount} 场外企校招`;
    els.foreignSummaryText.textContent = '这是首次建库基线，不把历史招聘活动标记为今日新增。';
  } else {
    els.foreignSummaryTitle.textContent = `今日新增 ${summary.addedCount} 场外企校招`;
    els.foreignSummaryText.textContent = summary.addedCount
      ? '按北京时间首次成功发现计算；申请前请再次核对企业招聘原文。'
      : '今天暂未发现新的合格活动，现有招聘仍可继续检索。';
  }
  const items = (summary.items || []).map((entry) => {
    const item = document.createElement('li');
    const company = document.createElement('strong');
    const link = document.createElement('a');
    company.textContent = entry.company;
    link.href = entry.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = entry.title;
    item.append(company, link, createSummaryBadge(entry.official));
    return item;
  });
  els.foreignTodayItems.replaceChildren(...items);
  els.foreignTodayOnly.disabled = summary.addedCount === 0;
  const historyItems = payloads.foreign.summaryHistory.map((entry) => {
    const item = document.createElement('li');
    const date = document.createElement('strong');
    const count = document.createElement('span');
    date.textContent = entry.date;
    count.textContent = entry.bootstrap
      ? `首批收录 ${entry.baselineCount} 场${entry.addedCount ? ` · 随后新增 ${entry.addedCount} 场` : ''}`
      : `新增 ${entry.addedCount} 场`;
    item.append(date, count);
    return item;
  });
  els.summaryHistoryList.replaceChildren(...historyItems);
}

function resetFilters() {
  if (activeChannel === 'public') {
    states.public = {
      ...stateFromSearchParams(new URLSearchParams()),
      savedOnly: false,
      savedIds: workspace.savedIds,
    };
  } else {
    states.foreign = {
      ...DEFAULT_FOREIGN_STATE,
      todayOnly: false,
      savedOnly: false,
      savedIds: workspace.savedIds,
    };
  }
  syncControls();
  render();
  updateUrl('replace');
  els.search.focus();
}

els.filters.addEventListener('submit', (event) => event.preventDefault());
els.channelNav.addEventListener('click', (event) => {
  const channel = event.target.closest('[data-channel]')?.dataset.channel;
  if (!channel) return;
  event.preventDefault();
  if (channel !== activeChannel) switchChannel(channel, { historyMode: 'push' });
});
els.search.addEventListener('input', () => setState({ q: els.search.value, todayOnly: false }));
els.location.addEventListener('change', () => setState({ location: els.location.value }));
els.audience.addEventListener('change', () => setState({ audience: els.audience.value }));
els.freshness.addEventListener('change', () => setState({ freshness: els.freshness.value }));
els.sort.addEventListener('change', () => setState({ sort: els.sort.value }));
els.foreignCompany.addEventListener('change', () => setState({ company: els.foreignCompany.value, todayOnly: false }));
els.foreignFunction.addEventListener('change', () => setState({ jobFunction: els.foreignFunction.value, todayOnly: false }));
els.foreignCity.addEventListener('change', () => setState({ city: els.foreignCity.value, todayOnly: false }));
els.foreignGraduationYear.addEventListener('change', () => setState({ graduationYear: els.foreignGraduationYear.value, todayOnly: false }));
els.foreignDegree.addEventListener('change', () => setState({ degree: els.foreignDegree.value, todayOnly: false }));
els.foreignRecruitmentType.addEventListener('change', () => setState({ recruitmentType: els.foreignRecruitmentType.value, todayOnly: false }));
els.foreignFreshness.addEventListener('change', () => setState({ freshness: els.foreignFreshness.value, todayOnly: false }));
els.foreignDeadline.addEventListener('change', () => setState({ deadline: els.foreignDeadline.value, todayOnly: false }));
els.foreignSort.addEventListener('change', () => setState({ sort: els.foreignSort.value }));
els.categoryTabs.addEventListener('click', (event) => {
  const category = event.target.closest('[data-category]')?.dataset.category;
  if (category) setState({ category, savedOnly: false });
});
els.matchTabs.addEventListener('click', (event) => {
  const match = event.target.closest('[data-match]')?.dataset.match;
  if (!match) return;
  setState({ match, sort: match === 'all' ? 'newest' : 'match', savedOnly: false });
});
els.savedOnly.addEventListener('click', () => {
  const enabling = !activeState().savedOnly;
  setState({
    savedOnly: enabling,
    ...(activeChannel === 'foreign' && enabling ? { todayOnly: false } : {}),
  });
});
els.foreignTodayOnly.addEventListener('click', () => setState({
  todayOnly: !states.foreign.todayOnly,
  savedOnly: false,
}));
els.clearFilters.addEventListener('click', resetFilters);
els.foreignClearFilters.addEventListener('click', resetFilters);
els.emptyReset.addEventListener('click', resetFilters);
els.retryButton.addEventListener('click', () => loadChannelData(activeChannel, { force: true }));
els.results.addEventListener('click', (event) => {
  const applicationId = event.target.closest('[data-application]')?.dataset.application;
  if (applicationId) {
    openApplicationDialog(applicationId);
    return;
  }
  const id = event.target.closest('[data-save]')?.dataset.save;
  if (id) persistWorkspace(toggleSaved(workspace, id));
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
els.workspaceExport.addEventListener('click', async () => {
  const pending = Object.keys(loadStates).filter((channel) => !loadStates[channel].loaded);
  if (pending.length) {
    els.workspaceExport.disabled = true;
    els.workspaceStatus.textContent = '正在补充读取两个频道的数据，完成后自动导出…';
    await Promise.allSettled(pending.map((channel) => loadChannelData(channel)));
    els.workspaceExport.disabled = false;
  }
  const backup = exportWorkspace(workspace, allRecords());
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
  const job = findJobById(els.calendarExport.dataset.jobId);
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
    targetFunctions: data.getAll('foreignFunction'),
    preferredIndustries: data.getAll('foreignIndustry'),
    englishLevel: data.get('englishLevel'),
  });
  localStorage.setItem(STORAGE.profile, JSON.stringify(profile));
  renderProfileSummary();
  els.profileDialog.close();
  setState({ match: 'recommended', sort: 'match', savedOnly: false });
});
els.viewOptions.addEventListener('change', (event) => applyView(event.target.value));
window.addEventListener('popstate', () => {
  const params = new URLSearchParams(location.search);
  const channel = channelFromSearchParams(params);
  if (channel === 'public') {
    states.public = {
      ...stateFromSearchParams(params),
      savedOnly: false,
      savedIds: workspace.savedIds,
    };
  } else {
    states.foreign = {
      ...DEFAULT_FOREIGN_STATE,
      ...foreignStateFromSearchParams(params),
      todayOnly: params.get('today') === '1',
      savedOnly: false,
      savedIds: workspace.savedIds,
    };
  }
  switchChannel(channel, { historyMode: 'none' });
});
document.addEventListener('keydown', (event) => {
  const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
  if (event.key === '/' && !isTyping) {
    event.preventDefault();
    els.search.focus();
  }
});

populateProfileOptions();
applyView(localStorage.getItem(STORAGE.view) || 'editorial');
renderChannelShell();
persistWorkspace(workspace, { rerender: false });
renderProfileSummary();
syncControls();
renderCounts();
renderSourceStatus();
renderTodaySummary();
render();
Promise.allSettled([
  loadChannelData('public'),
  loadChannelData('foreign'),
]);
