"""Shared I/O helpers for Claude Code hooks (Windows-safe UTF-8 stdout)."""

from __future__ import annotations

import sys


def ensure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8 when the runtime allows it."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
