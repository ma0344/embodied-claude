"""Persist room utterances to social.db (+ open loops for human turns)."""

from __future__ import annotations

from social_core import utc_now

from relationship_mcp.schemas import DismissOutcome

from presence_ui.deps import get_stores
from presence_ui.services.room_events import ROOM_WRITE_SOURCE


def ingest_human_turn(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
) -> tuple[str, DismissOutcome]:
    """Record human speech; refresh or close/cancel relationship threads."""

    stores = get_stores()
    when = ts or utc_now()
    result = stores.social_state.ingest_social_event(
        {
            "ts": when,
            "source": ROOM_WRITE_SOURCE,
            "kind": "human_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        }
    )
    event_id = str(result.get("event_id") or "")
    outcome = DismissOutcome()
    try:
        outcome = stores.relationship.note_human_utterance_for_loops(
            person_id=person_id,
            text=text,
            ts=when,
            source_event_id=event_id,
        )
    except Exception:
        pass
    return event_id, outcome


def ingest_agent_turn(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
) -> str:
    """Record Koyori's spoken reply (no open-loop inference on agent text)."""

    stores = get_stores()
    when = ts or utc_now()
    result = stores.social_state.ingest_social_event(
        {
            "ts": when,
            "source": ROOM_WRITE_SOURCE,
            "kind": "agent_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        }
    )
    return str(result.get("event_id") or "")
