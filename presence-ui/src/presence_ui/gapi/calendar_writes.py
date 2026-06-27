"""Calendar write helpers — GAPI-prep-2 / GAPI-7."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.discovery import Resource

from presence_ui.gapi.policy import CalendarPolicy, GooglePolicy

SMOKE_PREFIX = "[gapi-smoke]"
SMOKE_TITLE = f"{SMOKE_PREFIX} prep-2 test"


class CalendarWriteError(RuntimeError):
    """Policy or API blocked a calendar write."""


@dataclass(frozen=True, slots=True)
class CreatedEvent:
    calendar_id: str
    event_id: str
    summary: str
    start: str
    end: str
    html_link: str = ""


def calendar_by_id(policy: GooglePolicy, calendar_id: str) -> CalendarPolicy:
    cal_id = calendar_id.strip() or "primary"
    for cal in policy.calendars:
        if cal.enabled and cal.id == cal_id:
            return cal
    raise CalendarWriteError(f"Calendar not configured or disabled: {cal_id}")


def require_create_allowed(calendar: CalendarPolicy) -> None:
    if not calendar.allow_create:
        raise CalendarWriteError(
            f"allow_create=false for calendar {calendar.id!r}. "
            "Set allow_create=true in gapi-policy.toml for prep-2."
        )


def require_update_allowed(calendar: CalendarPolicy) -> None:
    if not calendar.allow_update:
        raise CalendarWriteError(
            f"allow_update=false for calendar {calendar.id!r}. "
            "Set allow_update=true in gapi-policy.toml for prep-2."
        )


def _dt_iso(value: datetime) -> str:
    return value.isoformat()


def default_smoke_slot(*, timezone: str, day_offset: int = 1) -> tuple[datetime, datetime]:
    """Tomorrow (or day_offset) 10:00–10:30 in policy timezone."""
    tz = ZoneInfo(timezone)
    base = datetime.now(tz).date() + timedelta(days=day_offset)
    start = datetime.combine(base, time(hour=10, minute=0), tzinfo=tz)
    end = start + timedelta(minutes=30)
    return start, end


def create_event(
    service: Resource,
    *,
    calendar: CalendarPolicy,
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
) -> CreatedEvent:
    require_create_allowed(calendar)
    body: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": _dt_iso(start), "timeZone": str(start.tzinfo)},
        "end": {"dateTime": _dt_iso(end), "timeZone": str(end.tzinfo)},
    }
    if description.strip():
        body["description"] = description.strip()
    result = (
        service.events()
        .insert(calendarId=calendar.id, body=body)
        .execute()
    )
    start_raw = (result.get("start") or {}).get("dateTime") or ""
    end_raw = (result.get("end") or {}).get("dateTime") or ""
    return CreatedEvent(
        calendar_id=calendar.id,
        event_id=str(result.get("id") or ""),
        summary=str(result.get("summary") or summary),
        start=str(start_raw),
        end=str(end_raw),
        html_link=str(result.get("htmlLink") or ""),
    )


def patch_event_times(
    service: Resource,
    *,
    calendar: CalendarPolicy,
    event_id: str,
    start: datetime,
    end: datetime,
) -> CreatedEvent:
    require_update_allowed(calendar)
    body = {
        "start": {"dateTime": _dt_iso(start), "timeZone": str(start.tzinfo)},
        "end": {"dateTime": _dt_iso(end), "timeZone": str(end.tzinfo)},
    }
    result = (
        service.events()
        .patch(calendarId=calendar.id, eventId=event_id, body=body)
        .execute()
    )
    start_raw = (result.get("start") or {}).get("dateTime") or ""
    end_raw = (result.get("end") or {}).get("dateTime") or ""
    return CreatedEvent(
        calendar_id=calendar.id,
        event_id=str(result.get("id") or event_id),
        summary=str(result.get("summary") or ""),
        start=str(start_raw),
        end=str(end_raw),
        html_link=str(result.get("htmlLink") or ""),
    )


def run_write_smoke(
    service: Resource,
    policy: GooglePolicy,
    *,
    calendar_id: str = "primary",
    dry_run: bool = False,
) -> tuple[CreatedEvent | None, CreatedEvent | None]:
    """Create smoke event then patch +1h. Returns (created, patched)."""
    calendar = calendar_by_id(policy, calendar_id)
    require_create_allowed(calendar)
    require_update_allowed(calendar)
    start, end = default_smoke_slot(timezone=policy.timezone)
    patched_start = start + timedelta(hours=1)
    patched_end = end + timedelta(hours=1)

    if dry_run:
        print(f"DRY RUN create {SMOKE_TITLE} {start.isoformat()} -> {end.isoformat()}")
        print(f"DRY RUN patch  -> {patched_start.isoformat()} -> {patched_end.isoformat()}")
        return None, None

    created = create_event(
        service,
        calendar=calendar,
        summary=SMOKE_TITLE,
        start=start,
        end=end,
        description="GAPI-prep-2 smoke — safe to delete manually",
    )
    patched = patch_event_times(
        service,
        calendar=calendar,
        event_id=created.event_id,
        start=patched_start,
        end=patched_end,
    )
    return created, patched
