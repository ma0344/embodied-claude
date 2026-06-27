"""OAuth scopes for GAPI (phase-gated)."""

from __future__ import annotations

CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"

# GAPI-prep-1 / GAPI-2: read only
DEFAULT_PREP_SCOPES = (CALENDAR_READONLY,)
