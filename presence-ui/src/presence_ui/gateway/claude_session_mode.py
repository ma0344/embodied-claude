"""Decide --session-id vs --resume for native Claude CLI chat."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from presence_ui.services.native_history import resolve_session_jsonl_path


class ClaudeSessionRegistry:
    """Track which Claude session ids are live in this process."""

    def __init__(self) -> None:
        self.registered: set[str] = set()
        self.in_flight: set[str] = set()

    def resolve(
        self,
        session_id: str | None,
        *,
        new_uuid: Callable[[], str] | None = None,
    ) -> tuple[str, bool]:
        """Return (session_id, is_new) for ClaudeAgent.chat."""
        mint = new_uuid or (lambda: str(uuid.uuid4()))
        sid = (session_id or "").strip() or mint()
        if not session_id:
            return sid, True
        if sid in self.registered:
            return sid, False
        if sid in self.in_flight:
            return sid, False
        if resolve_session_jsonl_path(sid) is not None:
            self.registered.add(sid)
            return sid, False
        return sid, True

    def mark_in_flight(self, sid: str) -> None:
        self.in_flight.add(sid)

    def mark_created(self, sid: str) -> None:
        self.registered.add(sid)
        self.in_flight.discard(sid)

    def clear_in_flight(self, sid: str) -> None:
        self.in_flight.discard(sid)
