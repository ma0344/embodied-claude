"""Room session transcript adapter tests."""

from __future__ import annotations

import json

from interaction_orchestrator_mcp.session_adapter import SqliteRoomSessionAdapter
from social_core import SocialDB
from social_core.events import EventStore, SocialEventCreate


def test_load_transcript_by_session_id(tmp_path) -> None:
    db = SocialDB(tmp_path / "social.db")
    events = EventStore(db)
    session_id = "room_test123"

    for kind, text in (
        ("human_utterance", "部屋で話そ"),
        ("agent_utterance", "うん"),
    ):
        events.ingest(
            SocialEventCreate(
                ts="2026-06-10T12:00:00+00:00",
                source="room",
                kind=kind,
                person_id="ma",
                session_id=session_id,
                confidence=1.0,
                payload={"text": text},
            )
        )

    adapter = SqliteRoomSessionAdapter(db=db)
    turns = adapter.load_transcript(person_id="ma", session_id=session_id)
    assert len(turns) == 2
    assert turns[0].text == "部屋で話そ"
    assert turns[1].sender == "koyori"

    # Legacy presence-ui source still readable in the same room pointer.
    events.ingest(
        SocialEventCreate(
            ts="2026-06-10T12:01:00+00:00",
            source="presence-ui",
            kind="human_utterance",
            person_id="ma",
            session_id=session_id,
            confidence=1.0,
            payload={"text": "続き"},
        )
    )
    turns = adapter.load_transcript(person_id="ma", session_id=session_id)
    assert len(turns) == 3
    assert turns[-1].text == "続き"
