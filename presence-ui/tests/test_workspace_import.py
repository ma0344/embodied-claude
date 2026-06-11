"""Workspace JSONL import tests — legacy; gateway reads history from Claude Code 8080."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
from presence_ui.schemas import ImportWorkspaceRequest
from presence_ui.services import sessions as sessions_mod
from presence_ui.services import workspace_import as import_mod
from presence_ui.services.session_log import _encode_project_path

pytestmark = pytest.mark.skip(reason="Legacy import path removed from gateway UI")


@pytest.fixture
def session_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "presence-ui" / "sessions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sessions_mod, "_storage_path", lambda: store)
    return store


@pytest.fixture
def claude_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    project_path = str(tmp_path / "embodied-claude")
    claude_home = tmp_path / ".claude"
    encoded = _encode_project_path(project_path)
    project_dir = claude_home / "projects" / encoded
    project_dir.mkdir(parents=True)

    jsonl_path = project_dir / "abc12345-aaaa-bbbb-cccc-ddddeeeeffff.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2026-06-10T10:00:00+00:00",
                        "message": {
                            "content": [{"type": "text", "text": "仕事の続き、ここで話そ"}],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-06-10T10:00:05+00:00",
                        "message": {
                            "content": [{"type": "text", "text": "うん、聞いてるで"}],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(import_mod, "get_claude_home", lambda: claude_home)
    monkeypatch.setattr(
        "presence_ui.services.session_log.get_claude_home",
        lambda: claude_home,
    )
    monkeypatch.setenv("PRESENCE_PROJECT_PATH", project_path)
    return claude_home, project_dir, jsonl_path


@pytest.fixture
def fake_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    import threading

    from social_core import SocialDB
    from social_core.events import EventStore

    ingested: list[dict] = []
    local = threading.local()

    def get_stores():
        stores = getattr(local, "stores", None)
        if stores is None:
            db = SocialDB(tmp_path / "social.db")
            events = EventStore(db)

            class FakeSocialState:
                def ingest_social_event(self, event: dict) -> dict[str, str]:
                    stored = events.ingest(event)
                    event_id = stored.event_id
                    ingested.append({**event, "event_id": event_id})
                    return {"event_id": event_id}

            class FakeStores:
                pass

            stores = FakeStores()
            stores.db = db
            stores.social_state = FakeSocialState()
            local.stores = stores
        return local.stores

    monkeypatch.setattr(import_mod, "get_stores", get_stores)
    monkeypatch.setattr(sessions_mod, "get_stores", get_stores)
    monkeypatch.setattr("presence_ui.services.chat.get_stores", get_stores)
    monkeypatch.setattr("presence_ui.deps.get_stores", get_stores)
    return ingested


def test_list_workspace_jsonl_files(claude_workspace: tuple[Path, Path, Path]) -> None:
    _, project_dir, jsonl_path = claude_workspace
    result = import_mod.list_workspace_jsonl_files()
    assert any(entry["project_dir"] == str(project_dir) for entry in result.project_dirs)
    assert len(result.files) == 1
    assert result.files[0].session_file_id == jsonl_path.stem
    assert result.files[0].message_count == 2


def test_import_workspace_jsonl_truncates_long_title(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, project_dir, _ = claude_workspace
    jsonl_path = project_dir / "long-title-session.jsonl"
    long_title = "あ" * 120
    jsonl_path.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-06-10T10:00:00+00:00",
                "message": {"content": [{"type": "text", "text": long_title}]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem, force=True),
        person_id="ma",
    )
    assert len(result.session.title) <= 80


def test_import_workspace_jsonl_creates_session(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, _, jsonl_path = claude_workspace
    result = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem),
        person_id="ma",
    )
    assert result.imported_count == 2
    assert result.already_imported is False
    assert result.session.session_id == sessions_mod.persistent_import_session_id(jsonl_path)
    assert result.session.message_count == 2
    assert len(fake_stores) == 2
    assert fake_stores[0]["kind"] == "human_utterance"
    assert fake_stores[1]["kind"] == "agent_utterance"
    assert fake_stores[0]["session_id"] == result.session.session_id

    raw = json.loads(session_store.read_text(encoding="utf-8"))
    record = raw["sessions"][result.session.session_id]
    assert record["imported_from"].endswith(jsonl_path.name)


def test_import_workspace_jsonl_syncs_new_messages(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, project_dir, jsonl_path = claude_workspace
    first = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem),
        person_id="ma",
    )
    assert first.imported_count == 2

    jsonl_path.write_text(
        jsonl_path.read_text(encoding="utf-8")
        + "\n"
        + json.dumps(
            {
                "type": "user",
                "timestamp": "2026-06-10T11:00:00+00:00",
                "message": {"content": [{"type": "text", "text": "追加分"}]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    second = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem),
        person_id="ma",
    )
    assert second.session.session_id == first.session.session_id
    assert second.imported_count == 1
    assert len(fake_stores) == 3


def test_import_workspace_jsonl_force_reimports_all(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, _, jsonl_path = claude_workspace
    first = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem),
        person_id="ma",
    )
    assert first.imported_count == 2

    jsonl_path.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-06-10T12:00:00+00:00",
                "message": {"content": [{"type": "text", "text": "書き換え後"}]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    forced = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem, force=True),
        person_id="ma",
    )
    assert forced.session.session_id == first.session.session_id
    assert forced.imported_count == 1
    from presence_ui.services.chat import fetch_session_transcript

    messages = fetch_session_transcript(
        person_id="ma",
        session_id=forced.session.session_id,
    )
    assert len(messages) == 1
    assert messages[0].message == "書き換え後"


def test_import_workspace_jsonl_is_idempotent(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, _, jsonl_path = claude_workspace
    first = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem),
        person_id="ma",
    )
    second = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(session_file_id=jsonl_path.stem),
        person_id="ma",
    )
    assert second.already_imported is True
    assert second.session.session_id == first.session.session_id
    assert len(fake_stores) == 2


def test_import_workspace_jsonl_use_latest(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, project_dir, _ = claude_workspace
    older = project_dir / "older-session.jsonl"
    older.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-06-09T10:00:00+00:00",
                "message": {"content": [{"type": "text", "text": "old"}]},
            }
        ),
        encoding="utf-8",
    )
    newest = next(path for path in project_dir.glob("abc12345*.jsonl"))
    newest.touch()
    result = import_mod.import_workspace_jsonl(
        payload=ImportWorkspaceRequest(use_latest=True),
        person_id="ma",
    )
    assert result.imported_count == 2
    assert newest.name in result.source_jsonl


def test_delete_session_endpoint(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    client = TestClient(create_app())
    imported = client.post(
        "/api/v1/sessions/import",
        json={"use_latest": True},
    )
    assert imported.status_code == 200
    session_id = imported.json()["session"]["session_id"]

    deleted = client.delete(f"/api/v1/sessions/{session_id}")
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["deleted_message_count"] == 2
    assert body["was_imported"] is True

    missing = client.get(f"/api/v1/chat?session_id={session_id}")
    assert missing.status_code == 404


def test_workspace_import_endpoints(
    claude_workspace: tuple[Path, Path, Path],
    session_store: Path,
    fake_stores: list[dict],
) -> None:
    _, _, jsonl_path = claude_workspace
    client = TestClient(create_app())
    listed = client.get("/api/v1/workspace/jsonl-files")
    assert listed.status_code == 200
    assert len(listed.json()["files"]) >= 1

    imported = client.post(
        "/api/v1/sessions/import",
        json={"use_latest": True},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["imported_count"] == 2
    assert body["session"]["session_id"] == jsonl_path.stem
