export const PROFILE_ROLES = Object.freeze([
  '综合文字',
  '宣传文化',
  '编辑出版',
  '新媒体',
  '高校行政',
  '中文教育',
]);

export const FOREIGN_FUNCTIONS = Object.freeze([
  '市场/品牌',
  '内容/传播',
  '产品',
  '运营',
  '人力资源',
  '财务',
  '销售/商务',
  '供应链',
  '技术/研发',
  '数据/分析',
  '法务/合规',
  '咨询',
]);

export const FOREIGN_INDUSTRIES = Object.freeze([
  '科技/互联网',
  '软件/企业服务',
  '半导体/硬件',
  '工业/制造',
  '能源',
  '化工/材料',
  '消费品',
  '美妆',
  '食品/饮料',
  '零售/电商',
  '零售/家居',
  '体育',
  '咨询/专业服务',
  '金融',
  '医药/医疗',
  '汽车',
  '物流/供应链',
]);

export const FOREIGN_ENGLISH_LEVELS = Object.freeze([
  '未设置',
  '英语四级',
  '英语六级',
  '英语流利',
]);

export const DEFAULT_PROFILE = Object.freeze({
  degree: '硕士',
  major: '中国语言文学',
  researchDirection: '',
  graduationYear: '',
  graduateStatus: '应届',
  politicalStatus: '未设置',
  certificates: [],
  preferredLocations: [],
  roleInterests: [...PROFILE_ROLES],
  targetFunctions: [],
  preferredIndustries: [],
  englishLevel: '未设置',
});

const POLITICAL_STATUSES = new Set(['未设置', '中共党员', '中共预备党员', '共青团员', '群众', '其他']);
const MATCH_MODES = new Set(['all', 'recommended', 'exact', 'writing', 'verify']);
const FOREIGN_FUNCTION_SET = new Set(FOREIGN_FUNCTIONS);
const FOREIGN_INDUSTRY_SET = new Set(FOREIGN_INDUSTRIES);
const FOREIGN_ENGLISH_LEVEL_SET = new Set(FOREIGN_ENGLISH_LEVELS);
const CHINESE_MAJOR_TERMS = [
  '中国语言文学', '汉语言文学', '汉语言文字学', '语言学及应用语言学', '文艺学',
  '中国古代文学', '中国现当代文学', '古典文献学', '比较文学与世界文学',
];

function cleanText(value, limit = 80) {
  return String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

function cleanList(value, { allowed = null, limit = 12 } = {}) {
  const items = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[，,、]/)
      : [];
  return [...new Set(items.map((item) => cleanText(item, 30)).filter(Boolean))]
    .filter((item) => !allowed || allowed.has(item))
    .slice(0, limit);
}

export function normalizeProfile(value = {}) {
  const candidate = value && typeof value === 'object' ? value : {};
  const yearMatch = cleanText(candidate.graduationYear, 12).match(/20\d{2}/);
  const politicalStatus = cleanText(candidate.politicalStatus, 20);
  const roles = Object.hasOwn(candidate, 'roleInterests')
    ? cleanList(candidate.roleInterests, { allowed: new Set(PROFILE_ROLES), limit: PROFILE_ROLES.length })
    : [...DEFAULT_PROFILE.roleInterests];
  return {
    degree: cleanText(candidate.degree, 20) || DEFAULT_PROFILE.degree,
    major: cleanText(candidate.major, 60) || DEFAULT_PROFILE.major,
    researchDirection: cleanText(candidate.researchDirection, 60),
    graduationYear: yearMatch?.[0] || '',
    graduateStatus: candidate.graduateStatus === '社会' ? '社会' : '应届',
    politicalStatus: POLITICAL_STATUSES.has(politicalStatus) ? politicalStatus : '未设置',
    certificates: cleanList(candidate.certificates, { limit: 10 }),
    preferredLocations: cleanList(candidate.preferredLocations, { limit: 12 }),
    roleInterests: roles,
    targetFunctions: cleanList(candidate.targetFunctions, {
      allowed: FOREIGN_FUNCTION_SET,
      limit: FOREIGN_FUNCTIONS.length,
    }),
    preferredIndustries: cleanList(candidate.preferredIndustries, {
      allowed: FOREIGN_INDUSTRY_SET,
      limit: FOREIGN_INDUSTRIES.length,
    }),
    englishLevel: FOREIGN_ENGLISH_LEVEL_SET.has(cleanText(candidate.englishLevel, 20))
      ? cleanText(candidate.englishLevel, 20)
      : '未设置',
  };
}

function safeHints(job) {
  const hints = job?.profileHints && typeof job.profileHints === 'object' ? job.profileHints : {};
  return {
    majorTags: cleanList(hints.majorTags),
    roleTags: cleanList(hints.roleTags),
    qualificationTags: cleanList(hints.qualificationTags),
    graduateYears: cleanList(hints.graduateYears),
    evidence: hints.evidence && typeof hints.evidence === 'object' ? { ...hints.evidence } : {},
  };
}

function userHasChineseMajor(profile) {
  const text = `${profile.major} ${profile.researchDirection}`;
  return CHINESE_MAJOR_TERMS.some((term) => text.includes(term));
}

export function analyzeJob(job = {}, profileValue = DEFAULT_PROFILE) {
  const profile = normalizeProfile(profileValue);
  const hints = safeHints(job);
  const reasons = [];
  const cautions = [];
  let score = 0;

  const majorMatch = userHasChineseMajor(profile) && hints.majorTags.includes('中国语言文学');
  if (majorMatch) {
    score += 60;
    reasons.push('公告原文提到中国语言文学');
    cautions.push('仍需核对职位表中的具体专业范围');
  }

  const interestedRoles = hints.roleTags.filter((tag) => profile.roleInterests.includes(tag));
  if (interestedRoles.length) {
    score += Math.min(54, interestedRoles.length * 18);
    reasons.push(`职责线索：${interestedRoles.join('、')}`);
  }

  if (hints.qualificationTags.includes('硕士') && profile.degree === '硕士') {
    score += 8;
    reasons.push('公告提到硕士条件');
  }
  if (hints.qualificationTags.includes('应届') && profile.graduateStatus === '应届') {
    score += 8;
    reasons.push('公告提到应届毕业生');
  }
  if (profile.graduationYear && hints.graduateYears.length) {
    if (hints.graduateYears.includes(profile.graduationYear)) {
      score += 10;
      reasons.push(`公告提到${profile.graduationYear}届`);
    } else {
      score -= 20;
      cautions.push(`公告提到${hints.graduateYears.map((year) => `${year}届`).join('、')}，与画像年份不同`);
    }
  }

  const isPartyMember = ['中共党员', '中共预备党员'].includes(profile.politicalStatus);
  if (hints.qualificationTags.includes('中共党员') && !isPartyMember) {
    score -= 20;
    cautions.push('公告出现党员条件，请核对是否为岗位硬性要求');
  }
  if (hints.qualificationTags.includes('工作经历') && profile.graduateStatus === '应届') {
    score -= 20;
    cautions.push('公告出现工作经历要求，应届生需要重点核对');
  }
  if (hints.qualificationTags.includes('教师资格证') && !profile.certificates.includes('教师资格证')) {
    score -= 20;
    cautions.push('公告出现教师资格证要求，画像中尚未标记该证书');
  }
  if (job.audience === '社会' && profile.graduateStatus === '应届') {
    score -= 8;
    cautions.push('该公告标记为社会招聘，请核对经历要求');
  }
  if (
    profile.preferredLocations.length
    && job.location
    && (job.location === '全国' || profile.preferredLocations.includes(job.location))
  ) {
    score += 6;
    reasons.push(`地区偏好：${job.location}`);
  }

  const hasHints = hints.majorTags.length || hints.roleTags.length || hints.qualificationTags.length || hints.graduateYears.length;
  let tier = 'verify';
  let label = '需要核对';
  if (majorMatch) {
    tier = 'exact';
    label = '专业相关';
  } else if (interestedRoles.length) {
    tier = 'writing';
    label = '文字岗位';
  } else if (hasHints && hints.roleTags.length) {
    tier = 'other';
    label = '一般相关';
  }
  if (!hasHints) {
    cautions.push('详情页尚未提取到足够的专业或职责线索');
  }

  return {
    tier,
    label,
    score: Math.max(0, Math.min(100, score)),
    reasons: reasons.slice(0, 4),
    cautions: [...new Set(cautions)].slice(0, 4),
    evidence: hints.evidence,
    roleTags: interestedRoles,
    majorTags: hints.majorTags,
  };
}

export function filterByMatchMode(jobs, mode = 'all', profile = DEFAULT_PROFILE) {
  const selectedMode = MATCH_MODES.has(mode) ? mode : 'all';
  const evaluated = jobs.map((job) => ({ ...job, _match: analyzeJob(job, profile) }));
  if (selectedMode === 'all') return evaluated;
  if (selectedMode === 'recommended') {
    return evaluated.filter((job) => ['exact', 'writing'].includes(job._match.tier));
  }
  return evaluated.filter((job) => job._match.tier === selectedMode);
}
