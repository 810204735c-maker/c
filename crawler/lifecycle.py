"""Conservative registration-window extraction for recruitment notices."""

from __future__ import annotations

from datetime import date, datetime
import html
import re


_DATE_PATTERN = re.compile(
    r"(?:(?P<year>20\d{2})\s*[年./\-]\s*)?"
    r"(?P<month>\d{1,2})\s*[月./\-]\s*"
    r"(?P<day>\d{1,2})\s*日?"
)
_REGISTRATION_MARKERS = ("报名", "报考")
_EXTENSION_MARKERS = ("延长至", "延期至", "顺延至")
_CLAUSE_SEPARATOR = re.compile(r"[，,。；;\n\r]+")


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _dates_in_order(clause: str, now: datetime) -> list[date]:
    resolved: list[date] = []
    previous: date | None = None
    for match in _DATE_PATTERN.finditer(clause):
        explicit_year = match.group("year")
        month = int(match.group("month"))
        day = int(match.group("day"))
        year = int(explicit_year) if explicit_year else (previous.year if previous else now.year)
        candidate = _safe_date(year, month, day)
        if candidate is None:
            continue
        if not explicit_year and previous and candidate < previous:
            candidate = _safe_date(year + 1, month, day)
            if candidate is None:
                continue
        resolved.append(candidate)
        previous = candidate
    return resolved


def _registration_clauses(text: str) -> list[str]:
    return [
        clause.strip()
        for clause in _CLAUSE_SEPARATOR.split(_clean_text(text))
        if clause.strip() and any(marker in clause for marker in _REGISTRATION_MARKERS)
    ]


def extract_registration_window(text: str, now: datetime) -> dict:
    """Return an evidence-backed registration window.

    Dates are considered only inside clauses that explicitly mention
    registration. An explicit extension clause may update the end date, while
    later exam, admission-ticket, interview, or document-submission dates are
    ignored when they appear in separate clauses.
    """

    clauses = _registration_clauses(text)
    registration_start: date | None = None
    registration_end: date | None = None
    evidence = ""
    extension_end: date | None = None
    extension_evidence = ""

    for clause in clauses:
        dates = _dates_in_order(clause, now)
        if not dates:
            continue
        if any(marker in clause for marker in _EXTENSION_MARKERS):
            extension_end = dates[-1]
            extension_evidence = clause
            continue
        if len(dates) >= 2:
            registration_start = registration_start or dates[0]
            registration_end = dates[-1]
        elif any(marker in clause for marker in ("截止", "截至")):
            registration_end = dates[0]
        else:
            registration_start = registration_start or dates[0]
            registration_end = registration_end or dates[0]
        evidence = clause

    if extension_end is not None:
        registration_end = extension_end
        evidence = extension_evidence

    return {
        "registrationStart": registration_start.isoformat() if registration_start else None,
        "registrationEnd": registration_end.isoformat() if registration_end else None,
        "deadlineConfidence": "high" if registration_end else "unknown",
        "deadlineEvidence": evidence[:120] if registration_end else "",
    }
