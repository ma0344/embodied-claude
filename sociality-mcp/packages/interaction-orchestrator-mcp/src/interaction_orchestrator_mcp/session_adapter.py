"""Load room-scoped conversation transcripts from social.db by session_id."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from social_core import (
    LEGACY_ROOM_SESSION_ID,
    ROOM_EVENT_SOURCES,
    SocialDB,
    get_social_db_path,
)

from .schemas import SessionTurn

_DEFAULT_HISTORY_LIMIT = 500
_UTTERANCE_KINDS = ("human_utterance", "agent_utterance")


class OrchestratorSessionAdapter(Protocol):
    """Read-side access to shared room transcripts."""

    def load_transcript(
        self,
        *,
        person_id: str,
        session_id: str,
        limit: int = _DEFAULT_HISTORY_LIMIT,
    ) -> list[SessionTurn]:
        ...


class SqliteRoomSessionAdapter:
    """Fetch the full room thread for one immutable session_id pointer."""

    def __init__(self, db: SocialDB | None = None, path: str | Path | None = None) -> None:
        self._db = db
        self._path = path

    def _connect(self) -> SocialDB:
        if self._db is not None:
            return self._db
        return SocialDB(self._path or get_social_db_path())

    def load_transcript(
        self,
        *,
        person_id: str,
        session_id: str,
        limit: int = _DEFAULT_HISTORY_LIMIT,
    ) -> list[SessionTurn]:
        if not session_id or not session_id.strip():
            return []

        db = self._connect()
        source_placeholders = ",".join("?" for _ in ROOM_EVENT_SOURCES)
        source_params = tuple(ROOM_EVENT_SOURCES)

        if session_id == LEGACY_ROOM_SESSION_ID:
            rows = db.fetchall(
                f"""
                SELECT event_id, ts, kind, payload_json
                FROM events
                WHERE person_id = ?
                  AND source IN ({source_placeholders})
                  AND kind IN ('human_utterance', 'agent_utterance')
                  AND session_id IS NULL
                ORDER BY ts DESC, event_seq DESC
                LIMIT ?
                """,
                (person_id, *source_params, limit),
            )
        else:
            rows = db.fetchall(
                f"""
                SELECT event_id, ts, kind, payload_json
                FROM events
                WHERE person_id = ?
                  AND source IN ({source_placeholders})
                  AND kind IN ('human_utterance', 'agent_utterance')
                  AND session_id = ?
                ORDER BY ts DESC, event_seq DESC
                LIMIT ?
                """,
                (person_id, *source_params, session_id, limit),
            )

        turns: list[SessionTurn] = []
        for row in reversed(rows):
            payload = json.loads(row["payload_json"])
            text = _extract_text(payload)
            if not text:
                continue
            sender = "ma" if row["kind"] == "human_utterance" else "koyori"
            turns.append(
                SessionTurn(
                    sender=sender,
                    text=text,
                    timestamp=row["ts"],
                    message_id=row["event_id"],
                )
            )
        return turns


class NullSessionAdapter:
    def load_transcript(
        self,
        *,
        person_id: str,
        session_id: str,
        limit: int = _DEFAULT_HISTORY_LIMIT,
    ) -> list[SessionTurn]:
        return []


def _extract_text(payload: dict) -> str:
    text = payload.get("text") or payload.get("message") or payload.get("content")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return ""


def make_default_session_adapter() -> OrchestratorSessionAdapter:
    backend = os.getenv("ORCHESTRATOR_SESSION_BACKEND", "auto").lower()
    if backend in {"null", "none", "off"}:
        return NullSessionAdapter()
    path = get_social_db_path()
    if backend == "sqlite" or (backend == "auto" and path.is_file()):
        return SqliteRoomSessionAdapter(path=path)
    return NullSessionAdapter()
