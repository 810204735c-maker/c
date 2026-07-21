"""Build and validate the public health snapshot for Job Radar."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
USER_AGENT = "Mozilla/5.0 (compatible; JobRadarCN/1.0; public-health-check)"
SUCCESS_STATUSES = {"ok", "empty"}


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


def _safe_error(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(
        r"(?i)(authorization|cookie|token|secret|password)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[redacted]",
        text,
    )
    return text[:180]


def validate_jobs(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["jobs snapshot must be an object"]
    errors: list[str] = []
    if not _parse_datetime(payload.get("generatedAt")):
        errors.append("jobs.generatedAt is required")
    if not isinstance(payload.get("jobs"), list):
        errors.append("jobs.jobs must be an array")
    if not isinstance(payload.get("sourceStatus"), list):
        errors.append("jobs.sourceStatus must be an array")
    total = payload.get("total")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        errors.append("jobs.total must be a non-negative integer")
    elif isinstance(payload.get("jobs"), list) and total != len(payload["jobs"]):
        errors.append("jobs.total does not match jobs array length")
    return errors


def validate_health(health: object) -> list[str]:
    if not isinstance(health, dict):
        return ["health snapshot must be an object"]
    errors: list[str] = []
    if not _parse_datetime(health.get("generatedAt")):
        errors.append("health.generatedAt is required")
    if not isinstance(health.get("currentTotal"), int):
        errors.append("health.currentTotal is required")
    success_rate = health.get("sourceSuccessRate")
    if not isinstance(success_rate, (int, float)) or isinstance(success_rate, bool):
        errors.append("health.sourceSuccessRate is required")
    elif not 0 <= success_rate <= 1:
        errors.append("health.sourceSuccessRate must be between 0 and 1")
    if not isinstance(health.get("sources"), list):
        errors.append("health.sources must be an array")
    return errors


def build_health(payload: dict, previous_health: dict, now: datetime) -> dict:
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
        elif state == "disabled":
            source["consecutiveFailures"] = 0
            source["reason"] = _safe_error(status.get("reason"))
        sources.append(source)

    enabled_sources = [source for source in sources if source["status"] != "disabled"]
    successful_sources = [source for source in enabled_sources if source["status"] in SUCCESS_STATUSES]
    jobs = payload.get("jobs", [])
    today = now.astimezone(SHANGHAI).date()
    seven_day_cutoff = today - timedelta(days=6)
    recent_count = 0
    for item in jobs:
        try:
            if date.fromisoformat(item.get("publishedAt", "")) >= seven_day_cutoff:
                recent_count += 1
        except (TypeError, ValueError):
            continue

    previous_total = previous_health.get("currentTotal")
    current_total = int(payload.get("total", len(jobs)))
    change_rate = None
    if isinstance(previous_total, int) and previous_total > 0:
        change_rate = (current_total - previous_total) / previous_total

    return {
        "generatedAt": generated_at,
        "currentTotal": current_total,
        "newLast7Days": recent_count,
        "deadlineCoverage": (sum(bool(item.get("deadline")) for item in jobs) / len(jobs)) if jobs else 0.0,
        "sourceSuccessRate": (len(successful_sources) / len(enabled_sources)) if enabled_sources else 0.0,
        "enabledSourceCount": len(enabled_sources),
        "disabledSourceCount": len(sources) - len(enabled_sources),
        "failedSourceCount": sum(source["status"] == "error" for source in enabled_sources),
        "previousTotal": previous_total if isinstance(previous_total, int) else None,
        "totalChangeRate": change_rate,
        "sources": sources,
        "publicSite": previous_health.get("publicSite", {"status": "pending"}),
    }


def quality_violations(
    payload: dict,
    previous: dict,
    health: dict,
    now: datetime | None = None,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    violations: list[dict] = []
    for message in validate_jobs(payload):
        violations.append({"code": "invalid_jobs", "severity": "critical", "message": message})
    for message in validate_health(health):
        violations.append({"code": "invalid_health", "severity": "critical", "message": message})

    current_total = health.get("currentTotal", 0)
    if current_total == 0:
        violations.append({"code": "empty_snapshot", "severity": "critical", "message": "公告总数为 0"})
    previous_total = previous.get("currentTotal")
    if isinstance(previous_total, int) and previous_total > 0 and current_total < previous_total * 0.6:
        violations.append({
            "code": "snapshot_drop",
            "severity": "critical",
            "message": f"公告总数从 {previous_total} 降至 {current_total}，降幅超过 40%",
        })

    enabled_count = int(health.get("enabledSourceCount", 0))
    success_rate = float(health.get("sourceSuccessRate", 0.0))
    if enabled_count and success_rate < 0.6:
        violations.append({
            "code": "low_source_success",
            "severity": "critical",
            "message": f"来源成功率 {success_rate:.1%} 低于 60%",
        })
    if enabled_count and health.get("failedSourceCount") == enabled_count:
        violations.append({"code": "all_sources_failed", "severity": "critical", "message": "全部启用来源均失败"})

    generated_at = _parse_datetime(payload.get("generatedAt"))
    if generated_at and now.astimezone(timezone.utc) - generated_at.astimezone(timezone.utc) > timedelta(hours=36):
        violations.append({"code": "stale_snapshot", "severity": "critical", "message": "数据生成时间超过 36 小时"})

    for source in health.get("sources", []):
        if source.get("status") == "error" and int(source.get("consecutiveFailures", 0)) >= 2:
            violations.append({
                "code": "source_failure_streak",
                "severity": "warning",
                "source": source.get("name"),
                "message": f"来源连续失败 {source.get('consecutiveFailures')} 次",
            })
    return violations


def check_public_site(
    base_url: str,
    timeout: int = 20,
    opener: Callable = urlopen,
) -> list[dict]:
    base_url = base_url.rstrip("/") + "/"
    targets = [
        ("homepage", base_url, "html"),
        ("jobs", urljoin(base_url, "data/jobs.json"), "jobs"),
        ("health", urljoin(base_url, "data/health.json"), "health"),
    ]
    checks: list[dict] = []
    for name, url, expected in targets:
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html, application/json"})
            with opener(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
            errors: list[str] = []
            if status != 200:
                errors.append(f"HTTP {status}")
            if expected == "html":
                if "html" not in content_type.lower() or b"<html" not in body[:2048].lower():
                    errors.append("response is not HTML")
            else:
                try:
                    document = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    errors.append("response is not valid JSON")
                else:
                    errors.extend(validate_jobs(document) if expected == "jobs" else validate_health(document))
            checks.append({"name": name, "url": url, "ok": not errors, "status": status, "errors": errors})
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            status = int(error.code) if isinstance(error, HTTPError) else None
            checks.append({"name": name, "url": url, "ok": False, "status": status, "errors": [_safe_error(error)]})
    return checks
