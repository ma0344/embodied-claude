"""Room session registry tests — legacy; gateway mode uses Claude Code sessionId only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from presence_ui.schemas import CreateSessionRequest
from presence_ui.services import sessions as sessions_mod

pytestmark = pytest.mark.skip(reason="Legacy session registry removed from gateway UI")


@pytest.fixture
def session_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "presence-ui" / "sessions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_mod, "_storage_path", lambda: store)
    return store


@pytest.fixture
def isolated_social_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import threading

    from social_core import SocialDB

    local = threading.local()

    def get_stores():
        stores = getattr(local, "stores", None)
        if stores is None:
            db = SocialDB(tmp_path / "social.db")

            class Stores:
                pass

            stores = Stores()
            stores.db = db
            local.stores = stores
        return local.stores

    monkeypatch.setattr(sessions_mod, "get_stores", get_stores)
    monkeypatch.setattr("presence_ui.services.chat.get_stores", get_stores)
    return get_stores


def test_create_and_list_sessions(
    session_store: Path,
    isolated_social_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sessions_mod, "_has_legacy_messages", lambda **_: False)
    created = sessions_mod.create_session(person_id="ma")
    assert len(created.session_id) >= 12
    assert created.title == "新しい部屋"

    listed = sessions_mod.list_sessions(person_id="ma")
    assert len(listed.sessions) == 1
    assert listed.sessions[0].session_id == created.session_id


def test_touch_session_updates_title(session_store: Path, isolated_social_db) -> None:
    created = sessions_mod.create_session(person_id="ma")
    sessions_mod.touch_session(
        session_id=created.session_id,
        person_id="ma",
        first_human_text="おはよう、こより",
    )
    updated = sessions_mod.get_session(session_id=created.session_id, person_id="ma")
    assert updated is not None
    assert updated.title == "おはよう、こより"


def test_create_session_with_custom_title(session_store: Path, isolated_social_db) -> None:
    created = sessions_mod.create_session(
        person_id="ma",
        payload=CreateSessionRequest(title="夜の部屋"),
    )
    assert created.title == "夜の部屋"
    raw = json.loads(session_store.read_text(encoding="utf-8"))
    assert raw["sessions"][created.session_id]["title"] == "夜の部屋"


def test_delete_session_removes_registry_and_events(
    session_store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from social_core import SocialDB
    from social_core.events import EventStore, SocialEventCreate

    social_db = SocialDB(tmp_path / "social.db")
    events = EventStore(social_db)

    class Stores:
        db = social_db

    monkeypatch.setattr(sessions_mod, "get_stores", lambda: Stores())
    monkeypatch.setattr(sessions_mod, "_has_legacy_messages", lambda **_: False)

    created = sessions_mod.create_session(person_id="ma")
    for kind, text in (
        ("human_utterance", "削除テスト"),
        ("agent_utterance", "うん"),
    ):
        events.ingest(
            SocialEventCreate(
                ts="2026-06-10T12:00:00+00:00",
                source="presence-ui",
                kind=kind,
                person_id="ma",
                session_id=created.session_id,
                confidence=1.0,
                payload={"text": text},
            )
        )

    refreshed = sessions_mod.get_session(session_id=created.session_id, person_id="ma")
    assert refreshed is not None
    assert refreshed.message_count == 2

    result = sessions_mod.delete_session(session_id=created.session_id, person_id="ma")
    assert result.deleted_message_count == 2
    assert sessions_mod.get_session(session_id=created.session_id, person_id="ma") is None
    raw = json.loads(session_store.read_text(encoding="utf-8"))
    assert created.session_id not in raw["sessions"]
