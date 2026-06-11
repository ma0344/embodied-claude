"""Chat messages from Claude Code session JSONL (webui / CLI on ma-home)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from presence_ui.schemas import ChatMessage

_KOYORI_SKIP_PREFIXES = (
    "[Request interrupted by user for tool use]",
    "[Tool use]",
)


def _encode_project_path(project_path: str) -> str:
    normalized = os.path.normpath(project_path)
    return "".join("-" if ch in (":", "\\", "/") else ch for ch in normalized)


def _find_project_dir(claude_home: Path, project_path: str) -> Path | None:
    projects_root = claude_home / "projects"
    encoded = _encode_project_path(project_path)
    if not projects_root.is_dir():
        return None
    exact = projects_root / encoded
    if exact.is_dir():
        return exact
    for child in projects_root.iterdir():
        if child.is_dir() and child.name.lower() == encoded.lower():
            return child
    return None


def _content_blocks(content: Any) -> list[tuple[str, str]]:
    if isinstance(content, str):
        text = content.strip()
        return [("prompt", text)] if text else []
    if not isinstance(content, list):
        return []
    parts: list[tuple[str, str]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type", "")
        if block_type == "text":
            text = (block.get("text") or "").strip()
            if text:
                parts.append(("prompt", text))
        elif block_type == "tool_result":
            continue
    return parts


def _should_skip_user_text(text: str) -> bool:
    if not text.strip():
        return True
    if text.startswith("[Tool"):
        return True
    return any(text.startswith(prefix) for prefix in _KOYORI_SKIP_PREFIXES)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _record_kind(record: dict[str, Any]) -> str | None:
    """Claude Code uses ``type``; Cursor agent transcripts use ``role``."""
    kind = record.get("type") or record.get("role")
    return str(kind) if kind else None


def _messages_from_jsonl(path: Path) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for record in _read_jsonl(path):
        rec_type = _record_kind(record)
        ts = str(record.get("timestamp") or "")
        if rec_type == "user":
            parts = _content_blocks((record.get("message") or {}).get("content"))
            prompts = [text for kind, text in parts if kind == "prompt"]
            if not prompts:
                continue
            text = "\n".join(prompts)
            if _should_skip_user_text(text):
                continue
            messages.append(ChatMessage(sender="ma", message=text, timestamp=ts))
        elif rec_type == "assistant":
            parts = _content_blocks((record.get("message") or {}).get("content"))
            replies = [text for kind, text in parts if kind == "prompt"]
            if not replies:
                continue
            messages.append(
                ChatMessage(sender="koyori", message="\n".join(replies), timestamp=ts)
            )
    return messages


def fetch_session_log_messages(
    *,
    project_path: str | None = None,
    limit: int = 120,
    max_sessions: int = 1,
) -> list[ChatMessage]:
    """Load recent dialogue from Claude Code JSONL session files (archive only)."""
    claude_home = get_claude_home()
    project = get_project_path(project_path)
    project_dir = _find_project_dir(claude_home, project)
    if project_dir is None:
        return []

    jsonl_files = sorted(
        project_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_sessions]

    merged: list[ChatMessage] = []
    for path in reversed(jsonl_files):
        merged.extend(_messages_from_jsonl(path))

    merged.sort(key=lambda msg: msg.timestamp)
    if len(merged) > limit:
        merged = merged[-limit:]
    return merged


def _default_project_path() -> str:
    return str(Path(__file__).resolve().parents[4])


def get_claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude"))).expanduser()


def get_cursor_home() -> Path:
    return Path(os.environ.get("CURSOR_HOME", str(Path.home() / ".cursor"))).expanduser()


def _project_dir_slug(project_path: str) -> str:
    parts = [part.lower() for part in Path(project_path).resolve().parts if part not in {"/", "\\"}]
    if parts and len(parts[0]) == 2 and parts[0].endswith(":"):
        parts = parts[1:]
    return "-".join(parts[-4:])


def _matches_project_dir(dir_name: str, project_path: str) -> bool:
    encoded = _encode_project_path(project_path)
    lowered = dir_name.lower()
    if lowered == encoded.lower():
        return True
    slug = _project_dir_slug(project_path)
    return slug in lowered


def _find_matching_project_dirs(root: Path, project_path: str) -> list[Path]:
    if not root.is_dir():
        return []
    matches: list[Path] = []
    for child in root.iterdir():
        if child.is_dir() and _matches_project_dir(child.name, project_path):
            matches.append(child)
    matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return matches


def discover_workspace_dirs(project_path: str | None = None) -> list[dict[str, str]]:
    """Find Claude Code project folders for the repo path (Cursor is excluded)."""
    project = get_project_path(project_path)
    discovered: list[dict[str, str]] = []
    claude_home = get_claude_home()
    root = claude_home / "projects"
    for project_dir in _find_matching_project_dirs(root, project):
        discovered.append(
            {
                "source": "claude-code",
                "project_path": project,
                "project_dir": str(project_dir),
                "workspace_home": str(claude_home),
            }
        )
    return discovered


def _jsonl_files_in_dir(project_dir: Path) -> list[Path]:
    files = list(project_dir.glob("*.jsonl"))
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def get_project_path(project_path: str | None = None) -> str:
    if project_path:
        return str(Path(project_path).resolve())
    return os.environ.get("PRESENCE_PROJECT_PATH", _default_project_path())


def load_history_index(claude_home: Path, project_path: str) -> dict[str, dict[str, object]]:
    """Map Claude Code session UUID → history.jsonl display metadata."""
    history_file = claude_home / "history.jsonl"
    if not history_file.is_file():
        return {}

    project_norm = os.path.normcase(os.path.normpath(project_path))
    index: dict[str, dict[str, object]] = {}
    with history_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if os.path.normcase(os.path.normpath(str(row.get("project") or ""))) != project_norm:
                continue
            session_id = row.get("sessionId")
            if not session_id:
                continue
            entry = index.setdefault(
                str(session_id),
                {"last_display": "", "last_timestamp": 0, "first_display": ""},
            )
            display = str(row.get("display") or "").strip()
            ts = int(row.get("timestamp") or 0)
            if display and not entry["first_display"]:
                entry["first_display"] = display
            if display and ts >= int(entry["last_timestamp"]):
                entry["last_display"] = display
                entry["last_timestamp"] = ts
    return index


def _title_for_jsonl(
    *,
    path: Path,
    history: dict[str, dict[str, object]],
    preview_messages: list[ChatMessage],
) -> str:
    session_id = path.stem
    hist = history.get(session_id, {})
    title = str(hist.get("last_display") or hist.get("first_display") or "").strip()
    if not title and preview_messages:
        title = preview_messages[0].message[:48]
    if not title:
        title = session_id[:8]
    return title


def list_project_jsonl_files(
    *,
    project_path: str | None = None,
    limit: int = 30,
) -> list[dict[str, object]]:
    """Scan ~/.claude/projects/<encoded>/ for Claude Code JSONL session logs."""
    claude_home = get_claude_home()
    project = get_project_path(project_path)
    history = load_history_index(claude_home, project)

    candidates: list[tuple[Path, Path]] = []
    for entry in discover_workspace_dirs(project):
        project_dir = Path(entry["project_dir"])
        for path in _jsonl_files_in_dir(project_dir):
            candidates.append((project_dir, path))

    candidates.sort(key=lambda item: item[1].stat().st_mtime, reverse=True)

    results: list[dict[str, object]] = []
    for project_dir, path in candidates[:limit]:
        preview_messages = _messages_from_jsonl(path)
        if not preview_messages:
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        session_id = path.stem
        results.append(
            {
                "session_file_id": session_id,
                "path": str(path),
                "filename": path.name,
                "modified_at": modified_at,
                "title": _title_for_jsonl(
                    path=path,
                    history=history,
                    preview_messages=preview_messages,
                ),
                "message_count": len(preview_messages),
                "project_path": project,
                "project_dir": str(project_dir),
                "source": "claude-code",
            }
        )
    return results
