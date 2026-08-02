"""Timezone helpers that keep China-local timestamps portable on Windows."""

from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def shanghai_timezone(loader: Callable[[str], tzinfo] = ZoneInfo) -> tzinfo:
    """Return Asia/Shanghai, including when the runtime has no IANA tzdata.

    China has a stable UTC+08:00 civil offset, so the fixed-offset fallback
    preserves the collector's timestamp semantics without adding a dependency.
    """

    try:
        return loader("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), "Asia/Shanghai")
