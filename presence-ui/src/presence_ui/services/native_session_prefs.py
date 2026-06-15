"""Server-side Native session preferences (shared across browsers on ma-home)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_SAFE_SESSION_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def _prefs_path() -> Path:
    base = Path(
        os.environ.get("PRESENCE_UI_HOME", str(Path.home() / ".claude" / "presence-ui")),
    )
    base.mkdir(parents=True, exist_ok=True)
    return base / "native-hidden-sessions.json"


def _validate_session_id(session_id: str) -> str:
    sid = session_id.strip()
    if not _SAFE_SESSION_ID.match(sid):
        raise ValueError("invalid session_id")
    return sid


def load_hidden_session_ids() -> set[str]:
    path = _prefs_path()
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    ids = raw.get("hidden_session_ids")
    if not isinstance(ids, list):
        return set()
    return {item for item in ids if isinstance(item, str) and _SAFE_SESSION_ID.match(item)}


def _save_hidden_session_ids(hidden: set[str]) -> None:
    path = _prefs_path()
    path.write_text(
        json.dumps({"hidden_session_ids": sorted(hidden)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def hide_session_ids(session_ids: list[str]) -> set[str]:
    """Add session ids to the shared hidden set; returns the full hidden set."""
    hidden = load_hidden_session_ids()
    for session_id in session_ids:
        hidden.add(_validate_session_id(session_id))
    _save_hidden_session_ids(hidden)
    return hidden


def hide_session(session_id: str) -> set[str]:
    return hide_session_ids([session_id])
