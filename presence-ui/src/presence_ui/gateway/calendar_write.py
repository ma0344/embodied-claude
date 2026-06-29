"""GAPI-7 — Google Calendar create/update on explicit utterances (gateway direct)."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service
from presence_ui.gapi.calendar_client import (
    list_events_for_day,
    match_event_by_local_start,
    parse_calendar_datetime,
)
from presence_ui.gapi.calendar_writes import (
    CalendarWriteError,
    CreatedEvent,
    calendar_by_id,
    create_event,
    patch_event_times,
)
from presence_ui.gapi.policy import GooglePolicy, load_google_policy
from presence_ui.gateway.calendar_pending import CalendarPendingRecord
from presence_ui.gateway.calendar_prefetch import gapi_router_enabled
from presence_ui.gateway.calendar_write_parse import (
    ParsedCreate,
    ParsedUpdate,
    parse_create,
    parse_update,
)
from presence_ui.gateway.room_events import progress_event

_CALENDAR_CTX = re.compile(
    r"(?:カレンダー|予定(?:入れ|を入れ|登録))",
    re.I,
)
_CREATE_VERB = re.compile(
    r"(?:入れておいて|入れといて|入れてくれ|入れとく|追加して|予定入れ|カレンダーに入れ|登録して|ブロックして)",
    re.I,
)
_UPDATE_VERB = re.compile(
    r"(?:ずらして|変更して|時間変えて|リスケ|移して|延ばして|短くして|時刻変更)",
    re.I,
)
_READ_QUERY = re.compile(
    r"(?:何か|何が|ある\?|ある？|教えて|確認|見せて|見て)",
    re.I,
)


class CalendarWriteKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"


def calendar_write_enabled() -> bool:
    if not gapi_router_enabled():
        return False
    raw = os.getenv("PRESENCE_GAPI_CALENDAR_WRITE", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def looks_like_calendar_create(text: str) -> bool:
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if not _CREATE_VERB.search(line):
        return False
    if not (_CALENDAR_CTX.search(line) or "カレンダー" in line):
        return False
    if _READ_QUERY.search(line):
        return False
    return True


def looks_like_calendar_update(text: str) -> bool:
    line = (text or "").strip()
    if not line or len(line) > 500:
        return False
    if not _UPDATE_VERB.search(line):
        return False
    return bool(_CALENDAR_CTX.search(line) or re.search(r"\d{1,2}\s*時", line))


def detect_calendar_write_kind(text: str) -> CalendarWriteKind | None:
    if not calendar_write_enabled():
        return None
    if looks_like_calendar_update(text):
        return CalendarWriteKind.UPDATE
    if looks_like_calendar_create(text):
        return CalendarWriteKind.CREATE
    return None


def detect_calendar_write_intent(text: str) -> bool:
    return detect_calendar_write_kind(text) is not None


def calendar_write_honesty_directive() -> str:
    return (
        "[Gateway directive — not for the user]\n"
        "User asked to create or change a Google Calendar event but gateway could not write.\n"
        "Tell まー honestly the calendar write is not connected "
        "or the request could not be parsed.\n"
        "Do NOT claim you added or moved an event without [calendar_write_result] status=ok."
    )


def _format_write_block(
    *,
    action: str,
    status: str,
    policy: GooglePolicy | None,
    detail: str = "",
    event: CreatedEvent | None = None,
) -> str:
    tz = policy.timezone if policy else "Asia/Tokyo"
    lines = [
        "[calendar_write_result]",
        f"action={action}",
        f"status={status}",
        f"timezone={tz}",
    ]
    if event is not None:
        lines.extend(
            [
                f"calendar_id={event.calendar_id}",
                f"event_id={event.event_id}",
                f"summary={event.summary}",
                f"start={event.start}",
                f"end={event.end}",
            ]
        )
        if event.html_link:
            lines.append(f"html_link={event.html_link}")
    if detail:
        lines.append(f"detail={detail[:240]}")
    lines.append("[/calendar_write_result]")
    lines.append("")
    if status == "ok":
        directive = (
            "Gateway executed Google Calendar write (create or update).\n"
            "Report ONLY what is in [calendar_write_result]. "
            "Say you added or moved the event using summary/start/end from the block.\n"
            "Do NOT invent links or claim success if status is not ok."
        )
    else:
        directive = calendar_write_honesty_directive().split("\n", 1)[-1]
    lines.append("[Gateway directive — not for the user]")
    lines.append(directive)
    return "\n".join(lines)


def _target_day(*, policy: GooglePolicy, day_offset: int) -> date:
    tz = ZoneInfo(policy.timezone)
    return (datetime.now(tz).date() + timedelta(days=day_offset))


def _run_create(
    service: Any,
    policy: GooglePolicy,
    parsed: ParsedCreate,
) -> tuple[str, str]:
    calendars = policy.creatable_calendars()
    if not calendars:
        return (
            _format_write_block(
                action="create",
                status="disabled",
                policy=policy,
                detail="no calendar with allow_create=true in gapi-policy",
            ),
            "disabled",
        )
    calendar = calendars[0]
    tz = ZoneInfo(policy.timezone)
    day = _target_day(policy=policy, day_offset=parsed.day_offset)
    start = datetime.combine(
        day,
        time(hour=parsed.start_hour, minute=parsed.start_minute),
        tzinfo=tz,
    )
    end = datetime.combine(
        day,
        time(hour=parsed.end_hour, minute=parsed.end_minute),
        tzinfo=tz,
    )
    if end <= start:
        end = start + timedelta(hours=1)
    try:
        created = create_event(
            service,
            calendar=calendar,
            summary=parsed.title,
            start=start,
            end=end,
        )
    except CalendarWriteError as exc:
        return (
            _format_write_block(
                action="create",
                status="error",
                policy=policy,
                detail=str(exc),
            ),
            "error",
        )
    return (
        _format_write_block(
            action="create",
            status="ok",
            policy=policy,
            event=created,
        ),
        "ok",
    )


def _run_update(
    service: Any,
    policy: GooglePolicy,
    parsed: ParsedUpdate,
) -> tuple[str, str]:
    if not policy.updatable_calendars():
        return (
            _format_write_block(
                action="update",
                status="disabled",
                policy=policy,
                detail="no calendar with allow_update=true in gapi-policy",
            ),
            "disabled",
        )
    tz = ZoneInfo(policy.timezone)
    day = _target_day(policy=policy, day_offset=parsed.day_offset)
    events = list_events_for_day(service, policy, day=day)
    matched = match_event_by_local_start(
        events,
        target_day=day,
        hour=parsed.old_hour,
        minute=parsed.old_minute,
        tz=tz,
    )
    if matched is None:
        return (
            _format_write_block(
                action="update",
                status="not_found",
                policy=policy,
                detail=(
                    f"no event near {parsed.old_hour}:{parsed.old_minute:02d} "
                    f"on {day.isoformat()}"
                ),
            ),
            "not_found",
        )
    try:
        calendar = calendar_by_id(policy, matched.calendar_id)
        require_update = calendar.allow_update
    except CalendarWriteError:
        require_update = False
    if not require_update:
        return (
            _format_write_block(
                action="update",
                status="disabled",
                policy=policy,
                detail=f"allow_update=false for calendar {matched.calendar_id}",
            ),
            "disabled",
        )
    old_start = parse_calendar_datetime(matched.start, tz)
    old_end = parse_calendar_datetime(matched.end, tz)
    duration = old_end - old_start
    new_start = datetime.combine(
        day,
        time(hour=parsed.new_hour, minute=parsed.new_minute),
        tzinfo=tz,
    )
    new_end = new_start + duration
    try:
        patched = patch_event_times(
            service,
            calendar=calendar,
            event_id=matched.event_id,
            start=new_start,
            end=new_end,
        )
    except CalendarWriteError as exc:
        return (
            _format_write_block(
                action="update",
                status="error",
                policy=policy,
                detail=str(exc),
            ),
            "error",
        )
    return (
        _format_write_block(
            action="update",
            status="ok",
            policy=policy,
            event=patched,
        ),
        "ok",
    )


def execute_calendar_write_sync(text: str) -> tuple[str | None, str]:
    kind = detect_calendar_write_kind(text)
    if kind is None:
        return None, "skip"

    policy = load_google_policy()
    if not policy.enabled:
        return (
            _format_write_block(
                action=kind.value,
                status="disabled",
                policy=policy,
                detail="gapi-policy google.enabled is false or policy missing",
            ),
            "disabled",
        )

    if kind is CalendarWriteKind.CREATE:
        parsed = parse_create(text)
        if parsed is None:
            return (
                _format_write_block(
                    action="create",
                    status="parse_failed",
                    policy=policy,
                    detail="could not parse day, time range, or title",
                ),
                "parse_failed",
            )
    else:
        parsed = parse_update(text)
        if parsed is None:
            return (
                _format_write_block(
                    action="update",
                    status="parse_failed",
                    policy=policy,
                    detail="could not parse day and old/new times",
                ),
                "parse_failed",
            )

    try:
        service = get_calendar_service()
    except GoogleAuthError as exc:
        return (
            _format_write_block(
                action=kind.value,
                status="error",
                policy=policy,
                detail=str(exc),
            ),
            "error",
        )

    if kind is CalendarWriteKind.CREATE:
        assert isinstance(parsed, ParsedCreate)
        return _run_create(service, policy, parsed)
    assert isinstance(parsed, ParsedUpdate)
    return _run_update(service, policy, parsed)


def execute_pending_calendar_sync(record: CalendarPendingRecord) -> tuple[str, str]:
    """Execute a confirmed pending draft (GAPI-7b)."""
    policy = load_google_policy()
    if not policy.enabled:
        return (
            _format_write_block(
                action=record.action,
                status="disabled",
                policy=policy,
                detail="gapi-policy disabled",
            ),
            "disabled",
        )
    if not record.start_iso or not record.end_iso:
        return (
            _format_write_block(
                action=record.action,
                status="error",
                policy=policy,
                detail="pending draft missing start/end",
            ),
            "error",
        )
    tz = ZoneInfo(policy.timezone)
    start = datetime.fromisoformat(record.start_iso)
    end = datetime.fromisoformat(record.end_iso)
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz)
    try:
        service = get_calendar_service()
    except GoogleAuthError as exc:
        return (
            _format_write_block(
                action=record.action,
                status="error",
                policy=policy,
                detail=str(exc),
            ),
            "error",
        )
    if record.action == "create":
        calendars = policy.creatable_calendars()
        if not calendars:
            return (
                _format_write_block(
                    action="create",
                    status="disabled",
                    policy=policy,
                    detail="allow_create=false",
                ),
                "disabled",
            )
        calendar = next((c for c in calendars if c.id == record.calendar_id), calendars[0])
        try:
            created = create_event(
                service,
                calendar=calendar,
                summary=record.topic or "（無題）",
                start=start,
                end=end,
            )
        except CalendarWriteError as exc:
            return (
                _format_write_block(
                    action="create",
                    status="error",
                    policy=policy,
                    detail=str(exc),
                ),
                "error",
            )
        return (
            _format_write_block(action="create", status="ok", policy=policy, event=created),
            "ok",
        )
    if not record.event_id:
        return (
            _format_write_block(
                action="update",
                status="error",
                policy=policy,
                detail="pending update missing event_id",
            ),
            "error",
        )
    cal_id = record.event_calendar_id or record.calendar_id
    try:
        calendar = calendar_by_id(policy, cal_id)
    except CalendarWriteError as exc:
        return (
            _format_write_block(
                action="update",
                status="disabled",
                policy=policy,
                detail=str(exc),
            ),
            "disabled",
        )
    try:
        patched = patch_event_times(
            service,
            calendar=calendar,
            event_id=record.event_id,
            start=start,
            end=end,
        )
    except CalendarWriteError as exc:
        return (
            _format_write_block(
                action="update",
                status="error",
                policy=policy,
                detail=str(exc),
            ),
            "error",
        )
    return (
        _format_write_block(action="update", status="ok", policy=policy, event=patched),
        "ok",
    )


async def execute_calendar_write_for_message(
    message: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    """7a immediate write — skipped when calendar_confirm_enabled (7b)."""
    from presence_ui.gateway.calendar_pending import calendar_confirm_enabled

    if calendar_confirm_enabled():
        return None, []
    text = (message or "").strip()
    if not text or not detect_calendar_write_intent(text):
        return None, []

    kind = detect_calendar_write_kind(text)
    block, status = await asyncio.to_thread(execute_calendar_write_sync, text)
    if kind is CalendarWriteKind.CREATE:
        if status == "ok":
            label = "カレンダーに入れた"
        elif status == "parse_failed":
            label = "予定の内容を読み取れなかった"
        elif status == "disabled":
            label = "カレンダー書込み未接続"
        else:
            label = "カレンダー登録に失敗"
    else:
        if status == "ok":
            label = "予定を変更した"
        elif status == "not_found":
            label = "変更する予定が見つからなかった"
        elif status == "parse_failed":
            label = "変更内容を読み取れなかった"
        elif status == "disabled":
            label = "カレンダー変更未接続"
        else:
            label = "予定の変更に失敗"
    return block, [progress_event(phase="calendar", label=label)]
