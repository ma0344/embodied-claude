"""Persistent import session id mapping tests — legacy ID mapping removed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from presence_ui.services.sessions import (
    ensure_session,
    find_session_by_import_source,
    persistent_import_session_id,
    resolve_import_session_id,
)

pytestmark = pytest.mark.skip(
    reason="room_imp_* mapping removed; Claude Code sessionId is canonical",
)


def test_persistent_import_session_id_from_jsonl_stem() -> None:
    path = Path(
        r"C:\Users\ma\.claude\projects\C--repo\6afd3195-1f52-4474-b3be-714d48e958aa.jsonl"
    )
    assert persistent_import_session_id(path) == "6afd3195-1f52-4474-b3be-714d48e958aa"


def test_resolve_import_session_id_prefers_existing_mapping(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "home"
    root.mkdir()
    store = root / "presence-ui" / "sessions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    jsonl = root / "abc.jsonl"
    jsonl.write_text("{}", encoding="utf-8")
    source = str(jsonl.resolve())
    store.write_text(
        json.dumps(
            {
                "sessions": {
                    "room_oldcopy": {
                        "session_id": "room_oldcopy",
                        "person_id": "ma",
                        "title": "old",
                        "imported_from": source,
                        "created_at": "2026-06-10T10:00:00+00:00",
                        "updated_at": "2026-06-10T10:00:00+00:00",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "presence_ui.services.sessions._storage_path",
        lambda: store,
    )
    assert resolve_import_session_id(jsonl_path=jsonl) == "room_oldcopy"
    assert find_session_by_import_source(source) == "room_oldcopy"


def test_ensure_session_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "home"
    root.mkdir()
    store = root / "presence-ui" / "sessions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("presence_ui.services.sessions._storage_path", lambda: store)
    monkeypatch.setattr(
        "presence_ui.services.sessions._has_legacy_messages",
        lambda **_: False,
    )
    monkeypatch.setattr(
        "presence_ui.services.sessions._session_stats",
        lambda **_: (0, None, None),
    )

    first = ensure_session(session_id="room_imp_test", person_id="ma", title="部屋A")
    second = ensure_session(session_id="room_imp_test", person_id="ma", title="部屋A")
    assert first.session_id == second.session_id == "room_imp_test"
