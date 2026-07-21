"""Brief S0 reasoning ON/OFF — env-backed tradeoff (default ON).

Separate from PRESENCE_CLAUDE_DISABLE_THINKING (surface Claude Code).
UI: room drawer → GET/POST /api/v1/brief-s0/reasoning
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ENV_KEY = "PRESENCE_BRIEF_S0_REASONING"
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def local_env_path() -> Path:
    return Path.home() / ".config" / "embodied-claude" / "presence-ui.local.env"


def brief_s0_reasoning_enabled() -> bool:
    """Default ON when unset. Explicit falsey values disable."""
    raw = os.getenv(ENV_KEY, "1").strip().lower()
    if raw in _FALSE:
        return False
    if raw in _TRUE or raw == "":
        return True
    # Unknown → treat as ON (prefer accuracy default).
    return True


def set_brief_s0_reasoning(enabled: bool) -> Path:
    """Persist to presence-ui.local.env and update process env immediately."""
    value = "1" if enabled else "0"
    path = upsert_local_env_key(ENV_KEY, value)
    os.environ[ENV_KEY] = value
    return path


def upsert_local_env_key(key: str, value: str) -> Path:
    """Insert or replace KEY=value in local.env (create file/dirs if needed)."""
    path = local_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{key}={value}"
    if not path.is_file():
        path.write_text(
            f"# written by presence-ui\n{line}\n",
            encoding="utf-8",
        )
        return path

    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^[ \t]*{re.escape(key)}[ \t]*=.*$", re.MULTILINE)
    if pattern.search(text):
        new_text = pattern.sub(line, text, count=1)
    else:
        sep = "" if text.endswith("\n") or not text else "\n"
        new_text = f"{text}{sep}{line}\n"
    path.write_text(new_text, encoding="utf-8")
    return path


def reasoning_effort_for_openai(enabled: bool) -> str:
    """LM Studio /v1/chat/completions: medium=on, none=off (Gemma 4)."""
    return "medium" if enabled else "none"
