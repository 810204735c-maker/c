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
try:
    from crawler.timezone import shanghai_timezone
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from timezone import shanghai_timezone

try:
    from crawler.lifecycle import extract_registration_window
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from lifecycle import extract_registration_window

try:
    from crawler.profile_hints import PROFILE_HINTS_SCHEMA_VERSION, extract_profile_hints
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from profile_hints import PROFILE_HINTS_SCHEMA_VERSION, extract_profile_hints

try:
    from crawler.application_hints import APPLICATION_HINTS_SCHEMA_VERSION, extract_application_hints
except ModuleNotFoundError:  # Support `python crawler/crawl.py`.
    from application_hints import APPLICATION_HINTS_SCHEMA_VERSION, extract_application_hints

try:
    from crawler.foreign_hints import FOREIGN_HINTS_SCHEMA_VERSION, extract_foreign_hints
except ModuleNotFoundError:  # Support `python crawler/foreign_crawl.py`.
    from foreign_hints import FOREIGN_HINTS_SCHEMA_VERSION, extract_foreign_hints


SHANGHAI = shanghai_timezone()
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


def _is_allowed_url(
    url: str,
    allowed_domains: list[str],
    allowed_url_prefixes: list[str] | tuple[str, ...] | None = None,
) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    for prefix in allowed_url_prefixes or []:
        candidate = str(prefix or "").strip()
        allowed = urlparse(candidate)
        allowed_host = (allowed.hostname or "").lower().rstrip(".")
        base_path = allowed.path.rstrip("/")
        same_origin = (
            allowed.scheme == "https"
            and parsed.scheme == allowed.scheme
            and host == allowed_host
            and parsed.port == allowed.port
        )
        path_allowed = parsed.path == base_path or parsed.path.startswith(base_path + "/")
        if same_origin and base_path and path_allowed:
            return True
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
    allowed_url_prefixes: list[str] | tuple[str, ...] | None = None,
) -> str:
    if not _is_allowed_url(url, allowed_domains, allowed_url_prefixes):
        raise RuntimeError("detail URL is outside allowed domains")
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "identity",
    })
    with opener(request, timeout=timeout) as response:
        final_url = response.geturl()
        if not _is_allowed_url(final_url, allowed_domains, allowed_url_prefixes):
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


def _cache_is_fresh(
    entry: object,
    now: datetime,
    fields_are_current: Callable[[dict], bool] | None = None,
) -> bool:
    if not isinstance(entry, dict):
        return False
    fetched_at = _parse_datetime(entry.get("fetchedAt"))
    if fetched_at is None:
        return False
    fields = entry.get("fields")
    if entry.get("status") == "ok":
        if not isinstance(fields, dict):
            return False
        if fields_are_current is not None and not fields_are_current(fields):
            return False
    ttl = SUCCESS_TTL if entry.get("status") == "ok" else FAILURE_TTL
    return now.astimezone(timezone.utc) - fetched_at.astimezone(timezone.utc) <= ttl


def _public_fields_are_current(fields: dict) -> bool:
    hints = fields.get("profileHints")
    application = fields.get("applicationHints")
    return (
        isinstance(hints, dict)
        and hints.get("schemaVersion") == PROFILE_HINTS_SCHEMA_VERSION
        and isinstance(application, dict)
        and application.get("schemaVersion") == APPLICATION_HINTS_SCHEMA_VERSION
    )


def _foreign_fields_are_current(fields: dict) -> bool:
    hints = fields.get("foreignHints")
    application = fields.get("applicationHints")
    return (
        isinstance(hints, dict)
        and hints.get("schemaVersion") == FOREIGN_HINTS_SCHEMA_VERSION
        and isinstance(application, dict)
        and application.get("schemaVersion") == APPLICATION_HINTS_SCHEMA_VERSION
    )


def _apply_fields(job: dict, entry: object) -> dict:
    if not isinstance(entry, dict) or entry.get("status") != "ok":
        return dict(job)
    fields = entry.get("fields")
    if not isinstance(fields, dict):
        return dict(job)
    enriched = dict(job)
    for key in ("registrationStart", "registrationEnd", "deadlineConfidence", "deadlineEvidence"):
        if fields.get(key) is not None:
            enriched[key] = fields[key]
    if fields.get("registrationEnd"):
        enriched["deadline"] = fields["registrationEnd"]
    hints = fields.get("profileHints")
    if isinstance(hints, dict) and any(
        hints.get(key) for key in ("roleTags", "majorTags", "qualificationTags", "graduateYears")
    ):
        enriched["profileHints"] = hints
    application = fields.get("applicationHints")
    if isinstance(application, dict) and any(
        application.get(key) for key in ("methods", "materialTags")
    ):
        enriched["applicationHints"] = application
    return enriched


def _apply_foreign_fields(campaign: dict, entry: object) -> dict:
    if not isinstance(entry, dict) or entry.get("status") != "ok":
        return dict(campaign)
    fields = entry.get("fields")
    if not isinstance(fields, dict):
        return dict(campaign)
    enriched = dict(campaign)
    hints = fields.get("foreignHints")
    if isinstance(hints, dict):
        enriched["foreignHints"] = hints
        for key in ("cities", "jobFunctions", "educationLevels", "englishRequirements"):
            if hints.get(key):
                enriched[key] = list(hints[key])
        if hints.get("deadline"):
            enriched["deadline"] = hints["deadline"]
            enriched["deadlineConfidence"] = hints.get("deadlineConfidence", "high")
            enriched["deadlineEvidence"] = hints.get("deadlineEvidence", "")
    application = fields.get("applicationHints")
    if isinstance(application, dict) and any(
        application.get(key) for key in ("methods", "materialTags")
    ):
        enriched["applicationHints"] = application
    return enriched


def _extract_public_fields(text: str, now: datetime) -> dict:
    fields = extract_registration_window(text, now)
    fields["profileHints"] = extract_profile_hints(text)
    fields["applicationHints"] = extract_application_hints(text)
    return fields


def _extract_foreign_fields(text: str, now: datetime) -> dict:
    return {
        "foreignHints": extract_foreign_hints(text, now),
        "applicationHints": extract_application_hints(text),
    }


def _source_for_record(record: dict, sources_by_id: dict, sources_by_name: dict) -> dict | None:
    source_value = record.get("source")
    source_id = source_value.get("id") if isinstance(source_value, dict) else None
    source_name = source_value.get("name") if isinstance(source_value, dict) else None
    return (
        sources_by_id.get(source_id)
        or sources_by_name.get(record.get("collector"))
        or sources_by_name.get(source_name)
    )


def enrich_records(
    records: list[dict],
    sources: list[dict],
    cache: dict,
    now: datetime,
    extractor: Callable[[str, datetime], dict],
    max_fetches: int = 40,
    max_workers: int = 4,
    fetcher: Callable[[str, list[str], int], str] | None = None,
    *,
    fields_are_current: Callable[[dict], bool] | None = None,
    apply_fields: Callable[[dict, object], dict] | None = None,
    is_complete: Callable[[dict], bool] | None = None,
) -> tuple[list[dict], dict]:
    """Enrich allowlisted records while sharing cache and concurrency safety."""
    custom_fetcher = fetcher
    apply_fields = apply_fields or (lambda record, _entry: dict(record))
    is_complete = is_complete or (lambda _record: False)
    sources_by_id = {
        source.get("id"): source
        for source in sources
        if isinstance(source, dict) and source.get("id")
    }
    sources_by_name = {
        source.get("name"): source
        for source in sources
        if isinstance(source, dict) and source.get("name")
    }
    entries = dict(cache.get("entries", {})) if isinstance(cache, dict) else {}
    enriched_records = [dict(record) for record in records]
    tasks: list[tuple[int, dict, dict, list[str], list[str]]] = []

    for index, record in enumerate(enriched_records):
        if is_complete(record):
            continue
        source = _source_for_record(record, sources_by_id, sources_by_name)
        if not source:
            continue
        allowed_domains = list(record.get("_allowedDomains") or source.get("allowedDomains", []))
        allowed_prefixes = list(record.get("_allowedUrlPrefixes") or source.get("allowedUrlPrefixes", []))
        url = record.get("url", "")
        if not _is_allowed_url(url, allowed_domains, allowed_prefixes):
            continue
        cached = entries.get(url)
        if _cache_is_fresh(cached, now, fields_are_current):
            enriched_records[index] = apply_fields(record, cached)
            continue
        if len(tasks) < max(0, max_fetches):
            tasks.append((index, record, source, allowed_domains, allowed_prefixes))

    host_limits: dict[str, BoundedSemaphore] = {}
    for _, record, _, _, _ in tasks:
        host = (urlparse(record["url"]).hostname or "").lower()
        host_limits.setdefault(host, BoundedSemaphore(2))
    fetched_at = now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()

    def fetch_one(task: tuple[int, dict, dict, list[str], list[str]]) -> tuple[int, str, dict]:
        index, record, source, allowed_domains, allowed_prefixes = task
        url = record["url"]
        host = (urlparse(url).hostname or "").lower()
        try:
            with host_limits[host]:
                if custom_fetcher is None:
                    html_text = fetch_detail_text(
                        url,
                        allowed_domains,
                        int(source.get("timeout", 20)),
                        allowed_url_prefixes=allowed_prefixes,
                    )
                else:
                    html_text = custom_fetcher(url, allowed_domains, int(source.get("timeout", 20)))
            fields = extractor(extract_main_text(html_text), now)
            entry = {"status": "ok", "fetchedAt": fetched_at, "fields": fields}
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            entry = {"status": "error", "fetchedAt": fetched_at, "error": _safe_error(error)}
        return index, url, entry

    if tasks:
        worker_count = max(1, min(max_workers, len(tasks)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for index, url, entry in executor.map(fetch_one, tasks):
                entries[url] = entry
                enriched_records[index] = apply_fields(enriched_records[index], entry)

    return enriched_records, {"version": 1, "entries": entries}


def enrich_jobs(
    jobs: list[dict],
    sources: list[dict],
    cache: dict,
    now: datetime,
    max_fetches: int = 40,
    max_workers: int = 4,
    fetcher: Callable[[str, list[str], int], str] | None = None,
) -> tuple[list[dict], dict]:
    return enrich_records(
        jobs,
        sources,
        cache,
        now,
        _extract_public_fields,
        max_fetches,
        max_workers,
        fetcher,
        fields_are_current=_public_fields_are_current,
        apply_fields=_apply_fields,
        is_complete=lambda job: bool(
            job.get("deadline") and job.get("profileHints") and job.get("applicationHints")
        ),
    )


def enrich_foreign_campaigns(
    campaigns: list[dict],
    sources: list[dict],
    cache: dict,
    now: datetime,
    max_fetches: int = 80,
    max_workers: int = 4,
    fetcher: Callable[[str, list[str], int], str] | None = None,
) -> tuple[list[dict], dict]:
    return enrich_records(
        campaigns,
        sources,
        cache,
        now,
        _extract_foreign_fields,
        max_fetches,
        max_workers,
        fetcher,
        fields_are_current=_foreign_fields_are_current,
        apply_fields=_apply_foreign_fields,
        is_complete=lambda campaign: bool(campaign.get("_detailComplete")),
    )
