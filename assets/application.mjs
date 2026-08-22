const SHANGHAI_DATE = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const GENERIC_MATERIALS = Object.freeze([
  { key: 'generic-position-table', label: '职位表与报名表' },
  { key: 'generic-id', label: '身份证明' },
  { key: 'generic-education', label: '学历学位与学信网材料' },
  { key: 'generic-other', label: '岗位要求的其他证明' },
]);

const FOREIGN_GENERIC_MATERIALS = Object.freeze([
  { key: 'foreign-resume', label: '中英文简历' },
  { key: 'foreign-transcript', label: '成绩单' },
  { key: 'foreign-education', label: '在读或学历证明' },
  { key: 'foreign-language', label: '语言成绩或证书' },
  { key: 'foreign-portfolio', label: '求职信、作品集或项目材料' },
]);

function parseDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const stamp = Date.UTC(year, month - 1, day);
  const check = new Date(stamp);
  if (
    check.getUTCFullYear() !== year
    || check.getUTCMonth() !== month - 1
    || check.getUTCDate() !== day
  ) return null;
  return { year, month, day, stamp };
}

function todayStamp(now) {
  const parts = Object.fromEntries(
    SHANGHAI_DATE.formatToParts(now)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, Number(part.value)]),
  );
  return Date.UTC(parts.year, parts.month - 1, parts.day);
}

function daysUntil(value, now = new Date()) {
  const parsed = parseDate(value);
  if (!parsed || Number.isNaN(now.getTime())) return null;
  return Math.round((parsed.stamp - todayStamp(now)) / 86_400_000);
}

function cleanList(value, limit = 20) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map((item) => String(item || '').trim()).filter(Boolean))].slice(0, limit);
}

function safeApplicationHints(job) {
  const hints = job?.applicationHints && typeof job.applicationHints === 'object'
    ? job.applicationHints
    : {};
  return {
    methods: cleanList(hints.methods, 6),
    materialTags: cleanList(hints.materialTags, 20),
    evidence: hints.evidence && typeof hints.evidence === 'object' ? { ...hints.evidence } : {},
  };
}

export function getJobAlerts(job = {}, match = {}, now = new Date()) {
  const alerts = [];
  const days = daysUntil(job.deadline, now);
  if (days !== null && days >= 0 && days <= 3) {
    alerts.push({
      type: 'deadline',
      label: days === 0 ? '今天截止' : `${days}天内截止`,
      detail: job.deadline,
    });
  }
  const isForeign = job.channel === 'foreign';
  const needsConditionCheck = isForeign
    ? match?.tier === 'verify' || match?.requiresVerification === true
    : match?.tier && match.tier !== 'exact';
  if (needsConditionCheck) {
    alerts.push({
      type: 'major',
      label: isForeign ? '申请条件待核对' : '专业待确认',
      detail: isForeign
        ? '请核对届别、学历、专业、语言要求和工作地点'
        : '请核对职位表中的专业名称与代码',
    });
  }
  if (isForeign && job.official === false) {
    alerts.push({
      type: 'source',
      label: '第三方信息，请核验',
      detail: '优先查找并核对企业官网或企业明确委托的申请入口',
    });
  }
  return alerts;
}

function publicSteps(methodText, materialsAreGeneric, materialCount) {
  return [
    { id: 'read', label: '阅读原公告与附件', detail: '确认公告状态、报名时间和具体职位表。' },
    { id: 'qualify', label: '核对具体岗位资格', detail: '逐项核对专业代码、学历学位、届别、政治面貌和经历。' },
    {
      id: 'materials',
      label: '准备并复核报名材料',
      detail: materialsAreGeneric
        ? '公告未提取到完整清单，以下为通用核对项，最终以原文为准。'
        : `已从公告正文识别 ${materialCount} 项材料，请对照原文复核。`,
    },
    { id: 'submit', label: '完成报名提交', detail: methodText },
    { id: 'retain', label: '留存凭证并跟进通知', detail: '保存提交截图或邮件，继续关注资格审查、笔试和面试通知。' },
  ];
}

function foreignSteps(methodText, materialsAreGeneric, materialCount) {
  return [
    { id: 'read', label: '核验招聘活动与入口', detail: '优先查看企业官网；第三方信息必须再次核对。' },
    { id: 'qualify', label: '核对申请条件', detail: '逐项核对学历、专业、2027届、语言要求和工作地点。' },
    {
      id: 'materials',
      label: '准备申请材料',
      detail: materialsAreGeneric
        ? '尚未提取到完整材料要求，按通用清单准备并以招聘页为准。'
        : `已识别 ${materialCount} 项材料线索，请对照招聘页复核。`,
    },
    { id: 'submit', label: '完成在线申请', detail: methodText },
    { id: 'retain', label: '跟进测评与面试', detail: '保存申请编号，留意在线测评、面试和补充材料通知。' },
  ];
}

export function buildApplicationGuide(job = {}) {
  const hints = safeApplicationHints(job);
  const isForeign = job.channel === 'foreign';
  const materialsAreGeneric = hints.materialTags.length === 0;
  const materials = materialsAreGeneric
    ? (isForeign ? FOREIGN_GENERIC_MATERIALS : GENERIC_MATERIALS).map((item) => ({ ...item }))
    : hints.materialTags.map((label) => ({ key: label, label }));
  const methodText = hints.methods.length
    ? isForeign
      ? `按招聘页说明通过${hints.methods.join('、')}提交`
      : `按公告说明通过${hints.methods.join('、')}提交`
    : isForeign
      ? '按企业招聘页指定方式提交；尚未识别到明确申请入口'
      : '按原公告指定方式提交；尚未识别到明确报名入口';
  return {
    methods: hints.methods,
    materials,
    materialsAreGeneric,
    evidence: hints.evidence,
    steps: isForeign
      ? foreignSteps(methodText, materialsAreGeneric, materials.length)
      : publicSteps(methodText, materialsAreGeneric, materials.length),
  };
}

function compactDate(parsed) {
  return `${String(parsed.year).padStart(4, '0')}${String(parsed.month).padStart(2, '0')}${String(parsed.day).padStart(2, '0')}`;
}

function nextDate(parsed) {
  const next = new Date(parsed.stamp + 86_400_000);
  return compactDate({
    year: next.getUTCFullYear(),
    month: next.getUTCMonth() + 1,
    day: next.getUTCDate(),
  });
}

function escapeCalendar(value) {
  return String(value || '')
    .replace(/\\/g, '\\\\')
    .replace(/\r?\n/g, '\\n')
    .replace(/([;,])/g, '\\$1');
}

function safeFilename(value) {
  return String(value || '招聘公告')
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 48) || '招聘公告';
}

export function buildCalendarFile(job = {}, now = new Date()) {
  const deadline = parseDate(job.deadline);
  if (!deadline) return null;
  const title = String(job.title || '招聘公告').trim() || '招聘公告';
  const url = /^https?:\/\//.test(String(job.url || '')) ? String(job.url) : '';
  const dtstamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  const uid = `${String(job.id || `${deadline.year}${deadline.month}${deadline.day}`)}@job-radar.local`;
  const deadlineNoun = job.channel === 'foreign' ? '申请截止' : '报名截止';
  const content = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Job Radar CN//Application Deadline//ZH',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${escapeCalendar(uid)}`,
    `DTSTAMP:${dtstamp}`,
    `DTSTART;VALUE=DATE:${compactDate(deadline)}`,
    `DTEND;VALUE=DATE:${nextDate(deadline)}`,
    `SUMMARY:${escapeCalendar(`${deadlineNoun}：${title}`)}`,
    `DESCRIPTION:${escapeCalendar(job.channel === 'foreign'
      ? '招考雷达提醒：请再次核对企业招聘页中的具体截止时刻和申请状态。'
      : '招考雷达提醒：请再次核对官方公告中的具体截止时刻和报名状态。')}`,
    ...(url ? [`URL:${url}`] : []),
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    'TRIGGER:-P3D',
    `DESCRIPTION:${deadlineNoun}前三天提醒`,
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
    '',
  ].join('\r\n');
  return {
    filename: `招考雷达-${job.deadline}-${safeFilename(title)}.ics`,
    content,
  };
}
