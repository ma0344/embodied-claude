"""Session-scoped chat history for Koyori's Room (shared pointer, not copied payloads)."""



from __future__ import annotations

import json

from social_core import LEGACY_ROOM_SESSION_ID, ROOM_EVENT_SOURCES

from presence_ui.deps import get_stores
from presence_ui.schemas import ChatMessage, ChatResponse
from presence_ui.services.sessions import (
    canonicalize_session_id,
    session_id_lookup_values,
)

_UTTERANCE_KINDS = ("human_utterance", "agent_utterance")





def _source_sql_params() -> tuple[str, tuple[str, ...]]:

    placeholders = ",".join("?" for _ in ROOM_EVENT_SOURCES)

    return placeholders, ROOM_EVENT_SOURCES





def _extract_text(payload: dict) -> str:

    text = payload.get("text") or payload.get("message") or payload.get("content")

    if isinstance(text, str) and text.strip():

        return text.strip()

    return ""





def _messages_from_room_events(

    *,

    person_id: str,

    session_id: str,

    limit: int,

) -> list[ChatMessage]:

    """Return utterances for exactly one room session_id across all room clients."""

    if not session_id or not session_id.strip():

        raise ValueError("session_id is required")



    stores = get_stores()

    source_sql, source_params = _source_sql_params()



    if session_id == LEGACY_ROOM_SESSION_ID:

        rows = stores.db.fetchall(

            f"""

            SELECT event_id, session_id, ts, kind, payload_json

            FROM events

            WHERE person_id = ?

              AND source IN ({source_sql})

              AND kind IN ('human_utterance', 'agent_utterance')

              AND session_id IS NULL

            ORDER BY ts DESC, event_seq DESC

            LIMIT ?

            """,

            (person_id, *source_params, limit),

        )

    else:
        lookup_ids = session_id_lookup_values(session_id)
        id_placeholders = ",".join("?" for _ in lookup_ids)
        rows = stores.db.fetchall(
            f"""
            SELECT event_id, session_id, ts, kind, payload_json
            FROM events
            WHERE person_id = ?
              AND source IN ({source_sql})
              AND kind IN ('human_utterance', 'agent_utterance')
              AND session_id IN ({id_placeholders})
            ORDER BY ts DESC, event_seq DESC
            LIMIT ?
            """,
            (person_id, *source_params, *lookup_ids, limit),
        )



    messages: list[ChatMessage] = []

    for row in reversed(rows):

        if session_id != LEGACY_ROOM_SESSION_ID and row["session_id"] != session_id:

            continue

        payload = json.loads(row["payload_json"])

        text = _extract_text(payload)

        if not text:

            continue

        sender = "ma" if row["kind"] == "human_utterance" else "koyori"

        messages.append(

            ChatMessage(

                sender=sender,

                message=text,

                timestamp=row["ts"],

                message_id=row["event_id"],

                session_id=row["session_id"] or LEGACY_ROOM_SESSION_ID,

            )

        )

    return messages





def fetch_session_transcript(

    *,

    person_id: str = "ma",

    session_id: str,

    limit: int = 500,

) -> list[ChatMessage]:

    """Room-scoped utterances for compose/plan (higher limit than UI pagination)."""

    return _messages_from_room_events(

        person_id=person_id,

        session_id=session_id,

        limit=limit,

    )





def fetch_chat_history(
    *,
    person_id: str = "ma",
    session_id: str,
    limit: int = 80,
) -> ChatResponse:
    canonical = canonicalize_session_id(session_id)
    messages = _messages_from_room_events(
        person_id=person_id,
        session_id=canonical,
        limit=limit,
    )
    return ChatResponse(session_id=canonical, messages=messages)


