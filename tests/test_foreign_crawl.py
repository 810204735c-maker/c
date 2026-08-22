import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from crawler.foreign_crawl import (
    apply_campaign_lifecycle,
    collect_foreign_source,
    crawl_foreign,
    dedupe_campaigns,
    merge_foreign_previous,
    update_daily_summary,
)
from crawler.foreign_rules import campaign_identity


NOW = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)


def company():
    return {
        "id": "deloitte",
        "name": "德勤",
        "nameEn": "Deloitte",
        "aliases": ["德勤", "德勤中国", "Deloitte", "Deloitte China"],
        "ownership": "foreign_controlled",
        "homeCountryOrRegion": "英国",
        "industryTags": ["咨询/专业服务"],
        "officialDomains": ["example.com"],
        "delegatedUrlPrefixes": [],
        "publishable": True,
    }


def campaign(identifier="foreign_same", official=True, url="https://example.com/2027"):
    return {
        "id": identifier,
        "campaignKey": "deloitte|2027|graduate_program|autumn|general",
        "channel": "foreign",
        "company": {
            "id": "deloitte",
            "name": "德勤",
            "nameEn": "Deloitte",
            "industryTags": ["咨询/专业服务"],
        },
        "title": "Deloitte China 2027 Graduate Program",
        "titleLanguage": "en",
        "url": url,
        "source": {
            "id": "official" if official else "third",
            "name": "企业官网" if official else "应届生求职网",
            "tier": "official_verified" if official else "third_party_only",
        },
        "alternateSources": [],
        "official": official,
        "publishedAt": "2026-08-21",
        "dateEstimated": False,
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
        "status": "deadline_unknown",
        "summary": "",
        "collector": "企业官网" if official else "应届生求职网",
    }


class ForeignCrawlTests(unittest.TestCase):
    def test_official_replaces_third_party_without_changing_id(self):
        third = campaign("foreign_same", False, "https://third.example/job-1")
        official = campaign("foreign_same", True, "https://example.com/2027")

        result = dedupe_campaigns([third, official])

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["official"])
        self.assertEqual(result[0]["id"], "foreign_same")
        self.assertEqual(result[0]["alternateSources"][0]["url"], third["url"])

    def test_campaign_page_uses_required_evidence_without_global_internship_false_negative(self):
        source = {
            "id": "deloitte-page",
            "name": "德勤官网",
            "kind": "campaign_page",
            "url": "https://example.com/graduate",
            "campaignTitle": "Deloitte China 2027 Graduate Program",
            "companyId": "deloitte",
            "tier": "official_verified",
            "scopeCountry": "CN",
            "requiredTerms": ["China", "2027"],
            "allowedDomains": ["example.com"],
            "allowEmpty": True,
        }
        body = (
            "<main><h1>China 2027 Graduate Programme 上海</h1>"
            "<p>Applications close on 18 October 2026.</p>"
            "<aside>Hong Kong Summer Internship applications are also open.</aside></main>"
        )
        with patch("crawler.foreign_crawl.fetch_detail_text", return_value=body):
            campaigns, status = collect_foreign_source(source, {"deloitte": company()}, NOW, "2027")

        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0]["graduateYears"], ["2027"])
        self.assertEqual(campaigns[0]["cities"], ["上海"])

    def test_campaign_title_cannot_replace_missing_page_year_evidence(self):
        source = {
            "id": "deloitte-page",
            "name": "德勤官网",
            "kind": "campaign_page",
            "url": "https://example.com/graduate",
            "campaignTitle": "Deloitte China 2027 Graduate Program",
            "companyId": "deloitte",
            "tier": "official_verified",
            "scopeCountry": "CN",
            "requiredTerms": ["2027"],
            "allowedDomains": ["example.com"],
            "allowEmpty": True,
        }
        with patch("crawler.foreign_crawl.fetch_detail_text", return_value="<main>China graduate careers</main>"):
            campaigns, status = collect_foreign_source(source, {"deloitte": company()}, NOW, "2027")

        self.assertEqual(campaigns, [])
        self.assertEqual(status["status"], "empty")

    def test_campaign_page_focuses_nearest_country_year_pair_and_range_deadline(self):
        source = {
            "id": "db-page",
            "name": "德意志银行官网",
            "kind": "campaign_page",
            "url": "https://example.com/graduate",
            "campaignTitle": "Deloitte China 2027 Graduate Program",
            "companyId": "deloitte",
            "tier": "official_verified",
            "scopeCountry": "CN",
            "requiredTerms": ["China", "2027"],
            "allowApplicationPeriodRange": True,
            "allowedDomains": ["example.com"],
            "allowEmpty": True,
        }
        body = (
            "<main><p>United States 2027 Graduate Program Human Resources</p>"
            "<p>Hong Kong 2027 Graduate Programme Human Resources 1 Sep - 11 Oct 2026</p>"
            "<p>China 2027 Graduate Programme Corporate Bank 7 Sep - 18 Oct 2026 "
            "Bachelor graduates start full time in 2027.</p>"
            "<p>Australia 2027 Graduate Programme 12 March - 14 April 2026</p></main>"
        )
        with patch("crawler.foreign_crawl.fetch_detail_text", return_value=body):
            campaigns, status = collect_foreign_source(source, {"deloitte": company()}, NOW, "2027")

        self.assertEqual(status["status"], "ok")
        self.assertEqual(campaigns[0]["deadline"], "2026-10-18")

    def test_campaign_page_accepts_company_level_chinese_2027_formal_offer_evidence(self):
        source = {
            "id": "roche-page",
            "name": "罗氏官网",
            "kind": "campaign_page",
            "url": "https://careers.roche.com/cn/zh/startup-china-pharma",
            "campaignTitle": "StartUp 罗氏制药中国人才发展项目（2027届校园招聘）",
            "companyId": "roche",
            "programKey": "startup-china-pharma",
            "tier": "official_verified",
            "scopeCountry": "CN",
            "requiredTerms": ["2027届招聘", "中国大陆学校", "正式 offer"],
            "allowedDomains": ["careers.roche.com"],
            "allowEmpty": True,
        }
        roche = {
            **company(),
            "id": "roche",
            "name": "罗氏",
            "nameEn": "Roche",
            "aliases": ["罗氏", "Roche"],
            "industryTags": ["医药/医疗"],
            "officialDomains": ["roche.com"],
        }
        body = (
            "<main><h1>StartUp 罗氏制药中国人才发展项目</h1>"
            "<p>正式 offer，可签三方。2027届招聘将于2026年9月启动，"
            "中国大陆学校：2027届毕业生。</p><p>招聘地点：上海、北京</p></main>"
        )
        with patch("crawler.foreign_crawl.fetch_detail_text", return_value=body):
            campaigns, status = collect_foreign_source(source, {"roche": roche}, NOW, "2027")

        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0]["company"]["id"], "roche")
        self.assertEqual(campaigns[0]["campaignType"], "campus_recruitment")
        self.assertEqual(campaigns[0]["employmentType"], "full_time")
        self.assertCountEqual(campaigns[0]["cities"], ["上海", "北京"])

    def test_campaign_page_uses_open_graph_evidence_for_script_rendered_workday_page(self):
        source = {
            "id": "shell-page",
            "name": "Shell Graduate Programme 2027 - China",
            "kind": "campaign_page",
            "url": "https://shell.wd3.myworkdayjobs.com/ShellCareers/job/example",
            "campaignTitle": "Shell Graduate Programme 2027 - China",
            "companyId": "shell",
            "programKey": "graduate-programme-2027-china",
            "tier": "official_verified",
            "scopeCountry": "CN",
            "requiredTerms": ["Shell Graduate Programme 2027 - China", "Worker Type: Regular"],
            "allowedUrlPrefixes": ["https://shell.wd3.myworkdayjobs.com/ShellCareers/"],
            "allowEmpty": True,
        }
        shell = {
            **company(),
            "id": "shell",
            "name": "壳牌",
            "nameEn": "Shell",
            "aliases": ["壳牌", "Shell"],
            "industryTags": ["能源", "工业/制造"],
            "officialDomains": ["shell.com"],
            "delegatedUrlPrefixes": ["https://shell.wd3.myworkdayjobs.com/ShellCareers/"],
        }
        body = (
            '<html><head><meta property="og:title" content="Shell Graduate Programme 2027 - China">'
            '<meta property="og:description" content="Beijing, China Worker Type: Regular. '
            'Join Shell China in a comprehensive 3-year programme based in Beijing and Shanghai.">'
            '</head><body><div id="root"></div><script>renderJob()</script></body></html>'
        )
        with patch("crawler.foreign_crawl.fetch_detail_text", return_value=body):
            campaigns, status = collect_foreign_source(source, {"shell": shell}, NOW, "2027")

        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0]["company"]["id"], "shell")
        self.assertEqual(campaigns[0]["campaignType"], "graduate_program")
        self.assertEqual(campaigns[0]["employmentType"], "full_time")
        self.assertCountEqual(campaigns[0]["cities"], ["北京", "上海"])
        self.assertNotIn("人力资源", campaigns[0]["jobFunctions"])

    def test_campaign_page_fails_closed_when_final_redirect_leaves_tenant_prefix(self):
        source = {
            "id": "shell-page",
            "name": "Shell Graduate Programme 2027 - China",
            "kind": "campaign_page",
            "url": "https://shell.wd3.myworkdayjobs.com/ShellCareers/job/example",
            "campaignTitle": "Shell Graduate Programme 2027 - China",
            "companyId": "shell",
            "tier": "official_verified",
            "scopeCountry": "CN",
            "requiredTerms": ["Worker Type: Regular"],
            "allowedUrlPrefixes": ["https://shell.wd3.myworkdayjobs.com/ShellCareers/"],
        }
        shell = {
            **company(),
            "id": "shell",
            "name": "壳牌",
            "nameEn": "Shell",
            "aliases": ["壳牌", "Shell"],
            "officialDomains": ["shell.com"],
            "delegatedUrlPrefixes": ["https://shell.wd3.myworkdayjobs.com/ShellCareers/"],
        }
        with patch(
            "crawler.foreign_crawl.fetch_detail_text",
            side_effect=RuntimeError("detail URL redirected outside allowed domains"),
        ) as fetcher:
            campaigns, status = collect_foreign_source(source, {"shell": shell}, NOW, "2027")

        self.assertEqual(campaigns, [])
        self.assertEqual(status["status"], "error")
        self.assertIn("redirected outside allowed domains", status["error"])
        fetcher.assert_called_once_with(
            source["url"],
            [],
            timeout=20,
            allowed_url_prefixes=source["allowedUrlPrefixes"],
        )

    def test_registry_search_requires_mainland_evidence_in_result_text(self):
        source = {
            "id": "official-search",
            "name": "官网搜索",
            "kind": "rss_search_registry",
            "queryTemplate": "site:{domain} {year} {company}",
            "tier": "official_job_feed",
            "scopeCountry": "CN",
            "maxItems": 20,
            "allowEmpty": True,
        }
        without_mainland = (
            "<rss><channel><item><title>Deloitte 2027 Graduate Program</title>"
            "<link>https://example.com/graduate</link>"
            "<description>Applications are open.</description></item></channel></rss>"
        )
        with patch("crawler.foreign_crawl.fetch_text", return_value=without_mainland):
            campaigns, status = collect_foreign_source(source, {"deloitte": company()}, NOW, "2027")
        self.assertEqual(campaigns, [])
        self.assertEqual(status["status"], "empty")

        with_mainland = without_mainland.replace(
            "Applications are open.",
            "Applications are open for Shanghai.",
        )
        with patch("crawler.foreign_crawl.fetch_text", return_value=with_mainland):
            campaigns, status = collect_foreign_source(source, {"deloitte": company()}, NOW, "2027")
        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(campaigns), 1)

    def test_bootstrap_is_not_today_new(self):
        item = campaign("foreign_a")
        today, history, seen = update_daily_summary([item], {}, {}, NOW)

        self.assertTrue(today["bootstrap"])
        self.assertEqual(today["addedCount"], 0)
        self.assertEqual(today["baselineCount"], 1)
        self.assertEqual(history, [today])
        self.assertIn("foreign_a", seen["entries"])

    def test_same_day_new_items_are_union_and_official_upgrade_refreshes_summary(self):
        first = campaign("foreign_a", False, "https://third.example/a")
        bootstrap, history, seen = update_daily_summary([first], {}, {}, NOW)
        previous = {"generatedAt": NOW.isoformat(), "summaryHistory": history}
        second = campaign("foreign_b", True, "https://example.com/b")
        upgraded = campaign("foreign_a", True, "https://example.com/a")

        today, _, updated = update_daily_summary([upgraded, second], previous, seen, NOW + timedelta(hours=1))

        self.assertTrue(today["bootstrap"])
        self.assertEqual(today["addedCount"], 1)
        self.assertEqual(today["items"][0]["id"], "foreign_b")
        self.assertEqual(updated["entries"]["foreign_a"]["firstSeenAt"], first["firstSeenAt"])
        self.assertEqual(bootstrap["baselineCount"], 1)

    def test_unobserved_retained_campaign_preserves_last_seen(self):
        item = {
            **campaign("foreign_a"),
            "firstSeenAt": "2026-08-01T08:00:00+08:00",
            "lastSeenAt": "2026-08-20T08:00:00+08:00",
            "_observedThisRun": False,
        }
        seen = {
            "schemaVersion": 1,
            "entries": {
                "foreign_a": {
                    "firstSeenAt": item["firstSeenAt"],
                    "lastSeenAt": item["lastSeenAt"],
                },
            },
        }

        update_daily_summary([item], {"generatedAt": NOW.isoformat()}, seen, NOW)

        self.assertEqual(item["lastSeenAt"], "2026-08-20T08:00:00+08:00")

    def test_official_upgrade_does_not_reset_first_seen(self):
        seen = {
            "schemaVersion": 1,
            "entries": {"foreign_a": {"firstSeenAt": "2026-08-21T07:20:00+08:00"}},
        }
        today, _, updated = update_daily_summary(
            [campaign("foreign_a", True, "https://example.com/a")],
            {"generatedAt": "2026-08-21T07:20:00+08:00", "summaryHistory": []},
            seen,
            NOW,
        )

        self.assertEqual(today["addedCount"], 0)
        self.assertEqual(updated["entries"]["foreign_a"]["firstSeenAt"], "2026-08-21T07:20:00+08:00")

    def test_summary_history_keeps_seven_natural_days(self):
        previous = {
            "generatedAt": "2026-08-21T07:20:00+08:00",
            "summaryHistory": [
                {"date": f"2026-08-{day:02d}", "bootstrap": False, "addedCount": 0, "baselineCount": 0, "items": []}
                for day in range(12, 22)
            ],
        }
        _, history, _ = update_daily_summary([], previous, {"entries": {"old": {"firstSeenAt": "2026-08-01T00:00:00+08:00"}}}, NOW)
        self.assertEqual([item["date"] for item in history], [
            "2026-08-22", "2026-08-21", "2026-08-20", "2026-08-19",
            "2026-08-18", "2026-08-17", "2026-08-16",
        ])

    def test_lifecycle_retains_expired_for_sixty_days_and_marks_unknown_stale(self):
        recent_expired = {**campaign("foreign_recent"), "deadline": "2026-08-01"}
        old_expired = {**campaign("foreign_old"), "deadline": "2026-06-22"}
        stale = {
            **campaign("foreign_stale"),
            "firstSeenAt": "2026-07-01T07:20:00+08:00",
            "lastSeenAt": "2026-07-01T07:20:00+08:00",
        }
        refreshed = {
            **campaign("foreign_refreshed"),
            "firstSeenAt": "2026-07-01T07:20:00+08:00",
            "lastSeenAt": "2026-08-21T07:20:00+08:00",
        }

        result = apply_campaign_lifecycle([recent_expired, old_expired, stale, refreshed], NOW)

        self.assertEqual(
            {item["id"] for item in result},
            {"foreign_recent", "foreign_stale", "foreign_refreshed"},
        )
        self.assertEqual(next(item for item in result if item["id"] == "foreign_recent")["status"], "expired")
        self.assertEqual(next(item for item in result if item["id"] == "foreign_stale")["status"], "stale")
        self.assertEqual(next(item for item in result if item["id"] == "foreign_refreshed")["status"], "deadline_unknown")

    def test_failed_source_keeps_previous_official_campaign(self):
        old = campaign("foreign_a", True, "https://example.com/a")
        result = merge_foreign_previous([], {"campaigns": [old]}, {"official", "企业官网"}, NOW)
        self.assertEqual(result[0]["id"], "foreign_a")
        self.assertNotIn("missingSinceAt", result[0])

    def test_crawl_dry_run_builds_valid_bootstrap_without_writing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path, companies_path = self._write_config(root)
            output = root / "data" / "foreign-campus.json"
            health = root / "data" / "foreign-health.json"
            body = "<main>China 2027 Graduate Programme for Marketing in Shanghai.</main>"
            with patch("crawler.foreign_crawl.fetch_detail_text", return_value=body):
                payload = crawl_foreign(config_path, companies_path, output, NOW, True, health)

            self.assertEqual(payload["channel"], "foreign-campus")
            self.assertEqual(payload["total"], 1)
            self.assertTrue(payload["todaySummary"]["bootstrap"])
            self.assertFalse(output.exists())
            self.assertFalse(health.exists())
            self.assertFalse((root / "cache" / "foreign-details.json").exists())
            self.assertFalse((root / "cache" / "foreign-seen.json").exists())

    def test_crawl_writes_snapshot_health_and_two_caches_after_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path, companies_path = self._write_config(root)
            output = root / "data" / "foreign-campus.json"
            health = root / "data" / "foreign-health.json"
            body = "<main>China 2027 Graduate Programme for Marketing in Shanghai.</main>"
            with patch("crawler.foreign_crawl.fetch_detail_text", return_value=body):
                crawl_foreign(config_path, companies_path, output, NOW, False, health)

            paths = [
                output,
                health,
                root / "cache" / "foreign-details.json",
                root / "cache" / "foreign-seen.json",
            ]
            self.assertTrue(all(path.exists() for path in paths))
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["total"], 1)

    @staticmethod
    def _write_config(root):
        config_path = root / "foreign_sources.json"
        companies_path = root / "foreign_companies.json"
        config_path.write_text(json.dumps({
            "schemaVersion": 1,
            "targetGraduateYear": "2027",
            "detailMaxFetches": 0,
            "detailCachePath": "cache/foreign-details.json",
            "seenCachePath": "cache/foreign-seen.json",
            "sources": [{
                "id": "deloitte-page",
                "name": "德勤官网",
                "kind": "campaign_page",
                "url": "https://example.com/graduate",
                "campaignTitle": "Deloitte China 2027 Graduate Program",
                "companyId": "deloitte",
                "tier": "official_verified",
                "scopeCountry": "CN",
                "requiredTerms": ["China", "2027"],
                "allowedDomains": ["example.com"],
                "allowEmpty": True,
            }],
        }), encoding="utf-8")
        companies_path.write_text(json.dumps({
            "schemaVersion": 1,
            "companies": [{
                **company(),
                "ownershipEvidenceUrl": "https://example.com/about",
                "ownershipCheckedAt": "2026-08-22",
            }],
        }), encoding="utf-8")
        return config_path, companies_path


if __name__ == "__main__":
    unittest.main()
