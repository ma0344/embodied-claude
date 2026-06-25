"""Claude CLI session id vs resume resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from presence_ui.gateway.claude_session_mode import ClaudeSessionRegistry
from presence_ui.services.native_history import resolve_session_jsonl_path
from presence_ui.services.session_log import _encode_project_path

SESSION_ID = "12274d9f-9c0b-43f9-869f-a2605b8f0eb6"


@pytest.fixture
def claude_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    project_path = str(tmp_path / "embodied-claude")
    claude_home = tmp_path / ".claude"
    encoded = _encode_project_path(project_path)
    project_dir = claude_home / "projects" / encoded
    project_dir.mkdir(parents=True)
    (project_dir / f"{SESSION_ID}.jsonl").write_text('{"type":"user"}\n', encoding="utf-8")
    monkeypatch.setenv("CLAUDE_HOME", str(claude_home))
    monkeypatch.setenv("PRESENCE_PROJECT_PATH", project_path)
    return SESSION_ID


def test_new_session_when_id_missing() -> None:
    reg = ClaudeSessionRegistry()
    sid, is_new = reg.resolve(None, new_uuid=lambda: "new-uuid")
    assert sid == "new-uuid"
    assert is_new is True


def test_resume_when_jsonl_exists(claude_jsonl: str) -> None:
    reg = ClaudeSessionRegistry()
    sid, is_new = reg.resolve(claude_jsonl)
    assert sid == claude_jsonl
    assert is_new is False
    assert claude_jsonl in reg.registered


def test_resume_after_process_restart_simulation(claude_jsonl: str) -> None:
    """Empty in-memory registry but JSONL on disk → must not use --session-id."""
    reg = ClaudeSessionRegistry()
    assert reg.registered == set()
    _, is_new = reg.resolve(claude_jsonl)
    assert is_new is False


def test_resume_when_already_registered() -> None:
    reg = ClaudeSessionRegistry()
    reg.mark_created("sess-1")
    _, is_new = reg.resolve("sess-1")
    assert is_new is False


def test_resume_when_creation_in_flight() -> None:
    reg = ClaudeSessionRegistry()
    reg.mark_in_flight("sess-2")
    _, is_new = reg.resolve("sess-2")
    assert is_new is False


def test_unknown_uuid_is_new() -> None:
    reg = ClaudeSessionRegistry()
    unknown = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    sid, is_new = reg.resolve(unknown)
    assert sid == unknown
    assert is_new is True


def test_resolve_session_jsonl_path_finds_file(claude_jsonl: str) -> None:
    assert resolve_session_jsonl_path(claude_jsonl) is not None
