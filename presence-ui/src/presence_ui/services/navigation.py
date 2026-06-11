"""Project / history discovery and session join for CLI navigation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from social_core import LEGACY_ROOM_SESSION_ID

from presence_ui.schemas import (
    HistoryListResponse,
    HistorySummary,
    ImportWorkspaceRequest,
    JoinSessionRequest,
    JoinSessionResponse,
    ProjectListResponse,
    ProjectSummary,
)
from presence_ui.services.session_log import (
    _encode_project_path,
    _jsonl_files_in_dir,
    _messages_from_jsonl,
    _title_for_jsonl,
    get_claude_home,
    get_project_path,
    load_history_index,
)
from presence_ui.services.sessions import (
    _registry,
    _session_stats,
    activate_session,
    claude_code_session_id,
    consolidate_to_canonical_session,
    get_session,
    list_sessions,
    resolve_import_session_id,
)
from presence_ui.services.workspace_import import import_workspace_jsonl


def _projects_root() -> Path:
    return get_claude_home() / "projects"


def _resolve_project_dir(project_id: str) -> Path | None:
    root = _projects_root()
    if not root.is_dir():
        return None
    exact = root / project_id
    if exact.is_dir():
        return exact
    lowered = project_id.lower()
    for child in root.iterdir():
        if child.is_dir() and child.name.lower() == lowered:
            return child
    return None


def _project_label(project_id: str, project_dir: Path) -> str:
    """Human-readable label from encoded dir name."""
    text = project_id.replace("--", " / ").replace("-", os.sep)
    if len(text) > 60:
        return text[:57] + "…"
    return text or project_dir.name


def _guess_project_path(project_id: str, project_dir: Path) -> str:
    configured = get_project_path(None)
    encoded_configured = _encode_project_path(configured)
    if project_id.lower() == encoded_configured.lower():
        return configured
    return str(project_dir)


def list_projects(*, limit: int = 40) -> ProjectListResponse:
    """Discover Claude Code project folders under ~/.claude/projects/."""
    root = _projects_root()
    claude_home = get_claude_home()
    projects: list[ProjectSummary] = []

    if root.is_dir():
        dirs = sorted(
            (p for p in root.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for project_dir in dirs[:limit]:
            project_id = project_dir.name
            jsonl_count = len(_jsonl_files_in_dir(project_dir))
            modified_at = datetime.fromtimestamp(
                project_dir.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat()
            projects.append(
                ProjectSummary(
                    project_id=project_id,
                    label=_project_label(project_id, project_dir),
                    project_dir=str(project_dir),
                    project_path=_guess_project_path(project_id, project_dir),
                    jsonl_count=jsonl_count,
                    modified_at=modified_at,
                )
            )

    return ProjectListResponse(claude_home=str(claude_home), projects=projects)


def list_project_histories(
    *,
    project_id: str,
    person_id: str = "ma",
    limit: int = 50,
) -> HistoryListResponse:
    """List joinable room histories for one Claude Code project."""
    project_dir = _resolve_project_dir(project_id)
    if project_dir is None:
        raise ValueError(f"unknown project: {project_id}")

    project_path = _guess_project_path(project_id, project_dir)
    history_index = load_history_index(get_claude_home(), project_path)
    registry = _registry()

    histories: list[HistorySummary] = []
    seen_room_ids: set[str] = set()

    for path in _jsonl_files_in_dir(project_dir)[:limit]:
        preview = _messages_from_jsonl(path)
        if not preview:
            continue
        jsonl_stem = path.stem
        session_id = claude_code_session_id(path)
        room = get_session(session_id=session_id, person_id=person_id)
        msg_count, _, last_ts = _session_stats(
            session_id=session_id,
            person_id=person_id,
        )
        if msg_count == 0:
            msg_count = len(preview)
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        histories.append(
            HistorySummary(
                history_id=jsonl_stem,
                title=_title_for_jsonl(
                    path=path,
                    history=history_index,
                    preview_messages=preview,
                ),
                kind="jsonl",
                session_id=session_id,
                room_session_id=session_id,
                jsonl_path=str(path),
                message_count=msg_count,
                modified_at=last_ts or modified_at,
                has_room=room is not None,
                active=False,
            )
        )
        seen_room_ids.add(session_id)

    # Native rooms (manual / legacy) tied to this project path in metadata.
    for record in registry.list_for_person(person_id=person_id, limit=limit):
        meta = record.metadata
        meta_project = str(meta.get("project_path") or meta.get("source_jsonl") or "")
        if meta_project and project_path not in meta_project and project_id not in meta_project:
            continue
        if record.session_id in seen_room_ids:
            continue
        msg_count, _, last_ts = _session_stats(
            session_id=record.session_id,
            person_id=person_id,
        )
        histories.append(
            HistorySummary(
                history_id=record.session_id,
                title=record.title,
                kind="room",
                session_id=record.session_id,
                room_session_id=record.session_id,
                jsonl_path=str(meta.get("source_jsonl") or "") or None,
                message_count=msg_count,
                modified_at=last_ts or record.updated_at,
                has_room=True,
                active=False,
            )
        )

    # Rooms without project metadata but created in this workspace (imported_from path).
    for record in registry.list_for_person(person_id=person_id, limit=limit):
        if record.session_id in seen_room_ids:
            continue
        imported_from = str(record.metadata.get("imported_from") or "")
        if project_dir.as_posix() not in imported_from.replace("\\", "/"):
            continue
        msg_count, _, last_ts = _session_stats(
            session_id=record.session_id,
            person_id=person_id,
        )
        histories.append(
            HistorySummary(
                history_id=record.session_id,
                title=record.title,
                kind="room",
                session_id=record.session_id,
                room_session_id=record.session_id,
                jsonl_path=imported_from or None,
                message_count=msg_count,
                modified_at=last_ts or record.updated_at,
                has_room=True,
                active=False,
            )
        )
        seen_room_ids.add(record.session_id)

    histories.sort(key=lambda item: item.modified_at, reverse=True)
    return HistoryListResponse(
        project_id=project_id,
        project_path=project_path,
        project_dir=str(project_dir),
        histories=histories[:limit],
    )


def _resolve_jsonl_for_history(*, project_id: str, history_id: str) -> Path:
    project_dir = _resolve_project_dir(project_id)
    if project_dir is None:
        raise ValueError(f"unknown project: {project_id}")

    exact = project_dir / f"{history_id}.jsonl"
    if exact.is_file():
        return exact

    prefix = [p for p in project_dir.glob("*.jsonl") if p.stem.startswith(history_id)]
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        raise ValueError(f"ambiguous history_id prefix: {history_id}")
    raise ValueError(f"history not found: {history_id}")


def join_session(*, payload: JoinSessionRequest) -> JoinSessionResponse:
    """Select a room and pin the CLI client to it (auto-join)."""
    person_id = payload.person_id
    client_id = payload.client_id
    imported_count = 0
    created_room = False

    if payload.session_id:
        room_session_id = consolidate_to_canonical_session(
            session_id=payload.session_id,
            person_id=person_id,
        )
    elif payload.history_id and payload.project_id:
        if payload.history_id == LEGACY_ROOM_SESSION_ID:
            room_session_id = LEGACY_ROOM_SESSION_ID
        else:
            jsonl_path = _resolve_jsonl_for_history(
                project_id=payload.project_id,
                history_id=payload.history_id,
            )
            room_session_id = resolve_import_session_id(jsonl_path=jsonl_path)
            had_room = get_session(session_id=room_session_id, person_id=person_id) is not None
            if not had_room or payload.sync_jsonl:
                result = import_workspace_jsonl(
                    payload=ImportWorkspaceRequest(
                        jsonl_path=str(jsonl_path),
                        person_id=person_id,
                        force=payload.force_resync,
                    ),
                    person_id=person_id,
                )
                imported_count = result.imported_count
                created_room = not had_room
                room_session_id = result.session.session_id
    else:
        raise ValueError("session_id or (project_id + history_id) is required")

    if get_session(session_id=room_session_id, person_id=person_id) is None:
        raise ValueError(f"unknown session: {room_session_id}")

    activation = activate_session(
        session_id=room_session_id,
        person_id=person_id,
        client_id=client_id,
    )
    room = get_session(session_id=room_session_id, person_id=person_id)
    if room is None:
        raise RuntimeError("session missing after join")

    return JoinSessionResponse(
        session_id=room_session_id,
        title=room.title,
        client_id=activation["client_id"],
        person_id=activation["person_id"],
        activated_at=activation["activated_at"],
        imported_count=imported_count,
        created_room=created_room,
        message_count=room.message_count,
    )


def list_local_rooms(*, person_id: str = "ma", limit: int = 40) -> list[HistorySummary]:
    """All rooms in social.db (Web UI session dropdown equivalent)."""
    items: list[HistorySummary] = []
    for session in list_sessions(person_id=person_id, limit=limit).sessions:
        items.append(
            HistorySummary(
                history_id=session.session_id,
                title=session.title,
                kind="room",
                room_session_id=session.session_id,
                jsonl_path=None,
                message_count=session.message_count,
                modified_at=session.updated_at,
                has_room=True,
                active=False,
            )
        )
    return items
