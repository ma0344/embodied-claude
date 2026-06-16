"""Parse human utterances like 「10時にリマインドして」 into reminder commitments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from social_core import parse_timestamp

from .date_resolution import DEFAULT_TIMEZONE

REMINDER_VERBS = ("リマインド", "起こして", "声かけて", "通知して")

# 「明日の10時」「10時30分に」「14:30に」
_TIME_RE = re.compile(
    r"(?:(?P<day>明日|明後日|あさって)\s*(?:の)?)?"
    r"(?:(?P<hour>\d{1,2})\s*時\s*(?:(?P<minute>\d{1,2})\s*分)?|"
    r"(?P<hour_colon>\d{1,2})\s*[:：]\s*(?P<minute_colon>\d{1,2}))"
    r"\s*(?:に|で)?",
    re.I,
)

_MINUTES_LATER_RE = re.compile(r"(?P<minutes>\d+|[０-９]+)\s*分\s*後", re.I)
_TEACH_RE = re.compile(r"教えて")
_QUOTE_RE = re.compile(r"[「『](?P<q>[^」』]+)[」』]")

_SAY_MARKERS = ("say", "しゃべ", "声で", "喋", "読み上げ")
_NUDGE_ONLY_MARKERS = ("テキストだけ", "sayせん", "say せん", "音声いら", "声はいら")

DeliveryMode = Literal["say", "nudge_only"]


@dataclass(frozen=True)
class ReminderSpec:
    """Structured reminder parsed from a human utterance."""

    title: str
    due_at: str
    speak_line: str | None = None
    delivery: DeliveryMode = "say"


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def _day_offset(day_marker: str | None) -> int:
    if not day_marker:
        return 0
    if "明後日" in day_marker or "あさって" in day_marker:
        return 2
    if "明日" in day_marker:
        return 1
    return 0


def _has_reminder_intent(text: str) -> bool:
    if any(verb in text for verb in REMINDER_VERBS):
        return True
    if _MINUTES_LATER_RE.search(text):
        lowered = text.lower()
        if _TEACH_RE.search(text):
            return True
        if "say" in lowered:
            return True
        if any(marker in text for marker in ("しゃべ", "声で", "喋")):
            return True
    return bool(_TEACH_RE.search(text) and _TIME_RE.search(text))


def extract_quoted_speak_line(text: str) -> str | None:
    """Return the first quoted phrase (「…」) if present."""
    match = _QUOTE_RE.search(text)
    if match is None:
        return None
    line = match.group("q").strip()
    return line[:240] if line else None


def detect_delivery_mode(text: str) -> DeliveryMode:
    lowered = text.lower()
    if any(marker in text or marker in lowered for marker in _NUDGE_ONLY_MARKERS):
        return "nudge_only"
    if any(marker in text or marker in lowered for marker in _SAY_MARKERS):
        return "say"
    return "say"


def _parse_clock_due_at(compact: str, *, base: datetime) -> datetime | None:
    match = _TIME_RE.search(compact)
    if match is None:
        return None

    hour = match.group("hour") or match.group("hour_colon")
    minute = match.group("minute") or match.group("minute_colon") or "0"
    if hour is None:
        return None

    hour_i = int(hour)
    minute_i = int(minute)
    if hour_i > 23 or minute_i > 59:
        return None

    offset = _day_offset(match.group("day"))
    target_date = base.date() + timedelta(days=offset)
    due = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour_i,
        minute_i,
        tzinfo=base.tzinfo,
    )
    if offset == 0 and due <= base:
        due += timedelta(days=1)
    return due


def _parse_minutes_later_due_at(compact: str, *, base: datetime) -> datetime | None:
    match = _MINUTES_LATER_RE.search(compact)
    if match is None:
        return None
    minutes = int(_normalize_digits(match.group("minutes")))
    if minutes <= 0 or minutes > 24 * 60:
        return None
    base_minute = base.replace(second=0, microsecond=0)
    return base_minute + timedelta(minutes=minutes)


def _build_title(compact: str, speak_line: str | None) -> str:
    if speak_line:
        return speak_line[:120]

    label = compact
    for verb in (*REMINDER_VERBS, "教えて"):
        label = label.replace(verb, "")
    label = _MINUTES_LATER_RE.sub("", label)
    label = _TIME_RE.sub("", label)
    label = re.sub(r"\s+", " ", label).strip("、。.!?？ 「」『』")
    if not label:
        label = "リマインド"
    return label[:120]


def extract_reminder_request(
    text: str,
    *,
    ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> ReminderSpec | None:
    """Return structured reminder spec or None if no timed reminder intent."""
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact or not _has_reminder_intent(compact):
        return None

    tz = ZoneInfo(tz_name)
    base = parse_timestamp(ts).astimezone(tz)

    due: datetime | None = None
    if _MINUTES_LATER_RE.search(compact):
        due = _parse_minutes_later_due_at(compact, base=base)
    if due is None:
        due = _parse_clock_due_at(compact, base=base)
    if due is None:
        return None

    speak_line = extract_quoted_speak_line(compact)
    title = _build_title(compact, speak_line)
    delivery = detect_delivery_mode(compact)

    return ReminderSpec(
        title=title,
        due_at=due.isoformat(),
        speak_line=speak_line,
        delivery=delivery,
    )
