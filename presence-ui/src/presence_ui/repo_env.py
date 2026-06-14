"""Load repo-level secrets for gateway services (camera, TTS, etc.)."""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOADED = False


def repo_root() -> Path:
    return _REPO_ROOT


def load_repo_env(*, force: bool = False) -> None:
    """Load wifi-cam / tts / repo .env and ma-home presence-ui.local.env."""
    global _LOADED
    if _LOADED and not force:
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        _LOADED = True
        return

    for path in (
        _REPO_ROOT / "wifi-cam-mcp" / ".env",
        _REPO_ROOT / "tts-mcp" / ".env",
        _REPO_ROOT / ".env",
    ):
        if path.is_file():
            load_dotenv(path, override=False)

    local_env = Path.home() / ".config" / "embodied-claude" / "presence-ui.local.env"
    if local_env.is_file():
        load_dotenv(local_env, override=False)

    _LOADED = True


def tts_configured() -> bool:
    load_repo_env()
    if os.getenv("ELEVENLABS_API_KEY", "").strip():
        return True
    return bool(os.getenv("VOICEVOX_URL", "").strip())
