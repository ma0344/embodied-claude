"""Resolve and anchor relative calendar days (明日, 来週の火曜, …) to concrete dates."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_RELATIVE_MARKERS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"明後日|あさって|day after tomorrow", re.I), 2),
    (re.compile(r"明日|tomorrow", re.I), 1),
    (re.compile(r"今日|きょう|today", re.I), 0),
]

_WEEKDAY_CHARS = "月火水木金土日"
_WEEK_OFFSET_LABELS = ("今週", "来週", "再来週", "来々週")

# Longer week offsets first (再来週 before 来週).
_WEEKDAY_IN_WEEK_RE = re.compile(
    rf"(?P<wo>来々週|再来週|来週|今週)の?(?P<wd>[{_WEEKDAY_CHARS}])(?:曜日?)?"
)
_ONE_WEEK_LATER_RE = re.compile(r"一週間後")
_N_DAYS_LATER_RE = re.compile(r"(?P<n>\d{1,3})日後")
_NEXT_MONTH_HEAD_RE = re.compile(r"来月の?頭|来月初め")
_MONTH_AFTER_NEXT_HEAD_RE = re.compile(r"再来月の?頭|再来月初め")
_THIS_WEEKEND_RE = re.compile(r"今週末|この週末")
_EXPLICIT_MONTH_DAY_RE = re.compile(r"(?<![\d年])(?P<m>\d{1,2})月(?P<d>\d{1,2})日")
_UPCOMING_WEEKDAY_RE = re.compile(
    rf"(?P<prefix>次の|今度の)(?P<wd>[{_WEEKDAY_CHARS}])(?:曜日?)?"
)
_BARE_WEEKDAY_RE = re.compile(
    rf"(?<!来週の)(?<!今週の)(?<!再来週の)(?<!来々週の)(?P<wd>[{_WEEKDAY_CHARS}])(?:曜日)"
)
_AMBIGUOUS_SPAN_RE = re.compile(
    r"来週中|今週中|再来週中|来々週中|来月中|今月中|来週末"
)

DEFAULT_TIMEZONE = "Asia/Tokyo"


@dataclass(frozen=True, slots=True)
class TemporalAnchorResult:
    """Outcome of temporal anchoring — concrete date, or confirmation needed."""

    text: str
    resolved_date: date | None
    needs_date_confirmation: bool = False
    ambiguous_phrases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SundayWeekBounds:
    """Sun–Sat week blocks (日曜始まり)."""

    this_sun: date
    this_sat: date
    next_sun: date
    next_sat: date
    week2_sun: date
    week2_sat: date


def _parse_updated_day(updated_at: str, tz: ZoneInfo) -> date:
    raw = updated_at.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).date()


def format_jp_date(day: date) -> str:
    """Concrete Japanese calendar label for prompts and stored topics."""
    return f"{day.year}年{day.month}月{day.day}日"


def sunday_start_week_bounds(anchor_day: date) -> SundayWeekBounds:
    """今週/来週/再来週 as Sun–Sat blocks containing *anchor_day*."""
    days_since_sunday = (anchor_day.weekday() + 1) % 7
    this_sun = anchor_day - timedelta(days=days_since_sunday)
    this_sat = this_sun + timedelta(days=6)
    next_sun = this_sun + timedelta(days=7)
    next_sat = next_sun + timedelta(days=6)
    week2_sun = this_sun + timedelta(days=14)
    week2_sat = week2_sun + timedelta(days=6)
    return SundayWeekBounds(
        this_sun=this_sun,
        this_sat=this_sat,
        next_sun=next_sun,
        next_sat=next_sat,
        week2_sun=week2_sun,
        week2_sat=week2_sat,
    )


def _week_offset_value(label: str) -> int:
    return {"今週": 0, "来週": 1, "再来週": 2, "来々週": 3}[label]


def _weekday_char_to_index(char: str) -> int:
    return _WEEKDAY_CHARS.index(char)


def weekday_in_week(*, anchor_day: date, week_offset: int, weekday: int) -> date:
    """Resolve a weekday inside 今週/来週/再来週 (weekday: Mon=0 .. Sun=6)."""
    bounds = sunday_start_week_bounds(anchor_day)
    week_sun = bounds.this_sun + timedelta(days=7 * week_offset)
    day_offset = (weekday + 1) % 7
    return week_sun + timedelta(days=day_offset)


def resolve_this_weekend(anchor_day: date) -> date:
    """Next Sat/Sun in 今週 on or after anchor (日曜始まり週)."""
    bounds = sunday_start_week_bounds(anchor_day)
    for offset in range(0, 7):
        day = bounds.this_sun + timedelta(days=offset)
        if day < anchor_day:
            continue
        if day.weekday() >= 5:  # Sat/Sun
            return day
    return bounds.this_sat


def resolve_next_month_head(anchor_day: date, *, months_ahead: int = 1) -> date:
    year = anchor_day.year
    month = anchor_day.month + months_ahead
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def resolve_explicit_month_day(
    *, month: int, day: int, anchor_day: date
) -> date | None:
    year = anchor_day.year
    if month < anchor_day.month or (month == anchor_day.month and day < anchor_day.day):
        year += 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def resolve_upcoming_weekday(anchor_day: date, weekday: int) -> tuple[date | None, bool]:
    """Next occurrence of *weekday* after *anchor_day* (Mon=0..Sun=6).

    Returns ``(None, True)`` when *anchor_day* is already that weekday — caller
    should ask まー instead of guessing.
    """
    delta = (weekday - anchor_day.weekday()) % 7
    if delta == 0:
        return None, True
    return anchor_day + timedelta(days=delta), False


def detect_ambiguous_temporal_phrases(text: str) -> list[str]:
    """Vague spans that must not be auto-anchored (来週中, 来月中, …)."""
    return [match.group(0) for match in _AMBIGUOUS_SPAN_RE.finditer(str(text or ""))]


def detect_upcoming_weekday_confirmation(
    text: str,
    *,
    updated_at: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> list[str]:
    """Phrases like 今度の日曜 on a Sunday — same weekday as anchor, needs confirm."""
    raw = str(text or "")
    if not raw:
        return []
    base = _parse_updated_day(updated_at, ZoneInfo(tz_name))
    phrases: list[str] = []
    for pattern in (_UPCOMING_WEEKDAY_RE, _BARE_WEEKDAY_RE):
        for match in pattern.finditer(raw):
            weekday = _weekday_char_to_index(match.group("wd"))
            _, needs = resolve_upcoming_weekday(base, weekday)
            if needs:
                phrases.append(match.group(0))
    return phrases


def _resolve_upcoming_weekday_match(match: re.Match[str], base: date) -> date | None:
    weekday = _weekday_char_to_index(match.group("wd"))
    resolved, needs = resolve_upcoming_weekday(base, weekday)
    if needs:
        return None
    return resolved


def _resolve_weekday_in_week_match(match: re.Match[str], base: date) -> date:
    week_offset = _week_offset_value(match.group("wo"))
    weekday = _weekday_char_to_index(match.group("wd"))
    return weekday_in_week(anchor_day=base, week_offset=week_offset, weekday=weekday)


_Resolver = Callable[[re.Match[str], date], date | None]


def _iter_resolvers(base: date) -> list[tuple[re.Pattern[str], _Resolver]]:
    return [
        (_WEEKDAY_IN_WEEK_RE, lambda m, b: _resolve_weekday_in_week_match(m, b)),
        (_UPCOMING_WEEKDAY_RE, lambda m, b: _resolve_upcoming_weekday_match(m, b)),
        (_BARE_WEEKDAY_RE, lambda m, b: _resolve_upcoming_weekday_match(m, b)),
        (_ONE_WEEK_LATER_RE, lambda _m, b: b + timedelta(days=7)),
        (_N_DAYS_LATER_RE, lambda m, b: b + timedelta(days=int(m.group("n")))),
        (_MONTH_AFTER_NEXT_HEAD_RE, lambda _m, b: resolve_next_month_head(b, months_ahead=2)),
        (_NEXT_MONTH_HEAD_RE, lambda _m, b: resolve_next_month_head(b, months_ahead=1)),
        (_THIS_WEEKEND_RE, lambda _m, b: resolve_this_weekend(b)),
        (
            _EXPLICIT_MONTH_DAY_RE,
            lambda m, b: resolve_explicit_month_day(
                month=int(m.group("m")), day=int(m.group("d")), anchor_day=b
            ),
        ),
    ]


def resolve_relative_date(*, topic: str, updated_at: str, tz_name: str) -> date | None:
    """Return the calendar day the topic refers to, or None if no relative marker."""
    tz = ZoneInfo(tz_name)
    base = _parse_updated_day(updated_at, tz)
    for pattern, offset_days in _RELATIVE_MARKERS:
        if pattern.search(topic):
            return base + timedelta(days=offset_days)
    for pattern, resolver in _iter_resolvers(base):
        match = pattern.search(topic)
        if not match:
            continue
        resolved = resolver(match, base)
        if resolved is None:
            continue
        return resolved
    return None


def anchor_temporal_in_text(
    text: str,
    *,
    updated_at: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> TemporalAnchorResult:
    """Anchor resolvable dates; defer vague or same-weekday phrases to confirmation."""
    raw = str(text or "").strip()
    if not raw:
        return TemporalAnchorResult(text=raw, resolved_date=None)

    ambiguous = detect_ambiguous_temporal_phrases(raw)
    if ambiguous:
        return TemporalAnchorResult(
            text=raw,
            resolved_date=None,
            needs_date_confirmation=True,
            ambiguous_phrases=tuple(ambiguous),
        )

    confirm = detect_upcoming_weekday_confirmation(
        raw, updated_at=updated_at, tz_name=tz_name
    )
    if confirm:
        return TemporalAnchorResult(
            text=raw,
            resolved_date=None,
            needs_date_confirmation=True,
            ambiguous_phrases=tuple(confirm),
        )

    anchored, resolved = _anchor_resolvable_dates(
        raw, updated_at=updated_at, tz_name=tz_name
    )
    return TemporalAnchorResult(text=anchored, resolved_date=resolved)


def _anchor_resolvable_dates(
    text: str,
    *,
    updated_at: str,
    tz_name: str,
) -> tuple[str, date | None]:
    """Replace relative markers with concrete dates (no confirmation path)."""
    raw = str(text or "").strip()
    if not raw:
        return raw, None

    tz = ZoneInfo(tz_name)
    base = _parse_updated_day(updated_at, tz)
    result = raw
    primary_resolved: date | None = None

    for pattern, offset_days in _RELATIVE_MARKERS:
        if not pattern.search(result):
            continue
        target = base + timedelta(days=offset_days)
        if primary_resolved is None:
            primary_resolved = target
        label = format_jp_date(target)
        result = pattern.sub(label, result, count=0)

    for pattern, resolver in _iter_resolvers(base):

        def _replacer(match: re.Match[str], *, pat: re.Pattern[str], res: Callable) -> str:
            nonlocal primary_resolved
            resolved = res(match, base)
            if resolved is None:
                return match.group(0)
            if primary_resolved is None:
                primary_resolved = resolved
            return format_jp_date(resolved)

        result = pattern.sub(
            lambda m, pat=pattern, res=resolver: _replacer(m, pat=pat, res=res),
            result,
        )

    return result, primary_resolved or resolve_relative_date(
        topic=raw, updated_at=updated_at, tz_name=tz_name
    )


def anchor_relative_dates_in_text(
    text: str,
    *,
    updated_at: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> tuple[str, date | None]:
    """Replace relative day words with concrete calendar dates anchored to *updated_at*."""
    result = anchor_temporal_in_text(text, updated_at=updated_at, tz_name=tz_name)
    return result.text, result.resolved_date


def is_resolved_date_stale(
    resolved: date,
    *,
    as_of: date,
    include_today: bool = False,
) -> bool:
    if resolved < as_of:
        return True
    return include_today and resolved == as_of


def stale_from_detail_json(
    detail_json: str | None,
    *,
    as_of: date,
    include_today: bool = False,
) -> date | None:
    """Return resolved_date from loop detail when it is stale, else None."""
    if not detail_json:
        return None
    try:
        detail = json.loads(detail_json)
    except json.JSONDecodeError:
        return None
    raw = detail.get("resolved_date")
    if not raw:
        return None
    try:
        resolved = date.fromisoformat(str(raw))
    except ValueError:
        return None
    if is_resolved_date_stale(resolved, as_of=as_of, include_today=include_today):
        return resolved
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
    if is_resolved_date_stale(resolved, as_of=as_of, include_today=include_today):
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


def calendar_anchor_line(*, ts: str, tz_name: str = DEFAULT_TIMEZONE) -> str:
    """One-line compose anchor: concrete calendar day for the model."""
    day = as_of_date(as_of_ts=ts, tz_name=tz_name)
    return f"Calendar today ({tz_name}): {format_jp_date(day)}."
