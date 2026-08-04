"""Extract evidence-backed application methods and material requirements."""

from __future__ import annotations

import re


APPLICATION_HINTS_SCHEMA_VERSION = 1

METHOD_RULES = {
    "网上报名": ("网上报名", "在线报名", "报名系统", "报名平台"),
    "邮箱报名": ("发送至报名邮箱", "报名材料发送至", "应聘材料发送至", "投递邮箱"),
    "现场报名": ("现场报名", "现场提交报名材料", "现场递交报名材料"),
}

MATERIAL_RULES = {
    "报名表": ("报名表", "应聘登记表", "应聘申请表"),
    "身份证": ("身份证扫描件", "身份证正反面", "本人身份证"),
    "学历学位证明": ("学历学位证书", "毕业证书和学位证书", "毕业证、学位证"),
    "学信网证明": ("学信网", "学历证书电子注册备案表", "学籍在线验证报告"),
    "个人简历": ("个人简历", "个人履历"),
    "资格证书": ("职业资格证书", "教师资格证", "专业技术资格证书"),
    "党员证明": ("党员证明", "党组织关系证明"),
    "工作经历证明": ("工作经历证明", "工作单位出具的证明", "劳动合同"),
    "近期照片": ("近期免冠", "证件照"),
    "成绩单": ("成绩单", "学习成绩证明"),
    "就业推荐表": ("就业推荐表", "毕业生推荐表"),
    "作品材料": ("代表作品", "作品集", "原创作品"),
}


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"[\t\r ]+", " ", text or "")
    parts = re.split(r"\n+|(?<=[。！？；;])", compact)
    return [re.sub(r"\s+", " ", part).strip() for part in parts if part.strip()]


def _bounded_evidence(sentence: str, term: str, limit: int = 120) -> str:
    if len(sentence) <= limit:
        return sentence
    index = sentence.find(term)
    if index < 0:
        return sentence[:limit]
    start = max(0, index - limit // 2)
    end = min(len(sentence), start + limit)
    return sentence[max(0, end - limit):end]


def _first_match(sentences: list[str], terms: tuple[str, ...]) -> tuple[str, str] | None:
    for sentence in sentences:
        for term in terms:
            if term in sentence:
                return sentence, term
    return None


def extract_application_hints(text: str) -> dict:
    """Return only application requirements explicitly present in official text."""
    sentences = _sentences(text)
    methods: list[str] = []
    materials: list[str] = []
    evidence: dict[str, str] = {}

    for tag, terms in METHOD_RULES.items():
        match = _first_match(sentences, terms)
        if match:
            sentence, term = match
            methods.append(tag)
            evidence[tag] = _bounded_evidence(sentence, term)

    for tag, terms in MATERIAL_RULES.items():
        match = _first_match(sentences, terms)
        if match:
            sentence, term = match
            materials.append(tag)
            evidence[tag] = _bounded_evidence(sentence, term)

    return {
        "schemaVersion": APPLICATION_HINTS_SCHEMA_VERSION,
        "methods": methods,
        "materialTags": materials,
        "evidence": evidence,
    }
