# 中文硕士个性化岗位匹配 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有招考雷达中加入仅保存在浏览器本地的中文硕士求职画像，并用官方详情页的原文线索生成可解释、保守的岗位相关度分级。

**Architecture:** Python 采集端从已经允许访问的官方详情页提取“中文专业、文字类职责、应届/党员/学历/经历”等原文线索，作为 `profileHints` 写入公告 JSON；它不直接断言用户一定有资格。浏览器端用纯函数把用户画像与这些线索组合成“专业相关、文字岗位、需要核对、一般相关”四档，支持筛选、适配优先排序和原文证据展示。个人画像只写入 `localStorage`，不进入公开仓库或数据文件。

**Tech Stack:** Python 3.12 标准库、HTML/CSS/ES modules、Node.js 内置测试器、Playwright 浏览器烟雾测试、GitHub Actions/Pages。

## Global Constraints

- 不把姓名、学校、证件、联系方式或个人画像写入 `data/jobs.json`、Git 提交或远端服务。
- 匹配结果使用“相关/建议核对”措辞，不使用“确定能报”；最终资格始终以原公告和职位表为准。
- 只有详情页原文实际出现的专业、职责和资格词才进入 `profileHints`，不得由标题或模型补写不存在的要求。
- 兼容没有 `profileHints` 的历史快照；此类公告进入“需要核对”，网站不能报错。
- 保持无前端第三方运行时依赖、三种阅读模式、390px 无横向溢出和至少 44px 触摸目标。
- 所有外链仍须由采集端官方域名白名单控制。

---

### Task 1: 从官方详情页提取中文硕士相关原文线索

**Files:**
- Create: `crawler/profile_hints.py`
- Modify: `crawler/detail.py`
- Create: `tests/test_profile_hints.py`
- Modify: `tests/test_detail.py`

**Interfaces:**
- Consumes: `extract_main_text(html_text: str) -> str` 得到的官方详情页纯文本。
- Produces: `extract_profile_hints(text: str) -> dict`，返回 `{roleTags, majorTags, qualificationTags, graduateYears, evidence}`；`detail.enrich_jobs()` 把结果写入每条公告的 `profileHints`。

- [ ] **Step 1: 写线索提取失败测试**

```python
def test_extracts_chinese_major_role_and_evidence():
    text = "宣传岗位负责文稿起草和新媒体编辑。专业要求：中国语言文学、新闻传播学。硕士研究生及以上，中共党员优先。"
    hints = extract_profile_hints(text)
    assert hints["majorTags"] == ["中国语言文学"]
    assert hints["roleTags"] == ["综合文字", "宣传文化", "编辑出版", "新媒体"]
    assert hints["qualificationTags"] == ["硕士", "中共党员"]
    assert "中国语言文学" in hints["evidence"]["中国语言文学"]

def test_does_not_invent_chinese_major_from_generic_recruitment_copy():
    hints = extract_profile_hints("现面向社会公开招聘工作人员，具体岗位见附件。")
    assert hints["majorTags"] == []
    assert hints["roleTags"] == []
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m unittest tests.test_profile_hints -v`

Expected: FAIL，因为 `crawler.profile_hints` 尚不存在。

- [ ] **Step 3: 实现固定词典和证据截取**

`crawler/profile_hints.py` 定义固定顺序词典：

```python
ROLE_RULES = {
    "综合文字": ("综合文字", "文字材料", "材料撰写", "文稿起草", "公文写作", "文秘"),
    "宣传文化": ("宣传策划", "新闻宣传", "宣传思想", "企业文化", "品牌传播", "文化建设"),
    "编辑出版": ("编辑", "校对", "审校", "出版", "古籍整理", "文献整理"),
    "新媒体": ("新媒体", "公众号", "融媒体", "内容运营", "新闻采编"),
    "高校行政": ("辅导员", "教学管理", "科研管理", "高校行政"),
    "中文教育": ("语文教师", "中文教师", "国际中文教育", "汉语教学"),
}
MAJOR_RULES = {
    "中国语言文学": ("中国语言文学", "汉语言文学", "汉语言文字学", "语言学及应用语言学", "文艺学", "中国古代文学", "中国现当代文学", "古典文献学", "比较文学与世界文学"),
}
```

资格规则只识别“硕士及以上/硕士研究生”“应届毕业生/校招”“中共党员”“教师资格证”和明确的 `N年工作经历`；`evidence` 保存命中词所在的最长 120 字原句。

- [ ] **Step 4: 让详情缓存携带线索并兼容旧缓存**

`detail.py` 在同一次详情请求中先调用 `extract_main_text()`，再分别调用 `extract_registration_window()` 与 `extract_profile_hints()`。成功缓存缺少 `profileHints` 时视为需要刷新；`_apply_fields()` 即使没有 `registrationEnd` 也必须把非空 `profileHints` 写入公告。

- [ ] **Step 5: 运行采集端测试**

Run: `python -m unittest tests.test_profile_hints tests.test_detail -v`

Expected: PASS，且旧缓存、无截止日期、有线索三种情况均通过。

### Task 2: 实现可解释的本地匹配纯函数

**Files:**
- Create: `assets/matching.mjs`
- Create: `tests/matching.test.mjs`
- Modify: `assets/core.mjs`
- Modify: `tests/core.test.mjs`

**Interfaces:**
- Consumes: 公告 `profileHints` 和浏览器画像 `profile`。
- Produces: `normalizeProfile(value)`, `analyzeJob(job, profile)`, `filterByMatchMode(jobs, mode, profile)`, `DEFAULT_PROFILE`, `PROFILE_ROLES`。

- [ ] **Step 1: 写四档匹配和保守措辞测试**

```javascript
test('Chinese major evidence creates an exact-related result without claiming eligibility', () => {
  const match = analyzeJob({ profileHints: {
    majorTags: ['中国语言文学'], roleTags: ['综合文字'], qualificationTags: ['硕士'], evidence: {},
  } }, DEFAULT_PROFILE);
  assert.equal(match.tier, 'exact');
  assert.equal(match.label, '专业相关');
  assert.ok(match.cautions.includes('仍需核对职位表中的具体专业范围'));
});

test('writing duties without a major signal stay in the writing tier', () => {
  const match = analyzeJob({ profileHints: {
    majorTags: [], roleTags: ['宣传文化'], qualificationTags: [], evidence: {},
  } }, DEFAULT_PROFILE);
  assert.equal(match.tier, 'writing');
});

test('missing hints are safe and require verification', () => {
  assert.equal(analyzeJob({}, DEFAULT_PROFILE).tier, 'verify');
});
```

- [ ] **Step 2: 运行测试并确认模块缺失**

Run: `node --test tests/matching.test.mjs`

Expected: FAIL，因为 `assets/matching.mjs` 尚不存在。

- [ ] **Step 3: 实现画像规范化和匹配评分**

默认画像固定为：硕士、中国语言文学、应届；毕业年份、研究方向、政治面貌和地区偏好为空。评分规则固定为：专业线索 +60、每个关注职责 +18（最多 54）、应届线索 +8、硕士线索 +8、偏好地区 +6；党员要求与画像不符、明确工作经历要求会各减 20 并增加警示。分档为 `exact`、`writing`、`verify`、`other`，不产生资格通过结论。

- [ ] **Step 4: 扩展 URL 状态和适配排序**

`core.mjs` 允许 `match=all|recommended|exact|writing|verify` 和 `sort=match`；`sortJobs()` 在 `match` 模式按 `job._match.score` 降序，再按发布日期降序。无效值回退到 `all` 与 `newest`。

- [ ] **Step 5: 运行前端纯函数测试**

Run: `node --test tests/core.test.mjs tests/matching.test.mjs`

Expected: 所有 Node 测试 PASS。

### Task 3: 加入本地求职画像、匹配入口和卡片解释

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Modify: `tests/browser-smoke.mjs`

**Interfaces:**
- Consumes: Task 2 的匹配纯函数和 `localStorage['job-radar:profile']`。
- Produces: `#profileDialog`、`#profileButton`、`#matchTabs`、卡片 `.match-explain`，以及可分享的 `match`/`sort` 查询状态。

- [ ] **Step 1: 扩展浏览器烟雾测试**

测试打开“我的画像”，确认默认学历和专业；填写研究方向与毕业年份后保存；确认 `localStorage` 有值、画像摘要更新；切换“适合我的”后页面不报错；重新加载后画像仍存在；390px 下画像按钮与筛选按钮高度至少 44px。

- [ ] **Step 2: 添加语义化 HTML**

页头新增“我的画像”；主视觉与搜索区之间新增画像摘要；搜索区新增“全部公告、适合我的、专业相关、文字岗位、需要核对”按钮；画像对话框只收集专业、研究方向、毕业年份、政治面貌、偏好地区和关注方向；职位模板新增匹配标签、最多两条理由和一条警示。

- [ ] **Step 3: 接入本地状态**

`app.js` 增加 `STORAGE.profile = 'job-radar:profile'`。加载时用 `normalizeProfile(readJson(STORAGE.profile, DEFAULT_PROFILE))`；渲染前给每条公告附加 `_match = analyzeJob(job, profile)`；按匹配入口过滤后再调用现有通用筛选；保存画像后写入 `localStorage`，切到 `match=recommended` 和 `sort=match`。

- [ ] **Step 4: 完成三种阅读模式和响应式样式**

画像摘要使用现有纸张、墨色、信号色变量；匹配标签 `exact` 使用绿色，`writing` 使用信号色，`verify` 使用中性色；移动端画像表单单列，匹配入口横向滚动，不新增渐变、阴影卡片或外部字体。

- [ ] **Step 5: 运行浏览器测试**

Run: `node tests/browser-smoke.mjs`

Expected: 桌面与 390px 测试 PASS，控制台无错误，画像重载后仍存在。

### Task 4: 文档、全套验证和安全上线

**Files:**
- Modify: `README.md`
- Modify: `docs/weekly-improvement-log.md`

**Interfaces:**
- Consumes: Tasks 1–3 的最终数据契约与 UI。
- Produces: 用户可理解的隐私说明、匹配边界和维护记录。

- [ ] **Step 1: 更新文档**

README 说明 `profileHints` 字段、个人画像仅存浏览器、清除浏览器数据会删除画像、匹配不是资格审核；周志记录本次功能、测试数量、联网 dry-run 结果和下一步“职位表附件解析”。

- [ ] **Step 2: 运行全套测试**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Run: `node --test tests/core.test.mjs tests/matching.test.mjs`

Run: `node tests/browser-smoke.mjs`

Expected: Python、Node、桌面与移动烟雾测试全部 PASS。

- [ ] **Step 3: 运行联网 dry-run 和质量门禁**

Run: `python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --dry-run`

Run: `python scripts/check_snapshot.py --jobs data/jobs.json --health data/health.json`

Expected: 单个来源失败不清空数据；公告数量无超过阈值的异常下降；稳定来源详情页开始产生 `profileHints`。

- [ ] **Step 4: 提交、推送并验证 Pages**

提交信息使用 `feat: add Chinese masters job matching`。推送 `main` 后等待“更新招考信息并部署网站”成功，再检查首页、`data/jobs.json` 和 `data/health.json` 均返回 200。

## Self-Review

- 用户画像、专业/能力双维度、解释性标签、应届与党员/经历提醒由 Tasks 1–3 覆盖。
- 个人隐私和“不宣称能报”的边界由 Global Constraints、Task 2 测试和 Task 4 文档覆盖。
- PDF/Excel/Word 职位表解析是独立子系统，本 MVP 不引入不可靠的附件推断；下一份计划单独实施。
- 接口命名在采集端、匹配模块和 UI 中一致；不存在未定义的后续依赖。
