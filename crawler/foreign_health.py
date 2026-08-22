"""Build and validate health snapshots for the foreign-campus channel."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
from typing import Iterable
from urllib.parse import urlparse

try:
    from crawler.timezone import shanghai_timezone
except ModuleNotFoundError:  # Support direct module execution.
    from timezone import shanghai_timezone


SHANGHAI = shanghai_timezone()
SUCCESS_STATUSES = {"ok", "empty"}
SOURCE_TIERS = {
    "official_verified",
    "official_job_feed",
    "secondary_verified",
    "third_party_only",
}
CAMPAIGN_TYPES = {
    "campus_recruitment",
    "graduate_program",
    "management_trainee",
    "supplemental",
}
CAMPAIGN_STATUSES = {"open", "deadline_unknown", "expired", "stale"}
SEASONS = {"spring", "autumn", "supplemental", "annual"}
NON_MAINLAND_LOCATIONS = {"香港", "澳门", "台湾", "Hong Kong", "Macau", "Taiwan"}


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


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _safe_error(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(
        r"(?i)(authorization|cookie|token|secret|password)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[redacted]",
        text,
    )
    return text[:180]


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _validate_string_list(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{field} must be an array of non-empty strings")


def _validate_summary(
    summary: object,
    field: str,
    known_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(summary, dict):
        errors.append(f"{field} must be an object")
        return
    if not _parse_date(summary.get("date")):
        errors.append(f"{field}.date must be YYYY-MM-DD")
    if not isinstance(summary.get("bootstrap"), bool):
        errors.append(f"{field}.bootstrap must be boolean")
    for count_field in ("addedCount", "baselineCount"):
        count = summary.get(count_field)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(f"{field}.{count_field} must be a non-negative integer")
    items = summary.get("items")
    if not isinstance(items, list):
        errors.append(f"{field}.items must be an array")
        return
    item_ids: list[str] = []
    for index, item in enumerate(items):
        prefix = f"{field}.items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        identifier = item.get("id")
        if identifier not in known_ids:
            errors.append(f"{prefix} references an unknown campaign id")
        item_ids.append(str(identifier))
        if not str(item.get("company", "")).strip():
            errors.append(f"{prefix}.company is required")
        if not str(item.get("title", "")).strip():
            errors.append(f"{prefix}.title is required")
        if not _is_http_url(item.get("url")):
            errors.append(f"{prefix}.url must be HTTP(S)")
        if not isinstance(item.get("official"), bool):
            errors.append(f"{prefix}.official must be boolean")
    if len(item_ids) != len(set(item_ids)):
        errors.append(f"{field}.items contains duplicate ids")
    if isinstance(summary.get("addedCount"), int) and summary["addedCount"] != len(items):
        errors.append(f"{field}.addedCount does not match items")


def validate_foreign_snapshot(payload: object) -> list[str]:
    """Return public-schema errors for a foreign-campus snapshot."""
    if not isinstance(payload, dict):
        return ["foreign snapshot must be an object"]
    errors: list[str] = []
    if payload.get("schemaVersion") != 1:
        errors.append("foreign.schemaVersion must be 1")
    if payload.get("channel") != "foreign-campus":
        errors.append("foreign.channel must be foreign-campus")
    if not _parse_datetime(payload.get("generatedAt")):
        errors.append("foreign.generatedAt is required")
    if payload.get("targetGraduateYear") != "2027":
        errors.append("foreign.targetGraduateYear must be 2027")
    campaigns = payload.get("campaigns")
    if not isinstance(campaigns, list):
        errors.append("foreign.campaigns must be an array")
        campaigns = []
    total = payload.get("total")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        errors.append("foreign.total must be a non-negative integer")
    elif total != len(campaigns):
        errors.append("foreign.total does not match campaigns array length")
    if not isinstance(payload.get("sourceStatus"), list):
        errors.append("foreign.sourceStatus must be an array")

    identifiers: list[str] = []
    campaign_keys: list[str] = []
    for index, item in enumerate(campaigns):
        prefix = f"foreign.campaigns[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        identifier = item.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"foreign_[0-9a-f]{20}", identifier):
            errors.append(f"{prefix}.id is invalid")
        identifiers.append(str(identifier))
        campaign_key = item.get("campaignKey")
        if not isinstance(campaign_key, str) or campaign_key.count("|") != 4:
            errors.append(f"{prefix}.campaignKey is invalid")
        campaign_keys.append(str(campaign_key))
        if item.get("channel") != "foreign":
            errors.append(f"{prefix}.channel must be foreign")
        company = item.get("company")
        if not isinstance(company, dict) or not str(company.get("id", "")).strip() or not str(company.get("name", "")).strip():
            errors.append(f"{prefix}.company is required")
        if not str(item.get("title", "")).strip():
            errors.append(f"{prefix}.title is required")
        if item.get("titleLanguage") not in {"zh", "en"}:
            errors.append(f"{prefix}.titleLanguage must be zh or en")
        if not _is_http_url(item.get("url")):
            errors.append(f"{prefix}.url must be HTTP(S)")
        source = item.get("source")
        if not isinstance(source, dict) or source.get("tier") not in SOURCE_TIERS:
            errors.append(f"{prefix}.source tier is invalid")
        if not isinstance(item.get("official"), bool):
            errors.append(f"{prefix}.official must be boolean")
        elif isinstance(source, dict):
            expected_official = source.get("tier") in {"official_verified", "official_job_feed"}
            if item["official"] != expected_official:
                errors.append(f"{prefix}.official conflicts with source tier")
        if item.get("graduateYears") != ["2027"]:
            errors.append(f"{prefix} must target 2027")
        if item.get("employmentType") != "full_time":
            errors.append(f"{prefix}.employmentType must be full_time")
        if item.get("campaignType") not in CAMPAIGN_TYPES:
            errors.append(f"{prefix}.campaignType is invalid")
        if item.get("season") not in SEASONS:
            errors.append(f"{prefix}.season is invalid")
        if item.get("status") not in CAMPAIGN_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        for field in (
            "cities",
            "jobFunctions",
            "educationLevels",
            "industryTags",
            "englishRequirements",
            "alternateSources",
        ):
            if field == "alternateSources":
                if not isinstance(item.get(field), list):
                    errors.append(f"{prefix}.{field} must be an array")
            else:
                _validate_string_list(item.get(field), f"{prefix}.{field}", errors)
        if any(location in NON_MAINLAND_LOCATIONS for location in item.get("cities", [])):
            errors.append(f"{prefix}.cities contains a non-mainland location")
        if not _parse_date(item.get("publishedAt")):
            errors.append(f"{prefix}.publishedAt must be YYYY-MM-DD")
        if not _parse_datetime(item.get("firstSeenAt")):
            errors.append(f"{prefix}.firstSeenAt is required")
        if not _parse_datetime(item.get("lastSeenAt")):
            errors.append(f"{prefix}.lastSeenAt is required")
        deadline = item.get("deadline")
        if deadline is not None and not _parse_date(deadline):
            errors.append(f"{prefix}.deadline must be null or YYYY-MM-DD")

    if len(identifiers) != len(set(identifiers)):
        errors.append("foreign campaign ids contain duplicates")
    if len(campaign_keys) != len(set(campaign_keys)):
        errors.append("foreign campaign keys contain duplicates")
    known_ids = set(identifiers)
    _validate_summary(payload.get("todaySummary"), "foreign.todaySummary", known_ids, errors)
    history = payload.get("summaryHistory")
    if not isinstance(history, list):
        errors.append("foreign.summaryHistory must be an array")
    else:
        if len(history) > 7:
            errors.append("foreign.summaryHistory cannot exceed 7 days")
        dates: list[str] = []
        for index, summary in enumerate(history):
            _validate_summary(summary, f"foreign.summaryHistory[{index}]", known_ids, errors)
            if isinstance(summary, dict):
                dates.append(str(summary.get("date", "")))
        if len(dates) != len(set(dates)):
            errors.append("foreign.summaryHistory contains duplicate dates")
        if dates != sorted(dates, reverse=True):
            errors.append("foreign.summaryHistory must be newest first")
    return errors


def validate_foreign_health(health: object) -> list[str]:
    if not isinstance(health, dict):
        return ["foreign health must be an object"]
    errors: list[str] = []
    if not _parse_datetime(health.get("generatedAt")):
        errors.append("foreign health.generatedAt is required")
    if not isinstance(health.get("currentTotal"), int):
        errors.append("foreign health.currentTotal is required")
    success_rate = health.get("sourceSuccessRate")
    if not isinstance(success_rate, (int, float)) or isinstance(success_rate, bool):
        errors.append("foreign health.sourceSuccessRate is required")
    elif not 0 <= success_rate <= 1:
        errors.append("foreign health.sourceSuccessRate must be between 0 and 1")
    official_ratio = health.get("officialSourceRatio")
    if not isinstance(official_ratio, (int, float)) or isinstance(official_ratio, bool):
        errors.append("foreign health.officialSourceRatio is required")
    elif not 0 <= official_ratio <= 1:
        errors.append("foreign health.officialSourceRatio must be between 0 and 1")
    if not isinstance(health.get("sources"), list):
        errors.append("foreign health.sources must be an array")
    return errors


def build_foreign_health(payload: dict, previous_health: dict, now: datetime) -> dict:
    generated_at = payload.get("generatedAt") or now.astimezone(SHANGHAI).replace(microsecond=0).isoformat()
    previous_sources = {
        item.get("name"): item
        for item in previous_health.get("sources", [])
        if isinstance(item, dict) and item.get("name")
    }
    sources: list[dict] = []
    for status in payload.get("sourceStatus", []):
        name = status.get("name", "unknown")
        state = status.get("status", "error")
        previous = previous_sources.get(name, {})
        source = {
            "name": name,
            "status": state,
            "count": int(status.get("count", 0)),
            "lastSuccessAt": previous.get("lastSuccessAt"),
            "lastFailureAt": previous.get("lastFailureAt"),
            "consecutiveFailures": int(previous.get("consecutiveFailures", 0)),
        }
        if state in SUCCESS_STATUSES:
            source["lastSuccessAt"] = generated_at
            source["consecutiveFailures"] = 0
        elif state == "error":
            source["lastFailureAt"] = generated_at
            source["consecutiveFailures"] += 1
            source["error"] = _safe_error(status.get("error"))
        elif state in {"disabled", "manual"}:
            source["consecutiveFailures"] = 0
            source["reason"] = _safe_error(status.get("reason") or status.get("disabledReason"))
        sources.append(source)

    enabled = [source for source in sources if source["status"] not in {"disabled", "manual"}]
    successful = [source for source in enabled if source["status"] in SUCCESS_STATUSES]
    campaigns = payload.get("campaigns", [])
    current_total = len(campaigns)
    previous_total = previous_health.get("currentTotal")
    change_rate = None
    if isinstance(previous_total, int) and previous_total > 0:
        change_rate = (current_total - previous_total) / previous_total
    official_count = sum(bool(item.get("official")) for item in campaigns)
    last_successful = generated_at if successful else previous_health.get("lastSuccessfulAt")
    return {
        "generatedAt": generated_at,
        "lastSuccessfulAt": last_successful,
        "currentTotal": current_total,
        "activeTotal": sum(item.get("status") in {"open", "deadline_unknown"} for item in campaigns),
        "expiredRetainedTotal": sum(item.get("status") == "expired" for item in campaigns),
        "staleTotal": sum(item.get("status") == "stale" for item in campaigns),
        "newToday": int(payload.get("todaySummary", {}).get("addedCount", 0)),
        "officialSourceRatio": (official_count / current_total) if current_total else 0.0,
        "registeredCompanyCount": len({
            item.get("company", {}).get("id")
            for item in campaigns
            if item.get("company", {}).get("id")
        }),
        "pendingReviewCount": int(payload.get("pendingReviewCount", 0)),
        "sourceSuccessRate": (len(successful) / len(enabled)) if enabled else 0.0,
        "enabledSourceCount": len(enabled),
        "disabledSourceCount": len(sources) - len(enabled),
        "failedSourceCount": sum(source["status"] == "error" for source in enabled),
        "previousTotal": previous_total if isinstance(previous_total, int) else None,
        "totalChangeRate": change_rate,
        "sources": sources,
    }


def foreign_quality_violations(
    payload: dict,
    previous_health: dict,
    health: dict,
    now: datetime | None = None,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    violations: list[dict] = []
    for message in validate_foreign_snapshot(payload):
        violations.append({"code": "invalid_foreign_snapshot", "severity": "critical", "message": message})
    for message in validate_foreign_health(health):
        violations.append({"code": "invalid_foreign_health", "severity": "critical", "message": message})
    current_total = int(health.get("currentTotal", 0))
    if current_total == 0:
        violations.append({"code": "empty_foreign_snapshot", "severity": "critical", "message": "外企校招活动总数为 0"})
    previous_total = previous_health.get("currentTotal")
    if isinstance(previous_total, int) and previous_total > 0 and current_total < previous_total * 0.6:
        violations.append({
            "code": "foreign_snapshot_drop",
            "severity": "critical",
            "message": f"外企校招活动从 {previous_total} 降至 {current_total}，降幅超过 40%",
        })
    enabled_count = int(health.get("enabledSourceCount", 0))
    failed_count = int(health.get("failedSourceCount", 0))
    success_rate = float(health.get("sourceSuccessRate", 0.0))
    all_failed = enabled_count > 0 and failed_count == enabled_count
    last_successful = _parse_datetime(health.get("lastSuccessfulAt"))
    recent_fallback = bool(
        all_failed
        and last_successful
        and now.astimezone(timezone.utc) - last_successful.astimezone(timezone.utc) <= timedelta(days=7)
    )
    if all_failed:
        violations.append({
            "code": "all_foreign_sources_failed",
            "severity": "warning" if recent_fallback else "critical",
            "message": "全部外企来源失败；保留最近稳定快照" if recent_fallback else "全部外企来源失败且稳定快照超过 7 天",
        })
    elif enabled_count and success_rate < 0.6:
        violations.append({
            "code": "low_foreign_source_success",
            "severity": "critical",
            "message": f"外企来源成功率 {success_rate:.1%} 低于 60%",
        })
    if float(health.get("officialSourceRatio", 0.0)) < 0.5 and current_total:
        violations.append({
            "code": "low_official_ratio",
            "severity": "warning",
            "message": "外企校招官网来源比例低于 50%",
        })
    generated_at = _parse_datetime(payload.get("generatedAt"))
    if (
        generated_at
        and now.astimezone(timezone.utc) - generated_at.astimezone(timezone.utc) > timedelta(hours=36)
        and not recent_fallback
    ):
        violations.append({
            "code": "stale_foreign_snapshot",
            "severity": "critical",
            "message": "外企校招快照生成时间超过 36 小时",
        })
    for source in health.get("sources", []):
        if source.get("status") == "error" and int(source.get("consecutiveFailures", 0)) >= 2:
            violations.append({
                "code": "foreign_source_failure_streak",
                "severity": "warning",
                "source": source.get("name"),
                "message": f"外企来源连续失败 {source.get('consecutiveFailures')} 次",
            })
    return violations


def critical_messages(violations: Iterable[dict]) -> list[str]:
    return [str(item.get("message", item.get("code"))) for item in violations if item.get("severity") == "critical"]


# Keep the generic name available to the crawler entry point while retaining a
# channel-specific public name for callers that import both health modules.
quality_violations = foreign_quality_violations
