import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from crawler.crawl import (
    classify,
    dedupe_jobs,
    is_allowed_url,
    merge_with_previous,
    parse_html,
    parse_rss,
    prune_old_jobs,
)


NOW = datetime(2026, 7, 20, 2, 30, tzinfo=timezone.utc)

SOURCE = {
    "name": "测试官方搜索",
    "category": "公务员",
    "allowedDomains": ["gov.cn", "scs.gov.cn"],
    "maxItems": 20,
}

RSS_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
  <item>
    <title>某省2026年度公务员招录公告</title>
    <link>https://example.gov.cn/notice/20260718.html</link>
    <description>报名时间为7月20日至7月25日</description>
    <pubDate>Sat, 18 Jul 2026 01:00:00 GMT</pubDate>
  </item>
  <item>
    <title>培训机构：公务员备考课程</title>
    <link>https://example.com/course</link>
    <pubDate>Sat, 18 Jul 2026 01:00:00 GMT</pubDate>
  </item>
</channel></rss>"""

HTML_FIXTURE = """<!doctype html><html><body>
<ul>
  <li><a href="/n/202607/t20260716_1.html">航空工业某单位2026年社会招聘公告</a><span>2026-07-16</span></li>
  <li><a href="https://ads.example.com/a">备考资料</a></li>
</ul>
</body></html>"""


class CrawlTests(unittest.TestCase):
    def test_allowed_domain_supports_subdomains_but_rejects_lookalikes(self):
        self.assertTrue(is_allowed_url("https://rsj.beijing.gov.cn/a", ["gov.cn"]))
        self.assertFalse(is_allowed_url("https://gov.cn.example.com/a", ["gov.cn"]))
        self.assertFalse(is_allowed_url("javascript:alert(1)", ["gov.cn"]))

    def test_parse_rss_keeps_official_items_only(self):
        jobs = parse_rss(RSS_FIXTURE, SOURCE, NOW)
        self.assertEqual([job["title"] for job in jobs], ["某省2026年度公务员招录公告"])
        self.assertEqual(jobs[0]["publishedAt"], "2026-07-18")
        self.assertEqual(jobs[0]["deadline"], "2026-07-25")
        self.assertEqual(jobs[0]["location"], "全国")

    def test_parse_html_resolves_relative_urls_and_adjacent_dates(self):
        source = {
            "name": "国务院国资委",
            "url": "https://www.sasac.gov.cn/list/index.html",
            "category": "央国企",
            "allowedDomains": ["sasac.gov.cn"],
            "maxItems": 20,
        }
        jobs = parse_html(HTML_FIXTURE, source, NOW)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["publishedAt"], "2026-07-16")
        self.assertEqual(jobs[0]["category"], "央国企")
        self.assertTrue(jobs[0]["url"].startswith("https://www.sasac.gov.cn/"))

    def test_parse_html_rejects_navigation_labels_without_a_date(self):
        source = {
            "name": "湖北事业单位招聘公告",
            "url": "https://rst.hubei.gov.cn/list/",
            "category": "事业单位",
            "allowedDomains": ["hubei.gov.cn"],
            "maxItems": 20,
        }
        html = '<a href="/category/">事业单位公开招聘</a><a href="/notice/">某医院公开招聘工作人员公告</a>'
        self.assertEqual(parse_html(html, source, NOW), [])

    def test_classification_prefers_specific_terms(self):
        self.assertEqual(classify("某市事业单位公开招聘公告", "公务员"), "事业单位")
        self.assertEqual(classify("中央机关公务员补充录用公告", "事业单位"), "公务员")
        self.assertEqual(classify("中国电信校园招聘启动", "公务员"), "央国企")

    def test_post_exam_results_are_not_treated_as_open_opportunities(self):
        source = {
            "name": "公务员栏目",
            "url": "https://example.gov.cn/list/",
            "category": "公务员",
            "allowedDomains": ["gov.cn"],
            "maxItems": 20,
        }
        html = '<a href="/result/20260720.html">某机关2026年度考试录用公务员拟录用人员公示</a><span>2026-07-20</span>'
        self.assertEqual(parse_html(html, source, NOW), [])

    def test_date_inside_anchor_is_removed_from_the_title(self):
        source = {
            "name": "湖北事业单位招聘公告",
            "url": "https://rst.hubei.gov.cn/list/",
            "category": "事业单位",
            "allowedDomains": ["hubei.gov.cn"],
            "maxItems": 20,
        }
        html = '<a href="/notice/20260202.html">湖北省事业单位2026年公开招聘公告 2026/02/02</a>'
        jobs = parse_html(html, source, NOW)
        self.assertEqual(jobs[0]["title"], "湖北省事业单位2026年公开招聘公告")

    def test_dedupe_prefers_job_with_more_metadata(self):
        minimal = {
            "id": "a",
            "title": "某单位公开招聘公告",
            "url": "https://a.gov.cn/1",
            "source": "政府官网",
            "collector": "搜索",
            "publishedAt": "2026-07-18",
            "category": "事业单位",
            "location": "全国",
            "audience": "不限",
            "deadline": None,
            "summary": "",
            "official": True,
            "collectedAt": "2026-07-20T10:00:00+08:00",
        }
        rich = {
            **minimal,
            "id": "b",
            "url": "https://b.gov.cn/2",
            "deadline": "2026-07-25",
            "summary": "报名时间为7月20日至7月25日。",
        }
        self.assertEqual(dedupe_jobs([minimal, rich]), [rich])

    def test_dedupe_merges_a_truncated_title_into_the_full_title(self):
        base = {
            "id": "short",
            "title": "国家统计局机关2026年度拟录用公务员和参...",
            "url": "https://stats.gov.cn/short",
            "source": "国家统计局",
            "collector": "国家统计局公务员招录",
            "publishedAt": "2026-05-12",
            "category": "公务员",
            "location": "全国",
            "audience": "不限",
            "deadline": None,
            "summary": "",
            "official": True,
            "collectedAt": "2026-07-20T10:00:00+08:00",
        }
        full = {**base, "id": "full", "title": "国家统计局机关2026年度拟录用公务员和参公单位工作人员公示公告", "url": "https://stats.gov.cn/full"}
        self.assertEqual(dedupe_jobs([base, full]), [full])

    def test_prune_old_jobs_uses_the_configured_retention_window(self):
        jobs = [
            {"id": "recent", "publishedAt": "2026-07-01"},
            {"id": "old", "publishedAt": "2025-02-01"},
        ]
        self.assertEqual(prune_old_jobs(jobs, NOW, 180), [jobs[0]])

    def test_failed_source_keeps_its_previous_jobs(self):
        previous = {
            "generatedAt": "2026-07-19T10:00:00+08:00",
            "total": 1,
            "jobs": [
                {
                    "id": "old",
                    "title": "旧公告",
                    "url": "https://www.sasac.gov.cn/old",
                    "source": "国务院国资委",
                    "collector": "国务院国资委",
                    "publishedAt": "2026-07-18",
                    "category": "央国企",
                    "location": "全国",
                    "audience": "不限",
                    "deadline": None,
                    "summary": "",
                    "official": True,
                    "collectedAt": "2026-07-19T10:00:00+08:00",
                }
            ],
            "sourceStatus": [],
        }
        result = merge_with_previous([], previous, {"国务院国资委"}, NOW)
        self.assertEqual([job["id"] for job in result], ["old"])

    def test_all_failed_sources_keep_an_initial_snapshot(self):
        previous = {
            "jobs": [
                {
                    "id": "seed",
                    "title": "初始公告",
                    "url": "https://example.gov.cn/seed",
                    "source": "政府官网",
                    "collector": "初始官方数据",
                    "publishedAt": "2026-07-18",
                    "category": "事业单位",
                    "location": "全国",
                    "audience": "不限",
                    "deadline": None,
                    "summary": "",
                    "official": True,
                    "collectedAt": "2026-07-19T10:00:00+08:00",
                }
            ]
        }
        result = merge_with_previous([], previous, {"来源一", "来源二"}, NOW)
        self.assertEqual([job["id"] for job in result], ["seed"])

    def test_partial_success_keeps_recent_seed_items_during_first_refresh(self):
        previous = {
            "jobs": [
                {
                    "id": "seed",
                    "title": "初始公告",
                    "url": "https://example.gov.cn/seed",
                    "source": "政府官网",
                    "collector": "初始官方数据",
                    "publishedAt": "2026-07-18",
                    "category": "事业单位",
                    "location": "全国",
                    "audience": "不限",
                    "deadline": None,
                    "summary": "",
                    "official": True,
                    "collectedAt": "2026-07-19T10:00:00+08:00",
                }
            ]
        }
        fresh = {**previous["jobs"][0], "id": "fresh", "title": "新公告", "collector": "成功来源"}
        result = merge_with_previous([fresh], previous, {"失败来源"}, NOW)
        self.assertEqual({job["id"] for job in result}, {"seed", "fresh"})


if __name__ == "__main__":
    unittest.main()
