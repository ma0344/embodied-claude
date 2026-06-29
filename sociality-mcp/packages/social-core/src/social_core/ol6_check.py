"""OL6 — post-deadline loop check-in helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from social_core.date_resolution import DEFAULT_TIMEZONE, as_of_date

_UNTIL_PHRASE_RE = re.compile(
    r"(?P<hour>\d{1,2})時(?:ごろ|位|くらい)?まで"
)
_UNTIL_PHRASE_EN_RE = re.compile(
    r"until\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?",
    re.I,
)

_OL6_CONFIRM_RE = re.compile(
    r"^(?:うん|はい|ええ|そう)?[,、]?\s*"
    r"(?:もう)?(?:終わ(?:った|り)?(?:よ|ね|わ)?|でき(?:た|たよ)?|済(?:んだ|み)?|"
    r"完了(?:した|)|終え(?:た|たよ)?|片付(?:け)?(?:た|たよ)?|"
    r"やっ(?:た|ちゃった|てきた)?|終了(?:した)?)"
    r"(?:よ|ね|わ|な|です)?[!！?？。.…~\s]*$",
    re.I,
)
_OL6_DENY_RE = re.compile(
    r"^(?:ううん|いや|まだ|これから|これから(?:やる|する)|"
    r"終わって(?:ない|へん)|できて(?:ない|へん)|"
    r"not\s+yet|still\s+working)"
    r".*$",
    re.I,
)


def extract_until_phrase(*, detail: dict, topic: str) -> str | None:
    """Return until phrase from loop detail or embedded topic text."""
    raw = detail.get("until_phrase")
    if raw and str(raw).strip():
        return str(raw).strip()
    event = detail.get("event")
    if isinstance(event, dict):
        nested = event.get("until_phrase")
        if nested and str(nested).strip():
            return str(nested).strip()
    topic_text = (topic or "").strip()
    match = _UNTIL_PHRASE_RE.search(topic_text)
    if match:
        return match.group(0)
    return None


def parse_until_clock(until_phrase: str) -> tuple[int, int] | None:
    """Parse hour (and optional minute) from Japanese until phrase."""
    text = (until_phrase or "").strip()
    if not text:
        return None
    match = _UNTIL_PHRASE_RE.search(text)
    if match:
        hour = int(match.group("hour"))
        if 0 <= hour <= 23:
            return hour, 0
    en = _UNTIL_PHRASE_EN_RE.search(text)
    if en:
        hour = int(en.group("hour"))
        minute = int(en.group("minute") or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    return None


def loop_end_datetime(
    *,
    resolved_date: date | None,
    until_phrase: str,
    as_of_ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> datetime | None:
    """Calendar end instant for a loop's until phrase."""
    clock = parse_until_clock(until_phrase)
    if clock is None:
        return None
    hour, minute = clock
    day = resolved_date or as_of_date(as_of_ts=as_of_ts, tz_name=tz_name)
    tz = ZoneInfo(tz_name)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def is_loop_past_deadline(
    *,
    detail: dict,
    topic: str,
    as_of_ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> bool:
    """True when now is strictly after the loop's until deadline."""
    until = extract_until_phrase(detail=detail, topic=topic)
    if not until:
        return False
    resolved_raw = detail.get("resolved_date")
    resolved: date | None = None
    if resolved_raw:
        try:
            resolved = date.fromisoformat(str(resolved_raw))
        except ValueError:
            resolved = None
    end_dt = loop_end_datetime(
        resolved_date=resolved,
        until_phrase=until,
        as_of_ts=as_of_ts,
        tz_name=tz_name,
    )
    if end_dt is None:
        return False
    raw = as_of_ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    now = datetime.fromisoformat(raw)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    return now.astimezone(end_dt.tzinfo) > end_dt


def is_ol6_completion_confirm(text: str) -> bool:
    """Short affirmative completion without loop-specific terms."""
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 80:
        return False
    return bool(_OL6_CONFIRM_RE.match(stripped))


def is_ol6_completion_denial(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 120:
        return False
    return bool(_OL6_DENY_RE.match(stripped))


def loop_due_for_check(
    *,
    detail: dict,
    topic: str,
    as_of_ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> bool:
    """Past until deadline and not yet asked for completion check."""
    if detail.get("check_asked_at"):
        return False
    pending = detail.get("pending_check")
    if isinstance(pending, dict) and pending.get("asked_at"):
        return False
    return is_loop_past_deadline(
        detail=detail,
        topic=topic,
        as_of_ts=as_of_ts,
        tz_name=tz_name,
    )
