"""Parse human utterances like 「10時にリマインドして」 into reminder commitments."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
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

_TEACH_RE = re.compile(r"教えて")


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
    # 「10時に教えて」 — time + 教えて, not bare questions
    return bool(_TEACH_RE.search(text) and _TIME_RE.search(text))


def extract_reminder_request(
    text: str,
    *,
    ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> tuple[str, str] | None:
    """Return (reminder_label, due_at_iso) or None if no timed reminder intent."""
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact or not _has_reminder_intent(compact):
        return None

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

    tz = ZoneInfo(tz_name)
    base = parse_timestamp(ts).astimezone(tz)
    offset = _day_offset(match.group("day"))
    target_date = base.date() + timedelta(days=offset)
    due = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour_i,
        minute_i,
        tzinfo=tz,
    )
    if offset == 0 and due <= base:
        due += timedelta(days=1)

    label = compact
    for verb in (*REMINDER_VERBS, "教えて"):
        label = label.replace(verb, "")
    label = re.sub(r"\s+", " ", label).strip("、。.!?？ ")
    if not label:
        label = compact[:48]

    return label[:120], due.isoformat()
