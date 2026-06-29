"""Parse Japanese calendar create/update utterances (GAPI-7 v1 rules)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_DAY_OFFSETS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"明後日|あさって", re.I), 2),
    (re.compile(r"明日|あした|tomorrow", re.I), 1),
    (re.compile(r"今日|きょう|today", re.I), 0),
]

_TIME_RANGE_RE = re.compile(
    r"(?P<sh>\d{1,2})\s*(?:時|:|：)(?:(?P<sm>\d{1,2})分?)?"
    r"\s*[～〜~\-－―]\s*"
    r"(?P<eh>\d{1,2})\s*(?:時|:|：)(?:(?P<em>\d{1,2})分?)?",
    re.I,
)

_TITLE_QUOTED_RE = re.compile(r"[「『](?P<title>[^」』]+)[」』]")
_TITLE_DE_TTE_RE = re.compile(
    r"で\s*(?P<title>[^「」『』\n、。]+?)\s*って(?:予定|入れ)",
    re.I,
)

_UPDATE_RE = re.compile(
    r"(?:(?P<day>明日|今日|明後日|あした|きょう).{0,24})?"
    r"(?P<old_h>(?<!\d)\d{1,2})\s*時(?:\s*(?P<old_m>\d{1,2})分)?.*?"
    r"(?P<new_h>(?<!\d)\d{1,2})\s*時(?:\s*(?P<new_m>\d{1,2})分)?に"
    r"(?:ずらして|変更して|移して|リスケ)",
    re.I | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class ParsedCreate:
    day_offset: int
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    title: str


@dataclass(frozen=True, slots=True)
class ParsedUpdate:
    day_offset: int
    old_hour: int
    old_minute: int
    new_hour: int
    new_minute: int


def _minute(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def parse_day_offset(text: str) -> int | None:
    line = (text or "").strip()
    for pattern, offset in _DAY_OFFSETS:
        if pattern.search(line):
            return offset
    return None


def _parse_title(text: str) -> str | None:
    quoted = _TITLE_QUOTED_RE.search(text)
    if quoted:
        title = quoted.group("title").strip()
        return title or None
    de_tte = _TITLE_DE_TTE_RE.search(text)
    if de_tte:
        title = de_tte.group("title").strip()
        return title or None
    return None


def parse_create(text: str) -> ParsedCreate | None:
    line = (text or "").strip()
    if not line:
        return None
    day_offset = parse_day_offset(line)
    if day_offset is None:
        return None
    time_match = _TIME_RANGE_RE.search(line)
    if not time_match:
        return None
    title = _parse_title(line)
    if not title:
        return None
    return ParsedCreate(
        day_offset=day_offset,
        start_hour=int(time_match.group("sh")),
        start_minute=_minute(time_match.group("sm")),
        end_hour=int(time_match.group("eh")),
        end_minute=_minute(time_match.group("em")),
        title=title,
    )


def _day_offset_from_label(label: str | None) -> int:
    if not label:
        return 0
    lowered = label.strip().lower()
    if lowered in {"明後日"}:
        return 2
    if lowered in {"明日", "あした"}:
        return 1
    return 0


def parse_update(text: str) -> ParsedUpdate | None:
    line = (text or "").strip()
    if not line:
        return None
    match = _UPDATE_RE.search(line)
    if not match:
        return None
    day_offset = parse_day_offset(line)
    if day_offset is None:
        day_offset = _day_offset_from_label(match.group("day"))
    return ParsedUpdate(
        day_offset=day_offset,
        old_hour=int(match.group("old_h")),
        old_minute=_minute(match.group("old_m")),
        new_hour=int(match.group("new_h")),
        new_minute=_minute(match.group("new_m")),
    )
