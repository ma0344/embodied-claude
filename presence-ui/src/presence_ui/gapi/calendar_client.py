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


def list_events_in_time_range(
    service: Resource,
    policy: GooglePolicy,
    *,
    time_min: datetime,
    time_max: datetime,
    search_query: str | None = None,
) -> list[CalendarEvent]:
    from presence_ui.gateway.calendar_read_search import filter_events_by_search_query

    q = (search_query or "").strip() or None
    events = _list_events_paginated(
        service,
        policy,
        time_min=time_min,
        time_max=time_max,
        search_query=q,
    )
    if q:
        filtered = filter_events_by_search_query(events, q)
        if filtered:
            return filtered
        # Google Calendar q= can miss Japanese substring matches — scan window locally.
        broad = _list_events_paginated(
            service,
            policy,
            time_min=time_min,
            time_max=time_max,
            search_query=None,
        )
        return filter_events_by_search_query(broad, q)
    return events


def _list_events_paginated(
    service: Resource,
    policy: GooglePolicy,
    *,
    time_min: datetime,
    time_max: datetime,
    search_query: str | None = None,
    max_pages: int = 20,
) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    q = (search_query or "").strip() or None
    for calendar in policy.readable_calendars():
        page_token: str | None = None
        for _ in range(max_pages):
            params: dict[str, Any] = {
                "calendarId": calendar.id,
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 250,
            }
            if q:
                params["q"] = q
            if page_token:
                params["pageToken"] = page_token
            result = service.events().list(**params).execute()
            for item in result.get("items") or []:
                if not isinstance(item, dict):
                    continue
                row = _event_row(calendar=calendar, item=item)
                if row is not None:
                    events.append(row)
            page_token = result.get("nextPageToken")
            if not page_token:
                break
    events.sort(key=lambda e: (e.start, e.calendar_id))
    return events


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
    return list_events_in_time_range(service, policy, time_min=time_min, time_max=time_max)


def parse_calendar_datetime(value: str, tz: ZoneInfo) -> datetime:
    """Parse Google Calendar ISO start/end into local tz."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty datetime")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if "T" not in raw and len(raw) == 10:
        day = date.fromisoformat(raw)
        return datetime.combine(day, time.min, tzinfo=tz)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def list_events_for_day(
    service: Resource,
    policy: GooglePolicy,
    *,
    day: date,
) -> list[CalendarEvent]:
    """Events on a single local calendar day across readable calendars."""
    tz = ZoneInfo(policy.timezone)
    time_min = datetime.combine(day, time.min, tzinfo=tz)
    time_max = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
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


def match_event_by_local_start(
    events: list[CalendarEvent],
    *,
    target_day: date,
    hour: int,
    minute: int,
    tz: ZoneInfo,
    tolerance_minutes: int = 45,
) -> CalendarEvent | None:
    """Pick the event whose local start is closest to hour:minute on target_day."""
    best: tuple[int, CalendarEvent] | None = None
    for event in events:
        if not event.start:
            continue
        try:
            start = parse_calendar_datetime(event.start, tz)
        except ValueError:
            continue
        if start.date() != target_day:
            continue
        target_mins = hour * 60 + minute
        start_mins = start.hour * 60 + start.minute
        diff = abs(start_mins - target_mins)
        if diff <= tolerance_minutes and (best is None or diff < best[0]):
            best = (diff, event)
    return best[1] if best else None


def format_calendar_prefetch_block(
    policy: GooglePolicy,
    events: list[CalendarEvent],
    *,
    status: str = "ok",
    range_label: str | None = None,
    resolution: str | None = None,
    search_query: str | None = None,
) -> str:
    cal_ids = ",".join(cal.id for cal in policy.readable_calendars())
    range_value = range_label or ",".join(policy.prefetch_day_range)
    lines = [
        "[calendar_prefetch]",
        f"range={range_value}",
        f"timezone={policy.timezone}",
        f"status={status}",
        f"calendars={cal_ids}",
    ]
    if resolution:
        lines.append(f"resolution={resolution}")
    if search_query:
        lines.append(f"search={search_query}")
    lines.append("--- events ---")
    for event in events:
        loc = f" | {event.location}" if event.location else ""
        lines.append(
            f"{event.start} | {event.summary}{loc} | cal={event.calendar_label}"
        )
    lines.append("[/calendar_prefetch]")
    return "\n".join(lines)
