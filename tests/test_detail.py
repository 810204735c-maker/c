import unittest
from datetime import datetime, timezone

from crawler.detail import (
    enrich_foreign_campaigns,
    enrich_jobs,
    extract_main_text,
    fetch_detail_text,
)


NOW = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)
SOURCE = {
    "name": "测试官方来源",
    "allowedDomains": ["example.gov.cn"],
    "timeout": 12,
}
JOB = {
    "id": "job-1",
    "title": "某单位2026年公开招聘公告",
    "url": "https://notice.example.gov.cn/2026/1.html",
    "collector": "测试官方来源",
    "publishedAt": "2026-07-20",
    "deadline": None,
}
DETAIL_HTML = """
<!doctype html><html><body>
  <nav>报名服务</nav>
  <main>
    <p>报名时间：2026年7月20日9:00至7月25日17:00。</p>
    <p>请登录报名系统网上报名，上传报名表和身份证正反面。</p>
    <p>文字综合岗位负责文稿起草和宣传策划，专业要求中国语言文学，硕士研究生及以上。</p>
    <script>报名截止时间为2026年12月31日</script>
    <p>7月28日打印准考证，8月2日笔试。</p>
  </main>
</body></html>
"""


class FakeResponse:
    def __init__(self, final_url: str, body: bytes = b"<html></html>"):
        self._final_url = final_url
        self._body = body
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def geturl(self):
        return self._final_url

    def read(self, amount=None):
        return self._body if amount is None else self._body[:amount]


class DetailTests(unittest.TestCase):
    def test_extract_main_text_ignores_script_and_preserves_clauses(self):
        text = extract_main_text(DETAIL_HTML)

        self.assertIn("报名时间：2026年7月20日9:00至7月25日17:00。", text)
        self.assertIn("7月28日打印准考证，8月2日笔试。", text)
        self.assertNotIn("12月31日", text)

    def test_fetch_detail_rejects_redirect_outside_allowlist(self):
        def opener(request, timeout):
            return FakeResponse("https://tracking.example.com/redirect")

        with self.assertRaisesRegex(RuntimeError, "redirected outside allowed domains"):
            fetch_detail_text(
                JOB["url"],
                SOURCE["allowedDomains"],
                timeout=SOURCE["timeout"],
                opener=opener,
            )

    def test_fetch_detail_accepts_allowlisted_redirect_and_decodes_gb18030(self):
        expected = "报名时间为7月20日至7月25日"

        def opener(request, timeout):
            response = FakeResponse(
                "https://notice.example.gov.cn/final",
                expected.encode("gb18030"),
            )
            response.headers["Content-Type"] = "text/html; charset=gb18030"
            return response

        text = fetch_detail_text(
            JOB["url"],
            SOURCE["allowedDomains"],
            timeout=SOURCE["timeout"],
            opener=opener,
        )

        self.assertEqual(text, expected)

    def test_enrich_jobs_adds_evidence_backed_deadline_and_cache(self):
        calls = []

        def fetcher(url, allowed_domains, timeout):
            calls.append((url, allowed_domains, timeout))
            return DETAIL_HTML

        jobs, cache = enrich_jobs(
            [JOB],
            [SOURCE],
            {"version": 1, "entries": {}},
            NOW,
            fetcher=fetcher,
        )

        self.assertEqual(calls, [(JOB["url"], ["example.gov.cn"], 12)])
        self.assertEqual(jobs[0]["registrationStart"], "2026-07-20")
        self.assertEqual(jobs[0]["registrationEnd"], "2026-07-25")
        self.assertEqual(jobs[0]["deadline"], "2026-07-25")
        self.assertEqual(jobs[0]["deadlineConfidence"], "high")
        self.assertIn("报名时间", jobs[0]["deadlineEvidence"])
        self.assertEqual(jobs[0]["profileHints"]["majorTags"], ["中国语言文学"])
        self.assertEqual(
            jobs[0]["profileHints"]["roleTags"],
            ["综合文字", "宣传文化"],
        )
        self.assertEqual(jobs[0]["applicationHints"]["methods"], ["网上报名"])
        self.assertEqual(
            jobs[0]["applicationHints"]["materialTags"],
            ["报名表", "身份证"],
        )
        self.assertEqual(cache["entries"][JOB["url"]]["status"], "ok")

    def test_fresh_success_cache_enriches_without_network(self):
        cache = {
            "version": 1,
            "entries": {
                JOB["url"]: {
                    "status": "ok",
                    "fetchedAt": "2026-07-22T14:00:00+08:00",
                    "fields": {
                        "registrationStart": "2026-07-20",
                        "registrationEnd": "2026-07-25",
                        "deadlineConfidence": "high",
                        "deadlineEvidence": "报名时间为7月20日至7月25日",
                        "profileHints": {
                            "schemaVersion": 3,
                            "majorTags": ["中国语言文学"],
                            "roleTags": ["综合文字"],
                            "qualificationTags": ["硕士"],
                            "graduateYears": [],
                            "evidence": {"中国语言文学": "专业要求中国语言文学"},
                        },
                        "applicationHints": {
                            "schemaVersion": 1,
                            "methods": ["网上报名"],
                            "materialTags": ["报名表"],
                            "evidence": {"网上报名": "请登录报名系统进行网上报名"},
                        },
                    },
                }
            },
        }

        jobs, updated = enrich_jobs(
            [JOB],
            [SOURCE],
            cache,
            NOW,
            fetcher=lambda *args: self.fail("fresh cache must not fetch"),
        )

        self.assertEqual(jobs[0]["deadline"], "2026-07-25")
        self.assertEqual(jobs[0]["profileHints"]["majorTags"], ["中国语言文学"])
        self.assertEqual(jobs[0]["applicationHints"]["methods"], ["网上报名"])
        self.assertEqual(updated, cache)

    def test_old_profile_hint_schema_refreshes_success_cache(self):
        cache = {
            "version": 1,
            "entries": {
                JOB["url"]: {
                    "status": "ok",
                    "fetchedAt": "2026-07-22T14:00:00+08:00",
                    "fields": {
                        "profileHints": {
                            "schemaVersion": 2,
                            "roleTags": ["新媒体"],
                            "majorTags": [],
                            "qualificationTags": [],
                            "graduateYears": [],
                            "evidence": {"新媒体": "关注微信公众号"},
                        },
                        "applicationHints": {
                            "schemaVersion": 1,
                            "methods": [],
                            "materialTags": [],
                            "evidence": {},
                        },
                    },
                }
            },
        }

        jobs, updated = enrich_jobs(
            [JOB],
            [SOURCE],
            cache,
            NOW,
            fetcher=lambda *args: "<main><p>现面向社会公开招聘工作人员。</p></main>",
        )

        self.assertNotIn("profileHints", jobs[0])
        self.assertEqual(
            updated["entries"][JOB["url"]]["fields"]["profileHints"]["schemaVersion"],
            3,
        )

    def test_old_application_hint_schema_refreshes_success_cache(self):
        cache = {
            "version": 1,
            "entries": {
                JOB["url"]: {
                    "status": "ok",
                    "fetchedAt": "2026-07-22T14:00:00+08:00",
                    "fields": {
                        "profileHints": {
                            "schemaVersion": 3,
                            "roleTags": [],
                            "majorTags": [],
                            "qualificationTags": [],
                            "graduateYears": [],
                            "evidence": {},
                        },
                        "applicationHints": {
                            "schemaVersion": 0,
                            "methods": ["邮箱报名"],
                            "materialTags": [],
                            "evidence": {},
                        },
                    },
                }
            },
        }

        jobs, updated = enrich_jobs(
            [JOB],
            [SOURCE],
            cache,
            NOW,
            fetcher=lambda *args: "<main><p>请登录报名系统网上报名。</p></main>",
        )

        self.assertEqual(jobs[0]["applicationHints"]["methods"], ["网上报名"])
        self.assertEqual(
            updated["entries"][JOB["url"]]["fields"]["applicationHints"]["schemaVersion"],
            1,
        )

    def test_profile_hints_apply_even_when_deadline_is_unknown(self):
        html = "<main><p>负责公文写作和企业文化宣传，专业要求汉语言文字学。</p></main>"

        jobs, cache = enrich_jobs(
            [JOB],
            [SOURCE],
            {"version": 1, "entries": {}},
            NOW,
            fetcher=lambda *args: html,
        )

        self.assertIsNone(jobs[0]["deadline"])
        self.assertEqual(jobs[0]["profileHints"]["majorTags"], ["中国语言文学"])
        self.assertEqual(
            jobs[0]["profileHints"]["roleTags"],
            ["综合文字", "宣传文化"],
        )
        self.assertIn("profileHints", cache["entries"][JOB["url"]]["fields"])

    def test_fresh_failure_cache_skips_network_and_keeps_job(self):
        cache = {
            "version": 1,
            "entries": {
                JOB["url"]: {
                    "status": "error",
                    "fetchedAt": "2026-07-23T13:00:00+08:00",
                    "error": "temporary network failure",
                }
            },
        }

        jobs, updated = enrich_jobs(
            [JOB],
            [SOURCE],
            cache,
            NOW,
            fetcher=lambda *args: self.fail("fresh failure cache must not fetch"),
        )

        self.assertEqual(jobs, [JOB])
        self.assertEqual(updated, cache)

    def test_detail_failure_keeps_job_and_caches_sanitized_error(self):
        def failing_fetcher(url, allowed_domains, timeout):
            raise RuntimeError("Cookie: secret-token network unavailable")

        jobs, cache = enrich_jobs(
            [JOB],
            [SOURCE],
            {"version": 1, "entries": {}},
            NOW,
            fetcher=failing_fetcher,
        )

        self.assertIsNone(jobs[0]["deadline"])
        entry = cache["entries"][JOB["url"]]
        self.assertEqual(entry["status"], "error")
        self.assertNotIn("secret-token", entry["error"])

    def test_enrichment_skips_non_allowlisted_job(self):
        untrusted = {**JOB, "url": "https://example.com/notice.html"}

        jobs, cache = enrich_jobs(
            [untrusted],
            [SOURCE],
            {"version": 1, "entries": {}},
            NOW,
            fetcher=lambda *args: self.fail("non-allowlisted URL must not fetch"),
        )

        self.assertEqual(jobs, [untrusted])
        self.assertEqual(cache["entries"], {})

    def test_fetch_detail_accepts_exact_delegated_prefix_only(self):
        url = "https://jobs.shared-ats.example/employer-a/campaign"

        def accepted(request, timeout):
            return FakeResponse("https://jobs.shared-ats.example/employer-a/final")

        self.assertEqual(
            fetch_detail_text(
                url,
                [],
                opener=accepted,
                allowed_url_prefixes=["https://jobs.shared-ats.example/employer-a/"],
            ),
            "<html></html>",
        )

        def rejected(request, timeout):
            return FakeResponse("https://jobs.shared-ats.example/employer-b/final")

        with self.assertRaisesRegex(RuntimeError, "redirected outside allowed domains"):
            fetch_detail_text(
                url,
                [],
                opener=rejected,
                allowed_url_prefixes=["https://jobs.shared-ats.example/employer-a/"],
            )

        for malicious in (
            "https://jobs.shared-ats.example.evil/employer-a/campaign",
            "https://jobs.shared-ats.example/employer-a-evil/campaign",
        ):
            with self.subTest(url=malicious):
                with self.assertRaisesRegex(RuntimeError, "outside allowed domains"):
                    fetch_detail_text(
                        malicious,
                        [],
                        opener=lambda *_args, **_kwargs: self.fail("malicious URL must not be fetched"),
                        allowed_url_prefixes=["https://jobs.shared-ats.example/employer-a/"],
                    )

    def test_enrich_foreign_campaigns_uses_bilingual_extractor_and_separate_schema(self):
        source = {
            "id": "deloitte-test",
            "name": "德勤测试来源",
            "allowedDomains": ["deloitte.example"],
            "timeout": 12,
        }
        campaign = {
            "id": "foreign_test",
            "url": "https://jobs.deloitte.example/2027",
            "collector": "德勤测试来源",
            "source": {"id": "deloitte-test", "name": "德勤测试来源"},
            "graduateYears": ["2027"],
            "deadline": None,
        }
        html = (
            "<main><p>China 2027 Graduate Programme for Marketing in Shanghai.</p>"
            "<p>Bachelor degree. Applications close on 18 October 2026.</p>"
            "<p>Apply online with your resume and transcript.</p></main>"
        )

        campaigns, cache = enrich_foreign_campaigns(
            [campaign],
            [source],
            {"version": 1, "entries": {}},
            NOW,
            fetcher=lambda *args: html,
        )

        self.assertEqual(campaigns[0]["cities"], ["上海"])
        self.assertEqual(campaigns[0]["jobFunctions"], ["市场/品牌"])
        self.assertEqual(campaigns[0]["educationLevels"], ["本科"])
        self.assertEqual(campaigns[0]["deadline"], "2026-10-18")
        self.assertEqual(campaigns[0]["applicationHints"]["methods"], ["网上报名"])
        fields = cache["entries"][campaign["url"]]["fields"]
        self.assertEqual(fields["foreignHints"]["schemaVersion"], 1)
        self.assertNotIn("profileHints", fields)


if __name__ == "__main__":
    unittest.main()
