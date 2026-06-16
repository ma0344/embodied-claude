"""Capture directory retention — prune old JPEGs (and optional TTS surface cache)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def resolve_capture_dir(explicit: str | None = None) -> Path:
    """Return the active capture directory (CAPTURE_DIR env or ServerConfig default)."""
    if explicit is not None and str(explicit).strip():
        return Path(explicit)
    env = os.getenv("CAPTURE_DIR", "").strip()
    if env:
        return Path(env)
    from wifi_cam_mcp.config import ServerConfig

    return Path(ServerConfig.from_env().capture_dir)


def _retention_limits() -> tuple[float, int]:
    max_age_hours = float(os.getenv("CAPTURE_MAX_AGE_HOURS", "24"))
    max_files = int(os.getenv("CAPTURE_MAX_FILES", "32"))
    return max(0.0, max_age_hours), max(0, max_files)


def prune_capture_dir(
    capture_dir: Path | str,
    *,
    max_age_hours: float | None = None,
    max_files: int | None = None,
    patterns: tuple[str, ...] = ("capture_*.jpg",),
) -> int:
    """Delete old capture JPEGs. Returns number of files removed."""
    root = Path(capture_dir)
    if not root.is_dir():
        return 0

    default_age, default_max = _retention_limits()
    age_limit = default_age if max_age_hours is None else max(0.0, max_age_hours)
    file_limit = default_max if max_files is None else max(0, max_files)

    files: list[Path] = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    files = sorted({p for p in files if p.is_file()}, key=lambda p: p.stat().st_mtime)

    now = datetime.now(timezone.utc).timestamp()
    deleted = 0

    for path in files:
        age_hours = (now - path.stat().st_mtime) / 3600.0
        if age_limit > 0 and age_hours > age_limit:
            path.unlink(missing_ok=True)
            deleted += 1

    remaining = [p for p in files if p.is_file()]
    if file_limit > 0 and len(remaining) > file_limit:
        for path in remaining[: len(remaining) - file_limit]:
            path.unlink(missing_ok=True)
            deleted += 1

    return deleted


def prune_tts_surface_dir(capture_dir: Path | str) -> int:
    """Prune hashed surface TTS files older than CAPTURE_MAX_AGE_HOURS."""
    surf = Path(capture_dir) / "tts-surface"
    if not surf.is_dir():
        return 0
    max_age_hours, _ = _retention_limits()
    if max_age_hours <= 0:
        return 0

    now = datetime.now(timezone.utc).timestamp()
    deleted = 0
    for path in surf.iterdir():
        if not path.is_file():
            continue
        age_hours = (now - path.stat().st_mtime) / 3600.0
        if age_hours > max_age_hours:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted
