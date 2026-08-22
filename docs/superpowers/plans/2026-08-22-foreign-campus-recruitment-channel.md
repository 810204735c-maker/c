# 外企校招频道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有招考雷达中新增独立的“外企校招”主频道，每天发现外企在中国发布、面向 2027 届毕业生的正式全职校园招聘活动，并提供检索、画像匹配、今日新增摘要、收藏和申请管理。

**Architecture:** 保持现有公考采集链路和 data/jobs.json 完全兼容，新增一条标准库 Python 外企采集链路，输出 data/foreign-campus.json 与 data/foreign-health.json。外企活动以公司、届别、批次、项目类型和申请窗口生成稳定 ID；官网信息优先，第三方只作发现或回退。前端使用共享的收藏、申请助手和日历能力，但为两个频道保留独立数据、筛选状态、URL 和来源健康状态。

**Tech Stack:** Python 3.12 标准库、静态 HTML/CSS、浏览器 ES modules、Node.js test runner、Playwright smoke tests、GitHub Actions、GitHub Pages。

## Global Constraints

- 外企频道只收录外企在中国大陆发布的岗位；港澳台和海外工作地点本阶段不收录。
- 企业范围包括外资独资、外资控股、外资品牌独立招聘的合资企业，以及港澳台企业；中国企业的海外岗位不算外企。
- 目标人群固定为 2027 届毕业生。
- 只收录正式全职校园招聘、秋招、春招、补录、Graduate Program 和 Management Trainee；排除实习、兼职、社会招聘和 experienced hire。
- 一场公司级招聘活动只展示一张卡片；城市、职能和学历使用数组字段，不能拆成岗位级卡片。
- 企业官网或由企业官网明确委托的 ATS 无条件优先；仅有第三方来源时必须展示“第三方信息，请核验”。
- 英文公告保留原标题，不调用翻译 API；结构化筛选和提示仍使用中文标签。
- “今日新增”按北京时间的首次成功发现计算，不按公告发布日期计算；保留最近 7 个自然日的摘要。
- 首次建库显示“首批收录”，不得把历史活动全部宣称为今日新增。
- 已截止活动默认隐藏但保留 60 天，以便收藏、备注和进度仍可访问；截止未知的活动发现 45 天后标记为 stale。
- 不绕过登录、Cookie 挑战、验证码、反爬脚本、访问控制或私有 API；禁止使用个人浏览器会话。
- 实习僧当前只作为人工参考来源，未取得书面许可或正式授权 API 前不得自动抓取。
- 保持零应用服务器、零付费 API 和 GitHub Pages 部署模式。
- 保留 localStorage 中 job-radar:view、job-radar:profile、job-radar:workspace 和旧 job-radar:saved 的兼容性。
- 没有 channel 查询参数时必须继续进入公考招录频道，现有公考分享链接不得改变语义。

## File Structure

**New collection files**

- crawler/foreign_companies.json：可发布外企注册表、别名、所有权证据、行业、官方域名及受委托 ATS 前缀。
- crawler/foreign_sources.json：官网、公开搜索、牛客、应届生、高校就业网和人工来源配置。
- crawler/foreign_rules.py：2027、正式全职、中国大陆、外企注册表和活动身份判定。
- crawler/foreign_hints.py：中英文城市、职能、学历、英语要求、季节、活动类型和截止日期提取。
- crawler/foreign_crawl.py：来源采集、官网优先去重、旧数据合并、生命周期、每日摘要和原子写入。
- crawler/foreign_health.py：外企快照逐项校验、健康指标、质量门禁和公网校验。
- crawler/cache/foreign-details.json：外企详情页成功/失败缓存。
- crawler/cache/foreign-seen.json：活动稳定 ID 的首次发现记录。
- data/foreign-campus.json：外企频道公开快照。
- data/foreign-health.json：外企来源与质量状态。
- scripts/check_foreign_snapshot.py：CI 本地快照门禁。
- docs/foreign-source-coverage.md：来源级别、覆盖企业、受限来源和扩充记录。

**New frontend files**

- assets/channels.mjs：频道配置及频道 URL 状态。
- assets/foreign-core.mjs：外企记录规范化、筛选、排序和 7 日摘要规范化。
- assets/foreign-matching.mjs：外企画像匹配与可解释理由。
- tests/foreign-core.test.mjs：外企筛选、排序、URL 和摘要纯函数测试。
- tests/foreign-matching.test.mjs：外企画像兼容和匹配测试。

**Modified files**

- crawler/profile_hints.py：扩充外企职能、英语和英文届别证据词典并升级 schema。
- crawler/application_hints.py：补充中英文简历、成绩单、求职信、作品集和语言成绩。
- crawler/detail.py：允许外企链路指定外企 hints extractor 和独立缓存。
- crawler/health.py：公网检查加入两个外企 JSON，但不改变现有公考 validator。
- assets/matching.mjs：向旧画像兼容地增加目标职能、行业和英语水平。
- assets/application.mjs：按频道生成不同的五步申请指南和提醒，保持步骤 ID 不变。
- assets/favorites.mjs：备份中增加可选 channel 和 company 字段，继续接受旧 v1 备份。
- assets/app.js：双频道控制器、跨频道记录查找、独立筛选状态和数据加载。
- index.html：页头频道导航、外企筛选、今日新增摘要和频道化文案。
- assets/styles.css：频道、摘要、八项筛选、第三方标识和响应式布局。
- tests/test_workflow.py、tests/test_health.py、tests/test_profile_hints.py、tests/test_application_hints.py、tests/test_detail.py、tests/application.test.mjs、tests/favorites.test.mjs、tests/browser-smoke.mjs。
- scripts/check_public_site.py、.github/workflows/update-jobs.yml、package.json、README.md、docs/weekly-improvement-log.md。

---

### Task 1: 固化外企范围、正式校招规则和稳定活动身份

**Files:**

- Create: crawler/foreign_companies.json
- Create: crawler/foreign_rules.py
- Create: tests/test_foreign_rules.py

**Interfaces:**

- Consumes: 来源标题、摘要、链接上下文和企业注册表。
- Produces: load_company_registry(path: Path) -> dict[str, dict]。
- Produces: resolve_company(text: str, source: dict, companies: dict[str, dict]) -> dict | None。
- Produces: evaluate_campaign(text: str, source: dict, target_year: str = "2027") -> dict。
- Produces: campaign_identity(company_id, graduate_year, campaign_type, season, program_key="general") -> tuple[str, str]。

- [ ] **Step 1: 写出会失败的范围和身份测试**

~~~python
import unittest

from crawler.foreign_rules import campaign_identity, evaluate_campaign, resolve_company


class ForeignRuleTests(unittest.TestCase):
    def test_accepts_only_2027_full_time_china_campaigns(self):
        accepted = evaluate_campaign(
            "Deloitte China 2027 Graduate Program 上海 全职申请",
            {"scopeCountry": "CN"},
        )
        self.assertTrue(accepted["eligible"])
        self.assertEqual(accepted["graduateYear"], "2027")
        self.assertEqual(accepted["employmentType"], "full_time")

        rejected = [
            "2027 Summer Internship Shanghai",
            "2027届暑期实习生招聘",
            "2027 Experienced Hire Beijing",
            "2026届校园招聘 中国",
            "2027 Graduate Program Hong Kong only",
        ]
        for text in rejected:
            with self.subTest(text=text):
                self.assertFalse(evaluate_campaign(text, {"scopeCountry": "CN"})["eligible"])

    def test_unknown_company_is_not_publishable(self):
        companies = {
            "deloitte": {
                "id": "deloitte",
                "name": "德勤",
                "nameEn": "Deloitte",
                "aliases": ["德勤中国", "Deloitte China"],
                "publishable": True,
            }
        }
        self.assertEqual(resolve_company("德勤中国2027校园招聘", {}, companies)["id"], "deloitte")
        self.assertIsNone(resolve_company("未知公司2027校园招聘", {}, companies))

    def test_identity_is_independent_of_title_and_url(self):
        first = campaign_identity("deloitte", "2027", "graduate_program", "autumn")
        replacement = campaign_identity("deloitte", "2027", "graduate_program", "autumn")
        spring = campaign_identity("deloitte", "2027", "graduate_program", "spring")
        self.assertEqual(first, replacement)
        self.assertNotEqual(first, spring)
        self.assertTrue(first[1].startswith("foreign_"))
~~~

- [ ] **Step 2: 运行测试并确认缺失模块**

Run: python -m unittest tests.test_foreign_rules -v

Expected: FAIL with ModuleNotFoundError for crawler.foreign_rules。

- [ ] **Step 3: 实现明确的正负规则**

~~~python
import hashlib
import json
import re

FORMAL_TERMS = (
    "校园招聘", "校招", "秋招", "春招", "补录", "管培生", "管理培训生",
    "graduate program", "graduate programme", "management trainee",
    "campus recruitment", "campus hiring", "new graduate program",
)
EXCLUDED_TERMS = (
    "实习", "internship", " intern ", "兼职", "part-time", "part time",
    "社会招聘", "社招", "experienced hire", "lateral hire",
)
CHINA_TERMS = (
    "中国", "china", "北京", "上海", "广州", "深圳", "杭州", "南京",
    "苏州", "成都", "重庆", "武汉", "西安", "天津", "青岛", "厦门",
)
OVERSEAS_ONLY_TERMS = (
    "hong kong only", "香港岗位", "macau only", "澳门岗位",
    "taiwan only", "台湾岗位", "singapore only", "海外岗位",
)


def normalize_key(value):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def campaign_type(text):
    if "管培生" in text or "管理培训生" in text or "management trainee" in text:
        return "management_trainee"
    if "graduate program" in text or "graduate programme" in text:
        return "graduate_program"
    if "补录" in text or "supplemental" in text:
        return "supplemental"
    return "campus_recruitment"


def campaign_season(text):
    if "春招" in text or "spring" in text:
        return "spring"
    if "秋招" in text or "autumn" in text or "fall recruitment" in text:
        return "autumn"
    if "补录" in text or "supplemental" in text:
        return "supplemental"
    return "annual"


def evaluate_campaign(text, source, target_year="2027"):
    compact = " " + re.sub(r"\s+", " ", str(text or "")).strip().lower() + " "
    has_year = bool(re.search(
        r"(?<!\d)" + re.escape(target_year)
        + r"(?:\s*届|\s+graduates?|\s+graduate|\s+class)?(?!\d)",
        compact,
    ))
    formal = any(term in compact for term in FORMAL_TERMS)
    excluded = any(term in compact for term in EXCLUDED_TERMS)
    china = any(term in compact for term in CHINA_TERMS) or source.get("scopeCountry") == "CN"
    overseas_only = any(term in compact for term in OVERSEAS_ONLY_TERMS)
    return {
        "eligible": has_year and formal and not excluded and china and not overseas_only,
        "graduateYear": target_year if has_year else "",
        "employmentType": "full_time" if formal and not excluded else "unknown",
        "campaignType": campaign_type(compact),
        "season": campaign_season(compact),
    }
~~~

- [ ] **Step 4: 实现注册表校验、公司别名匹配和稳定哈希**

~~~python
def load_company_registry(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != 1 or not isinstance(document.get("companies"), list):
        raise ValueError("foreign company registry must use schemaVersion 1")
    allowed = {
        "foreign_owned", "foreign_controlled", "joint_venture",
        "hong_kong", "macau", "taiwan",
    }
    companies = {}
    for raw in document["companies"]:
        company = dict(raw)
        identifier = str(company.get("id", "")).strip()
        if not re.fullmatch(r"[a-z0-9-]{2,60}", identifier):
            raise ValueError("company id must be a lowercase slug")
        if company.get("ownership") not in allowed:
            raise ValueError("company ownership is invalid")
        if not str(company.get("ownershipEvidenceUrl", "")).startswith("https://"):
            raise ValueError("ownershipEvidenceUrl is required")
        if not company.get("officialDomains"):
            raise ValueError("officialDomains is required")
        company["aliases"] = list(dict.fromkeys([
            company.get("name", ""), company.get("nameEn", ""), *company.get("aliases", []),
        ]))
        company["publishable"] = bool(company.get("publishable", True))
        companies[identifier] = company
    return companies


def resolve_company(text, source, companies):
    if source.get("companyId"):
        company = companies.get(source["companyId"])
        return company if company and company["publishable"] else None
    normalized = normalize_key(text)
    matches = []
    for company in companies.values():
        if not company["publishable"]:
            continue
        length = max(
            (len(alias) for alias in map(normalize_key, company["aliases"]) if alias in normalized),
            default=0,
        )
        if length:
            matches.append((length, company["id"], company))
    return max(matches, default=(0, "", None))[2]


def campaign_identity(company_id, graduate_year, campaign_type, season, program_key="general"):
    normalized_program = normalize_key(program_key) or "general"
    key = "|".join((company_id, graduate_year, campaign_type, season, normalized_program))
    return key, "foreign_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
~~~

- [ ] **Step 5: 建立首批 50 家外企注册表**

每条记录必须具有 id、name、nameEn、aliases、ownership、homeCountryOrRegion、industryTags、ownershipEvidenceUrl、ownershipCheckedAt、officialDomains、delegatedUrlPrefixes 和 publishable。

首批 ID 固定为：apple、microsoft、amazon、ibm、intel、cisco、sap、oracle、siemens、bosch、schneider-electric、abb、honeywell、basf、3m、pg、unilever、loreal、nestle、mars、mondelez、pepsico、coca-cola、ikea、nike、adidas、deloitte、pwc、ey、kpmg、accenture、deutsche-bank、jpmorgan、hsbc、standard-chartered、ubs、roche、novartis、sanofi、astrazeneca、pfizer、bayer、johnson-johnson、mercedes-benz、bmw、volkswagen、volvo-cars、ford、tesla、dhl。

格式合同：

~~~json
{
  "schemaVersion": 1,
  "companies": [
    {
      "id": "deloitte",
      "name": "德勤",
      "nameEn": "Deloitte",
      "aliases": ["德勤中国", "Deloitte China"],
      "ownership": "foreign_controlled",
      "homeCountryOrRegion": "英国",
      "industryTags": ["咨询/专业服务"],
      "ownershipEvidenceUrl": "https://www.deloitte.com/cn/en/about.html",
      "ownershipCheckedAt": "2026-08-22",
      "officialDomains": ["deloitte.com"],
      "delegatedUrlPrefixes": ["https://wecruit.hotjob.cn/SU"],
      "publishable": true
    }
  ]
}
~~~

共享 ATS 只有 delegatedUrlPrefixes 精确命中且存在 employer-owned 页面委托证据时才能标为官方；只匹配 hotjob.cn 或 myworkdayjobs.com 域名不够。

- [ ] **Step 6: 运行规则与完整 Python 回归后提交**

Run: python -m unittest tests.test_foreign_rules -v

Run: python -m unittest discover -s tests -p "test_*.py" -v

Expected: 当前 60 项测试与新增规则测试全部 PASS。

~~~bash
git add crawler/foreign_companies.json crawler/foreign_rules.py tests/test_foreign_rules.py
git commit -m "feat: define foreign campus campaign policy"
~~~

### Task 2: 建立合规来源注册表和中英文线索提取

**Files:**

- Create: crawler/foreign_sources.json
- Create: crawler/foreign_hints.py
- Create: tests/test_foreign_hints.py
- Modify: crawler/profile_hints.py
- Modify: crawler/application_hints.py
- Modify: crawler/detail.py
- Modify: tests/test_profile_hints.py
- Modify: tests/test_application_hints.py
- Modify: tests/test_detail.py

**Interfaces:**

- Consumes: 无需登录即可读取的官网、官网委托 ATS、允许访问的第三方页面正文。
- Produces: extract_foreign_hints(text: str, now: datetime) -> dict。
- Produces: enrich_foreign_campaigns(campaigns, sources, cache, now, max_fetches=80, max_workers=4) -> tuple[list[dict], dict]。

- [ ] **Step 1: 写出中英文提取测试**

~~~python
import unittest
from datetime import datetime, timezone

from crawler.foreign_hints import extract_foreign_hints


NOW = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)


class ForeignHintTests(unittest.TestCase):
    def test_extracts_chinese_fields(self):
        hints = extract_foreign_hints(
            "面向2027届本科及硕士毕业生，工作地点上海、北京，"
            "市场品牌与人力资源方向，英语六级优先，网申截止2026年10月18日。",
            NOW,
        )
        self.assertEqual(hints["graduateYears"], ["2027"])
        self.assertEqual(hints["cities"], ["北京", "上海"])
        self.assertEqual(hints["jobFunctions"], ["市场/品牌", "人力资源"])
        self.assertEqual(hints["educationLevels"], ["本科", "硕士"])
        self.assertEqual(hints["englishRequirements"], ["英语六级"])
        self.assertEqual(hints["deadline"], "2026-10-18")

    def test_extracts_english_fields(self):
        hints = extract_foreign_hints(
            "China 2027 Graduate Programme for Marketing and Supply Chain. "
            "Bachelor or Master degree. Applications close on 18 October 2026.",
            NOW,
        )
        self.assertEqual(hints["jobFunctions"], ["市场/品牌", "供应链"])
        self.assertEqual(hints["educationLevels"], ["本科", "硕士"])
        self.assertEqual(hints["deadline"], "2026-10-18")

    def test_negative_terms_override_positive_metadata(self):
        hints = extract_foreign_hints("China 2027 Summer Internship, full-time schedule", NOW)
        self.assertIn("internship", hints["excludedEmploymentTerms"])
~~~

- [ ] **Step 2: 运行测试并确认缺失模块**

Run: python -m unittest tests.test_foreign_hints -v

Expected: FAIL with ModuleNotFoundError for crawler.foreign_hints。

- [ ] **Step 3: 实现固定词典和证据上限**

~~~python
import re
from datetime import date, datetime

FOREIGN_HINTS_SCHEMA_VERSION = 1
CITY_RULES = {
    "北京": ("北京", "beijing"), "上海": ("上海", "shanghai"),
    "广州": ("广州", "guangzhou"), "深圳": ("深圳", "shenzhen"),
    "杭州": ("杭州", "hangzhou"), "南京": ("南京", "nanjing"),
    "苏州": ("苏州", "suzhou"), "成都": ("成都", "chengdu"),
    "重庆": ("重庆", "chongqing"), "武汉": ("武汉", "wuhan"),
    "西安": ("西安", "xi'an", "xian"), "天津": ("天津", "tianjin"),
    "青岛": ("青岛", "qingdao"), "厦门": ("厦门", "xiamen"),
}
FUNCTION_RULES = {
    "市场/品牌": ("市场", "品牌", "marketing", "brand"),
    "内容/传播": ("内容", "传播", "公关", "communications", "content", "public relations"),
    "产品": ("产品", "product"), "运营": ("运营", "operations"),
    "人力资源": ("人力资源", "human resources", "people team", "talent"),
    "财务": ("财务", "finance", "audit", "tax"),
    "销售/商务": ("销售", "商务", "sales", "business development"),
    "供应链": ("供应链", "采购", "物流", "supply chain", "procurement", "logistics"),
    "技术/研发": ("研发", "工程", "技术", "engineering", "research and development"),
    "数据/分析": ("数据", "分析", "data", "analytics"),
    "法务/合规": ("法务", "合规", "legal", "compliance"),
    "咨询": ("咨询", "consulting", "consultant"),
}
EDUCATION_RULES = {
    "本科": ("本科", "bachelor"), "硕士": ("硕士", "master"),
    "博士": ("博士", "phd", "doctorate"),
}
ENGLISH_RULES = {
    "英语四级": ("英语四级", "cet-4", "cet 4"),
    "英语六级": ("英语六级", "cet-6", "cet 6"),
    "英语流利": ("英语流利", "fluent english", "english fluency"),
}
EXCLUDED_EMPLOYMENT = {
    "实习": ("实习",), "internship": ("internship", " intern "),
    "兼职": ("兼职", "part-time", "part time"),
    "社会招聘": ("社会招聘", "社招", "experienced hire", "lateral hire"),
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def sentences(text):
    compact = re.sub(r"[\t\r ]+", " ", text or "")
    return [
        re.sub(r"\s+", " ", part).strip()
        for part in re.split(r"\n+|(?<=[。！？；;.!?])", compact)
        if part.strip()
    ]


def bounded(sentence, term, limit=120):
    if len(sentence) <= limit:
        return sentence
    index = max(0, sentence.lower().find(term.lower()))
    start = max(0, index - limit // 2)
    return sentence[start:start + limit]


def collect_tags(text, rules, evidence):
    parts = sentences(text)
    lowered = text.lower()
    found = []
    for tag, terms in rules.items():
        term = next((item for item in terms if item.lower() in lowered), None)
        if not term:
            continue
        found.append(tag)
        sentence = next(item for item in parts if term.lower() in item.lower())
        evidence[tag] = bounded(sentence, term)
    return found


def extract_deadline(text):
    chinese = re.search(
        r"(?:网申|申请|报名)(?:截止|截至|时间)?[^。；\n]{0,24}"
        r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?",
        text,
        re.IGNORECASE,
    )
    if chinese:
        parsed = date(int(chinese.group(1)), int(chinese.group(2)), int(chinese.group(3)))
        return parsed.isoformat(), chinese.group(0)
    iso = re.search(
        r"(?:apply by|applications? close(?:s)?(?: on)?|application deadline)[:：\s]*"
        r"(20\d{2})-(\d{1,2})-(\d{1,2})",
        text,
        re.IGNORECASE,
    )
    if iso:
        parsed = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        return parsed.isoformat(), iso.group(0)
    english = re.search(
        r"(?:apply by|applications? close(?:s)?(?: on)?|application deadline)[:：\s]*"
        r"(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",
        text,
        re.IGNORECASE,
    )
    if english and english.group(2).lower() in MONTHS:
        parsed = date(int(english.group(3)), MONTHS[english.group(2).lower()], int(english.group(1)))
        return parsed.isoformat(), english.group(0)
    return None, ""


def extract_foreign_hints(text, now):
    evidence = {}
    deadline, deadline_evidence = extract_deadline(text)
    year_matches = re.findall(
        r"(20\d{2})\s*届|(20\d{2})\s+(?:graduate|graduates|class)|"
        r"(?:class of|graduates?)\s+(20\d{2})",
        text,
        re.IGNORECASE,
    )
    years = sorted({year for groups in year_matches for year in groups if year})
    return {
        "schemaVersion": FOREIGN_HINTS_SCHEMA_VERSION,
        "cities": collect_tags(text, CITY_RULES, evidence),
        "jobFunctions": collect_tags(text, FUNCTION_RULES, evidence),
        "educationLevels": collect_tags(text, EDUCATION_RULES, evidence),
        "englishRequirements": collect_tags(text, ENGLISH_RULES, evidence),
        "graduateYears": years,
        "excludedEmploymentTerms": collect_tags(text, EXCLUDED_EMPLOYMENT, evidence),
        "deadline": deadline,
        "deadlineConfidence": "high" if deadline else "unknown",
        "deadlineEvidence": bounded(deadline_evidence, deadline_evidence) if deadline_evidence else "",
        "evidence": evidence,
    }
~~~

无证据时 deadline 必须为 null，不能从采集日期推断。

- [ ] **Step 4: 写入可审计来源配置**

foreign_sources.json 顶层固定为：

~~~json
{
  "schemaVersion": 1,
  "targetGraduateYear": "2027",
  "chinaOnly": true,
  "maxTotal": 1000,
  "retentionDays": 60,
  "unknownTtlDays": 45,
  "summaryHistoryDays": 7,
  "detailMaxFetches": 80,
  "detailMaxWorkers": 4,
  "detailCachePath": "cache/foreign-details.json",
  "seenCachePath": "cache/foreign-seen.json",
  "sources": [
    {
      "id": "deloitte-china-graduate",
      "name": "德勤中国 Graduate Program",
      "kind": "campaign_page",
      "url": "https://www.deloitte.com/cn/en/careers/explore-your-fit/students/graduate-program.html",
      "campaignTitle": "Deloitte China 2027 Graduate Program",
      "companyId": "deloitte",
      "tier": "official_verified",
      "scopeCountry": "CN",
      "requiredTerms": ["2027"],
      "allowedDomains": ["deloitte.com"],
      "timeout": 20,
      "allowEmpty": true
    },
    {
      "id": "pwc-china-students",
      "name": "普华永道中国学生招聘",
      "kind": "campaign_page",
      "url": "https://www.pwccn.com/en/careers/students.html",
      "campaignTitle": "PwC China 2027 Campus Recruitment",
      "companyId": "pwc",
      "tier": "official_verified",
      "scopeCountry": "CN",
      "requiredTerms": ["2027"],
      "allowedDomains": ["pwccn.com"],
      "timeout": 20,
      "allowEmpty": true
    },
    {
      "id": "deutsche-bank-apac-graduates",
      "name": "德意志银行亚太毕业生项目",
      "kind": "campaign_page",
      "url": "https://careers.db.com/students-graduates/your-application/",
      "campaignTitle": "Deutsche Bank China 2027 Graduate Programme",
      "companyId": "deutsche-bank",
      "tier": "official_verified",
      "scopeCountry": "CN",
      "requiredTerms": ["China", "2027"],
      "allowedDomains": ["careers.db.com"],
      "timeout": 20,
      "allowEmpty": true
    },
    {
      "id": "official-company-search",
      "name": "外企官网公开搜索",
      "kind": "rss_search_registry",
      "queryTemplate": "site:{domain} (2027 校园招聘 OR 2027 Graduate Program OR 2027 Management Trainee) (中国 OR China)",
      "tier": "official_job_feed",
      "scopeCountry": "CN",
      "maxItems": 20,
      "timeout": 20
    },
    {
      "id": "nowcoder-campus-schedule",
      "name": "牛客校招日程",
      "kind": "html",
      "url": "https://www.nowcoder.com/jobs/school/schedule",
      "tier": "third_party_only",
      "scopeCountry": "CN",
      "allowedDomains": ["nowcoder.com"],
      "timeout": 20,
      "maxItems": 80,
      "enabled": false,
      "disabledReason": "启用前复核现行服务条款；不访问 robots 禁止的 /search"
    },
    {
      "id": "yingjiesheng-public-discovery",
      "name": "应届生求职网公开信息",
      "kind": "rss_search",
      "query": "site:yingjiesheng.com 2027 校园招聘 外企 全职",
      "tier": "third_party_only",
      "scopeCountry": "CN",
      "allowedDomains": ["yingjiesheng.com"],
      "timeout": 20,
      "maxItems": 60,
      "enabled": true
    },
    {
      "id": "shixiseng-manual",
      "name": "实习僧",
      "kind": "manual",
      "url": "https://www.shixiseng.com/interns?city=%E5%85%A8%E5%9B%BD&type=school",
      "tier": "manual_only",
      "enabled": false,
      "manualOnly": true,
      "disabledReason": "现行用户协议禁止未经许可的机器人或脚本自动访问"
    }
  ]
}
~~~

牛客只能在再次检查 robots 与条款均允许校招日程页时启用；检查日期、结果和禁用原因写入 docs/foreign-source-coverage.md。应届生结果只作转载线索。实习僧不得自动访问。

- [ ] **Step 5: 抽取通用详情内核并保持公考行为**

从 crawler/detail.py 的 enrich_jobs 提取 enrich_records 内核，参数明确为 records、sources、cache、now、extractor、max_fetches、max_workers 和 fetcher。现有 enrich_jobs 用原 profile/application extractor；新增 enrich_foreign_campaigns 使用：

~~~python
extractor=lambda text, current: {
    "foreignHints": extract_foreign_hints(text, current),
    "applicationHints": extract_application_hints(text),
}
~~~

两条链路继续执行：成功缓存 7 天、失败缓存 6 小时、响应上限 2 MB、重定向不得离开 allowedDomains 或 allowedUrlPrefixes、每主机并发最多 2。

- [ ] **Step 6: 运行提取与详情回归后提交**

Run: python -m unittest tests.test_foreign_hints tests.test_profile_hints tests.test_application_hints tests.test_detail -v

Expected: 全部 PASS，旧 profileHints 与 applicationHints 行为不变。

~~~bash
git add crawler/foreign_sources.json crawler/foreign_hints.py crawler/profile_hints.py crawler/application_hints.py crawler/detail.py tests/test_foreign_hints.py tests/test_profile_hints.py tests/test_application_hints.py tests/test_detail.py
git commit -m "feat: add foreign campus source hints"
~~~

### Task 3: 实现官网优先去重、生命周期和 7 日新增摘要

**Files:**

- Create: crawler/foreign_crawl.py
- Create: crawler/cache/foreign-details.json
- Create: crawler/cache/foreign-seen.json
- Create: tests/test_foreign_crawl.py

**Interfaces:**

- Consumes: 企业、来源、旧快照、详情缓存和 seen 缓存。
- Produces: collect_foreign_source(source, companies, now, target_year) -> tuple[list[dict], dict]。
- Produces: dedupe_campaigns(campaigns: list[dict]) -> list[dict]。
- Produces: merge_foreign_previous(new_campaigns, previous, failed_sources, now) -> list[dict]。
- Produces: update_daily_summary(campaigns, previous, seen_cache, now, history_days=7) -> tuple[dict, list[dict], dict]。
- Produces: crawl_foreign(config_path, companies_path, output_path, now, dry_run=False, health_output_path=None) -> dict。

- [ ] **Step 1: 写出官网升级与摘要测试**

~~~python
import unittest
from datetime import datetime, timezone

from crawler.foreign_crawl import dedupe_campaigns, update_daily_summary


NOW = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)


def campaign(identifier, official, url):
    return {
        "id": identifier,
        "campaignKey": "deloitte|2027|graduate_program|autumn|general",
        "channel": "foreign",
        "company": {"id": "deloitte", "name": "德勤", "nameEn": "Deloitte", "industryTags": ["咨询/专业服务"]},
        "title": "Deloitte China 2027 Graduate Program",
        "url": url,
        "source": {
            "name": "企业官网" if official else "应届生求职网",
            "tier": "official_verified" if official else "third_party_only",
        },
        "alternateSources": [],
        "official": official,
        "publishedAt": "2026-08-21",
        "graduateYears": ["2027"],
        "campaignType": "graduate_program",
        "season": "autumn",
        "employmentType": "full_time",
        "cities": ["上海"],
        "jobFunctions": ["咨询"],
        "educationLevels": ["本科", "硕士"],
        "industryTags": ["咨询/专业服务"],
        "englishRequirements": [],
        "deadline": None,
        "status": "deadline_unknown",
        "summary": "",
    }


class ForeignCrawlTests(unittest.TestCase):
    def test_official_replaces_third_party_without_changing_id(self):
        third = campaign("foreign_same", False, "https://m.yingjiesheng.com/job-1.html")
        official = campaign("foreign_same", True, "https://www.deloitte.com/cn/careers/2027")
        result = dedupe_campaigns([third, official])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["official"])
        self.assertEqual(result[0]["id"], "foreign_same")
        self.assertEqual(result[0]["alternateSources"][0]["url"], third["url"])

    def test_bootstrap_is_not_today_new(self):
        today, history, seen = update_daily_summary(
            [campaign("foreign_a", True, "https://a.example/2027")], {}, {}, NOW,
        )
        self.assertTrue(today["bootstrap"])
        self.assertEqual(today["addedCount"], 0)
        self.assertEqual(today["baselineCount"], 1)
        self.assertEqual(history, [today])
        self.assertIn("foreign_a", seen["entries"])

    def test_official_upgrade_does_not_reset_first_seen(self):
        seen = {
            "schemaVersion": 1,
            "entries": {"foreign_a": {"firstSeenAt": "2026-08-21T07:20:00+08:00"}},
        }
        today, history, updated = update_daily_summary(
            [campaign("foreign_a", True, "https://official.example/a")],
            {"generatedAt": "2026-08-21T07:20:00+08:00", "summaryHistory": []},
            seen,
            NOW,
        )
        self.assertEqual(today["addedCount"], 0)
        self.assertEqual(updated["entries"]["foreign_a"]["firstSeenAt"], "2026-08-21T07:20:00+08:00")
~~~

- [ ] **Step 2: 运行测试并确认缺失模块**

Run: python -m unittest tests.test_foreign_crawl -v

Expected: FAIL with ModuleNotFoundError for crawler.foreign_crawl。

- [ ] **Step 3: 按来源级别选择主记录并保留证据链接**

~~~python
TIER_SCORE = {
    "official_verified": 400,
    "official_job_feed": 300,
    "secondary_verified": 200,
    "third_party_only": 100,
}


def campaign_score(campaign):
    return (
        TIER_SCORE.get(campaign.get("source", {}).get("tier"), 0)
        + (20 if campaign.get("deadline") else 0)
        + (10 if campaign.get("publishedAt") and not campaign.get("dateEstimated") else 0)
        + min(10, len(campaign.get("summary", "")) // 40)
    )


def dedupe_campaigns(campaigns):
    grouped = {}
    for campaign in campaigns:
        if campaign.get("campaignKey"):
            grouped.setdefault(campaign["campaignKey"], []).append(dict(campaign))
    result = []
    for candidates in grouped.values():
        ordered = sorted(candidates, key=campaign_score, reverse=True)
        chosen = ordered[0]
        chosen["alternateSources"] = [
            {"name": item["source"]["name"], "tier": item["source"]["tier"], "url": item["url"]}
            for item in ordered[1:]
            if item["url"] != chosen["url"]
        ][:8]
        chosen["official"] = chosen["source"]["tier"] in {
            "official_verified", "official_job_feed",
        }
        result.append(chosen)
    return sorted(
        result,
        key=lambda item: (item.get("publishedAt", ""), item["company"]["name"]),
        reverse=True,
    )
~~~

- [ ] **Step 4: 实现 firstSeenAt、同日并集和 7 日历史**

~~~python
from datetime import date, timedelta

from crawler.timezone import shanghai_timezone

SHANGHAI = shanghai_timezone()


def update_daily_summary(campaigns, previous, seen_cache, now, history_days=7):
    local_now = now.astimezone(SHANGHAI).replace(microsecond=0)
    today_key = local_now.date().isoformat()
    seen = {"schemaVersion": 1, "entries": dict(seen_cache.get("entries", {}))}
    history_by_date = {
        item["date"]: dict(item)
        for item in previous.get("summaryHistory", [])
        if isinstance(item, dict) and item.get("date")
    }
    bootstrap = not seen["entries"] and not previous.get("generatedAt")
    newly_seen = []
    for item in campaigns:
        entry = seen["entries"].get(item["id"])
        if entry:
            item["firstSeenAt"] = entry["firstSeenAt"]
        else:
            item["firstSeenAt"] = local_now.isoformat()
            seen["entries"][item["id"]] = {"firstSeenAt": item["firstSeenAt"]}
            newly_seen.append(item)
        item["lastSeenAt"] = local_now.isoformat()
    current = history_by_date.get(today_key, {
        "date": today_key,
        "bootstrap": bootstrap,
        "addedCount": 0,
        "baselineCount": len(campaigns) if bootstrap else 0,
        "items": [],
    })
    union = {item["id"]: item for item in current["items"]}
    if not bootstrap:
        for item in newly_seen:
            union[item["id"]] = {
                "id": item["id"], "company": item["company"]["name"],
                "title": item["title"], "url": item["url"], "official": bool(item["official"]),
            }
    current["items"] = sorted(union.values(), key=lambda item: (item["company"], item["title"]))
    current["addedCount"] = len(current["items"])
    history_by_date[today_key] = current
    cutoff = local_now.date() - timedelta(days=history_days - 1)
    history = [
        history_by_date[key]
        for key in sorted(history_by_date, reverse=True)
        if date.fromisoformat(key) >= cutoff
    ]
    return current, history, seen
~~~

- [ ] **Step 5: 实现采集顺序、生命周期和四文件原子写入**

crawl_foreign 必须依次：

1. 读取 config、company registry、旧 snapshot、旧 health、detail cache 和 seen cache。
2. 并发采集 campaign_page、html、rss_search 和 rss_search_registry；disabled/manual 来源不得联网。
3. resolve_company 后执行 evaluate_campaign；未注册企业计入 pendingReviewCount，但不公开。
4. 按 companyId + 2027 + campaignType + season + programKey 生成稳定 ID。
5. 官网优先去重；失败来源保留旧活动，成功来源消失的活动进入保留期。
6. 详情增强后设置 open、deadline_unknown、expired、stale；expired 保留 60 天，unknown 45 天后转 stale。
7. 更新摘要并运行 Task 4 的 validator 和质量门禁。
8. dry-run 不写文件；正式运行将四份内容先写同目录 .tmp，再依次 replace detail cache、seen cache、health、snapshot。

campaign_page 的 campaignTitle 只用于展示，绝不能作为 2027 或中国大陆的资格证据；requiredTerms 和页面正文必须实际包含目标届别。rss_search_registry 必须把每条结果重新限制在当前公司的 officialDomains 或已核验 delegatedUrlPrefixes。

公开快照必须包含 schemaVersion、channel、generatedAt、targetGraduateYear、total、campaigns、todaySummary、summaryHistory 和 sourceStatus。每条 campaign 必须包含 id、campaignKey、channel、company、title、titleLanguage、url、source、alternateSources、official、publishedAt、dateEstimated、firstSeenAt、lastSeenAt、graduateYears、campaignType、season、employmentType、cities、jobFunctions、educationLevels、industryTags、englishRequirements、deadline、deadlineConfidence、deadlineEvidence、summary 和 status。

- [ ] **Step 6: 运行采集测试和 dry-run 后提交**

Run: python -m unittest tests.test_foreign_crawl -v

Run: python crawler/foreign_crawl.py --config crawler/foreign_sources.json --companies crawler/foreign_companies.json --output data/foreign-campus.json --health-output data/foreign-health.json --dry-run

Expected: 启用来源为 ok、empty 或带安全错误的 error；不修改四个持久文件。

~~~bash
git add crawler/foreign_crawl.py crawler/cache/foreign-details.json crawler/cache/foreign-seen.json tests/test_foreign_crawl.py
git commit -m "feat: collect foreign campus campaigns"
~~~

### Task 4: 增加外企快照质量门禁、失败隔离和部署检查

**Files:**

- Create: crawler/foreign_health.py
- Create: scripts/check_foreign_snapshot.py
- Create: tests/test_foreign_health.py
- Modify: crawler/health.py
- Modify: scripts/check_public_site.py
- Modify: tests/test_health.py
- Modify: tests/test_workflow.py
- Modify: .github/workflows/update-jobs.yml

**Interfaces:**

- Consumes: data/foreign-campus.json、旧 data/foreign-health.json 和来源状态。
- Produces: validate_foreign_snapshot(payload: object) -> list[str]。
- Produces: build_foreign_health(payload: dict, previous_health: dict, now: datetime) -> dict。
- Produces: foreign_quality_violations(payload, previous_health, health, now) -> list[dict]。

- [ ] **Step 1: 写出逐项 schema 与工作流测试**

~~~python
def test_validator_rejects_wrong_cohort_duplicate_ids_and_broken_summary(self):
    payload = valid_foreign_payload()
    payload["campaigns"][0]["graduateYears"] = ["2028"]
    payload["campaigns"].append(dict(payload["campaigns"][0]))
    payload["todaySummary"]["items"] = [{
        "id": "foreign_missing", "company": "X", "title": "Y",
        "url": "https://example.com", "official": False,
    }]
    errors = validate_foreign_snapshot(payload)
    self.assertTrue(any("2027" in item for item in errors))
    self.assertTrue(any("duplicate" in item for item in errors))
    self.assertTrue(any("summary" in item for item in errors))


def test_workflow_collects_checks_and_commits_foreign_files(self):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    self.assertIn("crawler/foreign_crawl.py", workflow)
    self.assertIn("scripts/check_foreign_snapshot.py", workflow)
    self.assertIn("data/foreign-campus.json", workflow)
    self.assertIn("data/foreign-health.json", workflow)
    self.assertIn("crawler/cache/foreign-details.json", workflow)
    self.assertIn("crawler/cache/foreign-seen.json", workflow)
~~~

- [ ] **Step 2: 运行测试并确认缺失 validator**

Run: python -m unittest tests.test_foreign_health tests.test_workflow -v

Expected: FAIL because foreign_health and workflow commands do not exist。

- [ ] **Step 3: 实现强校验与来源健康指标**

~~~python
def validate_foreign_snapshot(payload):
    errors = []
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        return ["foreign snapshot must use schemaVersion 1"]
    campaigns = payload.get("campaigns")
    if not isinstance(campaigns, list):
        return ["foreign campaigns must be an array"]
    if payload.get("total") != len(campaigns):
        errors.append("foreign total does not match campaigns")
    identifiers = []
    for index, item in enumerate(campaigns):
        prefix = "campaigns[" + str(index) + "]"
        if not re.fullmatch(r"foreign_[0-9a-f]{20}", str(item.get("id", ""))):
            errors.append(prefix + ".id is invalid")
        identifiers.append(item.get("id"))
        if item.get("graduateYears") != ["2027"]:
            errors.append(prefix + " must target 2027")
        if item.get("employmentType") != "full_time":
            errors.append(prefix + " must be full_time")
        if item.get("status") not in {"open", "deadline_unknown", "expired", "stale"}:
            errors.append(prefix + ".status is invalid")
        if not isinstance(item.get("company"), dict) or not item["company"].get("id"):
            errors.append(prefix + ".company is required")
        if not str(item.get("url", "")).startswith(("http://", "https://")):
            errors.append(prefix + ".url is invalid")
    if len(identifiers) != len(set(identifiers)):
        errors.append("foreign campaign ids contain duplicates")
    known = set(identifiers)
    for summary in payload.get("summaryHistory", []):
        for item in summary.get("items", []):
            if item.get("id") not in known:
                errors.append("summary references an unknown campaign id")
    return errors
~~~

build_foreign_health 必须公开 currentTotal、activeTotal、expiredRetainedTotal、newToday、officialSourceRatio、registeredCompanyCount、pendingReviewCount、sourceSuccessRate、failedSourceCount、sources 和 lastSuccessfulAt。官方比例低于 50%为 warning；非零快照骤降超过 40%、来源成功率低于 60%、连续两次失败为现有同级门禁。

如果本次全部来源失败但存在 7 天内的上次成功快照，保留旧 campaigns、todaySummary 和 seen cache，只更新 health 的失败状态并以 warning 结束，让公考频道仍可部署；超过 7 天仍无成功采集时升级为 critical。

- [ ] **Step 4: 将公网检查扩展为五个目标**

crawler.health.check_public_site 的 targets 固定为 homepage、jobs、health、foreign-campus 和 foreign-health。foreign-campus 调用 validate_foreign_snapshot，foreign-health 调用 validate_foreign_health。

~~~python
targets = [
    ("homepage", base_url, "html"),
    ("jobs", urljoin(base_url, "data/jobs.json"), "jobs"),
    ("health", urljoin(base_url, "data/health.json"), "health"),
    ("foreign-campus", urljoin(base_url, "data/foreign-campus.json"), "foreign"),
    ("foreign-health", urljoin(base_url, "data/foreign-health.json"), "foreign-health"),
]
~~~

- [ ] **Step 5: 更新北京时间 07:20 工作流**

在现有公考更新之后加入：

~~~yaml
      - name: 更新外企校招数据
        run: python crawler/foreign_crawl.py --config crawler/foreign_sources.json --companies crawler/foreign_companies.json --output data/foreign-campus.json --health-output data/foreign-health.json

      - name: 检查外企校招快照质量
        run: python scripts/check_foreign_snapshot.py --campaigns data/foreign-campus.json --health data/foreign-health.json
~~~

将保存命令改为：

~~~yaml
          git add data/jobs.json data/health.json data/foreign-campus.json data/foreign-health.json crawler/cache/details.json crawler/cache/foreign-details.json crawler/cache/foreign-seen.json
~~~

部署仍使用 cp -r assets data _site/。不要改变 cron 20 23 * * *。

- [ ] **Step 6: 运行后端和工作流回归后提交**

Run: python -m unittest tests.test_foreign_health tests.test_health tests.test_workflow -v

Run: python -m unittest discover -s tests -p "test_*.py" -v

Expected: 所有 Python 测试 PASS，公网检查要求五个目标。

~~~bash
git add crawler/foreign_health.py crawler/health.py scripts/check_foreign_snapshot.py scripts/check_public_site.py tests/test_foreign_health.py tests/test_health.py tests/test_workflow.py .github/workflows/update-jobs.yml
git commit -m "ci: validate foreign campus snapshots"
~~~

### Task 5: 实现独立外企筛选、URL 状态和画像匹配

**Files:**

- Create: assets/channels.mjs
- Create: assets/foreign-core.mjs
- Create: assets/foreign-matching.mjs
- Create: tests/foreign-core.test.mjs
- Create: tests/foreign-matching.test.mjs
- Modify: assets/matching.mjs
- Modify: tests/matching.test.mjs
- Modify: package.json

**Interfaces:**

- Produces: CHANNELS、channelFromSearchParams(params)、searchParamsForChannel(channel, state)。
- Produces: DEFAULT_FOREIGN_STATE、normalizeForeignCampaign(value)、filterForeignCampaigns(campaigns, filters, now)、sortForeignCampaigns(campaigns, mode, now)、foreignStateFromSearchParams(params)、normalizeDailySummaries(value)。
- Produces: analyzeForeignCampaign(campaign, profile)、filterForeignByMatchMode(campaigns, mode, profile)。

- [ ] **Step 1: 写出组合筛选、截止状态和 URL 往返测试**

~~~javascript
test('foreign filters combine without splitting a company campaign', () => {
  const result = filterForeignCampaigns(CAMPAIGNS, {
    ...DEFAULT_FOREIGN_STATE,
    q: 'marketing',
    company: 'deloitte',
    jobFunction: '市场/品牌',
    city: '上海',
    graduationYear: '2027',
    degree: '硕士',
    recruitmentType: 'graduate_program',
  }, NOW);
  assert.deepEqual(result.map((item) => item.id), ['foreign_a']);
});

test('open is the default and saved mode can reveal expired records', () => {
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, DEFAULT_FOREIGN_STATE, NOW).map((item) => item.id),
    ['foreign_a', 'foreign_unknown'],
  );
  assert.deepEqual(
    filterForeignCampaigns(CAMPAIGNS, {
      ...DEFAULT_FOREIGN_STATE,
      deadline: 'all',
      savedOnly: true,
      savedIds: ['foreign_expired'],
    }, NOW).map((item) => item.id),
    ['foreign_expired'],
  );
});

test('foreign URL state rejects unsupported enum values', () => {
  const state = foreignStateFromSearchParams(new URLSearchParams(
    'channel=foreign&company=deloitte&degree=invalid&deadline=expired&sort=match',
  ));
  assert.equal(state.company, 'deloitte');
  assert.equal(state.degree, '全部');
  assert.equal(state.deadline, 'expired');
  assert.equal(state.sort, 'match');
});
~~~

- [ ] **Step 2: 写出旧画像兼容和可解释匹配测试**

~~~javascript
test('legacy profiles gain safe foreign defaults', () => {
  const profile = normalizeProfile({ major: '中国语言文学', graduationYear: '2027' });
  assert.deepEqual(profile.targetFunctions, []);
  assert.deepEqual(profile.preferredIndustries, []);
  assert.equal(profile.englishLevel, '未设置');
  assert.equal(profile.major, '中国语言文学');
});

test('foreign matching explains function city industry and cohort', () => {
  const match = analyzeForeignCampaign(CAMPAIGNS[0], normalizeProfile({
    graduationYear: '2027',
    preferredLocations: ['上海'],
    targetFunctions: ['市场/品牌'],
    preferredIndustries: ['咨询/专业服务'],
    englishLevel: '英语六级',
  }));
  assert.ok(match.score >= 60);
  assert.ok(match.reasons.some((item) => item.includes('市场/品牌')));
  assert.ok(match.reasons.some((item) => item.includes('上海')));
  assert.doesNotMatch(match.label, /保证|录用|符合资格/);
});
~~~

- [ ] **Step 3: 实现频道配置并保留旧 URL**

~~~javascript
export const CHANNELS = Object.freeze({
  public: {
    id: 'public',
    label: '公考招录',
    dataUrl: './data/jobs.json',
    healthUrl: './data/health.json',
  },
  foreign: {
    id: 'foreign',
    label: '外企校招',
    dataUrl: './data/foreign-campus.json',
    healthUrl: './data/foreign-health.json',
  },
});

export function channelFromSearchParams(params) {
  return params.get('channel') === 'foreign' ? 'foreign' : 'public';
}

export function searchParamsForChannel(channel, state) {
  if (channel === 'public') return searchParamsFromState(state);
  const params = foreignSearchParamsFromState(state);
  params.set('channel', 'foreign');
  return params;
}
~~~

- [ ] **Step 4: 实现外企纯函数状态**

DEFAULT_FOREIGN_STATE 必须包含 q、company、jobFunction、city、graduationYear、degree、recruitmentType、freshness、deadline、sort、match、savedOnly 和 savedIds。枚举固定为：

- graduationYear：全部、2027。
- degree：全部、本科、硕士、博士。
- recruitmentType：全部、campus_recruitment、graduate_program、management_trainee、supplemental。
- deadline：open、7days、30days、unknown、expired、all。
- sort：newest、deadline、company、match。
- match：all、recommended、function、location、verify。

~~~javascript
export function filterForeignCampaigns(campaigns, filters, now = new Date()) {
  const query = String(filters.q || '').trim().toLocaleLowerCase('zh-CN');
  const saved = new Set(filters.savedIds || []);
  return campaigns.map(normalizeForeignCampaign).filter((item) => {
    const searchable = [
      item.title, item.company.name, item.company.nameEn, item.summary,
      ...item.cities, ...item.jobFunctions, ...item.industryTags,
    ].join(' ').toLocaleLowerCase('zh-CN');
    if (query && !searchable.includes(query)) return false;
    if (filters.company !== '全部' && item.company.id !== filters.company) return false;
    if (filters.jobFunction !== '全部' && !item.jobFunctions.includes(filters.jobFunction)) return false;
    if (filters.city !== '全部' && !item.cities.includes(filters.city)) return false;
    if (filters.graduationYear !== '全部' && !item.graduateYears.includes(filters.graduationYear)) return false;
    if (filters.degree !== '全部' && !item.educationLevels.includes(filters.degree)) return false;
    if (filters.recruitmentType !== '全部' && item.campaignType !== filters.recruitmentType) return false;
    if (!deadlineMatches(item, filters.deadline, now)) return false;
    if (!freshnessMatches(item.publishedAt, filters.freshness, now)) return false;
    if (filters.savedOnly && !saved.has(item.id)) return false;
    return true;
  });
}
~~~

normalizeDailySummaries 只接受最近 7 个合法 YYYY-MM-DD 日期，去重 item.id，并剔除非 HTTP URL。公司级记录始终返回一条记录，数组字段只参与匹配。

deadline=open 只包含 status=open 和 status=deadline_unknown；status=expired 与 status=stale 均默认隐藏。savedOnly 模式将 deadline 切换为 all，确保保留期内的历史收藏仍可打开。

- [ ] **Step 5: 扩展画像并实现外企匹配**

normalizeProfile 在返回对象中追加：

~~~javascript
targetFunctions: cleanList(candidate.targetFunctions, {
  allowed: new Set(FOREIGN_FUNCTIONS),
  limit: FOREIGN_FUNCTIONS.length,
}),
preferredIndustries: cleanList(candidate.preferredIndustries, {
  allowed: new Set(FOREIGN_INDUSTRIES),
  limit: FOREIGN_INDUSTRIES.length,
}),
englishLevel: FOREIGN_ENGLISH_LEVELS.has(candidate.englishLevel)
  ? candidate.englishLevel
  : '未设置',
~~~

analyzeForeignCampaign 评分固定为：2027 届匹配 25 分、目标职能最多 30 分、偏好城市 15 分、行业 15 分、学历兼容 10 分；公告英语要求高于画像时只给 warning，不声称不具资格。recommended 为分数至少 40 且无届别冲突；function、location、verify 使用独立 tier。

- [ ] **Step 6: 扩充 npm test 并运行全部纯函数测试**

package.json：

~~~json
{
  "scripts": {
    "test": "node --test tests/core.test.mjs tests/foreign-core.test.mjs tests/matching.test.mjs tests/foreign-matching.test.mjs tests/application.test.mjs tests/favorites.test.mjs",
    "serve": "python -m http.server 4173",
    "test:browser": "node tests/browser-smoke.mjs"
  }
}
~~~

Run: npm test

Expected: 现有 28 项 Node 测试和新增外企测试全部 PASS。

~~~bash
git add assets/channels.mjs assets/foreign-core.mjs assets/foreign-matching.mjs assets/matching.mjs tests/foreign-core.test.mjs tests/foreign-matching.test.mjs tests/matching.test.mjs package.json
git commit -m "feat: add foreign channel filtering and matching"
~~~

### Task 6: 增加双频道导航、外企摘要、筛选与公司级卡片

**Files:**

- Modify: index.html
- Modify: assets/app.js
- Modify: assets/styles.css
- Modify: tests/browser-smoke.mjs

**Interfaces:**

- Consumes: CHANNELS、两份公开 payload、两套 state、共享 profile 和 workspace。
- Produces: loadChannelData(channel, { force = false })、switchChannel(channel, { historyMode = "push" })、activePayload()、findJobById(id)。

- [ ] **Step 1: 先扩展浏览器 smoke fixture**

使用 page.route 拦截 data/foreign-campus.json，返回固定的一条官网记录、一条第三方记录和一条过期记录；拦截 data/foreign-health.json 返回健康来源。测试必须覆盖：

~~~javascript
await page.goto(baseUrl + '/?channel=foreign', { waitUntil: 'networkidle' });
assert.equal(await page.locator('#foreignChannelLink').getAttribute('aria-current'), 'page');
assert.match(await page.locator('#pageTitle').textContent(), /外企校招/);
assert.equal(await page.locator('.job-item').count(), 2);
assert.match(await page.locator('#foreignTodaySummary').textContent(), /今日新增/);
assert.match(await page.locator('.job-item').nth(1).textContent(), /第三方信息，请核验/);

await page.locator('#foreignCompany').selectOption('deloitte');
await page.locator('#publicChannelLink').click();
await page.locator('#foreignChannelLink').click();
assert.equal(await page.locator('#foreignCompany').inputValue(), 'deloitte');

await page.goBack();
assert.equal(await page.locator('#publicChannelLink').getAttribute('aria-current'), 'page');
await page.goForward();
assert.equal(await page.locator('#foreignChannelLink').getAttribute('aria-current'), 'page');
~~~

- [ ] **Step 2: 增加真实频道链接和外企专属控件**

在 site-header 品牌之后加入：

~~~html
<nav class="channel-nav" id="channelNav" aria-label="招聘频道">
  <a id="publicChannelLink" href="./" data-channel="public" aria-current="page">公考招录</a>
  <a id="foreignChannelLink" href="?channel=foreign" data-channel="foreign">外企校招</a>
</nav>
~~~

在 search-deck 内保留一个搜索框；公考 category、audience 控件包进 data-channel-fields="public"，新增：

~~~html
<fieldset class="foreign-filter-grid" id="foreignFilters" data-channel-fields="foreign" hidden>
  <legend class="visually-hidden">外企校招筛选</legend>
  <label><span>企业</span><select id="foreignCompany"><option value="全部">全部企业</option></select></label>
  <label><span>岗位职能</span><select id="foreignFunction"><option value="全部">全部职能</option></select></label>
  <label><span>城市</span><select id="foreignCity"><option value="全部">全部城市</option></select></label>
  <label><span>毕业年份</span><select id="foreignGraduationYear"><option value="2027">2027 届</option></select></label>
  <label><span>学历</span><select id="foreignDegree"><option value="全部">不限学历</option><option value="本科">本科</option><option value="硕士">硕士</option><option value="博士">博士</option></select></label>
  <label><span>招聘类型</span><select id="foreignRecruitmentType"><option value="全部">全部类型</option><option value="campus_recruitment">校园招聘</option><option value="graduate_program">Graduate Program</option><option value="management_trainee">管培生</option><option value="supplemental">补录</option></select></label>
  <label><span>截止状态</span><select id="foreignDeadline"><option value="open">报名中与日期待核</option><option value="7days">7 天内截止</option><option value="30days">30 天内截止</option><option value="unknown">日期待核</option><option value="expired">已截止</option><option value="all">全部状态</option></select></label>
</fieldset>
~~~

在 feed 前加入带 time 元素的 foreignTodaySummary section 和 summaryHistory details；两者仅在 foreign 频道显示。

- [ ] **Step 3: 将 app.js 改为双 payload 与双 state**

~~~javascript
let activeChannel = channelFromSearchParams(new URLSearchParams(location.search));
const payloads = {
  public: { generatedAt: null, jobs: [], sourceStatus: [] },
  foreign: { generatedAt: null, campaigns: [], sourceStatus: [], summaryHistory: [] },
};
const states = {
  public: {
    ...stateFromSearchParams(new URLSearchParams(location.search)),
    savedOnly: false,
    savedIds: workspace.savedIds,
  },
  foreign: {
    ...foreignStateFromSearchParams(new URLSearchParams(location.search)),
    savedOnly: false,
    savedIds: workspace.savedIds,
  },
};

function activePayload() {
  return payloads[activeChannel];
}

function allRecords() {
  return [...payloads.public.jobs, ...payloads.foreign.campaigns];
}

function findJobById(id) {
  return allRecords().find((item) => item.id === id) || null;
}
~~~

loadChannelData 必须分别 fetch CHANNELS[channel].dataUrl；一个频道失败只能显示该频道的错误，不得清空另一个频道。首次加载并行请求两份数据，使收藏工作区能跨频道解析标题。

switchChannel 必须保存当前 state，切换 aria-current、hidden 区域、页面文案和 placeholder，使用 pushState 写入当前频道 URL；筛选变化继续 replaceState。popstate 从 URL 恢复频道及 state。

- [ ] **Step 4: 使用频道 view model 渲染同一个安全模板**

公考 view model 保持现有字段与文案。外企 view model 固定映射：

~~~javascript
function foreignCardModel(campaign) {
  return {
    id: campaign.id,
    title: campaign.title,
    url: campaign.url,
    source: campaign.source.name,
    badge: campaign.official ? '企业官方' : '第三方信息，请核验',
    badgeTone: campaign.official ? 'official' : 'third-party',
    primaryMeta: [
      campaign.company.name,
      campaign.cities.length ? campaign.cities.join('、') : '中国多地',
      campaign.graduateYears.join('、') + '届',
      campaign.educationLevels.length ? campaign.educationLevels.join('、') : '学历见公告',
      deadlineState(campaign.deadline).label,
    ],
    secondaryMeta: [
      ...campaign.jobFunctions,
      campaignTypeLabel(campaign.campaignType),
    ],
    actionLabel: campaign.official ? '查看企业招聘页' : '查看第三方信息',
  };
}
~~~

所有外部字段继续使用 textContent，不得插入 innerHTML。英文长标题、公司名和数组元数据允许换行。results 不再设置 aria-live；只由 resultSummary 的 aria-live="polite" 宣读数量变化。

- [ ] **Step 5: 渲染今天摘要与 7 日历史**

bootstrap 为 true 时显示“首批收录 N 场外企校招”；否则显示“今日新增 N 场”。每个摘要条目显示公司、标题、官网或第三方文字标识。点击“只看今日新增”将 foreign state 增加 todayOnly=true 并按摘要 ID 过滤；没有新增时显示明确的 0 场状态。

- [ ] **Step 6: 完成响应式和无障碍样式**

桌面 foreign-filter-grid 为四列两行；不超过 900px 为两列；不超过 620px 为一列。窄屏 header 第一行放品牌和工具，channel-nav 横跨第二行。频道链接、选择框、摘要按钮、收藏和申请按钮最小高度 44px；第三方状态必须同时有文字和边框，不能只靠颜色。

- [ ] **Step 7: 运行 smoke 和移动端检查后提交**

Run: python -m http.server 4173

Run in a second terminal: node tests/browser-smoke.mjs

Expected: 默认仍为公考；直接外企链接、频道历史、独立筛选、摘要、第三方标识和 390px 无横向滚动全部 PASS，控制台无错误。

~~~bash
git add index.html assets/app.js assets/styles.css tests/browser-smoke.mjs
git commit -m "feat: add foreign campus channel interface"
~~~

### Task 7: 让画像、收藏、申请助手和日历跨频道工作

**Files:**

- Modify: assets/application.mjs
- Modify: assets/favorites.mjs
- Modify: assets/app.js
- Modify: index.html
- Modify: tests/application.test.mjs
- Modify: tests/favorites.test.mjs
- Modify: tests/browser-smoke.mjs

**Interfaces:**

- Consumes: channel="public" 或 channel="foreign" 的记录。
- Produces: 同一 workspace 中无冲突的 public ID 和 foreign_ ID。
- Produces: 外企五步申请指南、第三方核验提醒、截止日历和兼容旧备份的公开字段。

- [ ] **Step 1: 写出外企申请指南和 v1 备份兼容测试**

~~~javascript
test('foreign guide keeps stable step ids and uses application wording', () => {
  const guide = buildApplicationGuide({
    channel: 'foreign',
    official: false,
    applicationHints: {},
  });
  assert.deepEqual(guide.steps.map((item) => item.id), [
    'read', 'qualify', 'materials', 'submit', 'retain',
  ]);
  assert.match(guide.steps[1].detail, /学历.*届别.*语言.*工作地点/);
  assert.ok(guide.materials.some((item) => item.label === '中英文简历'));
});

test('foreign third-party record produces a verification alert', () => {
  const alerts = getJobAlerts(
    { channel: 'foreign', official: false, deadline: null },
    { tier: 'verify' },
    NOW,
  );
  assert.ok(alerts.some((item) => item.type === 'source'));
  assert.ok(alerts.some((item) => item.label.includes('第三方')));
});

test('backup preserves optional foreign identity while accepting v1', () => {
  const workspace = normalizeWorkspace({ savedIds: ['foreign_a'] });
  const backup = exportWorkspace(workspace, [{
    id: 'foreign_a',
    channel: 'foreign',
    company: { name: '德勤' },
    title: '2027 Graduate Program',
    url: 'https://example.com/a',
  }]);
  assert.equal(backup.version, 1);
  assert.equal(backup.jobs[0].channel, 'foreign');
  assert.equal(backup.jobs[0].company, '德勤');
  assert.deepEqual(importWorkspace(JSON.stringify(backup)).savedIds, ['foreign_a']);
});
~~~

- [ ] **Step 2: 实现频道化五步指南而不改变进度 key**

~~~javascript
const FOREIGN_GENERIC_MATERIALS = Object.freeze([
  { key: 'foreign-resume', label: '中英文简历' },
  { key: 'foreign-transcript', label: '成绩单' },
  { key: 'foreign-education', label: '在读或学历证明' },
  { key: 'foreign-language', label: '语言成绩或证书' },
  { key: 'foreign-portfolio', label: '求职信、作品集或项目材料' },
]);

function foreignSteps(methodText, materialsAreGeneric, materialCount) {
  return [
    { id: 'read', label: '核验招聘活动与入口', detail: '优先查看企业官网；第三方信息必须再次核对。' },
    { id: 'qualify', label: '核对申请条件', detail: '逐项核对学历、专业、2027届、语言要求和工作地点。' },
    {
      id: 'materials',
      label: '准备申请材料',
      detail: materialsAreGeneric
        ? '尚未提取到完整材料要求，按通用清单准备并以招聘页为准。'
        : '已识别 ' + materialCount + ' 项材料线索，请对照招聘页复核。',
    },
    { id: 'submit', label: '完成在线申请', detail: methodText },
    { id: 'retain', label: '跟进测评与面试', detail: '保存申请编号，留意在线测评、面试和补充材料通知。' },
  ];
}
~~~

buildApplicationGuide 根据 job.channel 选择公共招录或外企步骤；步骤 id 永远保持 read、qualify、materials、submit、retain，避免旧进度失效。getJobAlerts 对外企使用“申请条件待核对”，并为 official=false 增加“第三方信息，请核验”。

- [ ] **Step 3: 扩充备份公开字段但保留版本 1**

~~~javascript
function publicJob(job) {
  return {
    id: cleanId(job.id),
    channel: job.channel === 'foreign' ? 'foreign' : 'public',
    company: String(job.company?.name || job.company || '').slice(0, 100),
    title: String(job.title || '').slice(0, 200),
    url: /^https?:\/\//.test(String(job.url || '')) ? String(job.url) : '',
    deadline: /^\d{4}-\d{2}-\d{2}$/.test(String(job.deadline || '')) ? job.deadline : null,
    source: String(job.source?.name || job.source || '').slice(0, 100),
    category: String(job.category || '').slice(0, 30),
    location: String(job.location || job.cities?.join('、') || '').slice(0, 100),
  };
}
~~~

importWorkspace 继续只要求 schema=job-radar-backup、version=1 和 workspace，因此历史备份不变。新增字段只用于导出后的可读性。

- [ ] **Step 4: 扩展画像表单**

在 profileForm 增加目标职能复选框、偏好行业复选框和英语水平 select；选项必须与 Task 5 的枚举完全一致。targetFunctions 默认不替用户猜测，保持空数组；graduationYear 仍由用户填写，但外企频道提示当前只展示 2027 届。

表单提交追加：

~~~javascript
targetFunctions: data.getAll('foreignFunction'),
preferredIndustries: data.getAll('foreignIndustry'),
englishLevel: data.get('englishLevel'),
~~~

renderProfileSummary 在外企频道追加已设置的目标职能、行业和英语水平；公考频道现有摘要文案不变。

- [ ] **Step 5: 修复跨频道收藏查找**

evaluatedJob、openApplicationDialog、renderWorkspaceList、calendarExport 和 workspaceExport 全部使用 findJobById 或 allRecords，不得只访问当前 payload。打开“我的收藏”时，外企 state 自动使用 deadline=all，以便已截止但仍在 60 日保留期内的收藏可见。

- [ ] **Step 6: 扩展浏览器持久化测试**

浏览器 smoke 必须在外企频道收藏一条、填写备注、勾选步骤、切到公考、打开收藏工作区、再次打开该外企申请助手并验证备注/清单；随后刷新并重复验证。最后导出的 JSON 必须同时包含 public 与 foreign 记录。

- [ ] **Step 7: 运行全部 Node 与浏览器测试后提交**

Run: npm test

Run: node tests/browser-smoke.mjs

Expected: 纯函数测试和跨频道 smoke 全部 PASS；旧收藏、旧画像和旧备份继续工作。

~~~bash
git add assets/application.mjs assets/favorites.mjs assets/app.js index.html tests/application.test.mjs tests/favorites.test.mjs tests/browser-smoke.mjs
git commit -m "feat: share application workspace across channels"
~~~

### Task 8: 生成首份真实快照、记录覆盖范围并完成端到端验收

**Files:**

- Create: data/foreign-campus.json
- Create: data/foreign-health.json
- Create: docs/foreign-source-coverage.md
- Modify: README.md
- Modify: docs/weekly-improvement-log.md

**Interfaces:**

- Consumes: Tasks 1–7 完成的采集、前端和 CI。
- Produces: 可部署的真实外企校招快照、来源覆盖说明和维护记录。

- [ ] **Step 1: 复核首批来源的访问与授权边界**

docs/foreign-source-coverage.md 必须为每个来源记录 source ID、tier、URL、robots URL、terms URL、checkedAt、enabled、最近状态和限制。首批重点复核：

- [德勤中国 2027 Graduate Program](https://www.deloitte.com/cn/en/careers/explore-your-fit/students/graduate-program.html)
- [德意志银行学生与毕业生申请时间](https://careers.db.com/students-graduates/your-application/)
- [普华永道中国学生招聘](https://www.pwccn.com/en/careers/students.html)
- [Sanofi 中国 Graduate Program 示例](https://jobs.sanofi.cn/zh-hans/%E5%B7%A5%E4%BD%9C/%E4%B8%8A%E6%B5%B7/m-and-s-graduate-program-project-manager-trainee-shanghai/3036/42369410304)
- [Apple 中国学生岗位搜索](https://jobs.apple.com/zh-cn/search?location=china-CHNC&team=corporate-STDNT-CORP)
- [Microsoft Students](https://careers.microsoft.com/v2/global/en/students)
- [Microsoft Greater China](https://careers.microsoft.com/v2/global/en/locations/gcr.html)
- [Siemens 公开岗位搜索](https://jobs.siemens.com/en_US/externaljobs/SearchJobs/)
- [Bosch 中国职业入口](https://www.bosch.com.cn/careers/)
- [牛客校招日程](https://www.nowcoder.com/jobs/school/schedule)
- [牛客 robots.txt](https://www.nowcoder.com/robots.txt)
- [应届生求职网 robots.txt](https://www.yingjiesheng.com/robots.txt)
- [实习僧用户协议](https://www.shixiseng.com/rule)

若来源要求登录、验证码、Cookie 挑战，或条款禁止自动访问，将 enabled 设为 false 并写明原因；不得换用个人 Cookie、隐藏接口或验证码服务。

- [ ] **Step 2: 运行两次联网 dry-run**

Run twice: python crawler/foreign_crawl.py --config crawler/foreign_sources.json --companies crawler/foreign_companies.json --output data/foreign-campus.json --health-output data/foreign-health.json --dry-run

Expected:

- 只出现 2027、中国大陆、正式全职校招活动。
- 实习、社招、海外岗位和未注册企业不进入公开 campaigns。
- 相同活动来自多个来源时只保留一张卡，官网链接为主。
- 两次 dry-run 不改变 data 或 cache。

- [ ] **Step 3: 生成首份正式快照并通过门禁**

Run: python crawler/foreign_crawl.py --config crawler/foreign_sources.json --companies crawler/foreign_companies.json --output data/foreign-campus.json --health-output data/foreign-health.json

Run: python scripts/check_foreign_snapshot.py --campaigns data/foreign-campus.json --health data/foreign-health.json

Expected: 快照非空、所有公开活动为 2027 full_time、摘要 bootstrap=true 且 addedCount=0、来源成功率至少 60%。如果没有任何合格真实活动，停止发布并修复来源；不得写入虚构种子数据。

- [ ] **Step 4: 运行全量自动化测试**

Run: python -m unittest discover -s tests -p "test_*.py" -v

Run: npm test

Expected: 全部 Python 和 Node 测试 PASS。

- [ ] **Step 5: 运行本地浏览器验收**

Run: python -m http.server 4173

Run in a second terminal: node tests/browser-smoke.mjs

验收桌面 1440×1000 和移动端 390×844：

- 默认打开公考招录，旧查询 URL 结果不变。
- 外企频道展示独立摘要、筛选和公司级卡片。
- 官网与第三方文字标识正确。
- 频道切换、浏览器返回/前进和刷新后状态正确。
- 收藏、备注、清单、备份和日历跨频道可用。
- 没有横向溢出、按钮触控高度不足、控制台错误或加载错误。

- [ ] **Step 6: 更新用户文档和持续扩展规则**

README.md 必须说明：

- 外企频道只覆盖外企在中国大陆发布、面向 2027 届的正式全职校招。
- 官网优先、第三方核验、英文原标题、公司级活动粒度和每日 07:20 更新。
- 今日新增按首次发现，不按发布日期；首次运行显示首批收录。
- 过期默认隐藏 60 天、截止未知 45 天后标记 stale。
- 画像、收藏和申请数据仅在浏览器本地。
- 来源受登录、条款、验证码和动态页面限制，网站不保证绝对完整。

docs/foreign-source-coverage.md 将扩展分为三个可验收批次：

1. 当前交付：50 家已核验注册企业，至少 3 个直接官网活动源、官网注册表搜索、应届生发现源，牛客按条款复核结果启用或禁用，实习僧 manual_only。
2. 后续覆盖：150–250 家已核验企业，优先增加 employer-linked ATS、Lever Public Postings API、SmartRecruiters Public Posting API 和 Ashby public job board feed。
3. 长尾维护：高校就业网和允许的平台只作发现队列；每周核验新企业所有权与官网，公开 registeredCompanyCount、healthy sources、officialSourceRatio 和 pendingReviewCount。

- [ ] **Step 7: 提交数据与文档**

~~~bash
git add data/foreign-campus.json data/foreign-health.json crawler/cache/foreign-details.json crawler/cache/foreign-seen.json README.md docs/foreign-source-coverage.md docs/weekly-improvement-log.md
git commit -m "data: launch foreign campus channel"
~~~

- [ ] **Step 8: 推送后验证 GitHub Pages**

Run: git push origin main

Run:

~~~powershell
$runs = gh run list --limit 1 --json databaseId | ConvertFrom-Json
gh run watch $runs[0].databaseId --exit-status
~~~

Expected: 公考采集、外企采集、Python 测试、Node 测试、两份快照门禁、Pages 部署和五目标公网 smoke 全部成功。

## Self-Review

- **Spec coverage:** Task 1 覆盖外企定义、2027、正式全职、中国大陆和公司级身份；Tasks 2–4 覆盖官网/第三方来源、合规边界、每日采集、去重、摘要、过期保留和健康状态；Tasks 5–7 覆盖双频道、推荐筛选、画像、收藏、申请助手和日历；Task 8 覆盖真实数据、文档和上线验证。
- **Source truthfulness:** 实习僧未自动化；牛客必须再次核对条款；应届生仅作为转载线索；共享 ATS 必须有企业官网委托证据。
- **Type consistency:** 后端与前端统一使用 campaigns、foreign_ ID、company.id、graduateYears、campaignType、cities、jobFunctions、educationLevels、industryTags、todaySummary 和 summaryHistory。
- **Backward compatibility:** data/jobs.json、公考筛选函数、旧 URL、localStorage key 和 v1 收藏备份保持兼容。
- **Failure isolation:** 外企来源失败不清空旧快照；7 天内的旧快照以 warning 保留，避免拖垮公考频道部署。
- **No fabricated content:** 首次正式快照只能来自真实可核验来源，无法采到合格活动时停止交付，不写虚构记录。
