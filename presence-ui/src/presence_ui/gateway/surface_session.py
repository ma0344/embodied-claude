"""Surface chat session log — JSONL mirror for native history and persona export."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from social_core import utc_now

_SAFE_SESSION_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


@dataclass(frozen=True, slots=True)
class SurfaceTurn:
    role: str
    text: str
    timestamp: str
    enriched: str | None = None


def surface_sessions_dir() -> Path:
    override = os.environ.get("PRESENCE_SURFACE_SESSIONS_DIR", "").strip()
    if override:
        # Reject accidental doc-line pastes like "# 省略時 ~/.claude/..." (relative → repo junk dir).
        if override.startswith("#") or "\n" in override:
            override = ""
    if override:
        path = Path(override).expanduser()
    else:
        path = Path.home() / ".claude" / "koyori-surface" / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_path(session_id: str) -> Path | None:
    if not _SAFE_SESSION_ID.match(session_id):
        return None
    return surface_sessions_dir() / f"{session_id}.jsonl"


def surface_session_exists(session_id: str) -> bool:
    path = _session_path(session_id)
    return path is not None and path.is_file()


def resolve_surface_session_path(session_id: str) -> Path | None:
    """Return surface JSONL path when the session exists."""
    if not surface_session_exists(session_id):
        return None
    return _session_path(session_id)


def append_surface_turn(
    *,
    session_id: str,
    role: str,
    text: str,
    timestamp: str | None = None,
    enriched: str | None = None,
) -> None:
    path = _session_path(session_id)
    if path is None:
        return
    body = (text or "").strip()
    if not body:
        return
    ts = timestamp or utc_now()
    record: dict[str, str] = {"role": role, "timestamp": ts, "text": body}
    if role == "user" and enriched and enriched.strip() != body:
        record["enriched"] = enriched.strip()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_surface_turns(session_id: str) -> list[SurfaceTurn]:
    path = _session_path(session_id)
    if path is None or not path.is_file():
        return []
    turns: list[SurfaceTurn] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = str(data.get("role") or "").strip()
        text = str(data.get("text") or "").strip()
        if role not in {"user", "assistant"} or not text:
            continue
        enriched = data.get("enriched")
        turns.append(
            SurfaceTurn(
                role=role,
                text=text,
                timestamp=str(data.get("timestamp") or ""),
                enriched=str(enriched).strip() if enriched else None,
            )
        )
    return turns


def _preview_text(text: str, *, limit: int = 80) -> str:
    body = re.sub(r"\s+", " ", (text or "").strip())
    if len(body) <= limit:
        return body
    return body[: limit - 1] + "…"


def _title_for_surface_turns(turns: list[SurfaceTurn], session_id: str) -> str:
    """First plain user line — same policy as CC JSONL session list."""
    from presence_ui.gateway.user_prompt import session_title_from_context

    messages = [
        {"sender": "ma" if turn.role == "user" else "koyori", "message": turn.text}
        for turn in turns
    ]
    return session_title_from_context(
        history_title="",
        messages=messages,
        session_id=session_id,
    )


def list_surface_session_rows(*, limit: int = 40) -> list[dict[str, object]]:
    root = surface_sessions_dir()
    paths = sorted(
        root.glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    rows: list[dict[str, object]] = []
    for path in paths[:limit]:
        session_id = path.stem
        if not _SAFE_SESSION_ID.match(session_id):
            continue
        turns = load_surface_turns(session_id)
        preview = ""
        if turns:
            for turn in reversed(turns):
                if turn.role == "assistant":
                    preview = _preview_text(turn.text)
                    break
            if not preview:
                preview = _preview_text(turns[-1].text)
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        if turns and turns[-1].timestamp:
            updated_at = turns[-1].timestamp
        title = _title_for_surface_turns(turns, session_id) if turns else session_id[:8]
        rows.append(
            {
                "session_id": session_id,
                "title": title,
                "preview": preview,
                "updated_at": updated_at,
                "message_count": len(turns),
                "path": str(path),
            }
        )
    return rows
