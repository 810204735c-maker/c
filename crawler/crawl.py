#!/usr/bin/env python3
"""Collect public recruitment notices into a static JSON snapshot.

The collector intentionally uses only Python's standard library so it can run
unchanged in GitHub Actions. It never bypasses authentication or access
controls; inaccessible sources are reported and their previous entries are
kept in the snapshot.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

try:
    from crawler.health import build_health, quality_violations, validate_health, validate_jobs
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from health import build_health, quality_violations, validate_health, validate_jobs

try:
    from crawler.lifecycle import extract_registration_window
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from lifecycle import extract_registration_window


SHANGHAI = ZoneInfo("Asia/Shanghai")
USER_AGENT = "Mozilla/5.0 (compatible; JobRadarCN/1.0; public-link-collector)"
RECRUITMENT_TERMS = (
    "招聘", "招募", "招考", "招录", "录用", "选调", "遴选", "校园招聘", "社会招聘", "补充录用",
)
NOISE_TERMS = (
    "培训班", "辅导班", "备考课程", "真题解析", "协议班", "考试培训", "广告",
    "拟录用", "录用公示", "面试公告", "面试人选", "体检名单", "考察人选", "资格复审",
    "拟聘用", "成绩查询", "成绩公告",
)
GENERIC_TITLES = {
    "招聘公告", "招考公告", "招录公告", "招录招聘", "招录政策", "招录聘类考试",
    "公务员招录", "公务员招录考试", "事业单位公开招聘", "企事业单位招聘",
    "中央机关及其直属机构公务员招录考试", "湖北省选调生考试", "湖北省省直机关公开遴选",
}
PROVINCES = (
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
    "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
    "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
    "新疆", "香港", "澳门", "台湾",
)


def clean_text(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_title(value: str | None) -> str:
    value = clean_text(value)
    trailing_date = r"\s*[\[【（(]?(20\d{2})[年./\-](\d{1,2})[月./\-](\d{1,2})日?[\]】）)]?\s*$"
    return re.sub(trailing_date, "", value).strip()


def normalize_title(value: str) -> str:
    value = clean_title(value).lower()
    value = re.sub(r"(?:[-—_｜|]\s*)?(?:官网|政府网|门户网站)$", "", value)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", value)


def canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"}:
        return ""
    query = parse_qs(parsed.query)
    for key in ("url", "target", "u"):
        candidate = query.get(key, [""])[0]
        if candidate.startswith(("http://", "https://")):
            return canonical_url(candidate)
    kept_query = "&".join(
        part for part in parsed.query.split("&")
        if part and not part.lower().startswith(("utm_", "spm=", "from="))
    )
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path, "", kept_query, ""))


def is_allowed_url(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    return any(host == domain.lower() or host.endswith("." + domain.lower()) for domain in allowed_domains)


def is_recruitment_title(title: str) -> bool:
    cleaned = clean_title(title).strip("-—_｜| ")
    return (
        cleaned not in GENERIC_TITLES
        and len(normalize_title(cleaned)) >= 6
        and any(term in cleaned for term in RECRUITMENT_TERMS)
        and not any(term in cleaned for term in NOISE_TERMS)
    )


def classify(title: str, default_category: str = "事业单位") -> str:
    compact = clean_text(title)
    if any(term in compact for term in ("公务员", "国考", "省考", "选调生", "遴选", "考试录用")):
        return "公务员"
    if any(term in compact for term in ("事业单位", "事业编", "教师招聘", "医院招聘", "公开招聘工作人员")):
        return "事业单位"
    if any(term in compact for term in (
        "央企", "国企", "集团", "公司", "中国电信", "中国移动", "中国联通", "国家电网",
        "南方电网", "航空工业", "航天科工", "航天科技", "中核", "中粮", "中建", "中铁",
    )):
        return "央国企"
    return default_category if default_category in {"公务员", "事业单位", "央国企"} else "事业单位"


def extract_location(text: str) -> str:
    for province in PROVINCES:
        if province in text:
            return province
    return "全国"


def extract_audience(text: str) -> str:
    has_graduate = any(term in text for term in ("应届", "校园招聘", "毕业生", "校招"))
    has_social = any(term in text for term in ("社会招聘", "面向社会", "社招", "在职人员"))
    if has_graduate and not has_social:
        return "应届"
    if has_social and not has_graduate:
        return "社会"
    return "不限"


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _infer_year(month: int, day: int, now: datetime) -> date | None:
    candidate = _safe_date(now.year, month, day)
    if candidate and candidate > now.date() + timedelta(days=45):
        candidate = _safe_date(now.year - 1, month, day)
    return candidate


def extract_publication_date(text: str, url: str, now: datetime) -> tuple[str, bool]:
    combined = f"{text} {url}"
    full = re.search(r"(20\d{2})[年./\-](\d{1,2})[月./\-](\d{1,2})日?", combined)
    if full:
        parsed = _safe_date(int(full.group(1)), int(full.group(2)), int(full.group(3)))
        if parsed:
            return parsed.isoformat(), False
    packed = re.search(r"(?:t|/)(20\d{2})(\d{2})(\d{2})(?:_|/|\.)", url, re.IGNORECASE)
    if packed:
        parsed = _safe_date(int(packed.group(1)), int(packed.group(2)), int(packed.group(3)))
        if parsed:
            return parsed.isoformat(), False
    short = re.search(r"(?<!\d)(\d{1,2})[./\-](\d{1,2})(?!\d)", text)
    if short:
        parsed = _infer_year(int(short.group(1)), int(short.group(2)), now)
        if parsed:
            return parsed.isoformat(), False
    return now.astimezone(SHANGHAI).date().isoformat(), True


def extract_deadline(text: str, now: datetime) -> str | None:
    return extract_registration_window(text, now)["registrationEnd"]


def source_label(url: str, fallback: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    labels = {
        "scs.gov.cn": "国家公务员局",
        "sasac.gov.cn": "国务院国资委",
        "mohrss.gov.cn": "人力资源社会保障部",
        "iguopin.com": "国聘",
    }
    for domain, label in labels.items():
        if host == domain or host.endswith("." + domain):
            return label
    if host.endswith(".gov.cn") or host == "gov.cn":
        return fallback
    return fallback


def _stable_id(title: str, url: str) -> str:
    value = f"{normalize_title(title)}|{canonical_url(url)}".encode("utf-8")
    return hashlib.sha1(value).hexdigest()[:16]


def make_job(
    title: str,
    url: str,
    context: str,
    source: dict,
    now: datetime,
    published_at: str | None = None,
) -> dict:
    title = clean_title(title)
    url = canonical_url(url)
    derived_date, date_estimated = extract_publication_date(f"{title} {context}", url, now)
    published_at = published_at or derived_date
    summary = clean_text(context)
    if summary.startswith(title):
        summary = summary[len(title):].strip(" -—|：:")
    summary = summary[:180]
    host = (urlparse(url).hostname or "").lower()
    official = host.endswith(".gov.cn") or host == "gov.cn" or host.endswith(".scs.gov.cn") or host.endswith(".iguopin.com")
    combined = f"{title} {summary}"
    return {
        "id": _stable_id(title, url),
        "title": title,
        "url": url,
        "source": source_label(url, source["name"]),
        "collector": source["name"],
        "publishedAt": published_at,
        "dateEstimated": date_estimated if published_at == derived_date else False,
        "category": classify(title, source.get("category", "事业单位")),
        "location": extract_location(combined),
        "audience": extract_audience(combined),
        "deadline": extract_deadline(combined, now),
        "summary": summary,
        "official": official,
        "collectedAt": now.astimezone(SHANGHAI).replace(microsecond=0).isoformat(),
    }


def _rss_text(element: ElementTree.Element, names: Iterable[str]) -> str:
    wanted = set(names)
    for child in element.iter():
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name in wanted:
            if local_name == "link" and child.attrib.get("href"):
                return child.attrib["href"]
            value = "".join(child.itertext()).strip()
            if value:
                return value
    return ""


def parse_rss(xml_text: str, source: dict, now: datetime) -> list[dict]:
    root = ElementTree.fromstring(xml_text)
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    jobs: list[dict] = []
    for entry in entries:
        title = clean_title(_rss_text(entry, ("title",)))
        url = canonical_url(_rss_text(entry, ("link", "url")))
        description = clean_text(_rss_text(entry, ("description", "summary", "content")))
        if not title or not url or not is_recruitment_title(title):
            continue
        if not is_allowed_url(url, source.get("allowedDomains", [])):
            continue
        published_raw = _rss_text(entry, ("pubdate", "published", "updated", "date"))
        published_at = None
        if published_raw:
            try:
                parsed = parsedate_to_datetime(published_raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                published_at = parsed.astimezone(SHANGHAI).date().isoformat()
            except (TypeError, ValueError, OverflowError):
                published_at = extract_publication_date(published_raw, url, now)[0]
        jobs.append(make_job(title, url, description, source, now, published_at))
        if len(jobs) >= int(source.get("maxItems", 50)):
            break
    return jobs


@dataclass
class LinkRecord:
    href: str
    text: str = ""
    tail: str = ""


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[LinkRecord] = []
        self.current: LinkRecord | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href") or ""
        self.current = LinkRecord(href=href)
        self.links.append(self.current)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current.text += " " + data
        elif self.links and len(self.links[-1].tail) < 180:
            self.links[-1].tail += " " + data


def parse_html(html_text: str, source: dict, now: datetime) -> list[dict]:
    parser = LinkParser()
    parser.feed(html_text)
    jobs: list[dict] = []
    base_url = source.get("url", "")
    for link in parser.links:
        title = clean_title(link.text)
        url = canonical_url(urljoin(base_url, link.href))
        context = clean_text(f"{title} {link.tail}")
        if not title or not url or not is_recruitment_title(title):
            continue
        if not is_allowed_url(url, source.get("allowedDomains", [])):
            continue
        job = make_job(title, url, context, source, now)
        if job["dateEstimated"] and not re.search(r"20\d{2}", title):
            continue
        jobs.append(job)
        if len(jobs) >= int(source.get("maxItems", 50)):
            break
    return jobs


def _metadata_score(job: dict) -> tuple[int, int, str]:
    score = 0
    score += 4 if job.get("deadline") else 0
    score += 3 if job.get("summary") else 0
    score += 2 if not job.get("dateEstimated") else 0
    score += 2 if job.get("official") else 0
    score += 1 if job.get("source") not in {"政府官网", job.get("collector")} else 0
    return score, len(normalize_title(job.get("title", ""))), job.get("publishedAt", "")


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    chosen: dict[str, dict] = {}
    for job in jobs:
        key = normalize_title(job.get("title", ""))
        if not key:
            continue
        matched_key = key
        job_is_truncated = clean_text(job.get("title", "")).endswith(("...", "…"))
        for existing_key, existing_job in chosen.items():
            existing_is_truncated = clean_text(existing_job.get("title", "")).endswith(("...", "…"))
            if (
                (job_is_truncated or existing_is_truncated)
                and min(len(key), len(existing_key)) >= 12
                and (key.startswith(existing_key) or existing_key.startswith(key))
            ):
                matched_key = existing_key
                break
        existing = chosen.get(matched_key)
        if existing is None or _metadata_score(job) > _metadata_score(existing):
            chosen[matched_key] = job
    complete_titles = [
        job for job in chosen.values()
        if not clean_text(job.get("title", "")).endswith(("...", "…"))
    ]
    return sorted(
        complete_titles,
        key=lambda item: (item.get("publishedAt") or "", item.get("deadline") or "", item.get("title") or ""),
        reverse=True,
    )


def merge_with_previous(new_jobs: list[dict], previous: dict, failed_sources: set[str], now: datetime) -> list[dict]:
    if failed_sources and not new_jobs:
        return dedupe_jobs(previous.get("jobs", []))
    seed_cutoff = now.astimezone(SHANGHAI).date() - timedelta(days=180)

    def is_recent_seed(job: dict) -> bool:
        if job.get("collector") != "初始官方数据":
            return False
        try:
            return date.fromisoformat(job.get("publishedAt", "")) >= seed_cutoff
        except ValueError:
            return False

    retained = [
        job for job in previous.get("jobs", [])
        if job.get("collector") in failed_sources or is_recent_seed(job)
    ]
    return dedupe_jobs([*new_jobs, *retained])


def prune_old_jobs(jobs: list[dict], now: datetime, retention_days: int) -> list[dict]:
    cutoff = now.astimezone(SHANGHAI).date() - timedelta(days=retention_days)
    kept: list[dict] = []
    for job in jobs:
        try:
            if date.fromisoformat(job.get("publishedAt", "")) >= cutoff:
                kept.append(job)
        except ValueError:
            continue
    return kept


def prune_expired_jobs(jobs: list[dict], now: datetime, unknown_ttl_days: int = 45) -> list[dict]:
    today = now.astimezone(SHANGHAI).date()
    unknown_cutoff = today - timedelta(days=unknown_ttl_days)
    kept: list[dict] = []
    for job in jobs:
        deadline = job.get("deadline")
        if not deadline:
            try:
                if date.fromisoformat(job.get("publishedAt", "")) >= unknown_cutoff:
                    kept.append(job)
            except (TypeError, ValueError):
                kept.append(job)
            continue
        try:
            if date.fromisoformat(deadline) >= today:
                kept.append(job)
        except (TypeError, ValueError):
            kept.append(job)
    return kept


def fetch_text(url: str, timeout: int = 20, attempts: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.5",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept-Encoding": "identity",
            })
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
                charset_match = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
                candidates = [charset_match.group(1)] if charset_match else []
                candidates.extend(["utf-8", "gb18030"])
                for charset in candidates:
                    try:
                        return body.decode(charset)
                    except (UnicodeDecodeError, LookupError):
                        continue
                return body.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else "unknown fetch error")


def _source_url(source: dict, now: datetime) -> str:
    if source.get("kind") == "rss_search":
        return "https://www.bing.com/search?" + urlencode({"format": "rss", "q": source["query"]})
    template = source.get("url", "")
    return template.format(year=now.year, nextYear=now.year + 1)


def _read_previous(path: Path) -> dict:
    if not path.exists():
        return {"jobs": [], "sourceStatus": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"jobs": [], "sourceStatus": []}


def _collect_source(configured_source: dict, now: datetime) -> tuple[list[dict], dict]:
    source = dict(configured_source)
    source["url"] = _source_url(source, now)
    try:
        body = fetch_text(source["url"], int(source.get("timeout", 20)))
        if source.get("kind") in {"rss", "rss_search"}:
            jobs = parse_rss(body, source, now)
        else:
            jobs = parse_html(body, source, now)
        if not jobs:
            if source.get("allowEmpty"):
                marker = source.get("emptyPageMarker")
                if marker and marker not in clean_text(body):
                    raise RuntimeError("accessible empty page did not contain its expected marker")
                return [], {"name": source["name"], "status": "empty", "count": 0}
            raise RuntimeError("source returned no matching official recruitment links")
        return jobs, {"name": source["name"], "status": "ok", "count": len(jobs)}
    except (RuntimeError, ElementTree.ParseError, ValueError) as error:
        return [], {
            "name": source["name"], "status": "error", "count": 0, "error": str(error)[:180],
        }


def crawl(
    config_path: Path,
    output_path: Path,
    now: datetime,
    dry_run: bool = False,
    health_output_path: Path | None = None,
) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    previous = _read_previous(output_path)
    health_output_path = health_output_path or output_path.with_name("health.json")
    previous_health = _read_previous(health_output_path)
    all_jobs: list[dict] = []
    failed_sources: set[str] = set()
    statuses: list[dict] = []

    sources = config.get("sources", [])
    enabled_sources = [source for source in sources if source.get("enabled", True)]
    worker_count = max(1, min(6, len(enabled_sources)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = iter(executor.map(lambda source: _collect_source(source, now), enabled_sources))
        for source in sources:
            if not source.get("enabled", True):
                statuses.append({
                    "name": source["name"],
                    "status": "disabled",
                    "count": 0,
                    "reason": source.get("disabledReason", "disabled in source configuration"),
                })
                continue
            jobs, status = next(results)
            all_jobs.extend(jobs)
            statuses.append(status)
            if status["status"] == "error":
                failed_sources.add(status["name"])

    jobs = merge_with_previous(all_jobs, previous, failed_sources, now)
    jobs = dedupe_jobs([job for job in jobs if is_recruitment_title(job.get("title", ""))])
    jobs = prune_old_jobs(jobs, now, int(config.get("retentionDays", 180)))
    jobs = prune_expired_jobs(jobs, now)
    for status in statuses:
        if status["status"] == "ok":
            status["count"] = sum(job.get("collector") == status["name"] for job in jobs)
    generated_at = now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()
    payload = {
        "generatedAt": generated_at,
        "total": len(jobs),
        "jobs": jobs[: int(config.get("maxTotal", 500))],
        "sourceStatus": statuses,
    }
    payload["total"] = len(payload["jobs"])
    if not payload["jobs"] and enabled_sources and all(status["status"] == "error" for status in statuses if status["status"] != "disabled"):
        raise RuntimeError("all sources failed and no previous jobs are available")
    health = build_health(payload, previous_health, now)
    violations = quality_violations(payload, previous_health, health, now)
    health["violations"] = violations
    validation_errors = [*validate_jobs(payload), *validate_health(health)]
    critical = [item for item in violations if item["severity"] == "critical"]
    if validation_errors or critical:
        messages = validation_errors + [item["message"] for item in critical]
        raise RuntimeError("quality gate rejected snapshot: " + "; ".join(dict.fromkeys(messages)))
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        health_output_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        health_temporary = health_output_path.with_suffix(health_output_path.suffix + ".tmp")
        jobs_temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        health_temporary.write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        health_temporary.replace(health_output_path)
        jobs_temporary.replace(output_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect public recruitment notices")
    parser.add_argument("--config", type=Path, default=Path("crawler/sources.json"))
    parser.add_argument("--output", type=Path, default=Path("data/jobs.json"))
    parser.add_argument("--health-output", type=Path, default=Path("data/health.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        payload = crawl(args.config, args.output, now, args.dry_run, args.health_output)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(f"collector failed: {error}", file=sys.stderr)
        return 1
    for status in payload["sourceStatus"]:
        suffix = f" ({status.get('error')})" if status["status"] == "error" else ""
        print(f"[{status['status']}] {status['name']}: {status['count']}{suffix}")
    print(f"total: {payload['total']} | generated: {payload['generatedAt']} | dry-run: {args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
