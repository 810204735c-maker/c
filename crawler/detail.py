"""Bounded, allowlisted enrichment from official recruitment detail pages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from threading import BoundedSemaphore
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

try:
    from crawler.lifecycle import extract_registration_window
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from lifecycle import extract_registration_window


SHANGHAI = ZoneInfo("Asia/Shanghai")
USER_AGENT = "Mozilla/5.0 (compatible; JobRadarCN/1.0; public-detail-enricher)"
SUCCESS_TTL = timedelta(days=7)
FAILURE_TTL = timedelta(hours=6)
MAX_RESPONSE_BYTES = 2_000_000
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "section", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "ul",
}
SKIP_TAGS = {"script", "style", "noscript", "template"}


def _is_allowed_url(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    for domain in allowed_domains:
        allowed = str(domain).lower().strip().rstrip(".")
        if allowed and (host == allowed or host.endswith("." + allowed)):
            return True
    return False


def _safe_error(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(
        r"(?i)(authorization|cookie|token|secret|password)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[redacted]",
        text,
    )
    return text[:180]


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class _DetailTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in SKIP_TAGS:
            self.skip_depth = 1
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self.skip_depth and tag.lower() in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag.lower() in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def extract_main_text(html_text: str) -> str:
    parser = _DetailTextParser()
    parser.feed(html_text or "")
    parser.close()
    lines = []
    for raw_line in "".join(parser.parts).splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def fetch_detail_text(
    url: str,
    allowed_domains: list[str],
    timeout: int = 20,
    opener: Callable = urlopen,
) -> str:
    if not _is_allowed_url(url, allowed_domains):
        raise RuntimeError("detail URL is outside allowed domains")
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "identity",
    })
    with opener(request, timeout=timeout) as response:
        final_url = response.geturl()
        if not _is_allowed_url(final_url, allowed_domains):
            raise RuntimeError("detail URL redirected outside allowed domains")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError("detail response exceeded 2000000 bytes")
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


def load_detail_cache(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "entries": {}}
    if not isinstance(document, dict) or not isinstance(document.get("entries"), dict):
        return {"version": 1, "entries": {}}
    return {"version": 1, "entries": dict(document["entries"])}


def _cache_is_fresh(entry: object, now: datetime) -> bool:
    if not isinstance(entry, dict):
        return False
    fetched_at = _parse_datetime(entry.get("fetchedAt"))
    if fetched_at is None:
        return False
    ttl = SUCCESS_TTL if entry.get("status") == "ok" else FAILURE_TTL
    return now.astimezone(timezone.utc) - fetched_at.astimezone(timezone.utc) <= ttl


def _apply_fields(job: dict, entry: object) -> dict:
    if not isinstance(entry, dict) or entry.get("status") != "ok":
        return dict(job)
    fields = entry.get("fields")
    if not isinstance(fields, dict) or not fields.get("registrationEnd"):
        return dict(job)
    enriched = dict(job)
    for key in ("registrationStart", "registrationEnd", "deadlineConfidence", "deadlineEvidence"):
        if key in fields:
            enriched[key] = fields[key]
    enriched["deadline"] = fields["registrationEnd"]
    return enriched


def enrich_jobs(
    jobs: list[dict],
    sources: list[dict],
    cache: dict,
    now: datetime,
    max_fetches: int = 40,
    max_workers: int = 4,
    fetcher: Callable[[str, list[str], int], str] | None = None,
) -> tuple[list[dict], dict]:
    fetcher = fetcher or fetch_detail_text
    source_by_name = {
        source.get("name"): source
        for source in sources
        if isinstance(source, dict) and source.get("name")
    }
    entries = dict(cache.get("entries", {})) if isinstance(cache, dict) else {}
    enriched_jobs = [dict(job) for job in jobs]
    tasks: list[tuple[int, dict, dict]] = []

    for index, job in enumerate(enriched_jobs):
        if job.get("deadline"):
            continue
        source = source_by_name.get(job.get("collector"))
        if not source:
            continue
        allowed_domains = source.get("allowedDomains", [])
        url = job.get("url", "")
        if not _is_allowed_url(url, allowed_domains):
            continue
        cached = entries.get(url)
        if _cache_is_fresh(cached, now):
            enriched_jobs[index] = _apply_fields(job, cached)
            continue
        if len(tasks) < max(0, max_fetches):
            tasks.append((index, job, source))

    host_limits: dict[str, BoundedSemaphore] = {}
    for _, job, _ in tasks:
        host = (urlparse(job["url"]).hostname or "").lower()
        host_limits.setdefault(host, BoundedSemaphore(2))
    fetched_at = now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()

    def fetch_one(task: tuple[int, dict, dict]) -> tuple[int, str, dict]:
        index, job, source = task
        url = job["url"]
        host = (urlparse(url).hostname or "").lower()
        try:
            with host_limits[host]:
                html_text = fetcher(
                    url,
                    list(source.get("allowedDomains", [])),
                    int(source.get("timeout", 20)),
                )
            fields = extract_registration_window(extract_main_text(html_text), now)
            entry = {
                "status": "ok",
                "fetchedAt": fetched_at,
                "fields": {
                    key: fields.get(key)
                    for key in (
                        "registrationStart",
                        "registrationEnd",
                        "deadlineConfidence",
                        "deadlineEvidence",
                    )
                },
            }
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            entry = {
                "status": "error",
                "fetchedAt": fetched_at,
                "error": _safe_error(error),
            }
        return index, url, entry

    if tasks:
        worker_count = max(1, min(max_workers, len(tasks)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for index, url, entry in executor.map(fetch_one, tasks):
                entries[url] = entry
                enriched_jobs[index] = _apply_fields(enriched_jobs[index], entry)

    return enriched_jobs, {"version": 1, "entries": entries}
