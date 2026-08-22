import { normalizeForeignCampaign } from './foreign-core.mjs';
import { normalizeProfile } from './matching.mjs';

const MATCH_MODES = new Set(['all', 'recommended', 'function', 'location', 'verify']);
const ENGLISH_RANK = new Map([
  ['未设置', 0],
  ['英语四级', 1],
  ['英语六级', 2],
  ['英语流利', 3],
]);

function intersection(preferences, available) {
  const choices = new Set(available);
  return preferences.filter((item) => choices.has(item));
}

function evidenceFor(campaign) {
  const hints = campaign.foreignHints && typeof campaign.foreignHints === 'object'
    ? campaign.foreignHints
    : {};
  const fallback = campaign.profileHints && typeof campaign.profileHints === 'object'
    ? campaign.profileHints
    : {};
  const evidence = hints.evidence && typeof hints.evidence === 'object'
    ? hints.evidence
    : fallback.evidence && typeof fallback.evidence === 'object'
      ? fallback.evidence
      : {};
  return Object.fromEntries(
    Object.entries(evidence).slice(0, 40).map(([key, value]) => [
      String(key).slice(0, 80), String(value ?? '').replace(/\s+/g, ' ').trim().slice(0, 160),
    ]).filter(([key, value]) => key && value),
  );
}

function highestEnglishRequirement(requirements) {
  return requirements.reduce((current, value) => (
    (ENGLISH_RANK.get(value) || 0) > (ENGLISH_RANK.get(current) || 0) ? value : current
  ), '未设置');
}

export function analyzeForeignCampaign(value = {}, profileValue = {}) {
  const campaign = normalizeForeignCampaign(value);
  const profile = normalizeProfile(profileValue);
  const reasons = [];
  const cautions = [];
  let score = 0;

  const cohortConflict = Boolean(
    profile.graduationYear
    && campaign.graduateYears.length
    && !campaign.graduateYears.includes(profile.graduationYear),
  );
  if (profile.graduationYear && campaign.graduateYears.includes(profile.graduationYear)) {
    score += 25;
    reasons.push(`届别匹配：${profile.graduationYear}届`);
  } else if (cohortConflict) {
    cautions.push(`招聘页提到${campaign.graduateYears.map((year) => `${year}届`).join('、')}，与画像年份不同`);
  }

  const matchedFunctions = intersection(profile.targetFunctions, campaign.jobFunctions);
  if (matchedFunctions.length) {
    score += Math.min(30, matchedFunctions.length * 15);
    reasons.push(`目标职能：${matchedFunctions.join('、')}`);
  }

  const matchedLocations = intersection(profile.preferredLocations, campaign.cities);
  if (matchedLocations.length) {
    score += 15;
    reasons.push(`目标城市：${matchedLocations.join('、')}`);
  }

  const matchedIndustries = intersection(profile.preferredIndustries, campaign.industryTags);
  if (matchedIndustries.length) {
    score += 15;
    reasons.push(`偏好行业：${matchedIndustries.join('、')}`);
  }

  const degreeMatch = Boolean(profile.degree && campaign.educationLevels.includes(profile.degree));
  if (degreeMatch) {
    score += 10;
    reasons.push(`学历线索：${profile.degree}`);
  }

  const requiredEnglish = highestEnglishRequirement(campaign.englishRequirements);
  const englishGap = (
    requiredEnglish !== '未设置'
    && (ENGLISH_RANK.get(profile.englishLevel) || 0) < (ENGLISH_RANK.get(requiredEnglish) || 0)
  );
  if (englishGap) {
    const profileCopy = profile.englishLevel === '未设置'
      ? '画像英语水平未设置'
      : `画像中设置为${profile.englishLevel}`;
    cautions.push(`招聘页提到${requiredEnglish}，${profileCopy}，请核对具体要求`);
  }

  const hasStructuredSignals = Boolean(
    campaign.graduateYears.length
    || campaign.jobFunctions.length
    || campaign.cities.length
    || campaign.educationLevels.length
    || campaign.industryTags.length,
  );
  if (!hasStructuredSignals) {
    cautions.push('招聘页尚未提取到足够的届别、职能、城市或学历线索');
  }

  let tier = 'other';
  let label = '一般相关';
  if (cohortConflict || !hasStructuredSignals) {
    tier = 'verify';
    label = '需要核对';
  } else if (matchedFunctions.length) {
    tier = 'function';
    label = score >= 60 ? '高度相关' : '职能相关';
  } else if (matchedLocations.length) {
    tier = 'location';
    label = '地点相关';
  }

  const evidence = evidenceFor(campaign);
  const evidenceKeys = [...new Set([
    ...matchedFunctions,
    ...matchedLocations,
    ...matchedIndustries,
  ])];
  return {
    tier,
    label,
    score: Math.max(0, Math.min(100, score)),
    reasons: reasons.slice(0, 5),
    cautions: [...new Set(cautions)].slice(0, 4),
    evidence,
    evidenceKeys,
    matchedFunctions,
    matchedLocations,
    matchedIndustries,
    cohortConflict,
    requiresVerification: cohortConflict || !hasStructuredSignals || englishGap,
    roleTags: matchedFunctions,
    majorTags: [],
  };
}

export function filterForeignByMatchMode(campaigns, mode = 'all', profile = {}) {
  const selectedMode = MATCH_MODES.has(mode) ? mode : 'all';
  const source = Array.isArray(campaigns) ? campaigns : [];
  const evaluated = source.map((value) => {
    const campaign = normalizeForeignCampaign(value);
    return { ...campaign, _match: analyzeForeignCampaign(campaign, profile) };
  });
  if (selectedMode === 'all') return evaluated;
  if (selectedMode === 'recommended') {
    return evaluated.filter((campaign) => (
      campaign._match.score >= 40 && !campaign._match.cohortConflict
    ));
  }
  if (selectedMode === 'function') {
    return evaluated.filter((campaign) => campaign._match.matchedFunctions.length > 0);
  }
  if (selectedMode === 'location') {
    return evaluated.filter((campaign) => campaign._match.matchedLocations.length > 0);
  }
  return evaluated.filter((campaign) => (
    campaign._match.requiresVerification || campaign.official === false
  ));
}
