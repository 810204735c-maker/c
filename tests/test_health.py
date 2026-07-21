import json
import unittest
from datetime import datetime, timedelta, timezone

from crawler.health import (
    build_health,
    check_public_site,
    quality_violations,
    validate_health,
    validate_jobs,
)


NOW = datetime(2026, 7, 21, 4, 30, tzinfo=timezone.utc)


def job(identifier, published_at, deadline=None):
    return {
        "id": identifier,
        "title": f"测试单位{identifier}公开招聘公告",
        "url": f"https://example.gov.cn/{identifier}",
        "publishedAt": published_at,
        "deadline": deadline,
    }


class FakeResponse:
    def __init__(self, status, body, content_type):
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class HealthTests(unittest.TestCase):
    def test_build_health_aggregates_enabled_sources_and_quality_metrics(self):
        payload = {
            "generatedAt": "2026-07-21T12:30:00+08:00",
            "total": 3,
            "jobs": [
                job("new", "2026-07-21", "2026-07-25"),
                job("recent", "2026-07-16"),
                job("old", "2026-07-01"),
            ],
            "sourceStatus": [
                {"name": "正常来源", "status": "ok", "count": 2},
                {"name": "暂无公告", "status": "empty", "count": 0},
                {"name": "失败来源", "status": "error", "count": 0, "error": "timeout"},
                {"name": "暂停来源", "status": "disabled", "count": 0, "reason": "访问要求脚本 Cookie"},
            ],
        }

        health = build_health(payload, {}, NOW)

        self.assertEqual(health["currentTotal"], 3)
        self.assertEqual(health["newLast7Days"], 2)
        self.assertAlmostEqual(health["deadlineCoverage"], 1 / 3, places=4)
        self.assertAlmostEqual(health["sourceSuccessRate"], 2 / 3, places=4)
        self.assertEqual(health["enabledSourceCount"], 3)
        self.assertEqual(health["disabledSourceCount"], 1)
        self.assertEqual(health["sources"][2]["consecutiveFailures"], 1)

    def test_build_health_carries_source_history_and_increments_failure_streak(self):
        previous = {
            "sources": [{
                "name": "失败来源",
                "status": "error",
                "lastSuccessAt": "2026-07-19T12:00:00+08:00",
                "lastFailureAt": "2026-07-20T12:00:00+08:00",
                "consecutiveFailures": 1,
            }]
        }
        payload = {
            "generatedAt": "2026-07-21T12:30:00+08:00",
            "total": 1,
            "jobs": [job("one", "2026-07-21")],
            "sourceStatus": [{"name": "失败来源", "status": "error", "count": 0, "error": "timeout"}],
        }

        source = build_health(payload, previous, NOW)["sources"][0]

        self.assertEqual(source["consecutiveFailures"], 2)
        self.assertEqual(source["lastSuccessAt"], "2026-07-19T12:00:00+08:00")
        self.assertEqual(source["lastFailureAt"], "2026-07-21T12:30:00+08:00")

    def test_quality_violations_detect_drop_low_success_stale_data_and_streaks(self):
        payload = {
            "generatedAt": (NOW - timedelta(hours=37)).isoformat(),
            "total": 59,
            "jobs": [job(str(index), "2026-07-21") for index in range(59)],
            "sourceStatus": [],
        }
        health = {
            "currentTotal": 59,
            "sourceSuccessRate": 0.5,
            "enabledSourceCount": 4,
            "sources": [{"name": "反复失败", "status": "error", "consecutiveFailures": 2}],
        }

        violations = quality_violations(payload, {"currentTotal": 100}, health, NOW)
        codes = {item["code"] for item in violations}

        self.assertTrue({"snapshot_drop", "low_source_success", "stale_snapshot", "source_failure_streak"} <= codes)
        self.assertEqual(
            {item["severity"] for item in violations if item["code"] != "source_failure_streak"},
            {"critical"},
        )

    def test_snapshot_validators_reject_missing_fields_and_count_mismatch(self):
        self.assertIn("jobs.generatedAt is required", validate_jobs({"total": 1, "jobs": []}))
        self.assertIn("jobs.total does not match jobs array length", validate_jobs({
            "generatedAt": "2026-07-21T12:30:00+08:00", "total": 1, "jobs": [], "sourceStatus": [],
        }))
        self.assertIn("health.sourceSuccessRate is required", validate_health({
            "generatedAt": "2026-07-21T12:30:00+08:00", "currentTotal": 1, "sources": [],
        }))

    def test_public_site_check_requires_html_and_two_valid_json_documents(self):
        responses = {
            "https://example.test/": FakeResponse(200, "<!doctype html><html><title>ok</title></html>", "text/html"),
            "https://example.test/data/jobs.json": FakeResponse(200, json.dumps({
                "generatedAt": "2026-07-21T12:30:00+08:00", "total": 0, "jobs": [], "sourceStatus": [],
            }), "application/json"),
            "https://example.test/data/health.json": FakeResponse(200, json.dumps({
                "generatedAt": "2026-07-21T12:30:00+08:00", "currentTotal": 0,
                "sourceSuccessRate": 1.0, "sources": [],
            }), "application/json"),
        }

        checks = check_public_site("https://example.test/", opener=lambda request, timeout: responses[request.full_url])

        self.assertTrue(all(check["ok"] for check in checks), checks)


if __name__ == "__main__":
    unittest.main()
