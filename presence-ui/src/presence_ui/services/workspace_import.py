"""Import Claude Code JSONL workspace logs into Koyori's Room sessions."""

from __future__ import annotations

from pathlib import Path

from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.schemas import (
    ChatMessage,
    ImportWorkspaceRequest,
    ImportWorkspaceResponse,
    WorkspaceJsonlFile,
    WorkspaceJsonlListResponse,
)
from presence_ui.services.chat import _messages_from_room_events
from presence_ui.services.room_events import ROOM_WRITE_SOURCE
from presence_ui.services.session_log import (
    _messages_from_jsonl,
    discover_workspace_dirs,
    get_claude_home,
    get_project_path,
    list_project_jsonl_files,
)
from presence_ui.services.sessions import (
    _title_from_text,
    consolidate_to_canonical_session,
    delete_session,
    ensure_session,
    find_session_by_import_source,
    get_session,
    resolve_import_session_id,
)


def _allowed_jsonl_roots() -> list[Path]:
    projects = get_claude_home() / "projects"
    return [projects.resolve()] if projects.is_dir() else []


def _is_allowed_jsonl_path(candidate: Path) -> bool:
    resolved = candidate.resolve()
    for root in _allowed_jsonl_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _resolve_jsonl_path(
    *,
    project_path: str | None,
    session_file_id: str | None,
    jsonl_path: str | None,
    use_latest: bool,
) -> Path:
    if jsonl_path:
        candidate = Path(jsonl_path).expanduser().resolve()
        if not _is_allowed_jsonl_path(candidate):
            raise ValueError("jsonl_path must be under ~/.claude/projects/")
        if not candidate.is_file() or candidate.suffix != ".jsonl":
            raise ValueError(f"jsonl file not found: {candidate}")
        return candidate

    listed = list_project_jsonl_files(project_path=project_path, limit=100)
    if not listed:
        project = get_project_path(project_path)
        dirs = discover_workspace_dirs(project)
        if not dirs:
            raise FileNotFoundError(
                f"No Claude Code project dir found for {project!r} "
                f"(expected under ~/.claude/projects/)"
            )
        raise FileNotFoundError(f"No importable JSONL sessions found for {project!r}")

    if use_latest:
        return Path(str(listed[0]["path"]))

    if not session_file_id:
        raise ValueError("session_file_id, jsonl_path, or use_latest is required")

    exact = [row for row in listed if row["session_file_id"] == session_file_id]
    if len(exact) == 1:
        return Path(str(exact[0]["path"]))

    prefix = [row for row in listed if str(row["session_file_id"]).startswith(session_file_id)]
    if len(prefix) == 1:
        return Path(str(prefix[0]["path"]))

    if len(prefix) > 1:
        raise ValueError(f"session_file_id prefix is ambiguous: {session_file_id}")
    raise FileNotFoundError(f"JSONL not found for session: {session_file_id}")


def _import_source_key(jsonl_path: Path) -> str:
    return str(jsonl_path.resolve())


def _sync_message_key(msg: ChatMessage) -> tuple[str, str, str]:
    ts = msg.timestamp[:19] if msg.timestamp else ""
    return (msg.sender, msg.message.strip(), ts)


def _existing_sync_keys(*, person_id: str, session_id: str) -> set[tuple[str, str, str]]:
    messages = _messages_from_room_events(person_id=person_id, session_id=session_id, limit=5000)
    return {_sync_message_key(msg) for msg in messages}


def _ingest_room_message(
    *,
    person_id: str,
    session_id: str,
    sender: str,
    message: str,
    ts: str,
) -> None:
    stores = get_stores()
    kind = "human_utterance" if sender == "ma" else "agent_utterance"
    stores.social_state.ingest_social_event(
        {
            "ts": ts or utc_now(),
            "source": ROOM_WRITE_SOURCE,
            "kind": kind,
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": message, "imported": True},
        }
    )


def _sync_jsonl_messages(
    *,
    person_id: str,
    session_id: str,
    messages: list[ChatMessage],
    existing_keys: set[tuple[str, str, str]],
) -> int:
    imported = 0
    for msg in messages:
        key = _sync_message_key(msg)
        if key in existing_keys:
            continue
        _ingest_room_message(
            person_id=person_id,
            session_id=session_id,
            sender=msg.sender,
            message=msg.message,
            ts=msg.timestamp or utc_now(),
        )
        existing_keys.add(key)
        imported += 1
    return imported


def _import_source_index() -> dict[str, str]:
    from presence_ui.services.sessions import _load_registry

    index: dict[str, str] = {}
    for session_id, record in _load_registry().items():
        source = record.get("imported_from")
        if source:
            index[str(source)] = session_id
    return index


def list_workspace_jsonl_files(
    *,
    project_path: str | None = None,
    limit: int = 30,
) -> WorkspaceJsonlListResponse:
    project = get_project_path(project_path)
    rows = list_project_jsonl_files(project_path=project, limit=limit)
    linked = _import_source_index()
    files = []
    for row in rows:
        path = str(row["path"])
        linked_session_id = linked.get(path) or find_session_by_import_source(path)
        files.append(
            WorkspaceJsonlFile.model_validate(
                {**row, "linked_session_id": linked_session_id}
            )
        )
    return WorkspaceJsonlListResponse(
        project_path=project,
        project_dirs=discover_workspace_dirs(project),
        claude_home=str(get_claude_home()),
        files=files,
    )


def import_workspace_jsonl(
    *,
    payload: ImportWorkspaceRequest,
    person_id: str = "ma",
) -> ImportWorkspaceResponse:
    project = get_project_path(payload.project_path)
    jsonl_path = _resolve_jsonl_path(
        project_path=project,
        session_file_id=payload.session_file_id,
        jsonl_path=payload.jsonl_path,
        use_latest=payload.use_latest,
    )
    source_key = _import_source_key(jsonl_path)
    session_id = resolve_import_session_id(jsonl_path=jsonl_path)
    session_id = consolidate_to_canonical_session(session_id=session_id, person_id=person_id)
    had_session = get_session(session_id=session_id, person_id=person_id) is not None

    if payload.force and had_session:
        delete_session(session_id=session_id, person_id=person_id)
        had_session = False

    messages = _messages_from_jsonl(jsonl_path)
    if not messages:
        raise ValueError("no dialogue found in JSONL (user/assistant text only)")

    title = (payload.title or "").strip()
    if not title:
        listed = list_project_jsonl_files(project_path=project, limit=50)
        match = next((row for row in listed if row["path"] == str(jsonl_path)), None)
        title = str(match["title"]) if match else messages[0].message
    title = _title_from_text(title, max_len=80)

    created_at = messages[0].timestamp or utc_now()
    updated_at = messages[-1].timestamp or utc_now()
    ensure_session(
        session_id=session_id,
        person_id=person_id,
        title=title,
        created_at=created_at,
        extra={
            "imported_from": source_key,
            "source_jsonl": str(jsonl_path),
            "jsonl_session_id": jsonl_path.stem,
            "updated_at": updated_at,
        },
    )

    existing_keys = (
        set()
        if payload.force
        else _existing_sync_keys(person_id=person_id, session_id=session_id)
    )
    imported_count = _sync_jsonl_messages(
        person_id=person_id,
        session_id=session_id,
        messages=messages,
        existing_keys=existing_keys,
    )

    refreshed = get_session(session_id=session_id, person_id=person_id)
    if refreshed is None:
        raise RuntimeError("imported session missing after write")

    return ImportWorkspaceResponse(
        session=refreshed,
        imported_count=imported_count,
        already_imported=had_session and imported_count == 0,
        source_jsonl=str(jsonl_path),
    )
