# Numbered Registration Deadline Implementation Plan

> **For agentic workers:** Implement this plan inline because the automated health-check task has already authorized a minimal repair and no executing-plans sub-skill is available in this session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recognize official notices that write a registration range as `1．报名。7月29日—8月7日`, then refresh legacy unknown-deadline cache entries so expired notices are removed on the next workflow run.

**Architecture:** Normalize only a registration label followed immediately by a Chinese full stop and a month/day expression before the existing conservative clause splitter runs. Tag cached public-detail fields with the registration-window parser schema, while refreshing only legacy entries whose deadline remained unknown so the 40-request cap is sufficient for the current snapshot.

**Tech Stack:** Python 3.12 standard library, `unittest`, existing GitHub Actions workflow.

## Global Constraints

- Keep date extraction evidence-based and registration-specific; exam, qualification-review, and admission-ticket dates remain excluded.
- Do not bypass access restrictions or widen source allowlists.
- Preserve unrelated work and use a normal commit and non-force push only after all Python, Node, and browser smoke tests pass.

---

### Task 1: Parse numbered registration clauses and refresh stale unknown cache entries

**Files:**
- Modify: `crawler/lifecycle.py`
- Modify: `crawler/detail.py`
- Test: `tests/test_lifecycle.py`
- Test: `tests/test_detail.py`

**Interfaces:**
- Consumes: `extract_registration_window(text: str, now: datetime) -> dict` and `_public_fields_are_current(fields: dict) -> bool`.
- Produces: `REGISTRATION_WINDOW_SCHEMA_VERSION: int` and cache field `registrationWindowSchemaVersion`.

- [x] **Step 1: Write failing tests**

```python
result = extract_registration_window(
    "1．报名。7月29日11:00—8月7日17:00。",
    NOW,
)
self.assertEqual(result["registrationEnd"], "2026-08-07")
```

Add a detail-cache regression whose fresh legacy fields contain `registrationEnd: None`; its fetcher returns the same numbered format and must produce `deadline == "2026-07-25"`.

- [x] **Step 2: Run focused tests and verify failure**

Run: `python -m unittest tests.test_lifecycle tests.test_detail -v`

Expected: the numbered registration test has no `registrationEnd`, and the legacy cache test does not call its fetcher.

- [x] **Step 3: Implement the minimal parser and cache schema change**

```python
REGISTRATION_WINDOW_SCHEMA_VERSION = 2
cleaned = re.sub(
    r"((?:网上|现场)?报名)[。．]\s*(?=(?:20\d{2}\s*年)?\d{1,2}\s*月)",
    r"\1时间：",
    _clean_text(text),
)
```

Persist `registrationWindowSchemaVersion` in `_extract_public_fields()`. In `_public_fields_are_current()`, accept a legacy entry only when it already has `registrationEnd`; otherwise require the current parser schema.

- [x] **Step 4: Run complete local verification**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Run: `npm test`

Run: `node tests/browser-smoke.mjs`

Expected: all commands pass and the browser console has no errors.

- [ ] **Step 5: Commit, push, and verify deployment**

Commit only the plan, parser, cache logic, and tests. Push `main` without rewriting history, wait for `更新招考信息并部署网站`, then confirm the public JSON no longer contains the expired湖北就业援疆 notice.
