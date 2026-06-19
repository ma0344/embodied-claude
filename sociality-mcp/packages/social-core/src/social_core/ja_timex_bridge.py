"""Optional ja-timex extractor bridge (dev / benchmark; not required at runtime).

ja-timex depends on pendulum 2.x and may not install on Python 3.13+. When
unavailable, callers fall back to :mod:`social_core.date_resolution` rules only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from social_core.date_resolution import DEFAULT_TIMEZONE


def ja_timex_available() -> bool:
    try:
        import ja_timex  # noqa: F401

        return True
    except ImportError:
        return False


def _reference_datetime(anchor_ts: str, tz_name: str) -> datetime:
    raw = anchor_ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name))


def extract_timex_spans(
    text: str,
    *,
    anchor_ts: str,
    tz_name: str = DEFAULT_TIMEZONE,
) -> list[dict[str, Any]]:
    """Return ja-timex TIMEX3 spans as plain dicts, or [] when unavailable."""
    if not ja_timex_available():
        return []

    from ja_timex import TimexParser

    parser = TimexParser(reference=_reference_datetime(anchor_ts, tz_name))
    spans: list[dict[str, Any]] = []
    for timex in parser.parse(str(text or "")):
        spans.append(
            {
                "text": getattr(timex, "text", ""),
                "type": getattr(timex, "type", ""),
                "value": getattr(timex, "value", ""),
                "mod": getattr(timex, "mod", None),
            }
        )
    return spans
