"""GAPI prep-3 — Google Calendar prefetch for conversation (WS-2 same shape)."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service
from presence_ui.gapi.calendar_client import (
    CalendarEvent,
    format_calendar_prefetch_block,
    list_events_in_prefetch_window,
)
from presence_ui.gapi.policy import GooglePolicy, load_google_policy
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
    """L0 calendar read intent — explicit schedule keywords only (not bare おはよ)."""
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if _CALENDAR_KEYWORDS.search(line):
        return True
    return bool(_SCHEDULE_WHEN.search(line) or _WHEN_SCHEDULE.search(line))


def detect_calendar_intent(text: str) -> bool:
    return calendar_prefetch_enabled() and looks_like_calendar_query(text)


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
) -> str:
    block = format_calendar_prefetch_block(policy, events, status=status)
    block, _ = _truncate_prefetch_block(block, max_chars=policy.max_prefetch_chars)
    lines = [block, ""]
    if status == "ok":
        directive = (
            "Gateway fetched Google Calendar (today+tomorrow window).\n"
            "Treat [calendar_prefetch] events as authoritative for schedule questions.\n"
            "[open_loops] in compose may supplement; do not contradict calendar events.\n"
            "Do NOT invent events beyond the prefetch block."
        )
    elif status == "empty":
        directive = (
            "Gateway fetched Google Calendar; no events in the prefetch window.\n"
            "Say honestly there is nothing on the calendar for today/tomorrow unless "
            "[open_loops] lists informal tasks."
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


def _format_error_block(*, policy: GooglePolicy | None, status: str, detail: str) -> str:
    tz = policy.timezone if policy else "Asia/Tokyo"
    day_range = policy.prefetch_day_range if policy else ["today", "tomorrow"]
    cal_ids = ",".join(cal.id for cal in policy.readable_calendars()) if policy else ""
    lines = [
        "[calendar_prefetch]",
        f"range={','.join(day_range)}",
        f"timezone={tz}",
        f"status={status}",
        f"calendars={cal_ids}",
        f"detail={detail[:240]}",
        "--- events ---",
        "[/calendar_prefetch]",
        "",
        "[Gateway directive — not for the user]",
        calendar_honesty_directive().split("\n", 1)[-1],
    ]
    return "\n".join(lines)


def fetch_calendar_prefetch_sync() -> tuple[str, str]:
    """Return (prefetch block with directive, status)."""
    policy = load_google_policy()
    if not policy.enabled:
        return (
            _format_error_block(
                policy=policy,
                status="disabled",
                detail="gapi-policy google.enabled is false or policy missing",
            ),
            "disabled",
        )
    if not policy.readable_calendars():
        return (
            _format_error_block(
                policy=policy,
                status="disabled",
                detail="no readable calendars in gapi-policy",
            ),
            "disabled",
        )
    try:
        service = get_calendar_service()
        events = list_events_in_prefetch_window(service, policy)
    except GoogleAuthError as exc:
        return (
            _format_error_block(policy=policy, status="error", detail=str(exc)),
            "error",
        )
    except Exception as exc:  # noqa: BLE001
        return (
            _format_error_block(policy=policy, status="error", detail=str(exc)),
            "error",
        )

    status = "ok" if events else "empty"
    block = format_calendar_prefetch_with_directive(policy=policy, events=events, status=status)
    return block, status


async def prefetch_calendar_for_message(
    message: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    text = (message or "").strip()
    if not text or not detect_calendar_intent(text):
        return None, []

    # Write turns carry [calendar_write_result]; skip redundant read prefetch.
    from presence_ui.gateway.calendar_write import detect_calendar_write_intent

    if detect_calendar_write_intent(text):
        return None, []

    block, status = await asyncio.to_thread(fetch_calendar_prefetch_sync)
    if status == "ok":
        label = "カレンダーを見た"
    elif status == "empty":
        label = "カレンダーに予定なし"
    elif status == "disabled":
        label = "カレンダー未接続"
    else:
        label = "カレンダー取得に失敗"
    return block, [progress_event(phase="calendar", label=label)]
