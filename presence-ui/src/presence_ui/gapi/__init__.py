"""GAPI — Google Calendar / Drive gateway integration (OAuth + prefetch)."""

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service, load_credentials
from presence_ui.gapi.calendar_client import CalendarEvent, list_events_in_prefetch_window
from presence_ui.gapi.policy import GooglePolicy, load_google_policy

__all__ = [
    "CalendarEvent",
    "GoogleAuthError",
    "GooglePolicy",
    "get_calendar_service",
    "list_events_in_prefetch_window",
    "load_credentials",
    "load_google_policy",
]
