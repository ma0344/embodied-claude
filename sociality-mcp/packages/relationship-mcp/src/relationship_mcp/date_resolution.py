"""Resolve relative calendar days in open-loop topics (明日, 今日, …)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_RELATIVE_MARKERS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"明後日|あさって|day after tomorrow", re.I), 2),
    (re.compile(r"明日|tomorrow", re.I), 1),
    (re.compile(r"今日|きょう|today", re.I), 0),
]

DEFAULT_TIMEZONE = "Asia/Tokyo"


def _parse_updated_day(updated_at: str, tz: ZoneInfo) -> date:
    raw = updated_at.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).date()


def resolve_relative_date(*, topic: str, updated_at: str, tz_name: str) -> date | None:
    """Return the calendar day the topic refers to, or None if no relative marker."""
    tz = ZoneInfo(tz_name)
    base = _parse_updated_day(updated_at, tz)
    for pattern, offset_days in _RELATIVE_MARKERS:
        if pattern.search(topic):
            return base + timedelta(days=offset_days)
    return None


def is_stale(
    *,
    topic: str,
    updated_at: str,
    tz_name: str,
    as_of: date,
    include_today: bool = False,
) -> date | None:
    """If stale, return the resolved date; else None."""
    resolved = resolve_relative_date(topic=topic, updated_at=updated_at, tz_name=tz_name)
    if resolved is None:
        return None
    if resolved < as_of or (include_today and resolved == as_of):
        return resolved
    return None


def as_of_date(*, as_of_ts: str, tz_name: str) -> date:
    """Calendar day for an ISO timestamp in the given timezone."""
    raw = as_of_ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name)).date()
