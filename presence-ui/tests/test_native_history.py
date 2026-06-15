"""Native JSONL-backed chat history (C10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
from presence_ui.services.native_history import (
    fetch_native_session_messages,
    list_native_sessions,
    resolve_session_jsonl_path,
)
from presence_ui.services.session_log import _encode_project_path

SESSION_ID = "abc12345-aaaa-bbbb-cccc-ddddeeeeffff"


@pytest.fixture
def claude_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    project_path = str(tmp_path / "embodied-claude")
    claude_home = tmp_path / ".claude"
    encoded = _encode_project_path(project_path)
    project_dir = claude_home / "projects" / encoded
    project_dir.mkdir(parents=True)

    jsonl_path = project_dir / f"{SESSION_ID}.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2026-06-10T10:00:00+00:00",
                        "message": {
                            "content": [{"type": "text", "text": "キオスクから見える？"}],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": "2026-06-10T10:00:05+00:00",
                        "message": {
                            "content": [{"type": "text", "text": "うん、同じ JSONL だよ"}],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    monkeypatch.setenv("PRESENCE_PROJECT_PATH", project_path)
    return jsonl_path, project_path


def test_resolve_session_jsonl_path(claude_workspace: tuple[Path, str]) -> None:
    jsonl_path, _ = claude_workspace
    resolved = resolve_session_jsonl_path(SESSION_ID)
    assert resolved == jsonl_path
    assert resolve_session_jsonl_path("../evil") is None
    assert resolve_session_jsonl_path("not-a-valid-session") is None


def test_list_native_sessions(claude_workspace: tuple[Path, str]) -> None:
    del claude_workspace
    result = list_native_sessions(limit=10)
    assert len(result.sessions) == 1
    row = result.sessions[0]
    assert row.session_id == SESSION_ID
    assert row.message_count == 2
    assert "キオスク" in row.title or row.preview


def test_fetch_native_session_messages(claude_workspace: tuple[Path, str]) -> None:
    del claude_workspace
    result = fetch_native_session_messages(SESSION_ID)
    assert result is not None
    assert result.session_id == SESSION_ID
    assert len(result.messages) == 2
    assert result.messages[0].sender == "ma"
    assert result.messages[1].sender == "koyori"
    assert fetch_native_session_messages("missing-session-id") is None


def test_list_native_sessions_strips_injected_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_path = str(tmp_path / "embodied-claude")
    claude_home = tmp_path / ".claude"
    encoded = _encode_project_path(project_path)
    project_dir = claude_home / "projects" / encoded
    project_dir.mkdir(parents=True)
    session_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    jsonl_path = project_dir / f"{session_id}.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2026-06-15T08:38:00+00:00",
                        "message": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "[gateway_turn_context — not for the user]\n"
                                        "[Social context]\n\n"
                                        "こんばんは"
                                    ),
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    monkeypatch.setenv("PRESENCE_PROJECT_PATH", project_path)

    result = list_native_sessions(limit=10)
    row = next(item for item in result.sessions if item.session_id == session_id)
    assert row.title == "こんばんは"


def test_native_history_http_routes(
    claude_workspace: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del claude_workspace
    monkeypatch.setenv("PRESENCE_NATIVE_CHAT", "1")
    client = TestClient(create_app())

    listed = client.get("/api/v1/native/sessions")
    assert listed.status_code == 200
    body = listed.json()
    assert body["sessions"][0]["session_id"] == SESSION_ID
    assert body["sessions"][0]["title"] == "キオスクから見える？"

    messages = client.get(f"/api/v1/native/sessions/{SESSION_ID}/messages")
    assert messages.status_code == 200
    assert len(messages.json()["messages"]) == 2

    missing = client.get("/api/v1/native/sessions/does-not-exist/messages")
    assert missing.status_code == 404


def test_ui_config_exposes_native_sessions_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_NATIVE_CHAT", "1")
    client = TestClient(create_app())
    body = client.get("/api/v1/ui-config").json()
    assert body["native_sessions_path"] == "/api/v1/native/sessions"
    assert body["display_timezone"] == "Asia/Tokyo"
