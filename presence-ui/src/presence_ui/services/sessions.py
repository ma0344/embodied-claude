"""Room session registry and metadata for Koyori's Room."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from social_core import (
    DEFAULT_ROOM_CLIENT_ID,
    LEGACY_ROOM_SESSION_ID,
    ROOM_EVENT_SOURCES,
    RoomSessionRegistry,
    utc_now,
)

from presence_ui.deps import get_stores
from presence_ui.schemas import (
    CreateSessionRequest,
    DeleteSessionResponse,
    RoomSession,
    SessionListResponse,
)

_LEGACY_SESSION_ID = LEGACY_ROOM_SESSION_ID
_DEFAULT_TITLE = "新しい部屋"


def legacy_session_id() -> str:
    return LEGACY_ROOM_SESSION_ID


def _registry() -> RoomSessionRegistry:
    return RoomSessionRegistry(get_stores().db)


def _source_sql_params() -> tuple[str, tuple[str, ...]]:
    placeholders = ",".join("?" for _ in ROOM_EVENT_SOURCES)
    return placeholders, ROOM_EVENT_SOURCES


def _storage_path() -> Path:
    base = Path(os.environ.get("PRESENCE_UI_HOME", str(Path.home() / ".claude" / "presence-ui")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "sessions.json"


def _load_registry() -> dict[str, dict]:
    path = _storage_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    sessions = raw.get("sessions")
    return sessions if isinstance(sessions, dict) else {}


def _save_registry(sessions: dict[str, dict]) -> None:
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _title_from_text(text: str, *, max_len: int = 42) -> str:
    line = text.strip().splitlines()[0] if text.strip() else _DEFAULT_TITLE
    if len(line) > max_len:
        return f"{line[: max_len - 1]}…"
    return line


def _migrate_json_to_db() -> None:
    """One-time mirror: sessions.json entries → social.db room_sessions."""
    registry = _registry()
    for session_id, record in _load_registry().items():
        if registry.get(session_id=session_id) is not None:
            continue
        registry.upsert(
            session_id=session_id,
            person_id=str(record.get("person_id") or "ma"),
            title=str(record.get("title") or _DEFAULT_TITLE),
            created_at=str(record.get("created_at") or utc_now()),
            updated_at=str(record.get("updated_at") or utc_now()),
            metadata={
                key: value
                for key, value in record.items()
                if key
                not in {
                    "session_id",
                    "person_id",
                    "title",
                    "created_at",
                    "updated_at",
                }
            },
        )


def _has_legacy_messages(*, person_id: str) -> bool:
    stores = get_stores()
    source_sql, source_params = _source_sql_params()
    row = stores.db.fetchone(
        f"""
        SELECT COUNT(*) AS cnt
        FROM events
        WHERE person_id = ?
          AND source IN ({source_sql})
          AND kind IN ('human_utterance', 'agent_utterance')
          AND session_id IS NULL
        """,
        (person_id, *source_params),
    )
    return bool(row and int(row["cnt"]) > 0)


def _session_stats(*, session_id: str, person_id: str) -> tuple[int, str | None, str | None]:
    stores = get_stores()
    source_sql, source_params = _source_sql_params()
    if session_id == _LEGACY_SESSION_ID:
        row = stores.db.fetchone(
            f"""
            SELECT COUNT(*) AS cnt, MIN(ts) AS first_ts, MAX(ts) AS last_ts
            FROM events
            WHERE person_id = ?
              AND source IN ({source_sql})
              AND kind IN ('human_utterance', 'agent_utterance')
              AND session_id IS NULL
            """,
            (person_id, *source_params),
        )
    else:
        lookup_ids = session_id_lookup_values(session_id)
        id_placeholders = ",".join("?" for _ in lookup_ids)
        row = stores.db.fetchone(
            f"""
            SELECT COUNT(*) AS cnt, MIN(ts) AS first_ts, MAX(ts) AS last_ts
            FROM events
            WHERE person_id = ?
              AND source IN ({source_sql})
              AND kind IN ('human_utterance', 'agent_utterance')
              AND session_id IN ({id_placeholders})
            """,
            (person_id, *source_params, *lookup_ids),
        )
    if not row:
        return 0, None, None
    return int(row["cnt"]), row["first_ts"], row["last_ts"]


def _ensure_legacy_session(*, person_id: str, registry: dict[str, dict]) -> bool:
    if not _has_legacy_messages(person_id=person_id):
        return False
    if _LEGACY_SESSION_ID in registry:
        return False
    _, first_ts, last_ts = _session_stats(session_id=_LEGACY_SESSION_ID, person_id=person_id)
    now = utc_now()
    registry[_LEGACY_SESSION_ID] = {
        "session_id": _LEGACY_SESSION_ID,
        "person_id": person_id,
        "title": "はじめの部屋",
        "created_at": first_ts or now,
        "updated_at": last_ts or now,
    }
    return True


def _to_room_session(record: dict, *, person_id: str) -> RoomSession:
    session_id = str(record["session_id"])
    count, first_ts, last_ts = _session_stats(session_id=session_id, person_id=person_id)
    return RoomSession(
        session_id=session_id,
        title=str(record.get("title") or _DEFAULT_TITLE),
        created_at=str(record.get("created_at") or first_ts or utc_now()),
        updated_at=str(
            last_ts or record.get("updated_at") or record.get("created_at") or utc_now()
        ),
        message_count=count,
    )


def list_sessions(*, person_id: str = "ma", limit: int = 40) -> SessionListResponse:
    json_registry = _load_registry()
    if _ensure_legacy_session(person_id=person_id, registry=json_registry):
        _save_registry(json_registry)
    _migrate_json_to_db()

    db_records = _registry().list_for_person(person_id=person_id, limit=limit)
    if db_records:
        items = [
            _to_room_session(
                {
                    "session_id": rec.session_id,
                    "person_id": rec.person_id,
                    "title": rec.title,
                    "created_at": rec.created_at,
                    "updated_at": rec.updated_at,
                    **rec.metadata,
                },
                person_id=person_id,
            )
            for rec in db_records
        ]
        return SessionListResponse(sessions=items)

    sessions = [
        rec for rec in json_registry.values() if str(rec.get("person_id", person_id)) == person_id
    ]
    sessions.sort(key=lambda rec: str(rec.get("updated_at") or ""), reverse=True)
    items = [_to_room_session(rec, person_id=person_id) for rec in sessions[:limit]]
    return SessionListResponse(sessions=items)


def get_session(*, session_id: str, person_id: str = "ma") -> RoomSession | None:
    _migrate_json_to_db()
    session_id = consolidate_to_canonical_session(session_id=session_id, person_id=person_id)
    db_record = _registry().get(session_id=session_id)
    if db_record is not None and db_record.person_id == person_id:
        return _to_room_session(
            {
                "session_id": db_record.session_id,
                "person_id": db_record.person_id,
                "title": db_record.title,
                "created_at": db_record.created_at,
                "updated_at": db_record.updated_at,
                **db_record.metadata,
            },
            person_id=person_id,
        )

    registry = _load_registry()
    if _ensure_legacy_session(person_id=person_id, registry=registry):
        _save_registry(registry)
    record = registry.get(session_id)
    if record is None and session_id != _LEGACY_SESSION_ID:
        return None
    if record is None:
        if not _has_legacy_messages(person_id=person_id):
            return None
        record = registry[_LEGACY_SESSION_ID]
    return _to_room_session(record, person_id=person_id)


def claude_code_session_id(jsonl_path: str | Path) -> str:
    """Claude Code sessionId — the JSONL file stem (UUID for imported sessions)."""
    stem = Path(jsonl_path).stem
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    return safe[:64]


def persistent_import_session_id(jsonl_path: str | Path) -> str:
    """Alias for claude_code_session_id (Claude Code sessionId is the room key)."""
    return claude_code_session_id(jsonl_path)


def legacy_import_session_id(canonical_id: str) -> str:
    """Pre-refactor import id (`room_imp_{uuid}`) kept for one-time migration."""
    return f"room_imp_{canonical_id}"[:64]


def canonicalize_session_id(session_id: str) -> str:
    """Normalize any session id to the Claude Code sessionId when applicable."""
    if session_id.startswith("room_imp_"):
        return session_id[len("room_imp_") :][:64]
    return session_id


def session_id_lookup_values(session_id: str) -> tuple[str, ...]:
    """Event rows may still use legacy `room_imp_*` ids until consolidated."""
    canonical = canonicalize_session_id(session_id)
    values: list[str] = []
    for candidate in (canonical, legacy_import_session_id(canonical), session_id):
        if candidate and candidate not in values:
            values.append(candidate)
    return tuple(values)


def consolidate_to_canonical_session(
    *,
    session_id: str,
    person_id: str = "ma",
) -> str:
    """Migrate legacy `room_imp_*` registry/events to Claude Code sessionId."""
    if session_id == _LEGACY_SESSION_ID:
        return _LEGACY_SESSION_ID
    canonical = canonicalize_session_id(session_id)
    legacy = legacy_import_session_id(canonical)
    if legacy == canonical:
        return canonical

    stores = get_stores()
    for from_id in (legacy, session_id):
        if from_id == canonical:
            continue
        stores.db.execute(
            """
            UPDATE events
            SET session_id = ?
            WHERE person_id = ? AND session_id = ?
            """,
            (canonical, person_id, from_id),
        )

    registry = _registry()
    for from_id in (legacy, session_id):
        if from_id == canonical:
            continue
        old = registry.get(session_id=from_id)
        if old is None:
            continue
        registry.upsert(
            session_id=canonical,
            person_id=old.person_id,
            title=old.title,
            created_at=old.created_at,
            updated_at=old.updated_at,
            metadata=old.metadata,
        )
        registry.delete(session_id=from_id)
        json_registry = _load_registry()
        if from_id in json_registry:
            json_registry[canonical] = {
                **json_registry[from_id],
                "session_id": canonical,
            }
            del json_registry[from_id]
            _save_registry(json_registry)

    pointer = registry.get_active(client_id=DEFAULT_ROOM_CLIENT_ID, person_id=person_id)
    if pointer is not None and pointer.session_id in {legacy, session_id}:
        registry.activate(
            client_id=pointer.client_id,
            person_id=person_id,
            session_id=canonical,
        )

    return canonical


def find_session_by_import_source(source_key: str) -> str | None:
    registry = _load_registry()
    for session_id, record in registry.items():
        if str(record.get("imported_from") or "") == source_key:
            return session_id
    return None


def find_session_by_jsonl_stem(jsonl_stem: str) -> str | None:
    registry = _load_registry()
    for session_id, record in registry.items():
        if str(record.get("jsonl_session_id") or "") == jsonl_stem:
            return session_id
    return None


def resolve_import_session_id(*, jsonl_path: Path) -> str:
    """Map a Claude Code JSONL file to its sessionId (file stem)."""
    source_key = str(jsonl_path.resolve())
    for existing in (
        find_session_by_import_source(source_key),
        find_session_by_jsonl_stem(jsonl_path.stem),
    ):
        if existing:
            return consolidate_to_canonical_session(session_id=existing)
    return claude_code_session_id(jsonl_path)


def ensure_session(
    *,
    session_id: str,
    person_id: str = "ma",
    title: str,
    created_at: str | None = None,
    extra: dict | None = None,
) -> RoomSession:
    registry = _load_registry()
    now = utc_now()
    record = registry.get(session_id)
    if record is None:
        record = {
            "session_id": session_id,
            "person_id": person_id,
            "title": _title_from_text(title, max_len=80),
            "created_at": created_at or now,
            "updated_at": now,
        }
        registry[session_id] = record
    else:
        if title and str(record.get("title") or "") in {_DEFAULT_TITLE, ""}:
            record["title"] = _title_from_text(title, max_len=80)
    if extra:
        record.update(extra)
    _save_registry(registry)
    metadata = {
        key: value
        for key, value in record.items()
        if key not in {"session_id", "person_id", "title", "created_at", "updated_at"}
    }
    _registry().upsert(
        session_id=session_id,
        person_id=person_id,
        title=str(record.get("title") or _DEFAULT_TITLE),
        created_at=str(record.get("created_at") or utc_now()),
        updated_at=str(record.get("updated_at") or utc_now()),
        metadata=metadata,
    )
    return _to_room_session(record, person_id=person_id)


def create_session(
    *,
    person_id: str = "ma",
    payload: CreateSessionRequest | None = None,
) -> RoomSession:
    payload = payload or CreateSessionRequest()
    session_id = str(uuid.uuid4())
    now = utc_now()
    title = (payload.title or "").strip() or _DEFAULT_TITLE
    record = {
        "session_id": session_id,
        "person_id": person_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }
    registry = _load_registry()
    registry[session_id] = record
    _save_registry(registry)
    _registry().upsert(
        session_id=session_id,
        person_id=person_id,
        title=title,
        created_at=now,
        updated_at=now,
    )
    return _to_room_session(record, person_id=person_id)


def touch_session(
    *,
    session_id: str,
    person_id: str = "ma",
    first_human_text: str | None = None,
) -> None:
    if session_id == _LEGACY_SESSION_ID:
        return
    registry = _load_registry()
    record = registry.get(session_id)
    if record is None:
        return
    now = utc_now()
    record["updated_at"] = now
    if first_human_text and str(record.get("title") or "") == _DEFAULT_TITLE:
        record["title"] = _title_from_text(first_human_text)
    _save_registry(registry)
    _registry().touch(session_id=session_id, title=str(record.get("title") or _DEFAULT_TITLE))


def activate_session(
    *,
    session_id: str,
    person_id: str = "ma",
    client_id: str = DEFAULT_ROOM_CLIENT_ID,
) -> dict[str, str]:
    """Mark a room as the active shared pointer for a client (Web UI or CLI)."""
    session_id = consolidate_to_canonical_session(session_id=session_id, person_id=person_id)
    room = get_session(session_id=session_id, person_id=person_id)
    if room is None:
        raise ValueError(f"unknown session: {session_id}")
    _registry().upsert(
        session_id=session_id,
        person_id=person_id,
        title=room.title,
        created_at=room.created_at,
        updated_at=room.updated_at,
    )
    pointer = _registry().activate(
        client_id=client_id,
        person_id=person_id,
        session_id=session_id,
    )
    _write_active_pointer_file(client_id=client_id, person_id=person_id, session_id=session_id)
    return {
        "client_id": pointer.client_id,
        "person_id": pointer.person_id,
        "session_id": pointer.session_id,
        "activated_at": pointer.activated_at,
    }


def get_active_session(
    *,
    person_id: str = "ma",
    client_id: str = DEFAULT_ROOM_CLIENT_ID,
) -> dict[str, str] | None:
    """Return the session_id a client is currently joined to (CLI / Web UI)."""
    pointer = _registry().get_active(client_id=client_id, person_id=person_id)
    if pointer is None:
        return None
    return {
        "client_id": pointer.client_id,
        "person_id": pointer.person_id,
        "session_id": pointer.session_id,
        "activated_at": pointer.activated_at,
    }


def _active_pointer_path() -> Path:
    base = Path(os.environ.get("PRESENCE_UI_HOME", str(Path.home() / ".claude" / "presence-ui")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "active-session.json"


def _write_active_pointer_file(*, client_id: str, person_id: str, session_id: str) -> None:
    path = _active_pointer_path()
    data: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (json.JSONDecodeError, OSError):
            data = {}
    data[client_id] = {
        "person_id": person_id,
        "session_id": session_id,
        "activated_at": utc_now(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _delete_room_events(*, person_id: str, session_id: str) -> int:
    stores = get_stores()
    source_sql, source_params = _source_sql_params()
    if session_id == _LEGACY_SESSION_ID:
        cursor = stores.db.execute(
            f"""
            DELETE FROM events
            WHERE person_id = ?
              AND source IN ({source_sql})
              AND kind IN ('human_utterance', 'agent_utterance')
              AND session_id IS NULL
            """,
            (person_id, *source_params),
        )
    else:
        lookup_ids = session_id_lookup_values(session_id)
        id_placeholders = ",".join("?" for _ in lookup_ids)
        cursor = stores.db.execute(
            f"""
            DELETE FROM events
            WHERE person_id = ?
              AND source IN ({source_sql})
              AND kind IN ('human_utterance', 'agent_utterance')
              AND session_id IN ({id_placeholders})
            """,
            (person_id, *source_params, *lookup_ids),
        )
    return int(cursor.rowcount)


def delete_session(*, session_id: str, person_id: str = "ma") -> DeleteSessionResponse:
    """Remove a room from the registry and delete its chat events from social.db."""
    registry = _load_registry()
    record = registry.get(session_id)

    if session_id != _LEGACY_SESSION_ID and record is None:
        raise ValueError(f"unknown session: {session_id}")

    was_imported = bool(record and record.get("imported_from"))
    deleted_count = _delete_room_events(person_id=person_id, session_id=session_id)

    if session_id in registry:
        del registry[session_id]
        _save_registry(registry)
    _registry().delete(session_id=session_id)

    return DeleteSessionResponse(
        session_id=session_id,
        deleted_message_count=deleted_count,
        was_imported=was_imported,
    )
