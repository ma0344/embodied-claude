"""OAuth scopes for GAPI (phase-gated)."""

from __future__ import annotations

import os

CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"

# GAPI-prep-1 / GAPI-2: read only
DEFAULT_PREP_SCOPES = (CALENDAR_READONLY,)


def calendar_scopes() -> tuple[str, ...]:
    """Active Calendar scopes — default events after prep-2 consent."""
    raw = os.environ.get("PRESENCE_GAPI_CALENDAR_SCOPE", "events").strip().lower()
    if raw == "readonly":
        return DEFAULT_PREP_SCOPES
    return (CALENDAR_EVENTS,)
