import unittest
from datetime import datetime, timezone

from crawler.detail import enrich_jobs, extract_main_text, fetch_detail_text


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
        self.assertEqual(updated, cache)

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


if __name__ == "__main__":
    unittest.main()
