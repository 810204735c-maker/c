# Deadline Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich current official recruitment records from their public detail pages so `deadlineCoverage` reflects evidence-backed registration deadlines without bypassing access controls or making unbounded requests.

**Architecture:** Add a standard-library detail module that validates the original and final URL against each source's exact domain allowlist, extracts readable block text, and applies the existing conservative registration-window parser. Cache parsed results rather than full pages, use separate success/failure TTLs, cap each run at 40 network fetches, and treat every detail failure as a per-record degradation rather than a source failure.

**Tech Stack:** Python 3.12 standard library, `urllib`, `html.parser`, JSON cache, `unittest`.

## Global Constraints

- Fetch only public pages that require no login, CAPTCHA bypass, cookies, or access-control workarounds.
- Validate both requested URLs and post-redirect URLs against the configured exact-domain allowlist.
- Use at most 40 stale or uncached detail requests per run, at most 4 workers globally, and at most 2 concurrent requests per hostname.
- Cache successful parsed results for 7 days and failures for 6 hours.
- Store at most the registration fields and a sanitized 180-character error; never store full response bodies, cookies, or headers.
- A detail failure must keep the list record and must not change the list source's health status.
- Continue publishing `deadline` as the compatibility alias for `registrationEnd`.

---

### Task 1: Detail-page parser, redirect boundary, and cache

**Files:**
- Create: `crawler/detail.py`
- Create: `crawler/cache/details.json`
- Test: `tests/test_detail.py`

**Interfaces:**
- Consumes: `crawler.lifecycle.extract_registration_window(text: str, now: datetime) -> dict`
- Produces: `extract_main_text(html_text: str) -> str`
- Produces: `fetch_detail_text(url: str, allowed_domains: list[str], timeout: int = 20, opener=urlopen) -> str`
- Produces: `load_detail_cache(path: Path) -> dict`
- Produces: `enrich_jobs(jobs: list[dict], sources: list[dict], cache: dict, now: datetime, max_fetches: int = 40, max_workers: int = 4, fetcher=fetch_detail_text) -> tuple[list[dict], dict]`

- [ ] **Step 1: Write failing parser and enrichment tests**

```python
def test_extract_main_text_ignores_script_and_preserves_clauses():
    text = extract_main_text(
        "<main><p>报名时间：7月20日至7月25日。</p>"
        "<script>报名截止12月31日</script><p>8月2日笔试。</p></main>"
    )
    self.assertIn("报名时间：7月20日至7月25日", text)
    self.assertNotIn("12月31日", text)

def test_enrich_jobs_adds_evidence_backed_deadline_and_cache():
    jobs, cache = enrich_jobs(
        [JOB],
        [SOURCE],
        {"version": 1, "entries": {}},
        NOW,
        fetcher=lambda url, domains, timeout: DETAIL_HTML,
    )
    self.assertEqual(jobs[0]["deadline"], "2026-07-25")
    self.assertEqual(jobs[0]["registrationEnd"], "2026-07-25")
    self.assertIn(JOB["url"], cache["entries"])
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python -m unittest tests.test_detail -v`

Expected: FAIL because `crawler.detail` does not exist.

- [ ] **Step 3: Implement block-aware text extraction and safe fetching**

Use `HTMLParser` to ignore `script`, `style`, `noscript`, and `template`, append newlines after block elements, and normalize whitespace without joining unrelated clauses. `fetch_detail_text` must call `response.geturl()` and reject a final hostname unless it equals or is a subdomain of an allowlisted hostname.

- [ ] **Step 4: Implement TTL cache and bounded enrichment**

Cache entries must have this exact shape:

```json
{
  "version": 1,
  "entries": {
    "https://example.gov.cn/notice/1": {
      "status": "ok",
      "fetchedAt": "2026-07-23T14:00:00+08:00",
      "fields": {
        "registrationStart": "2026-07-20",
        "registrationEnd": "2026-07-25",
        "deadlineConfidence": "high",
        "deadlineEvidence": "报名时间：7月20日至7月25日"
      }
    }
  }
}
```

Apply a fresh successful cache entry without networking. Skip a fresh failure entry. For stale entries, use a `ThreadPoolExecutor(max_workers=min(max_workers, task_count))` plus one `BoundedSemaphore(2)` per hostname. Apply fields only when `registrationEnd` exists; preserve list-derived deadlines when detail evidence is absent.

- [ ] **Step 5: Run focused tests**

Run: `python -m unittest tests.test_detail tests.test_lifecycle -v`

Expected: all detail and lifecycle tests PASS.

- [ ] **Step 6: Commit the detail module**

```powershell
git add crawler/detail.py crawler/cache/details.json tests/test_detail.py
git commit -m "feat: enrich deadlines from official detail pages"
```

### Task 2: Integrate detail enrichment into atomic snapshot generation

**Files:**
- Modify: `crawler/crawl.py`
- Modify: `crawler/sources.json`
- Modify: `.github/workflows/update-jobs.yml`
- Modify: `tests/test_crawl.py`

**Interfaces:**
- Consumes: `load_detail_cache()` and `enrich_jobs()` from Task 1
- Produces: jobs with `registrationStart`, `registrationEnd`, `deadlineConfidence`, `deadlineEvidence`, and compatibility `deadline`

- [ ] **Step 1: Write a failing crawl integration test**

Configure `detailMaxFetches: 1` and `detailCachePath: "cache/details.json"` in a temporary config, patch `crawler.detail.fetch_detail_text` to return a registration range, run `crawl()`, and assert that both `jobs.json` and the cache are written only after the quality gate passes.

- [ ] **Step 2: Run the integration test and verify failure**

Run: `python -m unittest tests.test_crawl.CrawlTests.test_crawl_enriches_deadline_and_writes_cache_atomically -v`

Expected: FAIL because `crawl()` does not call detail enrichment.

- [ ] **Step 3: Insert enrichment before lifecycle pruning**

The order must be:

```text
list discovery → merge previous → recruitment-title filter → dedupe
→ detail enrichment → 180-day retention → deadline/45-day pruning
→ health build → quality gate → atomic jobs/health/cache writes
```

Set `detailMaxFetches` to `40`, `detailMaxWorkers` to `4`, and `detailCachePath` to `cache/details.json` in `crawler/sources.json`. Resolve the cache path relative to the config file's directory. When `dry_run=True`, use the cache but do not write it.

- [ ] **Step 4: Persist the cache in Actions**

Change the data commit step to:

```yaml
git add data/jobs.json data/health.json crawler/cache/details.json
```

- [ ] **Step 5: Run all local validation**

Run:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/core.test.mjs
python crawler/crawl.py --config crawler/sources.json --output data/jobs.json --health-output data/health.json --dry-run
node tests/browser-smoke.mjs
```

Expected: all tests PASS; dry-run remains above the 40% drop gate, source failures do not increase, and deadline coverage is greater than 0.

- [ ] **Step 6: Commit integration**

```powershell
git add crawler/crawl.py crawler/sources.json .github/workflows/update-jobs.yml tests/test_crawl.py
git commit -m "feat: integrate bounded deadline enrichment"
```

### Task 3: Deploy and measure the improvement

**Files:**
- Modify only if generated by workflow: `data/jobs.json`, `data/health.json`, `crawler/cache/details.json`

**Interfaces:**
- Consumes: the repository's existing `更新招考信息并部署网站` workflow
- Produces: a public snapshot with non-zero `deadlineCoverage`

- [ ] **Step 1: Push `main` without force**

Run: `git push origin main`

Expected: fast-forward push succeeds. If a workflow data commit races, fetch and use a normal merge; never force-push.

- [ ] **Step 2: Wait for all workflow jobs**

Run:

```powershell
$run = gh run list --workflow "更新招考信息并部署网站" --limit 1 --json databaseId | ConvertFrom-Json
gh run watch $run[0].databaseId --exit-status
```

Expected: `refresh-and-build`, `deploy`, and `public-smoke` all PASS.

- [ ] **Step 3: Recheck public metrics**

Run: `python scripts/check_public_site.py --base-url https://810204735c-maker.github.io/c/`

Expected: homepage, jobs, and health return HTTP 200; `deadlineCoverage > 0`; expired deadlines and unknown records older than 45 days equal 0.
