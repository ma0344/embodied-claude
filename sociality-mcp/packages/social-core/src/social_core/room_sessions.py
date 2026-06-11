"""Persistent room session registry and active-session pointers in social.db."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .db import SocialDB
from .time import utc_now

# Canonical + legacy sources that share one room transcript per session_id.
ROOM_EVENT_SOURCES: tuple[str, ...] = ("room", "presence-ui", "chat", "claude-code")
LEGACY_ROOM_SESSION_ID = "room_legacy"
DEFAULT_ROOM_CLIENT_ID = "koyori-room"


@dataclass(frozen=True, slots=True)
class RoomSessionRecord:
    session_id: str
    person_id: str
    title: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ActiveSessionPointer:
    client_id: str
    person_id: str
    session_id: str
    activated_at: str


class RoomSessionRegistry:
    """Immutable session_id registry — rooms are pointers, not copied payloads."""

    def __init__(self, db: SocialDB) -> None:
        self.db = db

    def upsert(
        self,
        *,
        session_id: str,
        person_id: str,
        title: str,
        created_at: str | None = None,
        updated_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RoomSessionRecord:
        now = utc_now()
        existing = self.get(session_id=session_id)
        created = created_at or (existing.created_at if existing else now)
        updated = updated_at or now
        meta_json = json.dumps(metadata or (existing.metadata if existing else {}), ensure_ascii=False)
        self.db.execute(
            """
            INSERT INTO room_sessions(
                session_id, person_id, title, created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                person_id = excluded.person_id,
                title = excluded.title,
                updated_at = excluded.updated_at,
                metadata_json = excluded.metadata_json
            """,
            (session_id, person_id, title, created, updated, meta_json),
        )
        record = self.get(session_id=session_id)
        if record is None:
            raise RuntimeError(f"failed to upsert room session: {session_id}")
        return record

    def get(self, *, session_id: str) -> RoomSessionRecord | None:
        row = self.db.fetchone(
            "SELECT * FROM room_sessions WHERE session_id = ?",
            (session_id,),
        )
        if row is None:
            return None
        return _row_to_record(row)

    def list_for_person(self, *, person_id: str, limit: int = 40) -> list[RoomSessionRecord]:
        rows = self.db.fetchall(
            """
            SELECT * FROM room_sessions
            WHERE person_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (person_id, limit),
        )
        return [_row_to_record(row) for row in rows]

    def delete(self, *, session_id: str) -> None:
        self.db.execute("DELETE FROM session_pointers WHERE active_session_id = ?", (session_id,))
        self.db.execute("DELETE FROM room_sessions WHERE session_id = ?", (session_id,))

    def touch(
        self,
        *,
        session_id: str,
        title: str | None = None,
        updated_at: str | None = None,
    ) -> None:
        record = self.get(session_id=session_id)
        if record is None:
            return
        self.upsert(
            session_id=session_id,
            person_id=record.person_id,
            title=title or record.title,
            created_at=record.created_at,
            updated_at=updated_at or utc_now(),
            metadata=record.metadata,
        )

    def activate(
        self,
        *,
        client_id: str,
        person_id: str,
        session_id: str,
    ) -> ActiveSessionPointer:
        if self.get(session_id=session_id) is None:
            raise ValueError(f"unknown session: {session_id}")
        activated_at = utc_now()
        self.db.execute(
            """
            INSERT INTO session_pointers(client_id, person_id, active_session_id, activated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(client_id, person_id) DO UPDATE SET
                active_session_id = excluded.active_session_id,
                activated_at = excluded.activated_at
            """,
            (client_id, person_id, session_id, activated_at),
        )
        return ActiveSessionPointer(
            client_id=client_id,
            person_id=person_id,
            session_id=session_id,
            activated_at=activated_at,
        )

    def get_active(
        self,
        *,
        client_id: str,
        person_id: str,
    ) -> ActiveSessionPointer | None:
        row = self.db.fetchone(
            """
            SELECT client_id, person_id, active_session_id, activated_at
            FROM session_pointers
            WHERE client_id = ? AND person_id = ?
            """,
            (client_id, person_id),
        )
        if row is None:
            return None
        return ActiveSessionPointer(
            client_id=str(row["client_id"]),
            person_id=str(row["person_id"]),
            session_id=str(row["active_session_id"]),
            activated_at=str(row["activated_at"]),
        )


def _row_to_record(row: Any) -> RoomSessionRecord:
    raw_meta = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
    try:
        metadata = json.loads(raw_meta or "{}")
    except json.JSONDecodeError:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return RoomSessionRecord(
        session_id=str(row["session_id"]),
        person_id=str(row["person_id"]),
        title=str(row["title"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        metadata=metadata,
    )
