# 招考雷达持续完善实施计划

> **执行约定：** 本计划按任务顺序小步实施；每完成一个任务必须先通过对应自动化测试、再提交。来源配置和可逆的小改动可以自动上线；涉及账号、收费服务、验证码绕过、隐私数据、域名迁移或大规模架构替换的改动必须停下并报告。

**目标：** 把当前网站从“每日聚合公告的可用版本”升级为“来源覆盖更广、能识别报名有效期、筛选更实用、故障能被发现并通知、可以持续自我维护”的长期运行版本。

**当前基线：** 网站部署在 GitHub Pages；`.github/workflows/update-jobs.yml` 每天北京时间 07:20 运行采集、测试和部署；`crawler/sources.json` 当前包含 9 个入口；前端支持关键词、类型、地区、招聘对象、发布时间、排序和收藏。现阶段最明显的缺口是多数列表页没有可靠报名截止时间、来源覆盖仍少、来源失效只在数据弹窗内显示、没有部署后的公网探测。

**总体架构：** 保留“Python 标准库采集器 + 静态 JSON + 无依赖前端 + GitHub Actions/Pages”的低成本架构。采集分为栏目发现、官方详情页补全、生命周期判定、质量门禁四步；`data/jobs.json` 只发布仍可报名、即将报名或期限待核的公告；`data/health.json` 发布来源健康摘要；前端读取两份数据完成筛选和健康提示。GitHub Actions 负责每日生产任务，Codex 自动化负责每日独立巡检和每周受约束的持续改进。

**技术栈：** Python 3.12 标准库、HTML/CSS/ES modules、Node.js 内置测试器、GitHub Actions、GitHub Pages、GitHub Issues。

---

## 长期运行边界

- 只采集无需登录即可访问的公开页面，不绕过验证码、访问控制或 robots/站点限制。
- 优先政府、事业单位主管部门、央企官网和国务院国资委监管企业入口；商业转载站只能用于发现线索，不能作为最终公告链接。
- 所有外链必须命中来源配置中的精确域名白名单，禁止宽泛的后缀或跳转器放行。
- “报名已结束”必须基于详情页内和报名相关的明确日期判断；不能把笔试、准考证、面试或材料提交日期误当成报名截止日。
- 日期无法可靠识别时标记为“期限待核”，最多保留 45 天，并明确提示用户回原公告确认；不伪造截止日。
- 单个来源失败不能清空全站旧数据。数据量异常下降、全部来源失败或公网不可访问时阻止错误快照覆盖并触发告警。
- 每周自动改进只允许一次一个小改动；测试不通过、工作区有未知改动、来源合法性不明时不提交、不推送，只生成报告。

## 成功指标

- 第一阶段：至少 20 个稳定官方入口；随后覆盖 31 个省级公务员/人事考试入口及主要央企公开招聘入口，目标不少于 60 个可监控入口。
- 最近 7 天正常运行时，来源成功率不低于 80%；连续 2 次失败的来源进入告警，连续 7 天失败进入待修复清单。
- 有明确报名截止时间的公告，截止后下一次日更不再出现在主列表中；截止识别单元测试覆盖跨年、延期、时间区间和干扰日期。
- 每日数据生成时间不超过 36 小时；线上首页、`data/jobs.json`、`data/health.json` 均返回 200 且 JSON 可解析。
- 每次上线前 Python、Node 单元测试全部通过，部署后公网烟雾测试通过。

## 固定工作节奏

| 时间（北京时间） | 执行方 | 工作内容 | 异常处理 |
|---|---|---|---|
| 每天 07:20 | GitHub Actions | 发现公告、补全详情、剔除截止公告、质量门禁、测试、部署 | 失败时创建或更新唯一的站点健康 Issue |
| 每天 08:10 | Codex 自动巡检 | 检查线上页面、数据新鲜度、数量异常、来源失败、最近工作流状态 | 有问题时在 Codex 中通知，并给出诊断和安全修复结果 |
| 每周日 10:00 | Codex 持续完善 | 审核失败来源、验证并增加官方来源、完成一个小型筛选或可靠性改进 | 仅在工作区干净且全套测试通过后提交和推送 |
| 每月第一个周日 | 纳入周任务 | 输出覆盖率、过期识别率、失败源排行和下月优先级 | 指标倒退时暂停扩源，优先修复质量 |

---

### Task 1：建立报名期限与公告生命周期的可信规则

**Files:**
- Create: `crawler/lifecycle.py`
- Modify: `crawler/crawl.py`
- Modify: `crawler/sources.json`
- Create: `tests/test_lifecycle.py`
- Modify: `tests/test_crawl.py`

**数据契约：** 每条公告新增 `registrationStart`、`registrationEnd`、`status`、`deadlineConfidence`、`deadlineEvidence`。`status` 只允许 `upcoming`、`open`、`unknown`、`expired`、`cancelled`；主站只输出前三种。

- [ ] **Step 1：先写生命周期失败测试**

测试以下场景：`报名时间：7月10日9:00至7月20日17:00` 提取结束日；`延长至7月23日` 覆盖原截止日；跨年区间正确推断年份；“7月20日打印准考证、7月25日笔试”不能成为报名截止日；明确“取消招聘”得到 `cancelled`；截止日期早于当天得到 `expired`；期限未知且发布超过 45 天不再进入主列表。

- [ ] **Step 2：运行测试并确认失败**

Run: `python -m unittest tests.test_lifecycle -v`

Expected: FAIL，因为 `crawler.lifecycle` 尚不存在。

- [ ] **Step 3：实现纯函数生命周期模块**

实现以下公开函数：`extract_registration_window(text: str, now: datetime) -> dict`、`derive_status(job: dict, now: datetime, unknown_ttl_days: int = 45) -> str`、`is_publishable(job: dict, now: datetime, unknown_ttl_days: int = 45) -> bool`、`apply_lifecycle(job: dict, detail_text: str, now: datetime) -> dict`。

`deadlineEvidence` 只保存最长 120 字的报名相关原句；`deadlineConfidence` 只允许 `high`、`medium`、`unknown`。原有 `deadline` 暂时作为 `registrationEnd` 的兼容别名，待前端迁移完成后删除。

- [ ] **Step 4：在采集主流程中执行生命周期过滤**

`crawl()` 在去重后调用 `apply_lifecycle()` 和 `is_publishable()`。明确过期或取消的公告不进入 `data/jobs.json`；来源失败时保留旧公告也必须重新执行期限判断，禁止过期旧数据无限保留。

- [ ] **Step 5：运行回归测试**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 所有 Python 测试 PASS。

### Task 2：抓取官方详情页并补全可筛选字段

**Files:**
- Create: `crawler/detail.py`
- Create: `crawler/cache/details.json`
- Modify: `crawler/crawl.py`
- Modify: `.gitignore`
- Create: `tests/fixtures/detail_open.html`
- Create: `tests/fixtures/detail_expired.html`
- Create: `tests/test_detail.py`

**接口：** `enrich_jobs(jobs, sources, cache_path, now, fetcher=fetch_text) -> tuple[list[dict], dict]`。只访问已经通过域名白名单的公告详情页；按域名限速；缓存以规范化 URL 为键，成功结果保留 7 天，失败结果最多保留 6 小时。

- [ ] **Step 1：写详情解析、缓存和安全边界测试**

覆盖 HTML 正文提取、GB18030 内容、重定向后域名复核、缓存命中不联网、失败缓存短期退避、单域名并发上限、正文中学历/学位/招聘人数的保守提取。

- [ ] **Step 2：实现详情正文解析与缓存**

实现 `extract_main_text(html_text: str) -> str`、`extract_structured_fields(text: str) -> dict` 和 `enrich_jobs(jobs: list[dict], sources: list[dict], cache_path: Path, now: datetime, fetcher=fetch_text) -> tuple[list[dict], dict]`。

新增字段仅在有清晰证据时写入：`education`、`degree`、`recruitmentCount`、`applicationUrl`。不可靠字段留空，不以模型猜测填充。

- [ ] **Step 3：把详情补全接入采集顺序**

执行顺序固定为“列表发现 → 官方域名校验 → 详情补全 → 生命周期判断 → 去重 → 质量门禁”。每次最多补全 120 个新/缓存过期链接，避免对官方站点造成压力。

- [ ] **Step 4：验证详情补全不会拖垮日更**

Run: `python -m unittest tests.test_detail tests.test_lifecycle -v`

Run: `python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --dry-run`

Expected: 测试 PASS；单个详情页失败只降低该公告的字段完整度，不导致整个来源失败。

### Task 3：把来源配置扩展为可维护的官方来源目录

**Files:**
- Create: `crawler/sources/national.json`
- Create: `crawler/sources/provinces.json`
- Create: `crawler/sources/soe.json`
- Create: `crawler/source_registry.py`
- Create: `crawler/source_overrides.json`
- Modify: `crawler/sources.json`
- Create: `tests/test_source_registry.py`
- Create: `docs/source-coverage.md`

**来源分组：**

- 国家级：国家公务员局、人社部公共招聘、国务院国资委、中央和国家机关部门招录/招聘栏目。
- 地方级：31 个省级公务员主管部门、人事考试网、人社厅事业单位公开招聘栏目；直辖市单独配置。
- 央国企：国务院国资委监管企业名录能验证的集团招聘入口、国聘公开入口及各集团官方招聘域名。

- [ ] **Step 1：编写注册表校验测试**

验证来源名唯一、URL 唯一、域名非通配、协议为 HTTPS（确实只支持 HTTP 的官方站点需显式 `allowHttpReason`）、类别合法、超时和最大条数有界、同一来源有负责人/地区/层级元数据。

- [ ] **Step 2：实现多文件来源加载器**

实现 `load_source_registry(index_path: Path) -> list[dict]`、`validate_source(source: dict) -> list[str]` 和 `validate_registry(sources: list[dict]) -> None`。

根 `crawler/sources.json` 只保存全局阈值和三个分组文件路径，`crawl.py` 通过加载器合并。

- [ ] **Step 3：分批扩源并逐一验证**

第一批扩到至少 20 个稳定入口；第二批覆盖 31 省；第三批补全主要央企。每个新入口先 dry-run 两次，至少找到一条有效官方公告或明确记录“当前无公告”，才能标记 `enabled: true`。不要一次性加入大量未验证 URL。

- [ ] **Step 4：维护覆盖清单**

`docs/source-coverage.md` 记录来源、地区、类别、官方域名、最近成功日、解析方式、已知限制和状态。周度任务每次优先修复失败来源，其次再新增 2–5 个来源。

- [ ] **Step 5：运行注册表和采集回归**

Run: `python -m unittest tests.test_source_registry tests.test_crawl -v`

Expected: 配置错误在联网前直接失败；已启用来源均通过静态安全校验。

### Task 4：增强前端筛选、状态表达与链接分享

**Files:**
- Modify: `index.html`
- Modify: `assets/core.mjs`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Modify: `tests/core.test.mjs`
- Modify: `tests/browser-smoke.mjs`

**新增筛选：** 报名状态（报名中/即将开始/期限待核）、来源、截止时间（3 天内/7 天内/30 天内/未知）、学历；地区保持省级筛选，数据可靠后再增加城市级联。所有筛选继续采用跨条件 AND、同类单选的可预测规则。

- [ ] **Step 1：为筛选和 URL 状态写失败测试**

覆盖过期公告即使误入数据也不显示、报名状态、来源、截止窗口、学历、无效查询参数回退、重置筛选、分享链接恢复状态。

- [ ] **Step 2：扩展纯函数筛选接口**

`filterJobs()` 新增 `status`、`source`、`deadlineWindow`、`education`；`stateFromSearchParams()` 和 `searchParamsFromState()` 同步支持，并保持严格允许值校验。

- [ ] **Step 3：实现桌面与移动端筛选控件**

首页展示“当前有效公告”而不是历史总数；卡片明确显示“报名中”“即将报名”“期限待核”和截止剩余天数；已截止状态不再作为普通结果展示。移动端控件触摸高度至少 44px，激活筛选以可删除标签显示。

- [ ] **Step 4：增加数据质量提示**

对于 `deadlineConfidence=unknown`，展示“截止时间请以原公告为准”；详情提取字段显示证据不足时不展示。来源弹窗读取 `data/health.json`，显示最近成功时间和失败原因摘要。

- [ ] **Step 5：运行前端测试和浏览器烟雾测试**

Run: `node --test tests/core.test.mjs`

Run: `node tests/browser-smoke.mjs`

Expected: 桌面和 390px 视口均通过；控制台无错误；外链带 `noopener noreferrer`。

### Task 5：建立健康数据、异常阈值和质量门禁

**Files:**
- Create: `crawler/health.py`
- Create: `scripts/check_snapshot.py`
- Create: `scripts/check_public_site.py`
- Create: `data/health.json`
- Create: `tests/test_health.py`
- Modify: `crawler/crawl.py`

**健康指标：** `generatedAt`、当前公告数、7 日新增数、明确截止覆盖率、来源成功率、各来源最近成功/失败时间、连续失败次数、与上次快照的数量变化、线上探测结果。

- [ ] **Step 1：写异常判定失败测试**

覆盖：总量从上一版骤降超过 40%；来源成功率低于 60%；全部来源失败；数据超过 36 小时；JSON 缺少必填字段；首页或数据 URL 非 200；来源连续失败 2 次。

- [ ] **Step 2：实现健康聚合和质量门禁**

实现 `build_health(payload: dict, previous_health: dict, now: datetime) -> dict`、`quality_violations(payload: dict, previous: dict, health: dict) -> list[dict]` 和 `check_public_site(base_url: str, timeout: int = 20) -> list[dict]`。

严重异常返回非零退出码并保留上一份线上数据；单个来源失败只记录告警。错误信息不得包含令牌、Cookie 或完整响应正文。

- [ ] **Step 3：原子写入两份公开数据**

采集成功后同时生成 `data/jobs.json` 和 `data/health.json`；任一份校验失败都不覆盖稳定快照。

- [ ] **Step 4：运行健康检查**

Run: `python -m unittest tests.test_health -v`

Run: `python scripts/check_snapshot.py --jobs data/jobs.json --health data/health.json`

Expected: 正常快照退出 0，构造的异常快照退出非零并输出可读原因。

### Task 6：让 GitHub Actions 自动告警、恢复并验证公网部署

**Files:**
- Modify: `.github/workflows/update-jobs.yml`
- Create: `.github/scripts/report-health-issue.js`
- Create: `.github/ISSUE_TEMPLATE/site-health.md`
- Modify: `README.md`

- [ ] **Step 1：拆分工作流阶段**

将工作流拆为 `collect-and-test`、`deploy`、`public-smoke`、`report-health`。`deploy` 只依赖通过质量门禁的快照；`public-smoke` 在部署后检查首页和两份 JSON；定时分钟调整为非整点，继续使用北京时间 07:20。

- [ ] **Step 2：使用单一 GitHub Issue 报错**

为工作流增加最小权限 `issues: write`。失败时查找带 `site-health` 标签、标题固定为 `招考雷达自动巡检异常` 的开放 Issue：存在则追加本次时间、阶段、运行链接和脱敏摘要；不存在则创建。恢复后自动评论“已恢复”并关闭，防止每天生成重复 Issue。

- [ ] **Step 3：配置通知说明**

README 明确说明用户需要在仓库中选择 `Watch → Custom → Issues`，确保 GitHub 通过站内或账号邮件发送 Issue 通知。以后若用户愿意提供独立通知渠道，再增加邮件/企业微信/Telegram webhook；不把任何密钥写入仓库。

- [ ] **Step 4：手动演练故障和恢复**

在测试分支用不可达的测试 URL 触发失败，确认不会覆盖线上数据、Issue 只创建一次；恢复配置后确认部署成功、Issue 自动关闭。演练完成后删除测试配置，不在 `main` 留下故障源。

- [ ] **Step 5：全套验证**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Run: `node --test tests/core.test.mjs`

Run: `node tests/browser-smoke.mjs`

Expected: 全部 PASS；手动 GitHub Actions 运行成功；公网探测 PASS。

### Task 7：落实每日巡检与每周自主完善的操作边界

**Files:**
- Create: `docs/runbook.md`
- Create: `docs/weekly-improvement-log.md`
- Modify: `README.md`

- [ ] **Step 1：编写可执行故障手册**

`docs/runbook.md` 按“网站打不开、数据过旧、来源大量失败、公告数量骤降、截止误判、Actions 停跑”六类问题列出检查命令、恢复步骤和回滚原则。

- [ ] **Step 2：建立周度改进记录**

每周记录检查日期、健康指标、失败来源、候选来源、实际改动、测试结果、提交链接和下周优先级。没有安全改动时也记录“无变更及原因”，不为制造提交而修改。

- [ ] **Step 3：约束自主改动范围**

允许自动提交：已验证的官方来源配置、解析选择器、日期规则测试、健康阈值微调、文案和小型筛选改进。禁止自动执行：删除仓库/历史、改变公开性、购买服务、绑定域名、写入用户凭据、绕过站点限制、大版本框架迁移。

- [ ] **Step 4：最终验收**

连续观察 7 个每日运行周期：日更均完成或故障被及时告警；截止公告下一次日更消失；至少一次模拟来源失效不会清空站点；筛选 URL 可分享；周任务只提交一项已通过测试的改进。

---

## 推荐实施顺序与预计里程碑

1. **可靠性优先（Task 1、2、5）：** 先解决截止时间和错误快照问题，再扩大数量。
2. **可见性（Task 6）：** 让故障可被及时知道，而不是依赖人工打开网站发现。
3. **覆盖面（Task 3）：** 分批扩到 20、35、60+ 个官方入口，每批观察一周。
4. **使用体验（Task 4）：** 用已经可靠的结构化字段增加筛选，避免“有控件但数据不准”。
5. **长期治理（Task 7）：** 通过日报、周志和改动边界保证可以自动维护但不会无约束改站。

## 自检结论

- “更多网站和更多公告”对应 Task 3，并设定了官方来源、分批验证和覆盖率指标。
- “每日剔除报名结束公告”对应 Task 1、2，并明确了详情证据、过期规则与误判测试。
- “进一步完善筛选”对应 Task 4，字段来源由 Task 1、2 保证。
- “网站报错及时告知”对应 Task 5、6 以及每日 Codex 巡检。
- “无需重复发布命令、持续完善”对应固定工作节奏和 Task 7，同时保留安全边界。
