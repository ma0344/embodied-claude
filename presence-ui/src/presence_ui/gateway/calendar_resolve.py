"""Resolve calendar phrase fields to concrete datetimes (gateway, not LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from social_core.date_resolution import format_jp_date, resolve_relative_date

_TIME_POINT_RE = re.compile(
    r"(?P<h>(?<!\d)\d{1,2})\s*時(?:\s*(?P<m>\d{1,2})分)?",
    re.I,
)
_COLON_TIME_POINT_RE = re.compile(
    r"(?P<h>\d{1,2})\s*[:：]\s*(?P<m>\d{2})",
    re.I,
)
_COLON_TIME_RANGE_RE = re.compile(
    r"(?P<sh>\d{1,2})\s*[:：]\s*(?P<sm>\d{2})"
    r"\s*[～〜~\-－―]\s*"
    r"(?P<eh>\d{1,2})\s*[:：]\s*(?P<em>\d{2})",
    re.I,
)
_TIME_RANGE_INLINE_RE = re.compile(
    r"(?P<sh>\d{1,2})\s*時(?:\s*(?P<sm>\d{1,2})分?)?"
    r"\s*[～〜~\-－―]\s*"
    r"(?P<eh>\d{1,2})\s*時(?:\s*(?P<em>\d{1,2})分?)?",
    re.I,
)


def _normalize_time_phrase(phrase: str) -> str:
    line = (
        phrase.replace("：", ":")
        .replace("－", "-")
        .replace("―", "-")
    )
    # "9月 8日" → "9月8日" (month-day spacing breaks explicit date parse)
    return re.sub(r"(\d{1,2})月\s+(\d{1,2})日", r"\1月\2日", line)


@dataclass(frozen=True, slots=True)
class ResolvedRange:
    start: datetime
    end: datetime
    day: date


def _minute(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _resolve_day(*, phrase: str, anchor_iso: str, tz_name: str) -> date | None:
    resolved = resolve_relative_date(topic=phrase, updated_at=anchor_iso, tz_name=tz_name)
    if resolved is not None:
        return resolved
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if re.search(r"明後日|あさって", phrase, re.I):
        return today + timedelta(days=2)
    if re.search(r"明日|あした", phrase, re.I):
        return today + timedelta(days=1)
    if re.search(r"今日|きょう", phrase, re.I):
        return today
    return None


def _time_from_phrase(phrase: str, *, day: date, tz: ZoneInfo) -> datetime | None:
    line = _normalize_time_phrase((phrase or "").strip())
    if not line:
        return None
    colon_range = _COLON_TIME_RANGE_RE.search(line)
    if colon_range:
        return datetime.combine(
            day,
            time(
                hour=int(colon_range.group("sh")),
                minute=int(colon_range.group("sm")),
            ),
            tzinfo=tz,
        )
    colon_point = _COLON_TIME_POINT_RE.search(line)
    if colon_point:
        return datetime.combine(
            day,
            time(hour=int(colon_point.group("h")), minute=int(colon_point.group("m"))),
            tzinfo=tz,
        )
    range_match = _TIME_RANGE_INLINE_RE.search(line)
    if range_match:
        start = datetime.combine(
            day,
            time(
                hour=int(range_match.group("sh")),
                minute=_minute(range_match.group("sm")),
            ),
            tzinfo=tz,
        )
        return start
    point = _TIME_POINT_RE.search(line)
    if not point:
        return None
    return datetime.combine(
        day,
        time(hour=int(point.group("h")), minute=_minute(point.group("m"))),
        tzinfo=tz,
    )


def _end_from_phrase(phrase: str, *, day: date, tz: ZoneInfo, start: datetime) -> datetime | None:
    line = _normalize_time_phrase((phrase or "").strip())
    if not line:
        return None
    colon_range = _COLON_TIME_RANGE_RE.search(line)
    if colon_range:
        end = datetime.combine(
            day,
            time(
                hour=int(colon_range.group("eh")),
                minute=int(colon_range.group("em")),
            ),
            tzinfo=tz,
        )
        if end <= start:
            end = start + timedelta(hours=1)
        return end
    range_match = _TIME_RANGE_INLINE_RE.search(line)
    if range_match:
        end = datetime.combine(
            day,
            time(
                hour=int(range_match.group("eh")),
                minute=_minute(range_match.group("em")),
            ),
            tzinfo=tz,
        )
        if end <= start:
            end = start + timedelta(hours=1)
        return end
    colon_point = _COLON_TIME_POINT_RE.search(line)
    if colon_point:
        end = datetime.combine(
            day,
            time(hour=int(colon_point.group("h")), minute=int(colon_point.group("m"))),
            tzinfo=tz,
        )
        if end <= start:
            end = start + timedelta(hours=1)
        return end
    point = _TIME_POINT_RE.search(line)
    if point:
        end = datetime.combine(
            day,
            time(hour=int(point.group("h")), minute=_minute(point.group("m"))),
            tzinfo=tz,
        )
        if end <= start:
            end = start + timedelta(hours=1)
        return end
    return start + timedelta(hours=1)


def resolve_start_end_phrases(
    *,
    start_phrase: str | None,
    end_phrase: str | None,
    anchor_iso: str,
    tz_name: str,
) -> ResolvedRange | None:
    start_norm = _normalize_time_phrase(start_phrase or "")
    end_norm = _normalize_time_phrase(end_phrase or "")
    if not start_norm.strip():
        return None
    tz = ZoneInfo(tz_name)
    combined = f"{start_norm} {end_norm}".strip()
    day = _resolve_day(phrase=combined, anchor_iso=anchor_iso, tz_name=tz_name)
    if day is None:
        day = _resolve_day(phrase=start_norm, anchor_iso=anchor_iso, tz_name=tz_name)
    if day is None:
        return None
    start = _time_from_phrase(start_norm or combined, day=day, tz=tz)
    if start is None:
        start = _time_from_phrase(combined, day=day, tz=tz)
    if start is None:
        return None
    end = _end_from_phrase(end_norm or start_norm or combined, day=day, tz=tz, start=start)
    if end is None:
        end = start + timedelta(hours=1)
    return ResolvedRange(start=start, end=end, day=day)


def format_confirm_summary_ja(
    *,
    action: str,
    topic: str | None,
    start: datetime,
    end: datetime,
    match_label: str = "",
) -> str:
    day_label = format_jp_date(start.date())
    start_t = start.strftime("%H:%M")
    end_t = end.strftime("%H:%M")
    title = (topic or "").strip() or "（無題）"
    if action == "update" and match_label.strip():
        return f"{match_label.strip()} を {day_label} {start_t}〜{end_t} に変更"
    return f"{day_label} {start_t}〜{end_t}「{title}」"
