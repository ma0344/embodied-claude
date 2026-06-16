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
_MINUTES_BEFORE_RE = re.compile(r"(?P<minutes>\d+|[０-９]+)\s*分\s*前", re.I)
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


def _parse_event_minus_offset_due_at(compact: str, *, base: datetime) -> datetime | None:
    """e.g. 「15分後の打合せの10分前に」→ remind 5 minutes from now."""
    later = _MINUTES_LATER_RE.search(compact)
    before = _MINUTES_BEFORE_RE.search(compact)
    if later is None or before is None:
        return None
    event_minutes = int(_normalize_digits(later.group("minutes")))
    before_minutes = int(_normalize_digits(before.group("minutes")))
    if event_minutes <= 0 or before_minutes <= 0:
        return None
    if before_minutes >= event_minutes:
        return None
    base_minute = base.replace(second=0, microsecond=0)
    remind_at = base_minute + timedelta(minutes=event_minutes - before_minutes)
    if remind_at <= base_minute:
        return None
    return remind_at


def _rule_parse_defer_to_llm(compact: str) -> bool:
    """Ambiguous relative timing — let Phase B LLM resolve due_at."""
    if _MINUTES_BEFORE_RE.search(compact) and _MINUTES_LATER_RE.search(compact) is None:
        return True
    if "前に" in compact and any(
        word in compact for word in ("来週", "明日", "明後日", "あさって", "今日", "午後", "午前")
    ):
        return True
    return False


def _extract_event_label(compact: str) -> str | None:
    """Label between 「N分後」 and 「M分前」 (e.g. 打合せ)."""
    later = _MINUTES_LATER_RE.search(compact)
    before = _MINUTES_BEFORE_RE.search(compact)
    if later is None or before is None or before.start() <= later.end():
        return None
    middle = compact[later.end() : before.start()]
    middle = re.sub(r"\s+", " ", middle).strip("、。.!?？ 「」『』")
    middle = re.sub(r"^(に|が|は|を)", "", middle).strip()
    middle = re.sub(r"(が始まる|が始まり|になる|が始まって).*$", "", middle).strip("、 ")
    middle = re.sub(r"(から|ので|ので、).*$", "", middle).strip("、 ")
    if len(middle) >= 2:
        return middle[:120]
    return None


def _keyword_reminder_title(compact: str) -> str | None:
    for keyword in ("打合せ", "打ち合わせ", "会議", "歯医者", "薬", "standup", "ミーティング"):
        if keyword in compact:
            return f"{keyword}リマインド"
    return None


def _build_title(compact: str, speak_line: str | None) -> str:
    if speak_line:
        return speak_line[:120]

    event_label = _extract_event_label(compact)
    if event_label:
        return event_label

    keyword_title = _keyword_reminder_title(compact)
    if keyword_title:
        return keyword_title

    label = compact
    for verb in (*REMINDER_VERBS, "教えて"):
        label = label.replace(verb, "")
    label = _MINUTES_LATER_RE.sub("", label)
    label = _MINUTES_BEFORE_RE.sub("", label)
    label = _TIME_RE.sub("", label)
    label = re.sub(r"\s+", " ", label).strip("、。.!?？ 「」『』")
    if not label:
        label = "リマインド"
    return label[:120]


def extract_speak_line_followup(text: str) -> str | None:
    """Return quoted phrase when user confirms what Koyori should say at remind time."""
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact:
        return None
    speak_line = extract_quoted_speak_line(compact)
    if not speak_line:
        return None
    if any(verb in compact for verb in REMINDER_VERBS):
        return None
    if _MINUTES_LATER_RE.search(compact) or _MINUTES_BEFORE_RE.search(compact):
        return None
    if _TIME_RE.search(compact):
        return None
    if not re.search(
        r"(でいい|で大丈夫|でオッケー|でOK|にして|それで|お願い|って言って|って喋って)",
        compact,
        re.I,
    ):
        return None
    return speak_line


def needs_llm_reminder_parse(text: str) -> bool:
    """True when utterance looks like a timed reminder but rule parser failed."""
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact:
        return False
    if extract_reminder_request(compact, ts="2026-06-16T12:00:00+09:00") is not None:
        return False
    if not _has_reminder_intent(compact):
        return False
    # Avoid LLM for dismiss-only or recall noise.
    lowered = compact.lower()
    if any(marker in compact for marker in ("忘れて", "いらない", "キャンセル", "やめて")):
        return False
    if "リマインド" in compact or _TEACH_RE.search(compact):
        return True
    if _TIME_RE.search(compact) or _MINUTES_LATER_RE.search(compact):
        return True
    if any(word in compact for word in ("来週", "今度", "あとで", "午後", "午前", "半")):
        return True
    return "say" in lowered or any(marker in compact for marker in _SAY_MARKERS)


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

    if _rule_parse_defer_to_llm(compact):
        return None

    due: datetime | None = _parse_event_minus_offset_due_at(compact, base=base)
    if due is None and _MINUTES_LATER_RE.search(compact):
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
