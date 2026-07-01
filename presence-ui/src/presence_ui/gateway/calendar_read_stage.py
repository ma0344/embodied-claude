"""GAPI-2b — e4b calendar read window extract (fallback when C4 cannot resolve)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from presence_ui.gateway.calendar_read_stage_prompts import (
    build_calendar_read_search_system,
    build_calendar_read_search_task,
    build_calendar_read_window_system,
    build_calendar_read_window_task,
)
from presence_ui.gateway.calendar_read_search import sanitize_calendar_search_query
from presence_ui.gateway.gateway_turn_cache import calendar_search_cache_key, get_or_set_cached
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object


@dataclass(frozen=True, slots=True)
class CalendarReadWindowExtract:
    start: datetime
    end: datetime
    reason: str
    search_query: str | None = None


@dataclass(frozen=True, slots=True)
class CalendarReadSearchExtract:
    search_query: str | None
    reason: str


def calendar_read_e4b_enabled() -> bool:
    raw = os.getenv("PRESENCE_GAPI_READ_WINDOW_E4B", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def parse_calendar_read_window_response(
    text: str,
    *,
    tz_name: str,
) -> CalendarReadWindowExtract | None:
    data = _extract_json_object(text)
    if not data:
        return None
    start_raw = data.get("start")
    end_raw = data.get("end")
    if not start_raw or not end_raw:
        return None
    tz = ZoneInfo(tz_name)
    try:
        start = _parse_iso_datetime(str(start_raw), tz)
        end = _parse_iso_datetime(str(end_raw), tz)
    except ValueError:
        return None
    if end < start:
        return None
    reason = str(data.get("reason") or "").strip()
    search_raw = data.get("search_query")
    search_query: str | None = None
    if search_raw is not None and str(search_raw).strip().lower() not in ("", "null", "none"):
        search_query = sanitize_calendar_search_query(str(search_raw))
    return CalendarReadWindowExtract(
        start=start,
        end=end,
        reason=reason,
        search_query=search_query,
    )


def parse_calendar_read_search_response(text: str) -> CalendarReadSearchExtract | None:
    data = _extract_json_object(text)
    if not data:
        return None
    search_raw = data.get("search_query")
    search_query: str | None = None
    if search_raw is not None and str(search_raw).strip().lower() not in ("", "null", "none"):
        search_query = sanitize_calendar_search_query(str(search_raw))
    reason = str(data.get("reason") or "").strip()
    return CalendarReadSearchExtract(search_query=search_query, reason=reason)


def _parse_iso_datetime(raw: str, tz: ZoneInfo) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def run_calendar_read_window_extract(
    *,
    utterance: str,
    as_of: datetime,
    tz_name: str,
) -> CalendarReadWindowExtract | None:
    if not calendar_read_e4b_enabled():
        return None
    local = as_of.astimezone(ZoneInfo(tz_name))
    raw = run_classifier_turn(
        system=build_calendar_read_window_system(as_of=local),
        user=build_calendar_read_window_task(utterance=utterance),
        max_tokens=int(os.getenv("PRESENCE_GAPI_READ_WINDOW_MAX_TOKENS", "256")),
        log_label="GAPI-2b calendar read window",
    )
    if not raw:
        return None
    return parse_calendar_read_window_response(raw, tz_name=tz_name)


def calendar_read_search_e4b_enabled() -> bool:
    raw = os.getenv("PRESENCE_GAPI_READ_SEARCH_E4B", "1").strip().lower()
    return raw not in ("0", "false", "no", "off") and calendar_read_e4b_enabled()


def run_calendar_read_search_extract(*, utterance: str) -> CalendarReadSearchExtract | None:
    """e4b fallback for search_query when C4/regex did not extract a keyword."""
    if not calendar_read_search_e4b_enabled():
        return None

    def _extract() -> CalendarReadSearchExtract | None:
        raw = run_classifier_turn(
            system=build_calendar_read_search_system(),
            user=build_calendar_read_search_task(utterance=utterance),
            max_tokens=int(os.getenv("PRESENCE_GAPI_READ_SEARCH_MAX_TOKENS", "128")),
            log_label="GAPI-2s calendar read search",
        )
        if not raw:
            return None
        return parse_calendar_read_search_response(raw)

    return get_or_set_cached(calendar_search_cache_key(utterance), _extract)
