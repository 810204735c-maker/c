# Source Expansion and Application Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand official Chinese-language career sources and add a private, per-job application workspace with reminders, checklists, calendar export, notes, and backup.

**Architecture:** Keep collection in the existing standard-library Python pipeline and extract only evidence-backed application hints from allowlisted official detail pages. Add small browser-native ES modules for application guidance and favorite workspace state; all notes and progress remain in localStorage, while exports are user-initiated `.ics` and `.json` downloads.

**Tech Stack:** Python 3 standard library, static HTML/CSS, browser ES modules, Node test runner, Playwright smoke tests, GitHub Actions and GitHub Pages.

## Global Constraints

- Only add publicly readable official government, university, or central-enterprise domains; do not bypass authentication, cookies, CAPTCHAs, or robots controls.
- Do not claim that a reminder or checklist is a qualification decision; every application view must link back to the official announcement.
- Store notes, checklist state, and profile data only in the current browser.
- Preserve old `job-radar:saved` arrays by migrating them into the new workspace structure.
- Calendar exports must be valid UTF-8 iCalendar and JSON backups must exclude unrelated browser data.

---

### Task 1: Verified official source expansion

**Files:**
- Modify: `crawler/sources.json`
- Modify: `tests/test_crawl.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing `parse_html(html_text: str, source: dict, now: datetime) -> list[dict]`.
- Produces: source records with `name`, `url`, `category`, `allowedDomains`, `maxItems`, `timeout`, and optional `focusTags`.

- [ ] **Step 1: Add a failing configuration test**

```python
def test_focus_sources_are_official_and_allowlisted(self):
    required = {"国家广播电视总局公告公示", "中央事业单位招聘公告", "清华大学人事招聘", "华北电力大学人才招聘", "中国能建所属企业招聘"}
    config = json.loads(Path("crawler/sources.json").read_text(encoding="utf-8"))
    selected = {source["name"]: source for source in config["sources"] if source["name"] in required}
    self.assertEqual(set(selected), required)
    self.assertTrue(all(source["allowedDomains"] for source in selected.values()))
```

- [ ] **Step 2: Run the test and confirm the missing-source failure**

Run: `python -m unittest tests.test_crawl -v`

Expected: FAIL because the five source names are not configured.

- [ ] **Step 3: Add the five allowlisted source records**

```json
{
  "name": "国家广播电视总局公告公示",
  "kind": "html",
  "url": "https://www.nrta.gov.cn/col/col113/index.html",
  "category": "事业单位",
  "allowedDomains": ["nrta.gov.cn"],
  "focusTags": ["宣传文化", "编辑出版", "新媒体"],
  "maxItems": 60,
  "timeout": 20
}
```

Add equivalent records for the Ministry of Human Resources central-unit recruitment list, Tsinghua HR, North China Electric Power University recruitment, and China Energy Engineering enterprise recruitment pages, using only their exact official domains.

- [ ] **Step 4: Run configuration tests and two network dry-runs**

Run: `python -m unittest tests.test_crawl -v`

Expected: PASS.

Run twice: `python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --health-output data/health.json --dry-run`

Expected: each enabled new source is `ok` or an explicitly allowed `empty`; no source bypasses access controls and total jobs do not breach quality gates.

- [ ] **Step 5: Commit the verified source expansion**

```bash
git add crawler/sources.json tests/test_crawl.py README.md
git commit -m "feat: expand Chinese career sources"
```

### Task 2: Evidence-backed application hints

**Files:**
- Create: `crawler/application_hints.py`
- Modify: `crawler/detail.py`
- Create: `tests/test_application_hints.py`
- Modify: `tests/test_detail.py`

**Interfaces:**
- Consumes: official detail-page plain text from `extract_main_text(html_text: str) -> str`.
- Produces: `extract_application_hints(text: str) -> dict` with `schemaVersion`, `methods`, `materialTags`, and `evidence`.

- [ ] **Step 1: Write failing extraction tests**

```python
def test_extracts_methods_and_materials():
    hints = extract_application_hints("网上报名，上传报名表、身份证、学历学位证书及学信网验证报告。")
    self.assertEqual(hints["methods"], ["网上报名"])
    self.assertEqual(hints["materialTags"], ["报名表", "身份证", "学历学位证明", "学信网证明"])

def test_ignores_generic_contact_email():
    hints = extract_application_hints("咨询邮箱：help@example.gov.cn")
    self.assertEqual(hints["methods"], [])
```

- [ ] **Step 2: Run tests and confirm the import failure**

Run: `python -m unittest tests.test_application_hints -v`

Expected: FAIL because `crawler.application_hints` does not exist.

- [ ] **Step 3: Implement conservative dictionaries and bounded evidence**

```python
APPLICATION_HINTS_SCHEMA_VERSION = 1
METHOD_RULES = {
    "网上报名": ("网上报名", "在线报名", "报名系统"),
    "邮箱报名": ("发送至报名邮箱", "报名材料发送至", "投递邮箱"),
    "现场报名": ("现场报名", "现场提交报名材料"),
}
MATERIAL_RULES = {
    "报名表": ("报名表", "应聘登记表"),
    "身份证": ("身份证扫描件", "身份证正反面"),
    "学历学位证明": ("学历学位证书", "毕业证书和学位证书"),
    "学信网证明": ("学信网", "学历证书电子注册备案表", "学籍在线验证报告"),
    "个人简历": ("个人简历", "个人履历"),
    "资格证书": ("职业资格证书", "教师资格证"),
    "党员证明": ("党员证明", "党组织关系证明"),
    "工作经历证明": ("工作经历证明", "劳动合同"),
    "近期照片": ("近期免冠", "证件照"),
}
```

Return the first evidence sentence for every matched tag, bounded to 120 characters.

- [ ] **Step 4: Integrate hints with versioned detail cache**

```python
fields["applicationHints"] = extract_application_hints(detail_text)
```

Treat successful cache entries without the current application-hint schema as stale, and copy non-empty hints to the public job record.

- [ ] **Step 5: Run all Python tests and commit**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests PASS.

```bash
git add crawler/application_hints.py crawler/detail.py tests/test_application_hints.py tests/test_detail.py
git commit -m "feat: extract application requirements"
```

### Task 3: Application guide, reminders, and iCalendar export

**Files:**
- Create: `assets/application.mjs`
- Create: `tests/application.test.mjs`
- Modify: `.github/workflows/update-jobs.yml`

**Interfaces:**
- Consumes: a job record plus `_match` output from `analyzeJob`.
- Produces: `buildApplicationGuide(job)`, `getJobAlerts(job, match, now)`, and `buildCalendarFile(job)`.

- [ ] **Step 1: Write failing Node tests**

```javascript
test('three-day deadlines and unresolved majors produce alerts', () => {
  const alerts = getJobAlerts({ deadline: '2026-08-07' }, { tier: 'verify' }, new Date('2026-08-04T12:00:00+08:00'));
  assert.deepEqual(alerts.map((item) => item.type), ['deadline', 'major']);
});

test('calendar file includes deadline alarm and official URL', () => {
  const file = buildCalendarFile({ id: 'a', title: '招聘公告', deadline: '2026-08-07', url: 'https://example.gov.cn/a' });
  assert.match(file.content, /BEGIN:VCALENDAR/);
  assert.match(file.content, /TRIGGER:-P3D/);
  assert.match(file.content, /https:\/\/example.gov.cn\/a/);
});
```

- [ ] **Step 2: Run tests and confirm the missing-module failure**

Run: `node --test tests/application.test.mjs`

Expected: FAIL because `assets/application.mjs` does not exist.

- [ ] **Step 3: Implement deterministic helpers**

```javascript
export function getJobAlerts(job, match, now = new Date()) {
  const alerts = [];
  const days = daysUntil(job.deadline, now);
  if (days >= 0 && days <= 3) alerts.push({ type: 'deadline', label: days === 0 ? '今天截止' : `${days}天内截止` });
  if (match?.tier === 'verify') alerts.push({ type: 'major', label: '专业待确认' });
  return alerts;
}
```

`buildApplicationGuide` must merge extracted material tags with a short universal flow: read original announcement, check the position table, prepare documents, submit through the stated method, and retain submission evidence. `buildCalendarFile` must return `null` without a valid deadline and otherwise return `{ filename, content }` with an all-day event and a three-day `VALARM`.

- [ ] **Step 4: Add the new suite to GitHub Actions**

```yaml
run: node --test tests/core.test.mjs tests/matching.test.mjs tests/application.test.mjs tests/favorites.test.mjs
```

- [ ] **Step 5: Run Node tests and commit**

Run: `node --test tests/core.test.mjs tests/matching.test.mjs tests/application.test.mjs`

Expected: all tests PASS.

```bash
git add assets/application.mjs tests/application.test.mjs .github/workflows/update-jobs.yml
git commit -m "feat: add application guidance and reminders"
```

### Task 4: Favorite workspace, notes, and backup

**Files:**
- Create: `assets/favorites.mjs`
- Create: `tests/favorites.test.mjs`
- Modify: `assets/app.js`

**Interfaces:**
- Consumes: legacy saved-id arrays and new workspace objects.
- Produces: `normalizeWorkspace(value, legacySavedIds)`, `updateNote(workspace, id, note)`, `toggleCheck(workspace, id, group, key)`, `exportWorkspace(workspace, jobs, exportedAt)`, and `importWorkspace(value)`.

- [ ] **Step 1: Write failing migration and privacy tests**

```javascript
test('legacy favorite ids migrate without data loss', () => {
  assert.deepEqual(normalizeWorkspace(null, ['a']).savedIds, ['a']);
});

test('backup contains only saved public job fields and local workspace', () => {
  const backup = exportWorkspace({ version: 1, savedIds: ['a'], notes: { a: '准备作品集' }, progress: {} }, [{ id: 'a', title: '岗位', url: 'https://example.gov.cn/a' }], '2026-08-04T12:00:00Z');
  assert.equal(backup.jobs[0].title, '岗位');
  assert.equal(backup.workspace.notes.a, '准备作品集');
});
```

- [ ] **Step 2: Run tests and confirm the missing-module failure**

Run: `node --test tests/favorites.test.mjs`

Expected: FAIL because `assets/favorites.mjs` does not exist.

- [ ] **Step 3: Implement normalized version-1 workspace state**

```javascript
export const EMPTY_WORKSPACE = Object.freeze({ version: 1, savedIds: [], notes: {}, progress: {} });

export function normalizeWorkspace(value, legacySavedIds = []) {
  const source = value && typeof value === 'object' ? value : {};
  return {
    version: 1,
    savedIds: cleanIds(source.savedIds?.length ? source.savedIds : legacySavedIds),
    notes: cleanStringMap(source.notes, 500),
    progress: cleanProgress(source.progress),
  };
}
```

Limit each note to 500 characters, each checklist to known string keys, and every imported identifier to 100 characters. Export only favorite job `id`, `title`, `url`, `deadline`, `source`, `category`, and `location` plus the normalized workspace.

- [ ] **Step 4: Migrate app state and persist all workspace mutations**

Read `job-radar:workspace`, use `job-radar:saved` only as a migration source, and write every save, note, and checklist change back to `job-radar:workspace`. Keep the legacy array updated for backward compatibility during this release.

- [ ] **Step 5: Run tests and commit**

Run: `node --test tests/favorites.test.mjs tests/core.test.mjs tests/matching.test.mjs`

Expected: all tests PASS.

```bash
git add assets/favorites.mjs tests/favorites.test.mjs assets/app.js
git commit -m "feat: add private favorite workspace"
```

### Task 5: Application workspace UI

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Modify: `tests/browser-smoke.mjs`

**Interfaces:**
- Consumes: helpers from `application.mjs` and `favorites.mjs`.
- Produces: per-card alerts, an application-assistant dialog, note editing, checklist persistence, `.ics` download, JSON export, and JSON restore.

- [ ] **Step 1: Extend the browser smoke test first**

```javascript
await page.locator('.application-button').first().click();
await page.locator('#jobNote').fill('优先准备写作样本');
await page.locator('#applicationDialog input[type="checkbox"]').first().check();
await page.locator('#applicationClose').click();
await page.reload({ waitUntil: 'networkidle' });
await page.locator('.application-button').first().click();
assert.equal(await page.locator('#jobNote').inputValue(), '优先准备写作样本');
```

- [ ] **Step 2: Add semantic dialog and backup controls**

Add a “报名助手” button to each card, alert chips for “三天内截止” and “专业待确认”, and a dialog containing official link, five-step process, extracted material checklist, note textarea, calendar export, JSON backup export, and JSON backup import.

- [ ] **Step 3: Bind UI without HTML injection**

Create every job-derived label with `textContent`; generate downloads through `Blob` and `URL.createObjectURL`; revoke object URLs after clicks. Parse imported JSON in a `try/catch`, normalize it through `importWorkspace`, display a concise error on failure, and never execute imported text.

- [ ] **Step 4: Add responsive styles and verify accessibility**

Ensure dialog controls have visible labels, reminder colors are not the only status signal, buttons remain at least 44px high at 390px width, and the dialog scrolls within the viewport.

- [ ] **Step 5: Run browser tests and commit**

Run: `node tests/browser-smoke.mjs` against `python -m http.server 4173`.

Expected: desktop and 390px viewport checks PASS with no console errors.

```bash
git add index.html assets/app.js assets/styles.css tests/browser-smoke.mjs
git commit -m "feat: add application workspace interface"
```

### Task 6: Formal collection, documentation, and deployment

**Files:**
- Modify: `data/jobs.json`
- Modify: `data/health.json`
- Modify: `crawler/cache/details.json`
- Modify: `README.md`
- Modify: `docs/weekly-improvement-log.md`

**Interfaces:**
- Consumes: all completed tasks.
- Produces: the deployable static snapshot and a documented maintenance record.

- [ ] **Step 1: Run the formal collector and quality gate**

Run: `python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --health-output data/health.json`

Run: `python scripts/check_snapshot.py --jobs data/jobs.json --health data/health.json`

Expected: enabled source success rate is at least 60%, total jobs are non-zero, and the snapshot is younger than 36 hours.

- [ ] **Step 2: Run the complete local suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Run: `node --test tests/core.test.mjs tests/matching.test.mjs tests/application.test.mjs tests/favorites.test.mjs`

Run: `node tests/browser-smoke.mjs`

Expected: all suites PASS.

- [ ] **Step 3: Document privacy, limitations, and backup restore**

Add README instructions for local-only notes, checklist migration, `.ics` behavior, JSON export/import, official-source focus coverage, and the warning that calendar alarms and browser data depend on the user's device and calendar application.

- [ ] **Step 4: Add a dated weekly log entry and commit**

```bash
git add data/jobs.json data/health.json crawler/cache/details.json README.md docs/weekly-improvement-log.md
git commit -m "docs: record application assistant rollout"
```

- [ ] **Step 5: Push, watch deployment, and verify public output**

Run: `git push origin main`

Run: `gh run watch <run-id> --repo 810204735c-maker/c --exit-status`

Expected: collection, Python tests, all Node suites, Pages deployment, and public smoke checks succeed. Confirm the public homepage contains “报名助手” and the live JSON contains current `applicationHints` where official evidence exists.

## Self-Review

- Spec coverage: Task 1 covers all four requested source directions; Tasks 2, 3, and 5 cover process, materials, calendar, and reminders; Tasks 4 and 5 cover favorite notes and backup/restore.
- Placeholder scan: no TBD, TODO, or unspecified error-handling steps remain.
- Type consistency: `applicationHints`, workspace version 1, `buildApplicationGuide`, `getJobAlerts`, `buildCalendarFile`, `normalizeWorkspace`, and import/export helpers use the same names across producers, consumers, and tests.
