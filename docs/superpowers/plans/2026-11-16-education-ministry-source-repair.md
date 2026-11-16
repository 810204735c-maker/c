# 教育部公务员招录来源修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复教育部公务员招录来源，使每日采集能从稳定的官方栏目识别“考录”公告。

**Architecture:** 保留现有 HTML 列表解析和官方域名白名单。只更换失效的教育部栏目 URL，并将官方标题使用的“考录”加入招考标题词表。不增加搜索引擎依赖，不降低域名校验，不绕过访问限制。

**Tech Stack:** Python 3.12 标准库、`unittest`、JSON 来源配置、Node.js 前端测试、Playwright/Edge 浏览器烟雾测试。

## Global Constraints

- 不覆盖工作区中已有的用户改动。
- 仅访问无需登录的教育部官方页面，不绕过 Cookie、验证码或站点限制。
- 只有 Python、Node、联网试采集和浏览器烟雾测试全部通过后，才能提交和推送 `main`。
- 不使用强制推送，不重写历史，不改动账号、密钥、付费服务或 Pages 设置。

---

### Task 1: 增加教育部来源回归保护

**Files:**
- Modify: `tests/test_crawl.py`
- Modify: `crawler/crawl.py`
- Modify: `crawler/sources.json`

**Interfaces:**
- Consumes: `is_recruitment_title(title: str) -> bool`、`parse_html(html_text: str, source: dict, now: datetime) -> list[dict]`。
- Produces: 能识别“关于教育部2027年度公务员考录职位要求的说明”的标题规则，以及指向 `https://hudong.moe.gov.cn/jyb_xwfb/moe_2082/siju/rss/jggwyzl/` 的官方来源配置。

- [ ] **Step 1: 写失败测试**

```python
def test_education_ministry_source_uses_current_official_listing(self):
    config_path = Path(__file__).resolve().parents[1] / "crawler" / "sources.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = next(item for item in config["sources"] if item["name"] == "教育部公务员招录")
    self.assertEqual(
        source["url"],
        "https://hudong.moe.gov.cn/jyb_xwfb/moe_2082/siju/rss/jggwyzl/",
    )
    self.assertEqual(source["allowedDomains"], ["moe.gov.cn"])

def test_parse_html_accepts_official_civil_service_exam_recruitment_title(self):
    source = {
        "name": "教育部公务员招录",
        "url": "https://hudong.moe.gov.cn/jyb_xwfb/moe_2082/siju/rss/jggwyzl/",
        "category": "公务员",
        "allowedDomains": ["moe.gov.cn"],
        "maxItems": 50,
    }
    html = (
        '<li><a href="./202610/t20261014_1455803.html">'
        '关于教育部2027年度公务员考录职位要求的说明</a>'
        '<span>2026-10-14</span></li>'
    )
    jobs = parse_html(html, source, NOW)
    self.assertEqual(len(jobs), 1)
    self.assertEqual(jobs[0]["publishedAt"], "2026-10-14")
    self.assertEqual(jobs[0]["category"], "公务员")
```

- [ ] **Step 2: 运行定向测试并确认失败**

Run: `python -m unittest tests.test_crawl.CrawlTests.test_education_ministry_source_uses_current_official_listing tests.test_crawl.CrawlTests.test_parse_html_accepts_official_civil_service_exam_recruitment_title -v`

Expected: 来源 URL 仍为旧栏目，且“考录”标题未被识别，两项测试均失败。

- [ ] **Step 3: 实施最小修复**

```python
RECRUITMENT_TERMS = (
    "招聘", "招募", "招考", "招录", "考录", "录用", "选调", "遴选", "校园招聘", "社会招聘", "补充录用",
)
```

```json
{
  "name": "教育部公务员招录",
  "kind": "html",
  "url": "https://hudong.moe.gov.cn/jyb_xwfb/moe_2082/siju/rss/jggwyzl/",
  "category": "公务员",
  "allowedDomains": ["moe.gov.cn"],
  "maxItems": 50,
  "timeout": 20
}
```

- [ ] **Step 4: 运行定向测试并确认通过**

Run: `python -m unittest tests.test_crawl.CrawlTests.test_education_ministry_source_uses_current_official_listing tests.test_crawl.CrawlTests.test_parse_html_accepts_official_civil_service_exam_recruitment_title -v`

Expected: `Ran 2 tests` 且 `OK`。

- [ ] **Step 5: 运行全套验证**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Run: `npm test`

Run: `python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --health-output data/health.json --dry-run`

Run: `node tests/browser-smoke.mjs`

Expected: Python 和 Node 测试全部通过；联网试采集中“教育部公务员招录”状态为 `ok` 且至少采集 1 条；浏览器无控制台错误。

- [ ] **Step 6: 提交并推送**

```bash
git add crawler/crawl.py crawler/sources.json tests/test_crawl.py docs/superpowers/plans/2026-11-16-education-ministry-source-repair.md
git commit -m "fix: restore education ministry recruitment source"
git push origin main
```

Expected: 普通快进推送成功。如远端 `main` 已前进，先保留双方历史并解决与本次文件相关的冲突，不使用强制推送。

### Task 2: 防止长摘要撑宽移动端公告卡片

**Files:**
- Modify: `assets/styles.css`
- Test: `tests/browser-smoke.mjs`

**Interfaces:**
- Consumes: `.job-main`、`.job-summary` 现有卡片结构，以及浏览器测试已有的 `document.documentElement.scrollWidth <= clientWidth` 断言。
- Produces: 可在 390 像素视口内收缩的公告正文区，长连续文本按卡片宽度换行。

- [ ] **Step 1: 确认现有浏览器断言失败**

Run: 在 390 x 844 视口加载本地页面，读取 `document.documentElement.scrollWidth` 和 `clientWidth`。

Expected: 包含连续脚本文本的公告卡片将页面宽度撑到 420 像素，超过 390 像素视口。

- [ ] **Step 2: 增加局部收缩与换行规则**

```css
.job-main { min-width: 0; }
.job-summary { overflow-wrap: anywhere; }
```

- [ ] **Step 3: 重跑浏览器烟雾检查**

Run: 在 1440 x 1000 和 390 x 844 视口检查公告数量、`#loadError` 可见性、控制台错误和页面横向溢出。

Expected: 公告全部渲染，`#loadError` 隐藏，控制台错误和警告均为 0，移动端 `scrollWidth` 不大于 `clientWidth`。
