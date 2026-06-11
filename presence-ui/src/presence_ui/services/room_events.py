"""Shared room event constants — Web UI and CLI use the same session_id pointer."""

from __future__ import annotations

from social_core import LEGACY_ROOM_SESSION_ID, ROOM_EVENT_SOURCES

# Canonical write source for new room messages (CLI should use the same).
ROOM_WRITE_SOURCE = "room"

__all__ = [
    "LEGACY_ROOM_SESSION_ID",
    "ROOM_EVENT_SOURCES",
    "ROOM_WRITE_SOURCE",
]
