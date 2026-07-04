"""Native chat history — surface JSONL (direct LM) with Claude Code JSONL fallback."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from presence_ui.gateway.surface_session import (
    list_surface_session_rows,
    load_surface_turns,
    resolve_surface_session_path,
)
from presence_ui.schemas import (
    ChatMessage,
    NativeSessionListResponse,
    NativeSessionMessagesResponse,
    NativeSessionSummary,
)
from presence_ui.services.display_time import normalize_iso_timestamp
from presence_ui.services.native_session_prefs import load_hidden_session_ids
from presence_ui.services.session_log import (
    _find_matching_project_dirs,
    _messages_from_jsonl,
    _preview_for_messages,
    chat_project_paths,
    get_claude_home,
    list_project_jsonl_files,
)

_SAFE_SESSION_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def _surface_turns_to_messages(turns) -> list[ChatMessage]:
    """Map surface JSONL turns to API messages.

    User turns store display text in ``text`` and gateway injection in ``enriched``.
    The messages API returns ``enriched`` verbatim (CC JSONL parity) so the UI
    injection toggle can show ``[gateway_turn_context]`` blocks; stripping is client-side.
    """
    messages: list[ChatMessage] = []
    for turn in turns:
        sender = "ma" if turn.role == "user" else "koyori"
        body = turn.text
        if sender == "ma" and turn.enriched:
            body = turn.enriched
        messages.append(
            ChatMessage(
                sender=sender,
                message=body,
                timestamp=turn.timestamp,
            )
        )
    return messages


def resolve_session_jsonl_path(
    session_id: str,
    *,
    project_path: str | None = None,
) -> Path | None:
    """Return the JSONL file for a Claude Code session id (filename stem)."""
    if not _SAFE_SESSION_ID.match(session_id):
        return None
    claude_home = get_claude_home()
    root = claude_home / "projects"
    for project in chat_project_paths(project_path):
        for project_dir in _find_matching_project_dirs(root, project):
            candidate = (project_dir / f"{session_id}.jsonl").resolve()
            try:
                candidate.relative_to(project_dir.resolve())
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
    return None


def _session_updated_at(*, messages: list[ChatMessage], path: Path) -> str:
    for msg in reversed(messages):
        ts = normalize_iso_timestamp(msg.timestamp)
        if ts:
            return ts
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def list_native_sessions(
    *,
    project_path: str | None = None,
    limit: int = 40,
) -> NativeSessionListResponse:
    """List recent native chat sessions (surface JSONL + legacy Claude JSONL)."""
    hidden = load_hidden_session_ids()
    seen: set[str] = set()
    sessions: list[NativeSessionSummary] = []

    for row in list_surface_session_rows(limit=limit):
        session_id = str(row.get("session_id") or "")
        if not session_id or session_id in hidden or session_id in seen:
            continue
        seen.add(session_id)
        sessions.append(
            NativeSessionSummary(
                session_id=session_id,
                title=str(row.get("title") or session_id[:8]),
                preview=str(row.get("preview") or ""),
                updated_at=str(row.get("updated_at") or ""),
                message_count=int(row.get("message_count") or 0),
            )
        )

    remaining = max(0, limit - len(sessions))
    if remaining:
        rows = list_project_jsonl_files(project_path=project_path, limit=remaining + len(hidden))
        for row in rows:
            session_id = str(row.get("session_file_id") or "")
            if not session_id or session_id in hidden or session_id in seen:
                continue
            seen.add(session_id)
            path = Path(str(row.get("path") or ""))
            preview = ""
            messages: list[ChatMessage] = []
            updated_at = str(row.get("modified_at") or "")
            if path.is_file():
                messages = _messages_from_jsonl(path)
                if messages:
                    preview = _preview_for_messages(messages)
                    updated_at = _session_updated_at(messages=messages, path=path)
            sessions.append(
                NativeSessionSummary(
                    session_id=session_id,
                    title=str(row.get("title") or session_id[:8]),
                    preview=preview,
                    updated_at=updated_at,
                    message_count=int(row.get("message_count") or 0),
                )
            )
            if len(sessions) >= limit:
                break

    return NativeSessionListResponse(sessions=sessions[:limit])


def fetch_native_session_messages(
    session_id: str,
    *,
    project_path: str | None = None,
) -> NativeSessionMessagesResponse | None:
    """Load filtered user/assistant messages for one session."""
    from presence_ui.gateway.gw_internal_filter import filter_room_visible_messages

    surface_path = resolve_surface_session_path(session_id)
    if surface_path is not None:
        messages = _surface_turns_to_messages(load_surface_turns(session_id))
        filtered = filter_room_visible_messages(
            [
                {"sender": msg.sender, "message": msg.message, "timestamp": msg.timestamp}
                for msg in messages
            ]
        )
        out = [
            ChatMessage(
                sender=str(row["sender"]),
                message=str(row["message"]),
                timestamp=str(row.get("timestamp") or ""),
            )
            for row in filtered
        ]
        return NativeSessionMessagesResponse(session_id=session_id, messages=out)

    path = resolve_session_jsonl_path(session_id, project_path=project_path)
    if path is None:
        return None
    messages: list[ChatMessage] = _messages_from_jsonl(path, strip_user_injection=False)
    filtered = filter_room_visible_messages(
        [
            {"sender": msg.sender, "message": msg.message, "timestamp": msg.timestamp}
            for msg in messages
        ]
    )
    out = [
        ChatMessage(
            sender=str(row["sender"]),
            message=str(row["message"]),
            timestamp=str(row.get("timestamp") or ""),
        )
        for row in filtered
    ]
    return NativeSessionMessagesResponse(session_id=session_id, messages=out)
