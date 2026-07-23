# GitHub Actions Node 24 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Node.js 20 deprecation annotations from the GitHub Pages workflow using current official Node 24-compatible Pages actions.

**Architecture:** Upgrade only the two Pages actions named by the runner annotations. Add a static regression test so the workflow cannot silently return to the deprecated major versions, then validate by executing the real deployment.

**Tech Stack:** GitHub Actions YAML, Python `unittest`, GitHub CLI.

## Global Constraints

- Use official `actions/*` repositories only.
- Use `actions/upload-pages-artifact@v5` and `actions/deploy-pages@v5`, whose current official releases use Node 24-compatible dependencies/runtimes.
- Do not set `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`.
- Do not copy third-party action code into this repository.
- Preserve the current permissions, concurrency, artifact path, Pages environment, and public-smoke dependency graph.

---

### Task 1: Upgrade Pages actions and add a regression test

**Files:**
- Modify: `.github/workflows/update-jobs.yml`
- Create: `tests/test_workflow.py`

**Interfaces:**
- Consumes: the existing `_site` artifact and `deploy.outputs.page_url`
- Produces: the same Pages deployment without Node.js 20 annotations

- [ ] **Step 1: Write the failing workflow version test**

```python
def test_pages_actions_use_node24_compatible_majors(self):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    self.assertIn("actions/upload-pages-artifact@v5", workflow)
    self.assertIn("actions/deploy-pages@v5", workflow)
    self.assertNotIn("actions/upload-pages-artifact@v3", workflow)
    self.assertNotIn("actions/deploy-pages@v4", workflow)
```

- [ ] **Step 2: Run the test and verify failure**

Run: `python -m unittest tests.test_workflow -v`

Expected: FAIL because the workflow still uses upload v3 and deploy v4.

- [ ] **Step 3: Upgrade the two action references**

```yaml
- name: 上传 Pages 构建产物
  uses: actions/upload-pages-artifact@v5
  with:
    path: _site

- name: 部署到 GitHub Pages
  id: deployment
  uses: actions/deploy-pages@v5
```

- [ ] **Step 4: Run workflow and repository tests**

Run:

```powershell
python -m unittest tests.test_workflow -v
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/core.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 5: Commit the Actions update**

```powershell
git add .github/workflows/update-jobs.yml tests/test_workflow.py
git commit -m "ci: move Pages actions to Node 24"
```

### Task 2: Validate the real workflow annotations

**Files:**
- No repository changes expected

**Interfaces:**
- Consumes: the pushed workflow commit
- Produces: evidence that deployment succeeds without Node.js 20 warnings

- [ ] **Step 1: Push and watch the workflow**

Run:

```powershell
git push origin main
$run = gh run list --workflow "更新招考信息并部署网站" --limit 1 --json databaseId | ConvertFrom-Json
gh run watch $run[0].databaseId --exit-status
```

Expected: `refresh-and-build`, `deploy`, and `public-smoke` all PASS.

- [ ] **Step 2: Inspect annotations**

Run:

```powershell
$run = gh run list --workflow "更新招考信息并部署网站" --limit 1 --json databaseId | ConvertFrom-Json
$jobs = gh run view $run[0].databaseId --json jobs | ConvertFrom-Json
$jobs.jobs | ForEach-Object {
  gh api "repos/810204735c-maker/c/check-runs/$($_.databaseId)/annotations"
}
```

Expected: no annotation message contains `Node.js 20 is deprecated`.

- [ ] **Step 3: Confirm the public site remains healthy**

Run: `python scripts/check_public_site.py --base-url https://810204735c-maker.github.io/c/`

Expected: all three public resources return HTTP 200 with valid formats.
