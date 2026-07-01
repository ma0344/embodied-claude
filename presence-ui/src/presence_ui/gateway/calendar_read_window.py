"""GAPI-2b — resolve calendar read prefetch window from utterance (C4 → e4b → policy fallback)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from social_core.date_resolution import (
    detect_ambiguous_temporal_phrases,
    detect_upcoming_weekday_confirmation,
    resolve_relative_date,
    sunday_start_week_bounds,
)

from presence_ui.gateway.calendar_read_search import resolve_calendar_search_query
from presence_ui.gateway.calendar_read_stage import run_calendar_read_window_extract
from presence_ui.gateway.gateway_turn_cache import (
    get_or_set_cached_prefetch_window,
    prefetch_window_cache_key,
)

logger = logging.getLogger(__name__)

ResolutionKind = Literal["deterministic", "e4b", "ambiguous", "fallback"]

_WEEKDAY_CHARS = "月火水木金土日"
_YESTERDAY_RE = re.compile(r"昨日|きのう|yesterday", re.I)
_DAY_BEFORE_YESTERDAY_RE = re.compile(r"一昨日|おととい", re.I)
_WEEK2_SPAN_RE = re.compile(
    rf"来々週|再来週(?!の?[{_WEEKDAY_CHARS}]|中|末)",
    re.I,
)
_THIS_WEEK_SPAN_RE = re.compile(
    rf"今週(?!の?[{_WEEKDAY_CHARS}]|中|末)",
    re.I,
)
_NEXT_WEEK_SPAN_RE = re.compile(
    rf"来週(?!の?[{_WEEKDAY_CHARS}]|中|末)",
    re.I,
)
_NEXT_MONTH_SPAN_RE = re.compile(r"来月(?!の?頭|初め)", re.I)
_THIS_MONTH_SPAN_RE = re.compile(r"今月(?!の?頭|初め)", re.I)
_NEXT_YEAR_SPAN_RE = re.compile(r"来年", re.I)
_THIS_YEAR_SPAN_RE = re.compile(r"今年", re.I)
_FROM_TODAY_RE = re.compile(r"今日以降|今後(?:の)?|これから|これより先", re.I)
_ROLLING_MONTH_RE = re.compile(r"今日から(?:一|１|1)か?月", re.I)
_ROLLING_WEEK_FROM_TOMORROW_RE = re.compile(r"明日から(?:一|１|1)週間", re.I)
_FUTURE_MONTH_RE = re.compile(r"今後(?:一|１|1)か?月", re.I)


@dataclass(frozen=True, slots=True)
class PrefetchWindow:
    start: datetime
    end: datetime
    resolution: ResolutionKind
    range_label: str
    reason: str = ""
    ambiguous_phrases: tuple[str, ...] = ()
    search_query: str | None = None


def _anchor_day(anchor_iso: str, tz: ZoneInfo) -> date:
    raw = anchor_iso.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).date()


def _day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    time_min = datetime.combine(day, time.min, tzinfo=tz)
    time_max = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return time_min, time_max


def _span_bounds(start_day: date, end_day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    time_min = datetime.combine(start_day, time.min, tzinfo=tz)
    time_max = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
    return time_min, time_max


def _month_bounds(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_day = date(year, month, 1)
    if month == 12:
        end_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_day = date(year, month + 1, 1) - timedelta(days=1)
    return _span_bounds(start_day, end_day, tz)


def _year_bounds(year: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    return _span_bounds(date(year, 1, 1), date(year, 12, 31), tz)


def _range_label(time_min: datetime, time_max: datetime) -> str:
    end_inclusive = time_max.date() - timedelta(days=1)
    start_s = time_min.date().isoformat()
    end_s = end_inclusive.isoformat()
    if start_s == end_s:
        return start_s
    return f"{start_s}..{end_s}"


def _inclusive_end_to_exclusive(end: datetime, tz: ZoneInfo) -> datetime:
    if end.time() >= time(23, 59, 0):
        return datetime.combine(end.date() + timedelta(days=1), time.min, tzinfo=tz)
    return end + timedelta(seconds=1)


def _window_from_bounds(
    *,
    time_min: datetime,
    time_max: datetime,
    resolution: ResolutionKind,
    reason: str = "",
) -> PrefetchWindow:
    return PrefetchWindow(
        start=time_min,
        end=time_max,
        resolution=resolution,
        range_label=_range_label(time_min, time_max),
        reason=reason,
    )


def _resolve_deterministic(
    utterance: str,
    *,
    anchor_iso: str,
    tz_name: str,
) -> PrefetchWindow | None:
    text = (utterance or "").strip()
    if not text:
        return None
    tz = ZoneInfo(tz_name)
    base = _anchor_day(anchor_iso, tz)

    ambiguous = detect_ambiguous_temporal_phrases(text)
    if ambiguous:
        return PrefetchWindow(
            start=datetime.combine(base, time.min, tzinfo=tz),
            end=datetime.combine(base, time.min, tzinfo=tz),
            resolution="ambiguous",
            range_label="ambiguous",
            ambiguous_phrases=tuple(ambiguous),
            reason="ambiguous temporal span",
        )

    confirm = detect_upcoming_weekday_confirmation(
        text, updated_at=anchor_iso, tz_name=tz_name
    )
    if confirm:
        return PrefetchWindow(
            start=datetime.combine(base, time.min, tzinfo=tz),
            end=datetime.combine(base, time.min, tzinfo=tz),
            resolution="ambiguous",
            range_label="ambiguous",
            ambiguous_phrases=tuple(confirm),
            reason="weekday confirmation needed",
        )

    if _DAY_BEFORE_YESTERDAY_RE.search(text):
        time_min, time_max = _day_bounds(base - timedelta(days=2), tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _YESTERDAY_RE.search(text):
        time_min, time_max = _day_bounds(base - timedelta(days=1), tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _NEXT_YEAR_SPAN_RE.search(text):
        time_min, time_max = _year_bounds(base.year + 1, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _THIS_YEAR_SPAN_RE.search(text):
        time_min, time_max = _year_bounds(base.year, tz)
        if _FROM_TODAY_RE.search(text):
            today_min, _ = _day_bounds(base, tz)
            if today_min > time_min:
                time_min = today_min
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _NEXT_MONTH_SPAN_RE.search(text):
        month = base.month + 1
        year = base.year
        if month > 12:
            month = 1
            year += 1
        time_min, time_max = _month_bounds(year, month, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _THIS_MONTH_SPAN_RE.search(text):
        time_min, time_max = _month_bounds(base.year, base.month, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _FUTURE_MONTH_RE.search(text):
        month = base.month + 1
        year = base.year
        if month > 12:
            month = 1
            year += 1
        time_min, time_max = _month_bounds(year, month, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _ROLLING_MONTH_RE.search(text):
        end_day = base + timedelta(days=29)
        time_min, time_max = _span_bounds(base, end_day, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    if _ROLLING_WEEK_FROM_TOMORROW_RE.search(text):
        start_day = base + timedelta(days=1)
        end_day = start_day + timedelta(days=6)
        time_min, time_max = _span_bounds(start_day, end_day, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    bounds = sunday_start_week_bounds(base)
    if _WEEK2_SPAN_RE.search(text):
        time_min, time_max = _span_bounds(bounds.week2_sun, bounds.week2_sat, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")
    if _NEXT_WEEK_SPAN_RE.search(text):
        time_min, time_max = _span_bounds(bounds.next_sun, bounds.next_sat, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")
    if _THIS_WEEK_SPAN_RE.search(text):
        time_min, time_max = _span_bounds(bounds.this_sun, bounds.this_sat, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    day = resolve_relative_date(topic=text, updated_at=anchor_iso, tz_name=tz_name)
    if day is not None:
        time_min, time_max = _day_bounds(day, tz)
        return _window_from_bounds(time_min=time_min, time_max=time_max, resolution="deterministic")

    return None


def _policy_fallback_window(
    *,
    day_range: list[str],
    anchor_iso: str,
    tz_name: str,
) -> PrefetchWindow:
    from presence_ui.gapi.calendar_client import prefetch_window_bounds

    time_min, time_max = prefetch_window_bounds(
        day_range=day_range,
        timezone=tz_name,
        as_of=_anchor_day(anchor_iso, ZoneInfo(tz_name)),
    )
    label = ",".join(day_range)
    return PrefetchWindow(
        start=time_min,
        end=time_max,
        resolution="fallback",
        range_label=label,
        reason="policy prefetch_day_range",
    )


def _attach_search_query(
    window: PrefetchWindow,
    utterance: str,
    *,
    e4b_search: str | None = None,
) -> PrefetchWindow:
    if window.resolution == "ambiguous":
        return window
    query = resolve_calendar_search_query(utterance, e4b_search=e4b_search)
    if not query or query == window.search_query:
        return window
    return PrefetchWindow(
        start=window.start,
        end=window.end,
        resolution=window.resolution,
        range_label=window.range_label,
        reason=window.reason,
        ambiguous_phrases=window.ambiguous_phrases,
        search_query=query,
    )


def resolve_prefetch_window(
    utterance: str,
    *,
    anchor_iso: str,
    tz_name: str,
    fallback_day_range: list[str] | None = None,
) -> PrefetchWindow:
    """Resolve list window for calendar read prefetch."""
    cache_key = prefetch_window_cache_key(
        utterance,
        anchor_iso=anchor_iso,
        tz_name=tz_name,
        fallback_day_range=fallback_day_range,
    )
    return get_or_set_cached_prefetch_window(
        cache_key,
        lambda: _resolve_prefetch_window_uncached(
            utterance,
            anchor_iso=anchor_iso,
            tz_name=tz_name,
            fallback_day_range=fallback_day_range,
        ),
    )


def _resolve_prefetch_window_uncached(
    utterance: str,
    *,
    anchor_iso: str,
    tz_name: str,
    fallback_day_range: list[str] | None = None,
) -> PrefetchWindow:
    """Resolve list window for calendar read prefetch (no turn cache)."""
    deterministic = _resolve_deterministic(
        utterance, anchor_iso=anchor_iso, tz_name=tz_name
    )
    if deterministic is not None:
        if deterministic.resolution == "ambiguous":
            return deterministic
        return _attach_search_query(deterministic, utterance)

    tz = ZoneInfo(tz_name)
    anchor_dt = datetime.fromisoformat(
        anchor_iso.replace("Z", "+00:00") if anchor_iso.endswith("Z") else anchor_iso
    )
    if anchor_dt.tzinfo is None:
        anchor_dt = anchor_dt.replace(tzinfo=tz)
    else:
        anchor_dt = anchor_dt.astimezone(tz)

    extract = run_calendar_read_window_extract(
        utterance=utterance,
        as_of=anchor_dt,
        tz_name=tz_name,
    )
    if extract is not None:
        time_max = _inclusive_end_to_exclusive(extract.end, tz)
        time_min = extract.start
        if time_max <= time_min:
            time_max = time_min + timedelta(days=1)
        return _attach_search_query(
            _window_from_bounds(
                time_min=time_min,
                time_max=time_max,
                resolution="e4b",
                reason=extract.reason,
            ),
            utterance,
            e4b_search=extract.search_query,
        )

    day_range = fallback_day_range or ["today", "tomorrow"]
    logger.debug(
        "GAPI-2b: no utterance window for %r — fallback %s",
        utterance[:80],
        day_range,
    )
    return _attach_search_query(
        _policy_fallback_window(
            day_range=day_range,
            anchor_iso=anchor_iso,
            tz_name=tz_name,
        ),
        utterance,
    )
