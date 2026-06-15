"""Native chat history — Claude Code JSONL on ma-home as the single source of truth."""

from __future__ import annotations

import re
from pathlib import Path

from presence_ui.schemas import (
    ChatMessage,
    NativeSessionListResponse,
    NativeSessionMessagesResponse,
    NativeSessionSummary,
)
from presence_ui.services.session_log import (
    _find_project_dir,
    _messages_from_jsonl,
    get_claude_home,
    get_project_path,
    list_project_jsonl_files,
)

_SAFE_SESSION_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def resolve_session_jsonl_path(
    session_id: str,
    *,
    project_path: str | None = None,
) -> Path | None:
    """Return the JSONL file for a Claude Code session id (filename stem)."""
    if not _SAFE_SESSION_ID.match(session_id):
        return None
    claude_home = get_claude_home()
    project = get_project_path(project_path)
    project_dir = _find_project_dir(claude_home, project)
    if project_dir is None:
        return None
    candidate = (project_dir / f"{session_id}.jsonl").resolve()
    try:
        candidate.relative_to(project_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def list_native_sessions(
    *,
    project_path: str | None = None,
    limit: int = 40,
) -> NativeSessionListResponse:
    """List recent Native chat sessions from ~/.claude/projects JSONL files."""
    rows = list_project_jsonl_files(project_path=project_path, limit=limit)
    sessions = []
    for row in rows:
        session_id = str(row.get("session_file_id") or "")
        if not session_id:
            continue
        path = Path(str(row.get("path") or ""))
        preview = ""
        if path.is_file():
            messages = _messages_from_jsonl(path)
            if messages:
                preview = messages[-1].message[:48]
        sessions.append(
            NativeSessionSummary(
                session_id=session_id,
                title=str(row.get("title") or session_id[:8]),
                preview=preview,
                updated_at=str(row.get("modified_at") or ""),
                message_count=int(row.get("message_count") or 0),
            )
        )
    return NativeSessionListResponse(sessions=sessions)


def fetch_native_session_messages(
    session_id: str,
    *,
    project_path: str | None = None,
) -> NativeSessionMessagesResponse | None:
    """Load filtered user/assistant messages for one session."""
    path = resolve_session_jsonl_path(session_id, project_path=project_path)
    if path is None:
        return None
    messages: list[ChatMessage] = _messages_from_jsonl(path)
    return NativeSessionMessagesResponse(session_id=session_id, messages=messages)
