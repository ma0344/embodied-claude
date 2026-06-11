"""Chat service unit tests."""

from __future__ import annotations

import json

import pytest
from social_core import SocialDB
from social_core.events import EventStore

from presence_ui.services.chat import _extract_text, _messages_from_room_events, fetch_chat_history
from presence_ui.services.session_log import _content_blocks, _should_skip_user_text


def test_extract_text_from_payload() -> None:
    assert _extract_text({"text": "  hello  "}) == "hello"
    assert _extract_text({"message": "hey"}) == "hey"
    assert _extract_text({}) == ""


def test_content_blocks_user_string() -> None:
    assert _content_blocks("  こんにちは  ") == [("prompt", "こんにちは")]


def test_skip_tool_interrupted() -> None:
    assert _should_skip_user_text("[Request interrupted by user for tool use]") is True
    assert _should_skip_user_text("まー、おはよう") is False


def test_room_events_filters_presence_ui_source(monkeypatch) -> None:
    class FakeRow:
        def __init__(self, ts: str, kind: str, payload: dict, *, session_id: str) -> None:
            self._data = {
                "event_id": f"evt_{kind}_{ts}",
                "session_id": session_id,
                "ts": ts,
                "kind": kind,
                "payload_json": json.dumps(payload),
            }

        def __getitem__(self, key: str):
            return self._data[key]

    class FakeDB:
        def fetchall(self, sql: str, params: tuple) -> list[FakeRow]:
            assert "room" in params
            assert "room_test" in params
            return [
                FakeRow(
                    "2026-06-10T10:00:05+00:00",
                    "agent_utterance",
                    {"text": "yo"},
                    session_id="room_test",
                ),
                FakeRow(
                    "2026-06-10T10:00:00+00:00",
                    "human_utterance",
                    {"text": "hi"},
                    session_id="room_test",
                ),
            ]

    class FakeStores:
        db = FakeDB()

    monkeypatch.setattr("presence_ui.services.chat.get_stores", lambda: FakeStores())
    messages = _messages_from_room_events(person_id="ma", session_id="room_test", limit=10)
    assert [m.sender for m in messages] == ["ma", "koyori"]
    assert all(m.session_id == "room_test" for m in messages)
    assert all(m.message_id for m in messages)


@pytest.fixture
def social_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "social.db"
    db = SocialDB(db_path)
    events = EventStore(db)

    class Stores:
        def __init__(self) -> None:
            self.db = db
            self.events = events

    stores = Stores()
    monkeypatch.setattr("presence_ui.services.chat.get_stores", lambda: stores)
    return events


def _ingest_chat(
    events: EventStore,
    *,
    session_id: str | None,
    kind: str,
    text: str,
    ts: str,
) -> None:
    events.ingest(
        {
            "ts": ts,
            "source": "presence-ui",
            "kind": kind,
            "person_id": "ma",
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text},
        }
    )


def test_fetch_chat_history_isolates_sessions(social_db: EventStore) -> None:
    _ingest_chat(
        social_db,
        session_id="room_a",
        kind="human_utterance",
        text="room A only",
        ts="2026-06-10T10:00:00+00:00",
    )
    _ingest_chat(
        social_db,
        session_id="room_b",
        kind="human_utterance",
        text="room B only",
        ts="2026-06-10T10:00:01+00:00",
    )
    _ingest_chat(
        social_db,
        session_id=None,
        kind="human_utterance",
        text="legacy bucket",
        ts="2026-06-10T10:00:02+00:00",
    )
    social_db.ingest(
        {
            "ts": "2026-06-10T10:00:04+00:00",
            "source": "hook",
            "kind": "human_utterance",
            "person_id": "ma",
            "session_id": None,
            "confidence": 1.0,
            "payload": {"text": "hook global"},
        }
    )

    room_a = fetch_chat_history(person_id="ma", session_id="room_a", limit=20)
    room_b = fetch_chat_history(person_id="ma", session_id="room_b", limit=20)
    legacy = fetch_chat_history(person_id="ma", session_id="room_legacy", limit=20)

    assert [m.message for m in room_a.messages] == ["room A only"]
    assert [m.message for m in room_b.messages] == ["room B only"]
    assert [m.message for m in legacy.messages] == ["legacy bucket"]
    assert all(m.session_id == "room_a" for m in room_a.messages)
    assert all(m.session_id == "room_b" for m in room_b.messages)
