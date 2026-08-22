#!/usr/bin/env python3
"""Collect verified foreign-enterprise campus campaigns into a static snapshot."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, urljoin, urlparse
from xml.etree import ElementTree

try:
    from crawler.crawl import (
        LinkParser,
        canonical_url,
        clean_text,
        clean_title,
        extract_publication_date,
        fetch_text,
        is_allowed_url,
    )
except ModuleNotFoundError:  # Support `python crawler/foreign_crawl.py`.
    from crawl import (  # type: ignore
        LinkParser,
        canonical_url,
        clean_text,
        clean_title,
        extract_publication_date,
        fetch_text,
        is_allowed_url,
    )

try:
    from crawler.detail import enrich_foreign_campaigns, extract_main_text, fetch_detail_text, load_detail_cache
except ModuleNotFoundError:  # Support direct script execution.
    from detail import enrich_foreign_campaigns, extract_main_text, fetch_detail_text, load_detail_cache  # type: ignore

try:
    from crawler.application_hints import extract_application_hints
except ModuleNotFoundError:  # Support direct script execution.
    from application_hints import extract_application_hints  # type: ignore

try:
    from crawler.foreign_hints import extract_foreign_hints
except ModuleNotFoundError:  # Support direct script execution.
    from foreign_hints import extract_foreign_hints  # type: ignore

try:
    from crawler.foreign_rules import (
        campaign_identity,
        evaluate_campaign,
        is_official_tier,
        load_company_registry,
        resolve_company,
    )
except ModuleNotFoundError:  # Support direct script execution.
    from foreign_rules import (  # type: ignore
        campaign_identity,
        evaluate_campaign,
        is_official_tier,
        load_company_registry,
        resolve_company,
    )

try:
    from crawler.timezone import shanghai_timezone
except ModuleNotFoundError:  # Support direct script execution.
    from timezone import shanghai_timezone  # type: ignore


SHANGHAI = shanghai_timezone()
TIER_SCORE = {
    "official_verified": 400,
    "official_job_feed": 300,
    "secondary_verified": 200,
    "third_party_only": 100,
}
SUPPORTED_SOURCE_KINDS = {"campaign_page", "html", "rss_search", "rss_search_registry"}
CAMPAIGN_META_FIELDS = {
    "description",
    "og:title",
    "og:description",
    "twitter:title",
    "twitter:description",
}


class _CampaignMetadataParser(HTMLParser):
    """Collect only public summary metadata used by script-rendered job pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attributes = {str(key).lower(): value for key, value in attrs if key}
        field = str(attributes.get("property") or attributes.get("name") or "").lower()
        content = clean_text(attributes.get("content") or "")
        if field in CAMPAIGN_META_FIELDS and content:
            self.values.append(content[:10_000])


def _campaign_page_text(html_text: str) -> str:
    main_text = extract_main_text(html_text)
    parser = _CampaignMetadataParser()
    parser.feed(html_text or "")
    parser.close()
    parts = list(dict.fromkeys([main_text, *parser.values]))
    return "\n".join(part for part in parts if part)


def _read_json(path: Path, fallback: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return value if isinstance(value, dict) else dict(fallback)


def _resolve_path(config_path: Path, configured: object, fallback: str) -> Path:
    path = Path(str(configured or fallback))
    return path if path.is_absolute() else config_path.parent / path


def _safe_error(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(
        r"(?i)(authorization|cookie|token|secret|password)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[redacted]",
        text,
    )
    return text[:180]


def _url_allowed(url: str, domains: list[str], prefixes: list[str] | None = None) -> bool:
    if is_allowed_url(url, domains):
        return True
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    for prefix in prefixes or []:
        allowed = urlparse(str(prefix or "").strip())
        allowed_host = (allowed.hostname or "").lower().rstrip(".")
        base_path = allowed.path.rstrip("/")
        same_origin = (
            allowed.scheme == "https"
            and parsed.scheme == allowed.scheme
            and host == allowed_host
            and parsed.port == allowed.port
        )
        if same_origin and base_path and (
            parsed.path == base_path or parsed.path.startswith(base_path + "/")
        ):
            return True
    return False


def _rss_text(element: ElementTree.Element, names: tuple[str, ...]) -> str:
    wanted = set(names)
    for child in element.iter():
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name not in wanted:
            continue
        if local_name == "link" and child.attrib.get("href"):
            return child.attrib["href"]
        value = "".join(child.itertext()).strip()
        if value:
            return value
    return ""


def _search_url(query: str) -> str:
    return "https://www.bing.com/search?" + urlencode({"format": "rss", "q": query})


def _published_from_rss(raw: str, context: str, url: str, now: datetime) -> tuple[str, bool]:
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(SHANGHAI).date().isoformat(), False
        except (TypeError, ValueError, OverflowError):
            pass
    return extract_publication_date(context, url, now)


def _focused_context(
    text: str,
    terms: list[str],
    before: int = 0,
    after: int = 900,
) -> str:
    """Return the tightest window that contains every configured evidence term."""
    text = clean_text(text)
    lowered = text.lower()
    normalized_terms = list(dict.fromkeys(
        str(term).strip().lower() for term in terms if str(term).strip()
    ))
    positions: list[tuple[str, list[int]]] = []
    for term in normalized_terms:
        matches = [match.start() for match in re.finditer(re.escape(term), lowered)]
        if not matches:
            return ""
        positions.append((term, matches[:200]))
    if not positions:
        return ""

    best: tuple[int, int, int] | None = None
    anchor_term, anchors = positions[0]
    for anchor in anchors:
        selected = [(anchor, anchor + len(anchor_term))]
        for term, matches in positions[1:]:
            nearest = min(matches, key=lambda index: abs(index - anchor))
            selected.append((nearest, nearest + len(term)))
        cluster_start = min(item[0] for item in selected)
        cluster_end = max(item[1] for item in selected)
        candidate = (cluster_end - cluster_start, cluster_start, cluster_end)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return ""
    _, cluster_start, cluster_end = best
    return clean_text(text[max(0, cluster_start - before):min(len(text), cluster_end + after)])


def _public_company(company: dict) -> dict:
    return {
        "id": company["id"],
        "name": company.get("name", ""),
        "nameEn": company.get("nameEn", ""),
        "ownership": company.get("ownership", ""),
        "homeCountryOrRegion": company.get("homeCountryOrRegion", ""),
        "industryTags": list(company.get("industryTags", [])),
    }


def _make_campaign(
    title: str,
    url: str,
    context: str,
    source: dict,
    company: dict,
    eligibility: dict,
    hints: dict,
    now: datetime,
    published_at: str | None = None,
    date_estimated: bool | None = None,
    *,
    allowed_domains: list[str] | None = None,
    allowed_prefixes: list[str] | None = None,
) -> dict:
    campaign_key, identifier = campaign_identity(
        company["id"],
        eligibility["graduateYear"],
        eligibility["campaignType"],
        eligibility["season"],
        str(source.get("programKey", "general")),
    )
    url = canonical_url(url)
    if published_at is None:
        published_at, inferred = extract_publication_date(context, url, now)
        date_estimated = inferred if date_estimated is None else date_estimated
    local_now = now.astimezone(SHANGHAI).replace(microsecond=0)
    deadline = hints.get("deadline")
    campaign = {
        "id": identifier,
        "campaignKey": campaign_key,
        "channel": "foreign",
        "company": _public_company(company),
        "title": clean_title(title),
        "titleLanguage": "zh" if re.search(r"[\u4e00-\u9fff]", title or "") else "en",
        "url": url,
        "source": {
            "id": source.get("id", ""),
            "name": source.get("name", ""),
            "tier": source.get("tier", "third_party_only"),
        },
        "alternateSources": [],
        "official": is_official_tier(source.get("tier")),
        "publishedAt": published_at,
        "dateEstimated": bool(date_estimated),
        "graduateYears": [eligibility["graduateYear"]],
        "campaignType": eligibility["campaignType"],
        "season": eligibility["season"],
        "employmentType": "full_time",
        "cities": list(hints.get("cities", [])),
        "jobFunctions": list(hints.get("jobFunctions", [])),
        "educationLevels": list(hints.get("educationLevels", [])),
        "industryTags": list(company.get("industryTags", [])),
        "englishRequirements": list(hints.get("englishRequirements", [])),
        "deadline": deadline,
        "deadlineConfidence": hints.get("deadlineConfidence", "unknown"),
        "deadlineEvidence": hints.get("deadlineEvidence", ""),
        "summary": clean_text(context)[:240],
        "status": "open" if deadline else "deadline_unknown",
        "collector": source.get("name", ""),
        "collectedAt": local_now.isoformat(),
        "foreignHints": hints,
        "_allowedDomains": list(allowed_domains if allowed_domains is not None else source.get("allowedDomains", [])),
        "_allowedUrlPrefixes": list(allowed_prefixes if allowed_prefixes is not None else source.get("allowedUrlPrefixes", [])),
    }
    application = extract_application_hints(f"{title} {context}")
    if application.get("methods") or application.get("materialTags"):
        campaign["applicationHints"] = application
    return campaign


def _candidate_from_text(
    title: str,
    url: str,
    context: str,
    source: dict,
    companies: dict[str, dict],
    now: datetime,
    target_year: str,
    published_at: str | None = None,
    date_estimated: bool | None = None,
    company_override: dict | None = None,
) -> tuple[dict | None, bool]:
    eligibility = evaluate_campaign(f"{title} {context}", source, target_year)
    if not eligibility["eligible"]:
        return None, False
    company = company_override or resolve_company(f"{title} {context}", source, companies)
    if company is None:
        return None, True
    domains = list(company.get("officialDomains", [])) if is_official_tier(source.get("tier")) else list(source.get("allowedDomains", []))
    prefixes = list(company.get("delegatedUrlPrefixes", [])) if is_official_tier(source.get("tier")) else list(source.get("allowedUrlPrefixes", []))
    if not _url_allowed(url, domains, prefixes):
        return None, False
    hints = extract_foreign_hints(f"{title} {context}", now)
    return _make_campaign(
        title,
        url,
        context,
        source,
        company,
        eligibility,
        hints,
        now,
        published_at,
        date_estimated,
        allowed_domains=domains,
        allowed_prefixes=prefixes,
    ), False


def _collect_campaign_page(
    source: dict,
    companies: dict[str, dict],
    now: datetime,
    target_year: str,
) -> tuple[list[dict], int]:
    domains = list(source.get("allowedDomains", []))
    prefixes = list(source.get("allowedUrlPrefixes", []))
    body = fetch_detail_text(
        source["url"],
        domains,
        timeout=int(source.get("timeout", 20)),
        allowed_url_prefixes=prefixes,
    )
    detail_text = _campaign_page_text(body)
    lowered = detail_text.lower()
    required = [str(item) for item in source.get("requiredTerms", [])]
    missing = [term for term in required if term.lower() not in lowered]
    target_present = bool(re.search(r"(?<!\d)" + re.escape(target_year) + r"(?!\d)", detail_text))
    if missing or not target_present:
        if source.get("allowEmpty"):
            return [], 0
        missing_label = ", ".join(missing or [target_year])
        raise RuntimeError("campaign page did not contain required terms: " + missing_label)
    title = clean_title(source.get("campaignTitle") or source.get("name"))
    focused = _focused_context(detail_text, [target_year, *required]) or detail_text[:720]
    # The configured title defines the intended programme; the actual page body
    # above must independently prove the target year and configured terms.
    eligibility = evaluate_campaign(title, source, target_year)
    if not eligibility["eligible"]:
        return [], 0
    company = resolve_company(title, source, companies)
    if company is None:
        return [], 1
    if not _url_allowed(source["url"], domains, prefixes):
        raise RuntimeError("campaign URL is outside its allowlist")
    hints = extract_foreign_hints(
        focused,
        now,
        allow_application_range=bool(source.get("allowApplicationPeriodRange")),
    )
    published_at = now.astimezone(SHANGHAI).date().isoformat()
    campaign = _make_campaign(
        title,
        source["url"],
        focused,
        source,
        company,
        eligibility,
        hints,
        now,
        published_at,
        True,
        allowed_domains=domains,
        allowed_prefixes=prefixes,
    )
    campaign["_detailComplete"] = True
    return [campaign], 0


def _collect_html(
    source: dict,
    companies: dict[str, dict],
    now: datetime,
    target_year: str,
) -> tuple[list[dict], int]:
    body = fetch_text(source["url"], int(source.get("timeout", 20)))
    parser = LinkParser()
    parser.feed(body)
    campaigns = []
    pending = 0
    max_items = int(source.get("maxItems", 50))
    for link in parser.links:
        title = clean_title(link.text)
        url = canonical_url(urljoin(source["url"], link.href))
        context = clean_text(f"{title} {link.tail}")
        if not title or not url or not _url_allowed(url, list(source.get("allowedDomains", [])), list(source.get("allowedUrlPrefixes", []))):
            continue
        campaign, needs_review = _candidate_from_text(title, url, context, source, companies, now, target_year)
        pending += int(needs_review)
        if campaign:
            campaigns.append(campaign)
        if len(campaigns) >= max_items:
            break
    return campaigns, pending


def _rss_entries(xml_text: str) -> list[ElementTree.Element]:
    root = ElementTree.fromstring(xml_text)
    return [
        node for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}
    ]


def _collect_rss_search(
    source: dict,
    companies: dict[str, dict],
    now: datetime,
    target_year: str,
) -> tuple[list[dict], int]:
    body = fetch_text(_search_url(source["query"]), int(source.get("timeout", 20)))
    campaigns = []
    pending = 0
    max_items = int(source.get("maxItems", 50))
    for entry in _rss_entries(body):
        title = clean_title(_rss_text(entry, ("title",)))
        url = canonical_url(_rss_text(entry, ("link", "url")))
        description = clean_text(_rss_text(entry, ("description", "summary", "content")))
        if not title or not url or not _url_allowed(url, list(source.get("allowedDomains", [])), list(source.get("allowedUrlPrefixes", []))):
            continue
        raw_date = _rss_text(entry, ("pubdate", "published", "updated", "date"))
        published_at, estimated = _published_from_rss(raw_date, f"{title} {description}", url, now)
        campaign, needs_review = _candidate_from_text(
            title,
            url,
            description,
            source,
            companies,
            now,
            target_year,
            published_at,
            estimated,
        )
        pending += int(needs_review)
        if campaign:
            campaigns.append(campaign)
        if len(campaigns) >= max_items:
            break
    return campaigns, pending


def _collect_registry_search(
    source: dict,
    companies: dict[str, dict],
    now: datetime,
    target_year: str,
) -> tuple[list[dict], int]:
    campaigns = []
    errors = []
    successful_queries = 0
    max_items = int(source.get("maxItems", 20))
    for company in companies.values():
        if not company.get("publishable"):
            continue
        domains = list(company.get("officialDomains", []))
        if not domains:
            continue
        query = str(source["queryTemplate"]).format(
            domain=domains[0],
            year=target_year,
            company=company.get("nameEn") or company.get("name"),
        )
        try:
            entries = _rss_entries(fetch_text(_search_url(query), int(source.get("timeout", 20))))
            successful_queries += 1
        except (RuntimeError, ElementTree.ParseError, ValueError) as error:
            errors.append(_safe_error(error))
            continue
        dynamic_source = {
            **source,
            "companyId": company["id"],
            # Query scope is discovery input, not publication evidence. Every
            # result must independently identify mainland China in its text.
            "requireExplicitChinaEvidence": True,
        }
        for entry in entries:
            title = clean_title(_rss_text(entry, ("title",)))
            url = canonical_url(_rss_text(entry, ("link", "url")))
            description = clean_text(_rss_text(entry, ("description", "summary", "content")))
            prefixes = list(company.get("delegatedUrlPrefixes", []))
            if not title or not url or not _url_allowed(url, domains, prefixes):
                continue
            raw_date = _rss_text(entry, ("pubdate", "published", "updated", "date"))
            published_at, estimated = _published_from_rss(raw_date, f"{title} {description}", url, now)
            campaign, _ = _candidate_from_text(
                title,
                url,
                description,
                dynamic_source,
                companies,
                now,
                target_year,
                published_at,
                estimated,
                company,
            )
            if campaign:
                campaigns.append(campaign)
            if len(campaigns) >= max_items:
                return campaigns, 0
    if not successful_queries and errors:
        raise RuntimeError(errors[0])
    return campaigns, 0


def collect_foreign_source(
    source: dict,
    companies: dict[str, dict],
    now: datetime,
    target_year: str,
) -> tuple[list[dict], dict]:
    if not source.get("enabled", True) or source.get("kind") == "manual":
        return [], {
            "id": source.get("id", ""),
            "name": source.get("name", ""),
            "tier": source.get("tier", "manual_only"),
            "status": "disabled",
            "count": 0,
            "pendingReviewCount": 0,
            "reason": source.get("disabledReason", "disabled in source configuration"),
        }
    try:
        kind = source.get("kind")
        if kind == "campaign_page":
            campaigns, pending = _collect_campaign_page(source, companies, now, target_year)
        elif kind == "html":
            campaigns, pending = _collect_html(source, companies, now, target_year)
        elif kind == "rss_search":
            campaigns, pending = _collect_rss_search(source, companies, now, target_year)
        elif kind == "rss_search_registry":
            campaigns, pending = _collect_registry_search(source, companies, now, target_year)
        else:
            raise RuntimeError("unsupported foreign source kind")
        if not campaigns and not source.get("allowEmpty") and not pending:
            raise RuntimeError("source returned no eligible 2027 China full-time campaigns")
        status = "ok" if campaigns else "empty"
        return campaigns, {
            "id": source.get("id", ""),
            "name": source.get("name", ""),
            "tier": source.get("tier", "third_party_only"),
            "status": status,
            "count": len(campaigns),
            "pendingReviewCount": pending,
        }
    except (OSError, RuntimeError, ElementTree.ParseError, ValueError) as error:
        return [], {
            "id": source.get("id", ""),
            "name": source.get("name", ""),
            "tier": source.get("tier", "third_party_only"),
            "status": "error",
            "count": 0,
            "pendingReviewCount": 0,
            "error": _safe_error(error),
        }


def campaign_score(campaign: dict) -> int:
    return (
        TIER_SCORE.get(campaign.get("source", {}).get("tier"), 0)
        + (20 if campaign.get("deadline") else 0)
        + (10 if campaign.get("publishedAt") and not campaign.get("dateEstimated") else 0)
        + min(10, len(campaign.get("summary", "")) // 40)
    )


def dedupe_campaigns(campaigns: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for campaign in campaigns:
        if campaign.get("campaignKey"):
            grouped.setdefault(campaign["campaignKey"], []).append(dict(campaign))
    result = []
    for candidates in grouped.values():
        ordered = sorted(
            candidates,
            key=lambda item: (campaign_score(item), item.get("publishedAt") or "", item.get("url") or ""),
            reverse=True,
        )
        chosen = dict(ordered[0])
        chosen["_observedThisRun"] = any(
            item.get("_observedThisRun", True) for item in ordered
        )
        alternatives = []
        for item in ordered:
            if item is not ordered[0] and item.get("url") != chosen.get("url"):
                alternatives.append({
                    "name": item.get("source", {}).get("name", ""),
                    "tier": item.get("source", {}).get("tier", "third_party_only"),
                    "url": item.get("url", ""),
                })
            alternatives.extend(item.get("alternateSources", []))
        unique = {}
        for item in alternatives:
            url = item.get("url") if isinstance(item, dict) else None
            if url and url != chosen.get("url"):
                unique[url] = {
                    "name": item.get("name", ""),
                    "tier": item.get("tier", "third_party_only"),
                    "url": url,
                }
        chosen["alternateSources"] = list(unique.values())[:8]
        chosen["official"] = is_official_tier(chosen.get("source", {}).get("tier"))
        result.append(chosen)
    return sorted(
        result,
        key=lambda item: (item.get("publishedAt") or "", item.get("company", {}).get("name", "")),
        reverse=True,
    )


def merge_foreign_previous(
    new_campaigns: list[dict],
    previous: dict,
    failed_sources: set[str],
    now: datetime,
) -> list[dict]:
    new_keys = {item.get("campaignKey") for item in new_campaigns}
    retained = []
    missing_at = now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()
    for old in previous.get("campaigns", []):
        if not isinstance(old, dict) or not old.get("campaignKey"):
            continue
        source = old.get("source", {})
        source_failed = source.get("id") in failed_sources or source.get("name") in failed_sources
        if old["campaignKey"] in new_keys and not source_failed:
            continue
        kept = dict(old)
        kept["_observedThisRun"] = False
        if source_failed:
            kept["_detailComplete"] = True
        if old["campaignKey"] not in new_keys and not source_failed:
            kept.setdefault("missingSinceAt", missing_at)
        retained.append(kept)
    return dedupe_campaigns([*new_campaigns, *retained])


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def apply_campaign_lifecycle(
    campaigns: list[dict],
    now: datetime,
    retention_days: int = 60,
    unknown_ttl_days: int = 45,
) -> list[dict]:
    today = now.astimezone(SHANGHAI).date()
    kept = []
    for raw in campaigns:
        campaign = dict(raw)
        missing_since = _parse_date(campaign.get("missingSinceAt"))
        if missing_since and missing_since < today - timedelta(days=retention_days):
            continue
        deadline = _parse_date(campaign.get("deadline"))
        if deadline:
            if deadline < today:
                if deadline < today - timedelta(days=retention_days):
                    continue
                campaign["status"] = "expired"
            else:
                campaign["status"] = "open"
        else:
            last_seen = _parse_date(campaign.get("lastSeenAt") or campaign.get("firstSeenAt"))
            if last_seen and last_seen < today - timedelta(days=unknown_ttl_days):
                campaign["status"] = "stale"
            else:
                campaign["status"] = "deadline_unknown"
        kept.append(campaign)
    return kept


def update_daily_summary(
    campaigns: list[dict],
    previous: dict,
    seen_cache: dict,
    now: datetime,
    history_days: int = 7,
) -> tuple[dict, list[dict], dict]:
    local_now = now.astimezone(SHANGHAI).replace(microsecond=0)
    today_key = local_now.date().isoformat()
    seen = {"schemaVersion": 1, "entries": dict(seen_cache.get("entries", {}))}
    history_by_date = {
        item["date"]: dict(item)
        for item in previous.get("summaryHistory", [])
        if isinstance(item, dict) and item.get("date")
    }
    bootstrap = not seen["entries"] and not previous.get("generatedAt")
    newly_seen = []
    for item in campaigns:
        entry = seen["entries"].get(item["id"])
        if isinstance(entry, dict) and entry.get("firstSeenAt"):
            item["firstSeenAt"] = entry["firstSeenAt"]
        else:
            item["firstSeenAt"] = local_now.isoformat()
            seen["entries"][item["id"]] = {"firstSeenAt": item["firstSeenAt"]}
            newly_seen.append(item)
        observed = item.get("_observedThisRun", True)
        if observed:
            item["lastSeenAt"] = local_now.isoformat()
            seen["entries"][item["id"]]["lastSeenAt"] = item["lastSeenAt"]
        else:
            preserved_last_seen = (
                seen["entries"][item["id"]].get("lastSeenAt")
                or item.get("lastSeenAt")
                or item["firstSeenAt"]
            )
            item["lastSeenAt"] = preserved_last_seen
            seen["entries"][item["id"]]["lastSeenAt"] = preserved_last_seen
    current = dict(history_by_date.get(today_key, {
        "date": today_key,
        "bootstrap": bootstrap,
        "addedCount": 0,
        "baselineCount": len(campaigns) if bootstrap else 0,
        "items": [],
    }))
    union = {item["id"]: dict(item) for item in current.get("items", []) if isinstance(item, dict) and item.get("id")}
    current_by_id = {item["id"]: item for item in campaigns}
    for identifier in set(union) & set(current_by_id):
        item = current_by_id[identifier]
        union[identifier] = {
            "id": identifier,
            "company": item["company"]["name"],
            "title": item["title"],
            "url": item["url"],
            "official": bool(item["official"]),
        }
    if not bootstrap:
        for item in newly_seen:
            union[item["id"]] = {
                "id": item["id"],
                "company": item["company"]["name"],
                "title": item["title"],
                "url": item["url"],
                "official": bool(item["official"]),
            }
    current["items"] = sorted(union.values(), key=lambda item: (item["company"], item["title"]))
    current["addedCount"] = len(current["items"])
    history_by_date[today_key] = current
    cutoff = local_now.date() - timedelta(days=max(1, history_days) - 1)
    history = []
    for key in sorted(history_by_date, reverse=True):
        parsed = _parse_date(key)
        if parsed and parsed >= cutoff:
            history.append(history_by_date[key])
    return current, history, seen


def _strip_internal(campaign: dict) -> dict:
    return {key: value for key, value in campaign.items() if not key.startswith("_") and key != "foreignHints"}


def _filter_summary_items(summary: dict, known_ids: set[str]) -> dict:
    filtered = dict(summary)
    filtered["items"] = [item for item in summary.get("items", []) if item.get("id") in known_ids]
    filtered["addedCount"] = len(filtered["items"])
    return filtered


def _basic_health(payload: dict, previous_health: dict, now: datetime) -> dict:
    statuses = payload.get("sourceStatus", [])
    enabled = [item for item in statuses if item.get("status") != "disabled"]
    successful = [item for item in enabled if item.get("status") in {"ok", "empty"}]
    campaigns = payload.get("campaigns", [])
    return {
        "schemaVersion": 1,
        "generatedAt": now.astimezone(SHANGHAI).replace(microsecond=0).isoformat(),
        "currentTotal": len(campaigns),
        "activeTotal": sum(item.get("status") in {"open", "deadline_unknown"} for item in campaigns),
        "expiredRetainedTotal": sum(item.get("status") == "expired" for item in campaigns),
        "newToday": payload.get("todaySummary", {}).get("addedCount", 0),
        "officialSourceRatio": (
            sum(bool(item.get("official")) for item in campaigns) / len(campaigns) if campaigns else 0.0
        ),
        "registeredCompanyCount": 0,
        "pendingReviewCount": sum(int(item.get("pendingReviewCount", 0)) for item in statuses),
        "sourceSuccessRate": len(successful) / len(enabled) if enabled else 0.0,
        "failedSourceCount": sum(item.get("status") == "error" for item in enabled),
        "sources": statuses,
        "lastSuccessfulAt": previous_health.get("lastSuccessfulAt"),
        "violations": [],
    }


def _health_and_gate(payload: dict, previous_health: dict, now: datetime) -> tuple[dict, list[str]]:
    try:
        from crawler.foreign_health import (  # type: ignore
            build_foreign_health,
            foreign_quality_violations,
            validate_foreign_health,
            validate_foreign_snapshot,
        )
    except ModuleNotFoundError:
        from foreign_health import (  # type: ignore
            build_foreign_health,
            foreign_quality_violations,
            validate_foreign_health,
            validate_foreign_snapshot,
        )
    health_payload = {
        **payload,
        "generatedAt": now.astimezone(SHANGHAI).replace(microsecond=0).isoformat(),
    }
    health = build_foreign_health(health_payload, previous_health, now)
    violations = foreign_quality_violations(payload, previous_health, health, now)
    health["violations"] = violations
    errors = [*validate_foreign_snapshot(payload), *validate_foreign_health(health)]
    errors.extend(item["message"] for item in violations if item.get("severity") == "critical")
    return health, list(dict.fromkeys(errors))


def crawl_foreign(
    config_path: Path,
    companies_path: Path,
    output_path: Path,
    now: datetime,
    dry_run: bool = False,
    health_output_path: Path | None = None,
) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schemaVersion") != 1 or config.get("targetGraduateYear") != "2027":
        raise ValueError("foreign source config must use schemaVersion 1 and target 2027")
    companies = load_company_registry(companies_path)
    previous = _read_json(output_path, {})
    health_output_path = health_output_path or output_path.with_name("foreign-health.json")
    previous_health = _read_json(health_output_path, {})
    detail_cache_path = _resolve_path(config_path, config.get("detailCachePath"), "cache/foreign-details.json")
    seen_cache_path = _resolve_path(config_path, config.get("seenCachePath"), "cache/foreign-seen.json")
    detail_cache = load_detail_cache(detail_cache_path)
    seen_cache = _read_json(seen_cache_path, {"schemaVersion": 1, "entries": {}})
    sources = list(config.get("sources", []))
    target_year = config["targetGraduateYear"]
    enabled = [
        source for source in sources
        if source.get("enabled", True) and source.get("kind") in SUPPORTED_SOURCE_KINDS
    ]
    collected = []
    statuses_by_id: dict[str, dict] = {}
    if enabled:
        workers = max(1, min(6, len(enabled)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = executor.map(
                lambda source: collect_foreign_source(source, companies, now, target_year),
                enabled,
            )
            for source, (campaigns, status) in zip(enabled, results):
                collected.extend(campaigns)
                statuses_by_id[source.get("id", source.get("name", ""))] = status
    statuses = []
    for source in sources:
        key = source.get("id", source.get("name", ""))
        if key in statuses_by_id:
            statuses.append(statuses_by_id[key])
        else:
            _, status = collect_foreign_source(source, companies, now, target_year)
            statuses.append(status)
    failed_sources = {
        value
        for status in statuses if status.get("status") == "error"
        for value in (status.get("id"), status.get("name")) if value
    }
    enabled_statuses = [status for status in statuses if status.get("status") != "disabled"]
    all_failed = bool(enabled_statuses) and all(status.get("status") == "error" for status in enabled_statuses)

    if all_failed and previous.get("campaigns"):
        campaigns = [dict(item) for item in previous["campaigns"]]
        today_summary = dict(previous.get("todaySummary", {}))
        summary_history = list(previous.get("summaryHistory", []))
        updated_seen = seen_cache
        generated_at = previous.get("generatedAt") or now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()
    else:
        fresh_campaigns = dedupe_campaigns(collected)
        for item in fresh_campaigns:
            item["_observedThisRun"] = True
        campaigns = merge_foreign_previous(fresh_campaigns, previous, failed_sources, now)
        campaigns, detail_cache = enrich_foreign_campaigns(
            campaigns,
            sources,
            detail_cache,
            now,
            max_fetches=int(config.get("detailMaxFetches", 80)),
            max_workers=int(config.get("detailMaxWorkers", 4)),
        )
        campaign_pages = {
            source.get("id") for source in sources if source.get("kind") == "campaign_page"
        }
        campaigns = [
            item for item in campaigns
            if item.get("source", {}).get("id") in campaign_pages
            or not item.get("foreignHints", {}).get("excludedEmploymentTerms")
        ]
        today_summary, summary_history, updated_seen = update_daily_summary(
            campaigns,
            previous,
            seen_cache,
            now,
            int(config.get("summaryHistoryDays", 7)),
        )
        campaigns = apply_campaign_lifecycle(
            campaigns,
            now,
            int(config.get("retentionDays", 60)),
            int(config.get("unknownTtlDays", 45)),
        )
        campaigns = dedupe_campaigns(campaigns)[: int(config.get("maxTotal", 1000))]
        known_ids = {item["id"] for item in campaigns}
        today_summary = _filter_summary_items(today_summary, known_ids)
        summary_history = [_filter_summary_items(item, known_ids) for item in summary_history]
        generated_at = now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()

    public_campaigns = [_strip_internal(item) for item in campaigns]
    for status in statuses:
        if status.get("status") == "ok":
            status["count"] = sum(
                item.get("source", {}).get("id") == status.get("id") for item in public_campaigns
            )
    payload = {
        "schemaVersion": 1,
        "channel": "foreign-campus",
        "generatedAt": generated_at,
        "targetGraduateYear": target_year,
        "total": len(public_campaigns),
        "campaigns": public_campaigns,
        "todaySummary": today_summary,
        "summaryHistory": summary_history,
        "sourceStatus": statuses,
        "pendingReviewCount": sum(int(item.get("pendingReviewCount", 0)) for item in statuses),
    }
    health, gate_errors = _health_and_gate(payload, previous_health, now)
    health["registeredCompanyCount"] = len(companies)
    if gate_errors:
        raise RuntimeError("foreign quality gate rejected snapshot: " + "; ".join(gate_errors))
    if not dry_run:
        for path in (output_path, health_output_path, detail_cache_path, seen_cache_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        documents = (
            (detail_cache_path, detail_cache),
            (seen_cache_path, updated_seen),
            (health_output_path, health),
            (output_path, payload),
        )
        temporary = []
        for path, document in documents:
            candidate = path.with_suffix(path.suffix + ".tmp")
            candidate.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.append((candidate, path))
        for candidate, path in temporary:
            candidate.replace(path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect 2027 foreign-enterprise campus campaigns in China")
    parser.add_argument("--config", type=Path, default=Path("crawler/foreign_sources.json"))
    parser.add_argument("--companies", type=Path, default=Path("crawler/foreign_companies.json"))
    parser.add_argument("--output", type=Path, default=Path("data/foreign-campus.json"))
    parser.add_argument("--health-output", type=Path, default=Path("data/foreign-health.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = crawl_foreign(
            args.config,
            args.companies,
            args.output,
            datetime.now(timezone.utc),
            args.dry_run,
            args.health_output,
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(f"foreign collector failed: {error}", file=sys.stderr)
        return 1
    for status in payload["sourceStatus"]:
        suffix = f" ({status.get('error')})" if status.get("status") == "error" else ""
        print(f"[{status.get('status')}] {status.get('name')}: {status.get('count', 0)}{suffix}")
    print(
        f"total: {payload['total']} | today: {payload['todaySummary'].get('addedCount', 0)} "
        f"| generated: {payload['generatedAt']} | dry-run: {args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
