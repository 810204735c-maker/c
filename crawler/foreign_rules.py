"""Policy rules for publishable foreign-enterprise campus campaigns."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


FORMAL_TERMS = (
    "校园招聘",
    "校招",
    "秋招",
    "春招",
    "补录",
    "管培生",
    "管理培训生",
    "graduate program",
    "graduate programme",
    "management trainee",
    "campus recruitment",
    "campus hiring",
    "new graduate program",
    "new graduate programme",
)
EXCLUDED_TERMS = (
    "实习",
    "internship",
    "summer intern",
    "winter intern",
    " intern ",
    "兼职",
    "part-time",
    "part time",
    "社会招聘",
    "社招",
    "experienced hire",
    "experienced professional",
    "lateral hire",
)
CHINA_TERMS = (
    "中国",
    "china",
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "苏州",
    "成都",
    "重庆",
    "武汉",
    "西安",
    "天津",
    "青岛",
    "厦门",
)
MAINLAND_SPECIFIC_TERMS = (
    "中国大陆",
    "mainland china",
    "chinese mainland",
    *CHINA_TERMS[2:],
    "beijing",
    "shanghai",
    "guangzhou",
    "shenzhen",
    "hangzhou",
    "nanjing",
    "suzhou",
    "chengdu",
    "chongqing",
    "wuhan",
    "xi'an",
    "xian",
    "tianjin",
    "qingdao",
    "xiamen",
    "沈阳", "shenyang", "大连", "dalian", "长春", "changchun",
    "哈尔滨", "harbin", "石家庄", "shijiazhuang", "太原", "taiyuan",
    "济南", "jinan", "烟台", "yantai", "郑州", "zhengzhou",
    "合肥", "hefei", "无锡", "wuxi", "常州", "changzhou",
    "昆山", "kunshan", "宁波", "ningbo", "嘉兴", "jiaxing",
    "温州", "wenzhou", "福州", "fuzhou", "泉州", "quanzhou",
    "东莞", "dongguan", "佛山", "foshan", "珠海", "zhuhai",
    "惠州", "huizhou", "南昌", "nanchang", "长沙", "changsha",
    "南宁", "nanning", "海口", "haikou", "贵阳", "guiyang",
    "昆明", "kunming", "兰州", "lanzhou", "呼和浩特", "hohhot",
    "乌鲁木齐", "urumqi",
    "河北", "hebei", "山西", "shanxi", "辽宁", "liaoning",
    "吉林", "jilin", "黑龙江", "heilongjiang", "江苏", "jiangsu",
    "浙江", "zhejiang", "安徽", "anhui", "福建", "fujian",
    "江西", "jiangxi", "山东", "shandong", "河南", "henan",
    "湖北", "hubei", "湖南", "hunan", "广东", "guangdong",
    "海南", "hainan", "四川", "sichuan", "贵州", "guizhou",
    "云南", "yunnan", "陕西", "shaanxi", "甘肃", "gansu",
    "青海", "qinghai", "内蒙古", "inner mongolia", "广西", "guangxi",
    "西藏", "tibet", "宁夏", "ningxia", "新疆", "xinjiang",
)
NON_MAINLAND_CHINA_TERMS = (
    "香港",
    "hong kong",
    "澳门",
    "macau",
    "台湾",
    "taiwan",
)
OVERSEAS_ONLY_TERMS = (
    "hong kong only",
    "香港岗位",
    "仅限香港",
    "macau only",
    "澳门岗位",
    "仅限澳门",
    "taiwan only",
    "台湾岗位",
    "仅限台湾",
    "singapore only",
    "海外岗位",
    "overseas only",
)
OWNERSHIP_TYPES = {
    "foreign_owned",
    "foreign_controlled",
    "joint_venture",
    "hong_kong",
    "macau",
    "taiwan",
}
OFFICIAL_TIERS = {"official_verified", "official_job_feed"}


def normalize_key(value: object) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def _campaign_type(text: str) -> str:
    if any(term in text for term in ("管培生", "管理培训生", "management trainee")):
        return "management_trainee"
    if any(term in text for term in ("graduate program", "graduate programme", "new graduate program")):
        return "graduate_program"
    if "补录" in text or "supplemental" in text:
        return "supplemental"
    return "campus_recruitment"


def _campaign_season(text: str) -> str:
    if "春招" in text or "spring" in text:
        return "spring"
    if any(term in text for term in ("秋招", "autumn", "fall recruitment", "fall hiring")):
        return "autumn"
    if "补录" in text or "supplemental" in text:
        return "supplemental"
    return "annual"


def _has_explicit_mainland_evidence(text: str) -> bool:
    if any(term in text for term in MAINLAND_SPECIFIC_TERMS):
        return True
    has_generic_china = "中国" in text or "china" in text
    has_non_mainland_region = any(term in text for term in NON_MAINLAND_CHINA_TERMS)
    return has_generic_china and not has_non_mainland_region


def evaluate_campaign(text: str, source: dict, target_year: str = "2027") -> dict:
    """Return a conservative eligibility decision with normalized campaign tags."""
    compact = " " + re.sub(r"\s+", " ", str(text or "")).strip().lower() + " "
    has_year = bool(re.search(
        r"(?<!\d)" + re.escape(target_year)
        + r"(?:\s*届|\s+(?:new\s+)?graduates?|\s+graduate|\s+class)?(?!\d)",
        compact,
    )) or bool(re.search(r"(?:class\s+of|graduates?)\s+" + re.escape(target_year) + r"(?!\d)", compact))
    formal = any(term in compact for term in FORMAL_TERMS)
    excluded_matches = [term.strip() for term in EXCLUDED_TERMS if term in compact]
    explicit_china = _has_explicit_mainland_evidence(compact)
    china = explicit_china or (
        source.get("scopeCountry") == "CN"
        and not source.get("requireExplicitChinaEvidence")
    )
    overseas_only = any(term in compact for term in OVERSEAS_ONLY_TERMS)
    eligible = has_year and formal and not excluded_matches and china and not overseas_only
    reasons = []
    if not has_year:
        reasons.append("target_year_missing")
    if not formal:
        reasons.append("formal_campus_signal_missing")
    if excluded_matches:
        reasons.append("excluded_employment_type")
    if not china:
        reasons.append("china_scope_missing")
    if overseas_only:
        reasons.append("overseas_only")
    return {
        "eligible": eligible,
        "graduateYear": target_year if has_year else "",
        "employmentType": "full_time" if formal and not excluded_matches else "unknown",
        "campaignType": _campaign_type(compact),
        "season": _campaign_season(compact),
        "reasons": reasons,
    }


def _clean_domain(value: object) -> str:
    domain = str(value or "").strip().lower().rstrip(".")
    if not domain or "/" in domain or ":" in domain:
        raise ValueError("officialDomains entries must be bare host names")
    return domain


def load_company_registry(path: Path) -> dict[str, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != 1 or not isinstance(document.get("companies"), list):
        raise ValueError("foreign company registry must use schemaVersion 1")
    companies: dict[str, dict] = {}
    for raw in document["companies"]:
        if not isinstance(raw, dict):
            raise ValueError("company registry entries must be objects")
        company = dict(raw)
        identifier = str(company.get("id", "")).strip()
        if not re.fullmatch(r"[a-z0-9-]{2,60}", identifier):
            raise ValueError("company id must be a lowercase slug")
        if identifier in companies:
            raise ValueError("company ids must be unique")
        if company.get("ownership") not in OWNERSHIP_TYPES:
            raise ValueError("company ownership is invalid")
        if not str(company.get("ownershipEvidenceUrl", "")).startswith("https://"):
            raise ValueError("ownershipEvidenceUrl is required")
        domains = [_clean_domain(item) for item in company.get("officialDomains", [])]
        if not domains:
            raise ValueError("officialDomains is required")
        prefixes = []
        for item in company.get("delegatedUrlPrefixes", []):
            prefix = str(item or "").strip()
            if not prefix.startswith("https://"):
                raise ValueError("delegatedUrlPrefixes entries must use HTTPS")
            if not prefix.endswith("/"):
                raise ValueError("delegatedUrlPrefixes entries must end with a slash")
            prefixes.append(prefix)
        aliases = [company.get("name", ""), company.get("nameEn", ""), *company.get("aliases", [])]
        company["aliases"] = list(dict.fromkeys(str(item).strip() for item in aliases if str(item).strip()))
        if not company["aliases"]:
            raise ValueError("company aliases are required")
        company["officialDomains"] = list(dict.fromkeys(domains))
        company["delegatedUrlPrefixes"] = list(dict.fromkeys(prefixes))
        company["industryTags"] = list(dict.fromkeys(company.get("industryTags", [])))
        company["publishable"] = bool(company.get("publishable", True))
        companies[identifier] = company
    return companies


def _alias_match_length(text: str, alias: str) -> int:
    alias = str(alias or "").strip()
    if not alias:
        return 0
    if re.search(r"[\u4e00-\u9fff]", alias):
        key = normalize_key(alias)
        return len(key) if key and key in normalize_key(text) else 0
    words = re.findall(r"[a-z0-9]+", alias.lower())
    if not words:
        return 0
    pattern = r"(?<![a-z0-9])" + r"[\s&._\-/]*".join(map(re.escape, words)) + r"(?![a-z0-9])"
    return len(normalize_key(alias)) if re.search(pattern, text.lower()) else 0


def resolve_company(text: str, source: dict, companies: dict[str, dict]) -> dict | None:
    configured = source.get("companyId")
    if configured:
        company = companies.get(str(configured))
        return company if company and company.get("publishable") else None
    matches = []
    for company in companies.values():
        if not company.get("publishable"):
            continue
        length = max((_alias_match_length(text, alias) for alias in company.get("aliases", [])), default=0)
        if length:
            matches.append((length, company["id"], company))
    return max(matches, default=(0, "", None))[2]


def campaign_identity(
    company_id: str,
    graduate_year: str,
    campaign_type: str,
    season: str,
    program_key: str = "general",
) -> tuple[str, str]:
    normalized_program = normalize_key(program_key) or "general"
    key = "|".join((company_id, graduate_year, campaign_type, season, normalized_program))
    identifier = "foreign_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return key, identifier


def is_official_tier(value: object) -> bool:
    return str(value or "") in OFFICIAL_TIERS
