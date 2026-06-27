"""Google Calendar read — today + tomorrow window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.discovery import Resource

from presence_ui.gapi.policy import CalendarPolicy, GooglePolicy


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    calendar_id: str
    calendar_label: str
    event_id: str
    summary: str
    start: str
    end: str
    location: str = ""


def prefetch_window_bounds(
    *,
    day_range: list[str],
    timezone: str,
    as_of: date | None = None,
) -> tuple[datetime, datetime]:
    """Return [time_min, time_max) in tz for policy day_range (e.g. today+tomorrow)."""
    tz = ZoneInfo(timezone)
    today = as_of or datetime.now(tz).date()
    names = {str(d).strip().lower() for d in day_range}
    start_day = today
    end_day = today
    if "tomorrow" in names:
        end_day = today + timedelta(days=1)
    if "today" not in names and "tomorrow" in names:
        start_day = today + timedelta(days=1)
    time_min = datetime.combine(start_day, time.min, tzinfo=tz)
    time_max = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
    return time_min, time_max


def _event_row(
    *,
    calendar: CalendarPolicy,
    item: dict[str, Any],
) -> CalendarEvent | None:
    event_id = str(item.get("id") or "").strip()
    if not event_id:
        return None
    start = item.get("start") or {}
    end = item.get("end") or {}
    start_s = str(start.get("dateTime") or start.get("date") or "")
    end_s = str(end.get("dateTime") or end.get("date") or "")
    return CalendarEvent(
        calendar_id=calendar.id,
        calendar_label=calendar.label,
        event_id=event_id,
        summary=str(item.get("summary") or "（無題）"),
        start=start_s,
        end=end_s,
        location=str(item.get("location") or ""),
    )


def list_events_in_prefetch_window(
    service: Resource,
    policy: GooglePolicy,
    *,
    as_of: date | None = None,
) -> list[CalendarEvent]:
    time_min, time_max = prefetch_window_bounds(
        day_range=policy.prefetch_day_range,
        timezone=policy.timezone,
        as_of=as_of,
    )
    events: list[CalendarEvent] = []
    for calendar in policy.readable_calendars():
        result = (
            service.events()
            .list(
                calendarId=calendar.id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
            )
            .execute()
        )
        for item in result.get("items") or []:
            if not isinstance(item, dict):
                continue
            row = _event_row(calendar=calendar, item=item)
            if row is not None:
                events.append(row)
    events.sort(key=lambda e: (e.start, e.calendar_id))
    return events


def format_calendar_prefetch_block(
    policy: GooglePolicy,
    events: list[CalendarEvent],
    *,
    status: str = "ok",
) -> str:
    cal_ids = ",".join(cal.id for cal in policy.readable_calendars())
    lines = [
        "[calendar_prefetch]",
        f"range={','.join(policy.prefetch_day_range)}",
        f"timezone={policy.timezone}",
        f"status={status}",
        f"calendars={cal_ids}",
        "--- events ---",
    ]
    for event in events:
        loc = f" | {event.location}" if event.location else ""
        lines.append(
            f"{event.start} | {event.summary}{loc} | cal={event.calendar_label}"
        )
    lines.append("[/calendar_prefetch]")
    return "\n".join(lines)
