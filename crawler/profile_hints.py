"""Extract conservative, evidence-backed hints for personal job matching."""

from __future__ import annotations

import re


PROFILE_HINTS_SCHEMA_VERSION = 3


ROLE_RULES = {
    "综合文字": ("综合文字", "文字综合", "文字材料", "材料撰写", "文稿起草", "公文写作", "文秘"),
    "宣传文化": ("宣传策划", "新闻宣传", "宣传思想", "企业文化", "品牌传播", "文化建设"),
    "编辑出版": (
        "编辑部",
        "文字编辑",
        "图书编辑",
        "报刊编辑",
        "编辑出版",
        "编校",
        "稿件校对",
        "出版发行",
        "古籍整理",
        "文献整理",
    ),
    "新媒体": (
        "新媒体",
        "融媒体",
        "内容运营",
        "新闻采编",
        "公众号运营",
        "运营微信公众号",
        "公众号编辑",
        "公众号内容",
    ),
    "高校行政": ("辅导员", "教学管理", "科研管理", "高校行政"),
    "中文教育": ("语文教师", "中文教师", "国际中文教育", "汉语教学"),
}

MAJOR_RULES = {
    "中国语言文学": (
        "中国语言文学",
        "汉语言文学",
        "汉语言文字学",
        "语言学及应用语言学",
        "文艺学",
        "中国古代文学",
        "中国现当代文学",
        "古典文献学",
        "比较文学与世界文学",
    ),
}

QUALIFICATION_RULES = {
    "硕士": ("硕士研究生及以上", "硕士及以上", "硕士研究生", "硕士学位"),
    "应届": ("应届毕业生", "应届高校毕业生", "校园招聘", "校招"),
    "中共党员": ("中共党员", "中共预备党员"),
    "教师资格证": ("教师资格证", "教师资格"),
}

ENGLISH_RULES = {
    "英语四级": ("英语四级", "cet-4", "cet 4"),
    "英语六级": ("英语六级", "cet-6", "cet 6"),
    "英语流利": ("英语流利", "流利英语", "fluent english", "english fluency", "fluency in english"),
}


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"[\t\r ]+", " ", text or "")
    parts = re.split(r"\n+|(?<=[。！？；;])", compact)
    return [re.sub(r"\s+", " ", part).strip() for part in parts if part.strip()]


def _bounded_evidence(sentence: str, term: str, limit: int = 120) -> str:
    if len(sentence) <= limit:
        return sentence
    index = sentence.lower().find(term.lower())
    if index < 0:
        return sentence[:limit]
    start = max(0, index - limit // 2)
    end = min(len(sentence), start + limit)
    start = max(0, end - limit)
    return sentence[start:end]


def _first_match(sentences: list[str], terms: tuple[str, ...]) -> tuple[str, str] | None:
    for sentence in sentences:
        for term in terms:
            if term.lower() in sentence.lower():
                return sentence, term
    return None


def _first_role_match(sentences: list[str], terms: tuple[str, ...]) -> tuple[str, str] | None:
    for sentence in sentences:
        normalized = sentence.strip("【】[] ")
        if re.fullmatch(r"责任编辑[：:].+", normalized):
            continue
        if normalized in {"新媒体", "政务新媒体"}:
            continue
        for term in terms:
            if term in sentence:
                return sentence, term
    return None


def extract_profile_hints(text: str) -> dict:
    """Return only matching hints explicitly present in official page text."""
    sentences = _sentences(text)
    role_tags: list[str] = []
    major_tags: list[str] = []
    qualification_tags: list[str] = []
    english_requirements: list[str] = []
    evidence: dict[str, str] = {}

    for tag, terms in ROLE_RULES.items():
        match = _first_role_match(sentences, terms)
        if match:
            sentence, term = match
            role_tags.append(tag)
            evidence[tag] = _bounded_evidence(sentence, term)

    for tag, terms in MAJOR_RULES.items():
        match = _first_match(sentences, terms)
        if match:
            sentence, term = match
            major_tags.append(tag)
            evidence[tag] = _bounded_evidence(sentence, term)

    for tag, terms in QUALIFICATION_RULES.items():
        match = _first_match(sentences, terms)
        if match:
            sentence, term = match
            qualification_tags.append(tag)
            evidence[tag] = _bounded_evidence(sentence, term)

    for tag, terms in ENGLISH_RULES.items():
        match = _first_match(sentences, terms)
        if match:
            sentence, term = match
            english_requirements.append(tag)
            evidence[tag] = _bounded_evidence(sentence, term)

    experience_pattern = re.compile(r"\d+\s*年(?:以上)?[^。！？；;\n]{0,16}工作(?:经历|经验)")
    for sentence in sentences:
        experience = experience_pattern.search(sentence)
        if experience:
            qualification_tags.append("工作经历")
            evidence["工作经历"] = _bounded_evidence(sentence, experience.group(0))
            break

    year_matches = re.findall(
        r"(20\d{2})\s*届|(20\d{2})\s+(?:new\s+)?(?:graduate|graduates|class)|"
        r"(?:class\s+of|graduates?)\s+(20\d{2})",
        text or "",
        re.IGNORECASE,
    )
    graduate_years = sorted({year for groups in year_matches for year in groups if year})
    for year in graduate_years:
        match = _first_match(sentences, (
            f"{year}届",
            f"{year} 届",
            f"{year} graduate",
            f"{year} graduates",
            f"class of {year}",
            f"graduates {year}",
        ))
        if match:
            evidence[f"{year}届"] = _bounded_evidence(match[0], match[1])

    return {
        "schemaVersion": PROFILE_HINTS_SCHEMA_VERSION,
        "roleTags": role_tags,
        "majorTags": major_tags,
        "qualificationTags": qualification_tags,
        "englishRequirements": english_requirements,
        "graduateYears": graduate_years,
        "evidence": evidence,
    }
