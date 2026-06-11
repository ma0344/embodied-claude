"""Claude Code Web UI backend (brain) connection settings."""

from __future__ import annotations

import os


def backend_base_url() -> str:
    """Base URL for claude-code-webui (default http://127.0.0.1:8080)."""
    return os.environ.get("CLAUDE_CODE_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
