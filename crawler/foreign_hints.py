"""Extract conservative bilingual metadata from foreign campus campaign pages."""

from __future__ import annotations

from datetime import date, datetime
import re


FOREIGN_HINTS_SCHEMA_VERSION = 1

CITY_RULES = {
    "北京": ("北京", "beijing"),
    "上海": ("上海", "shanghai"),
    "广州": ("广州", "guangzhou"),
    "深圳": ("深圳", "shenzhen"),
    "杭州": ("杭州", "hangzhou"),
    "南京": ("南京", "nanjing"),
    "苏州": ("苏州", "suzhou"),
    "成都": ("成都", "chengdu"),
    "重庆": ("重庆", "chongqing"),
    "武汉": ("武汉", "wuhan"),
    "西安": ("西安", "xi'an", "xian"),
    "天津": ("天津", "tianjin"),
    "青岛": ("青岛", "qingdao"),
    "厦门": ("厦门", "xiamen"),
    "沈阳": ("沈阳", "shenyang"),
    "大连": ("大连", "dalian"),
    "长春": ("长春", "changchun"),
    "哈尔滨": ("哈尔滨", "harbin"),
    "石家庄": ("石家庄", "shijiazhuang"),
    "太原": ("太原", "taiyuan"),
    "济南": ("济南", "jinan"),
    "烟台": ("烟台", "yantai"),
    "郑州": ("郑州", "zhengzhou"),
    "合肥": ("合肥", "hefei"),
    "无锡": ("无锡", "wuxi"),
    "常州": ("常州", "changzhou"),
    "昆山": ("昆山", "kunshan"),
    "宁波": ("宁波", "ningbo"),
    "嘉兴": ("嘉兴", "jiaxing"),
    "温州": ("温州", "wenzhou"),
    "福州": ("福州", "fuzhou"),
    "泉州": ("泉州", "quanzhou"),
    "东莞": ("东莞", "dongguan"),
    "佛山": ("佛山", "foshan"),
    "珠海": ("珠海", "zhuhai"),
    "惠州": ("惠州", "huizhou"),
    "南昌": ("南昌", "nanchang"),
    "长沙": ("长沙", "changsha"),
    "南宁": ("南宁", "nanning"),
    "海口": ("海口", "haikou"),
    "贵阳": ("贵阳", "guiyang"),
    "昆明": ("昆明", "kunming"),
    "兰州": ("兰州", "lanzhou"),
    "呼和浩特": ("呼和浩特", "hohhot"),
    "乌鲁木齐": ("乌鲁木齐", "urumqi"),
}
FUNCTION_RULES = {
    "市场/品牌": ("市场", "品牌", "marketing", "brand"),
    "内容/传播": ("内容", "传播", "公关", "communications", "content", "public relations"),
    "产品": ("产品", "product"),
    "运营": ("运营", "operations"),
    "人力资源": ("人力资源", "human resources", "people team", "talent acquisition"),
    "财务": ("财务", "finance", "audit", "tax"),
    "销售/商务": ("销售", "商务", "sales", "business development"),
    "供应链": ("供应链", "采购", "物流", "supply chain", "procurement", "logistics"),
    "技术/研发": ("研发", "工程", "技术", "engineering", "research and development", "r&d"),
    "数据/分析": ("数据", "分析", "data science", "data analytics", "analytics"),
    "法务/合规": ("法务", "合规", "legal", "compliance"),
    "咨询": ("咨询", "consulting", "consultant"),
}
EDUCATION_RULES = {
    "本科": ("本科", "bachelor"),
    "硕士": ("硕士", "master"),
    "博士": ("博士", "phd", "ph.d", "doctorate"),
}
ENGLISH_RULES = {
    "英语四级": ("英语四级", "cet-4", "cet 4"),
    "英语六级": ("英语六级", "cet-6", "cet 6"),
    "英语流利": ("英语流利", "流利英语", "fluent english", "english fluency", "fluency in english"),
}
EXCLUDED_EMPLOYMENT = {
    "实习": ("实习",),
    "internship": ("internship", "summer intern", " intern "),
    "兼职": ("兼职", "part-time", "part time"),
    "社会招聘": ("社会招聘", "社招", "experienced hire", "experienced professional", "lateral hire"),
}
MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"[\t\r ]+", " ", text or "")
    return [
        re.sub(r"\s+", " ", part).strip()
        for part in re.split(r"\n+|(?<=[。！？；;.!?])", compact)
        if part.strip()
    ]


def _bounded(sentence: str, term: str, limit: int = 120) -> str:
    if len(sentence) <= limit:
        return sentence
    index = sentence.lower().find(term.lower())
    if index < 0:
        return sentence[:limit]
    start = max(0, index - limit // 2)
    end = min(len(sentence), start + limit)
    return sentence[max(0, end - limit):end]


def _collect_tags(text: str, rules: dict[str, tuple[str, ...]], evidence: dict[str, str]) -> list[str]:
    parts = _sentences(text)
    lowered = (text or "").lower()
    found = []
    for tag, terms in rules.items():
        term = next((item for item in terms if item.lower() in lowered), None)
        if term is None:
            continue
        found.append(tag)
        sentence = next((item for item in parts if term.lower() in item.lower()), text or "")
        evidence[tag] = _bounded(sentence, term)
    return found


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_deadline(
    text: str,
    allow_application_range: bool = False,
) -> tuple[str | None, str]:
    text = text or ""
    chinese = re.search(
        r"(?:网申|申请|报名)(?:截止|截至|时间)?[^。；\n]{0,24}"
        r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?",
        text,
        re.IGNORECASE,
    )
    if chinese:
        parsed = _safe_date(int(chinese.group(1)), int(chinese.group(2)), int(chinese.group(3)))
        if parsed:
            return parsed.isoformat(), chinese.group(0)
    iso = re.search(
        r"(?:apply by|applications? close(?:s)?(?: on)?|application deadline)[:：\s]*"
        r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
        text,
        re.IGNORECASE,
    )
    if iso:
        parsed = _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if parsed:
            return parsed.isoformat(), iso.group(0)
    english = re.search(
        r"(?:apply by|applications? close(?:s)?(?: on)?|application deadline)[:：\s]*"
        r"(\d{1,2})\s+([A-Za-z]+)\s*,?\s*(20\d{2})",
        text,
        re.IGNORECASE,
    )
    if english:
        month = MONTHS.get(english.group(2).lower())
        parsed = _safe_date(int(english.group(3)), month, int(english.group(1))) if month else None
        if parsed:
            return parsed.isoformat(), english.group(0)
    if allow_application_range:
        application_range = re.search(
            r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)"
            r"(?:\s+(20\d{2}))?\s*[-–—]\s*"
            r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(20\d{2})(?!\d)",
            text,
            re.IGNORECASE,
        )
        if application_range:
            month = MONTHS.get(application_range.group(5).lower())
            parsed = _safe_date(
                int(application_range.group(6)),
                month,
                int(application_range.group(4)),
            ) if month else None
            if parsed:
                return parsed.isoformat(), application_range.group(0)
    return None, ""


def _graduate_years(text: str) -> list[str]:
    matches = re.findall(
        r"(20\d{2})\s*届|(20\d{2})\s+(?:new\s+)?(?:graduate|graduates|class)|"
        r"(?:class\s+of|graduates?)\s+(20\d{2})",
        text or "",
        re.IGNORECASE,
    )
    return sorted({year for groups in matches for year in groups if year})


def extract_foreign_hints(
    text: str,
    now: datetime,
    allow_application_range: bool = False,
) -> dict:
    """Return evidence-backed bilingual tags; never infer an absent deadline."""
    del now  # Kept in the interface for future relative-date support.
    text = text or ""
    evidence: dict[str, str] = {}
    deadline, deadline_evidence = extract_deadline(text, allow_application_range)
    return {
        "schemaVersion": FOREIGN_HINTS_SCHEMA_VERSION,
        "cities": _collect_tags(text, CITY_RULES, evidence),
        "jobFunctions": _collect_tags(text, FUNCTION_RULES, evidence),
        "educationLevels": _collect_tags(text, EDUCATION_RULES, evidence),
        "englishRequirements": _collect_tags(text, ENGLISH_RULES, evidence),
        "graduateYears": _graduate_years(text),
        "excludedEmploymentTerms": _collect_tags(text, EXCLUDED_EMPLOYMENT, evidence),
        "deadline": deadline,
        "deadlineConfidence": "high" if deadline else "unknown",
        "deadlineEvidence": _bounded(deadline_evidence, deadline_evidence) if deadline_evidence else "",
        "evidence": evidence,
    }
