"""GAPI prep-3 — Google Calendar prefetch for conversation (WS-2 same shape)."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from presence_ui.gapi.calendar_client import (
    CalendarEvent,
    format_calendar_prefetch_block,
)
from presence_ui.gapi.policy import GooglePolicy
from presence_ui.gateway.calendar_read_window import PrefetchWindow
from presence_ui.gateway.room_events import progress_event

_CALENDAR_KEYWORDS = re.compile(
    r"(?:予定|スケジュール|カレンダー|カレンダ)",
    re.I,
)
_SCHEDULE_WHEN = re.compile(
    r"(?:今日|明日|あした|来週).*(?:予定|スケジュール|何か|何が|あった|ある|空いて|忙し)",
    re.I,
)
_WHEN_SCHEDULE = re.compile(
    r"(?:予定|スケジュール).*(?:今日|明日|あした|来週)",
    re.I,
)


def gapi_router_enabled() -> bool:
    raw = os.getenv("PRESENCE_GAPI_ENABLED", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def calendar_prefetch_enabled() -> bool:
    if not gapi_router_enabled():
        return False
    raw = os.getenv("PRESENCE_GAPI_CALENDAR_PREFETCH", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def looks_like_calendar_query(text: str) -> bool:
    """Light calendar cue — gates Stage1; not sufficient alone for prefetch (GAPI-2r-S2)."""
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if _CALENDAR_KEYWORDS.search(line):
        return True
    return bool(_SCHEDULE_WHEN.search(line) or _WHEN_SCHEDULE.search(line))


# Alias — cue before Stage1, not the read classifier.
calendar_read_cue = looks_like_calendar_query


def detect_calendar_intent(text: str) -> bool:
    from presence_ui.gateway.calendar_read_flow import should_run_calendar_read

    return should_run_calendar_read(text)


def calendar_honesty_directive() -> str:
    return (
        "[Gateway directive — not for the user]\n"
        "User asked about calendar/schedule but gateway could not fetch Google Calendar.\n"
        "Tell まー honestly the calendar is not connected yet.\n"
        "Use [open_loops] from compose when present; do NOT invent schedule from "
        "dream_digest, interpretation_shifts, memories, or training data."
    )


def _truncate_prefetch_block(block: str, *, max_chars: int) -> tuple[str, bool]:
    if len(block) <= max_chars:
        return block, False
    suffix = "[/calendar_prefetch]"
    body = block.removesuffix(suffix).rstrip("\n")
    budget = max_chars - len(suffix) - 1
    cut = body[:budget].rsplit("\n", 1)[0]
    lines = cut.split("\n")
    for index, line in enumerate(lines):
        if line.startswith("status="):
            lines[index] = "status=truncated"
            break
    return "\n".join(lines) + f"\n{suffix}", True


def format_calendar_prefetch_with_directive(
    *,
    policy: GooglePolicy,
    events: list[CalendarEvent],
    status: str = "ok",
    window: PrefetchWindow | None = None,
) -> str:
    range_label = window.range_label if window else None
    resolution = window.resolution if window else None
    block = format_calendar_prefetch_block(
        policy,
        events,
        status=status,
        range_label=range_label,
        resolution=resolution,
        search_query=window.search_query if window else None,
    )
    block, truncated = _truncate_prefetch_block(block, max_chars=policy.max_prefetch_chars)
    if truncated and window and window.search_query:
        block = block.replace("status=truncated", "status=truncated_search", 1)
    lines = [block, ""]
    range_hint = (window.range_label if window else ",".join(policy.prefetch_day_range))
    if status == "ok" and not truncated:
        directive = (
            f"Gateway fetched Google Calendar (range={range_hint}"
            f"{f', search={window.search_query}' if window and window.search_query else ''}).\n"
            "Treat [calendar_prefetch] events as authoritative for schedule questions.\n"
            "[open_loops] in compose may supplement; do not contradict calendar events.\n"
            "Do NOT invent events beyond the prefetch block."
        )
    elif status == "ok" and truncated:
        directive = (
            f"Gateway fetched Google Calendar (range={range_hint}) but the list was "
            "TRUNCATED by max_prefetch_chars.\n"
            "The prefetch block is INCOMPLETE — do NOT claim you listed every event in the range.\n"
            "Say honestly that only the earliest part of the window is shown, or ask まー to "
            "narrow the date range or add a keyword filter."
        )
    elif status == "empty":
        directive = (
            f"Gateway fetched Google Calendar; no events in range {range_hint}"
            f"{f' matching search={window.search_query}' if window and window.search_query else ''}.\n"
            "Say honestly there is nothing on the calendar for that window unless "
            "[open_loops] lists informal tasks."
        )
    elif status == "ambiguous":
        phrases = ", ".join(window.ambiguous_phrases) if window else ""
        directive = (
            "User asked about schedule but the date window is ambiguous "
            f"({phrases or 'unspecified span'}).\n"
            "Ask まー which dates they mean before inventing events."
        )
    elif status == "disabled":
        directive = calendar_honesty_directive().split("\n", 1)[-1]
    else:
        directive = (
            "Gateway calendar prefetch failed or is unavailable.\n"
            "Tell まー honestly; use [open_loops] only — do NOT invent schedule."
        )
    lines.append("[Gateway directive — not for the user]")
    lines.append(directive)
    return "\n".join(lines)


def _format_error_block(
    *,
    policy: GooglePolicy | None,
    status: str,
    detail: str,
    range_label: str | None = None,
) -> str:
    tz = policy.timezone if policy else "Asia/Tokyo"
    day_range = range_label or (
        ",".join(policy.prefetch_day_range) if policy else "today,tomorrow"
    )
    lines = [
        "[calendar_prefetch]",
        f"range={day_range}",
        f"timezone={tz}",
        f"status={status}",
        f"calendars={','.join(cal.id for cal in policy.readable_calendars()) if policy else ''}",
        f"detail={detail[:240]}",
        "--- events ---",
        "[/calendar_prefetch]",
        "",
        "[Gateway directive — not for the user]",
        calendar_honesty_directive().split("\n", 1)[-1],
    ]
    return "\n".join(lines)


def fetch_calendar_prefetch_sync(
    utterance: str = "",
    *,
    anchor_iso: str | None = None,
) -> tuple[str, str]:
    """Return (prefetch block with directive, status)."""
    from presence_ui.gateway.calendar_read_flow import run_calendar_read_pipeline

    return run_calendar_read_pipeline(utterance, anchor_iso=anchor_iso)


async def prefetch_calendar_for_message(
    message: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    text = (message or "").strip()
    from presence_ui.gateway.calendar_read_flow import should_run_calendar_read

    if not text or not should_run_calendar_read(text):
        return None, []

    block, status = await asyncio.to_thread(fetch_calendar_prefetch_sync, text)
    if status == "ok":
        label = "カレンダーを見た"
    elif status == "empty":
        label = "カレンダーに予定なし"
    elif status == "ambiguous":
        label = "日付を確認して"
    elif status == "disabled":
        label = "カレンダー未接続"
    else:
        label = "カレンダー取得に失敗"
    return block, [progress_event(phase="calendar", label=label)]
