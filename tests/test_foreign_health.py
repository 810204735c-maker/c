import json
import unittest
from datetime import datetime, timedelta, timezone

from crawler.foreign_health import (
    build_foreign_health,
    foreign_quality_violations,
    validate_foreign_health,
    validate_foreign_snapshot,
)


NOW = datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc)


def campaign(identifier="foreign_0123456789abcdefabcd", official=True):
    tier = "official_verified" if official else "third_party_only"
    return {
        "id": identifier,
        "campaignKey": f"deloitte|2027|graduate_program|autumn|{identifier[-4:]}",
        "channel": "foreign",
        "company": {
            "id": "deloitte",
            "name": "德勤",
            "nameEn": "Deloitte",
            "industryTags": ["咨询/专业服务"],
        },
        "title": "Deloitte China 2027 Graduate Program",
        "titleLanguage": "en",
        "url": "https://www.deloitte.com/cn/en/careers/graduate-program.html",
        "source": {"name": "德勤官网", "tier": tier, "platform": None},
        "alternateSources": [],
        "official": official,
        "publishedAt": "2026-08-22",
        "dateEstimated": False,
        "firstSeenAt": "2026-08-23T08:00:00+08:00",
        "lastSeenAt": "2026-08-23T08:00:00+08:00",
        "graduateYears": ["2027"],
        "campaignType": "graduate_program",
        "season": "autumn",
        "employmentType": "full_time",
        "cities": ["上海"],
        "jobFunctions": ["咨询"],
        "educationLevels": ["本科", "硕士"],
        "industryTags": ["咨询/专业服务"],
        "englishRequirements": [],
        "deadline": None,
        "deadlineConfidence": "unknown",
        "deadlineEvidence": "",
        "summary": "",
        "status": "deadline_unknown",
    }


def payload():
    item = campaign()
    summary_item = {
        "id": item["id"],
        "company": "德勤",
        "title": item["title"],
        "url": item["url"],
        "official": True,
    }
    summary = {
        "date": "2026-08-23",
        "bootstrap": False,
        "addedCount": 1,
        "baselineCount": 0,
        "items": [summary_item],
    }
    return {
        "schemaVersion": 1,
        "channel": "foreign-campus",
        "generatedAt": "2026-08-23T08:00:00+08:00",
        "targetGraduateYear": "2027",
        "total": 1,
        "campaigns": [item],
        "todaySummary": summary,
        "summaryHistory": [summary],
        "sourceStatus": [{"name": "德勤官网", "status": "ok", "count": 1}],
    }


class ForeignHealthTests(unittest.TestCase):
    def test_valid_snapshot_and_health(self):
        document = payload()
        self.assertEqual(validate_foreign_snapshot(document), [])
        health = build_foreign_health(document, {}, NOW)
        self.assertEqual(validate_foreign_health(health), [])
        self.assertEqual(health["currentTotal"], 1)
        self.assertEqual(health["activeTotal"], 1)
        self.assertEqual(health["officialSourceRatio"], 1.0)
        self.assertEqual(health["enabledSourceCount"], 1)
        self.assertEqual(health["lastSuccessfulAt"], document["generatedAt"])

    def test_validator_rejects_wrong_cohort_duplicate_ids_and_broken_summary(self):
        document = payload()
        document["campaigns"][0]["graduateYears"] = ["2028"]
        document["campaigns"].append(dict(document["campaigns"][0]))
        document["total"] = 2
        document["todaySummary"]["items"] = [{
            "id": "foreign_missing",
            "company": "X",
            "title": "Y",
            "url": "https://example.com",
            "official": False,
        }]
        errors = validate_foreign_snapshot(document)
        self.assertTrue(any("2027" in item for item in errors))
        self.assertTrue(any("duplicate" in item for item in errors))
        self.assertTrue(any("summary" in item or "unknown campaign" in item for item in errors))

    def test_all_failed_sources_use_recent_snapshot_as_warning(self):
        document = payload()
        document["generatedAt"] = (NOW - timedelta(days=2)).isoformat()
        document["sourceStatus"] = [{"name": "德勤官网", "status": "error", "count": 0, "error": "timeout"}]
        previous = {
            "currentTotal": 1,
            "lastSuccessfulAt": (NOW - timedelta(days=2)).isoformat(),
            "sources": [],
        }
        health = build_foreign_health(document, previous, NOW)
        violations = foreign_quality_violations(document, previous, health, NOW)
        failure = next(item for item in violations if item["code"] == "all_foreign_sources_failed")
        self.assertEqual(failure["severity"], "warning")
        self.assertFalse(any(item["code"] == "stale_foreign_snapshot" for item in violations))

    def test_all_failed_sources_become_critical_after_seven_days(self):
        document = payload()
        document["sourceStatus"] = [{"name": "德勤官网", "status": "error", "count": 0, "error": "timeout"}]
        previous = {
            "currentTotal": 1,
            "lastSuccessfulAt": (NOW - timedelta(days=8)).isoformat(),
            "sources": [],
        }
        health = build_foreign_health(document, previous, NOW)
        violations = foreign_quality_violations(document, previous, health, NOW)
        failure = next(item for item in violations if item["code"] == "all_foreign_sources_failed")
        self.assertEqual(failure["severity"], "critical")


if __name__ == "__main__":
    unittest.main()
