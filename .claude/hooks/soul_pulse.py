"""Short SOUL.md identity line for UserPromptSubmit injection."""

from __future__ import annotations

import os
import re
from pathlib import Path


def _soul_path() -> Path | None:
    env_path = os.environ.get("SOUL_PATH") or os.environ.get("PRESENCE_SOUL_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.is_file():
            return path
    repo = os.environ.get("CLAUDE_PROJECT_DIR")
    if repo:
        path = Path(repo) / "SOUL.md"
        if path.is_file():
            return path
    return None


def _first_body_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            continue
        if stripped.startswith("|") or stripped.startswith("---"):
            continue
        return stripped
    return ""


def identity_line() -> str | None:
    """One-line identity pulse from SOUL.md (hook-sized, not the full file)."""
    path = _soul_path()
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    name = os.environ.get("AGENT_NAME", "こより")
    body = _first_body_line(text)
    if body:
        body = re.sub(r"\s+", " ", body)
        if len(body) > 120:
            body = body[:117] + "..."
        return f"[identity_pulse] {body}"

    return f"[identity_pulse] うちは「{name}」。SOUL.md を Read または /soul で読み直す。"
