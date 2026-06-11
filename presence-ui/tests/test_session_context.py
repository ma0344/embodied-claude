"""Session reference architecture — orchestrator loads history by session_id."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    ResponseContract,
)
from social_core import SocialDB
from social_core.events import EventStore, SocialEventCreate

from presence_ui.services import sessions as sessions_mod
from presence_ui.services.interact import _compose_and_plan
from presence_ui.services.room_events import ROOM_WRITE_SOURCE


@pytest.fixture
def room_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    social_db = SocialDB(tmp_path / "social.db")
    events = EventStore(social_db)
    store = tmp_path / "sessions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_mod, "_storage_path", lambda: store)
    monkeypatch.setattr(sessions_mod, "_has_legacy_messages", lambda **_: False)

    class Stores:
        db = social_db

    monkeypatch.setattr(sessions_mod, "get_stores", lambda: Stores())
    monkeypatch.setattr("presence_ui.services.chat.get_stores", lambda: Stores())

    session = sessions_mod.create_session(person_id="ma", payload=None)
    session_id = session.session_id

    for kind, text in (
        ("human_utterance", "部屋Aの1番目"),
        ("agent_utterance", "うん、聞いてるで"),
        ("human_utterance", "部屋Aの2番目"),
    ):
        events.ingest(
            SocialEventCreate(
                ts="2026-06-10T12:00:00+00:00",
                source=ROOM_WRITE_SOURCE,
                kind=kind,
                person_id="ma",
                session_id=session_id,
                confidence=1.0,
                payload={"text": text},
            )
        )

    return Stores(), session_id


def test_chat_reads_shared_room_events(room_db) -> None:
    from presence_ui.services.chat import fetch_session_transcript

    _, session_id = room_db
    messages = fetch_session_transcript(person_id="ma", session_id=session_id)
    assert len(messages) == 3
    assert messages[0].message == "部屋Aの1番目"


def test_compose_and_plan_sends_session_id_only(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_compose(payload, **kwargs):
        captured["payload"] = payload
        return InteractionContext(
            ts="2026-06-10T12:00:00+00:00",
            local_time="2026-06-10T21:00:00+09:00",
            timezone="Asia/Tokyo",
            agent_state=AgentStateSummary(ts="2026-06-10T12:00:00+00:00"),
            response_contract=ResponseContract(),
            prompt_summary="test",
            compact_prompt_block="ctx",
            session_context_block="room",
        )

    monkeypatch.setattr(
        "presence_ui.services.interact.compose_interaction_context",
        fake_compose,
    )
    monkeypatch.setattr(
        "presence_ui.services.interact.plan_response",
        lambda payload: MagicMock(primary_move="answer_directly"),
    )
    monkeypatch.setattr(
        "presence_ui.services.interact.get_stores",
        lambda: SimpleNamespace(
            social_state=MagicMock(),
            relationship=MagicMock(),
            joint_attention=MagicMock(),
            boundary=MagicMock(),
            self_narrative=MagicMock(),
            orchestrator=MagicMock(),
            policy_timezone="Asia/Tokyo",
        ),
    )

    _compose_and_plan(person_id="ma", session_id="room_test", text="続き")
    payload = captured["payload"]
    assert payload.session_id == "room_test"
    assert payload.session_history == []
    assert payload.max_chars == 10000


@pytest.mark.skip(reason="Legacy activate endpoint removed in gateway mode")
def test_activate_session_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    from fastapi.testclient import TestClient

    from presence_ui.main import create_app

    store = tmp_path / "presence-ui" / "sessions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_mod, "_storage_path", lambda: store)
    monkeypatch.setattr(sessions_mod, "_has_legacy_messages", lambda **_: False)

    local = threading.local()

    def get_stores():
        stores = getattr(local, "stores", None)
        if stores is None:
            social_db = SocialDB(tmp_path / "social.db")

            class Stores:
                db = social_db

            local.stores = Stores()
            stores = local.stores
        return stores

    monkeypatch.setattr(sessions_mod, "get_stores", get_stores)
    monkeypatch.setattr("presence_ui.services.chat.get_stores", get_stores)
    monkeypatch.setattr("presence_ui.deps.get_stores", get_stores)

    created = sessions_mod.create_session(person_id="ma")
    client = TestClient(create_app())

    activated = client.post(f"/api/v1/sessions/{created.session_id}/activate", json={})
    assert activated.status_code == 200
    assert activated.json()["session_id"] == created.session_id

    active = client.get("/api/v1/sessions/active?client_id=koyori-room")
    assert active.status_code == 200
    assert active.json()["session_id"] == created.session_id
