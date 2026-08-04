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
  if (match?.tier && match.tier !== 'exact') {
    alerts.push({
      type: 'major',
      label: '专业待确认',
      detail: '请核对职位表中的专业名称与代码',
    });
  }
  return alerts;
}

export function buildApplicationGuide(job = {}) {
  const hints = safeApplicationHints(job);
  const materialsAreGeneric = hints.materialTags.length === 0;
  const materials = materialsAreGeneric
    ? GENERIC_MATERIALS.map((item) => ({ ...item }))
    : hints.materialTags.map((label) => ({ key: label, label }));
  const methodText = hints.methods.length
    ? `按公告说明通过${hints.methods.join('、')}提交` 
    : '按原公告指定方式提交；尚未识别到明确报名入口';
  return {
    methods: hints.methods,
    materials,
    materialsAreGeneric,
    evidence: hints.evidence,
    steps: [
      { id: 'read', label: '阅读原公告与附件', detail: '确认公告状态、报名时间和具体职位表。' },
      { id: 'qualify', label: '核对具体岗位资格', detail: '逐项核对专业代码、学历学位、届别、政治面貌和经历。' },
      {
        id: 'materials',
        label: '准备并复核报名材料',
        detail: materialsAreGeneric
          ? '公告未提取到完整清单，以下为通用核对项，最终以原文为准。'
          : `已从公告正文识别 ${materials.length} 项材料，请对照原文复核。`,
      },
      { id: 'submit', label: '完成报名提交', detail: methodText },
      { id: 'retain', label: '留存凭证并跟进通知', detail: '保存提交截图或邮件，继续关注资格审查、笔试和面试通知。' },
    ],
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
    `SUMMARY:${escapeCalendar(`报名截止：${title}`)}`,
    `DESCRIPTION:${escapeCalendar('招考雷达提醒：请再次核对官方公告中的具体截止时刻和报名状态。')}`,
    ...(url ? [`URL:${url}`] : []),
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    'TRIGGER:-P3D',
    'DESCRIPTION:报名截止前三天提醒',
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
