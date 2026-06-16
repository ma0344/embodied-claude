"""TTS synthesis for browser playback (A4c+ voice_surface)."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

_TOKEN_RE = re.compile(r"^[a-f0-9]{16}$")
_MEDIA_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
}


def surface_tts_enabled() -> bool:
    if os.getenv("PRESENCE_OUTBOUND_SURFACE_TTS", "1").lower() in {"0", "false", "no"}:
        return False
    from presence_ui.repo_env import tts_configured

    return tts_configured()


def surface_dir() -> Path:
    explicit = os.getenv("PRESENCE_TTS_SURFACE_DIR", "").strip()
    if explicit:
        path = Path(explicit)
    else:
        capture = os.getenv("CAPTURE_DIR", "").strip()
        if capture:
            base = Path(capture)
        else:
            import tempfile

            base = Path(tempfile.gettempdir()) / "wifi-cam-mcp"
        path = base / "tts-surface"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _text_token(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    digest = hashlib.sha256(collapsed.encode("utf-8")).hexdigest()
    return digest[:16]


def _build_engine():
    from presence_ui.repo_env import load_repo_env

    load_repo_env(force=True)
    from tts_mcp.config import TTSConfig
    from tts_mcp.engines.elevenlabs import ElevenLabsEngine
    from tts_mcp.engines.voicevox import VoicevoxEngine

    config = TTSConfig.from_env()
    engine_name = config.resolve_engine(None)
    if engine_name == "elevenlabs" and config.elevenlabs:
        eleven = config.elevenlabs
        return ElevenLabsEngine(
            api_key=eleven.api_key,
            voice_id=eleven.voice_id,
            model_id=eleven.model_id,
            output_format=eleven.output_format,
        )
    if engine_name == "voicevox" and config.voicevox:
        vv = config.voicevox
        return VoicevoxEngine(url=vv.url, speaker=vv.speaker)
    raise RuntimeError("no TTS engine configured")


def synthesize_surface_audio(text: str) -> tuple[str, str, str]:
    """Return (token, audio_format, content_type). Writes cached file under surface_dir."""
    line = text.strip()
    if not line:
        raise ValueError("empty text")

    token = _text_token(line)
    surf_dir = surface_dir()
    for ext, media in _MEDIA_TYPES.items():
        candidate = surf_dir / f"{token}.{ext}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return token, ext, media

    engine = _build_engine()
    audio_bytes, audio_format = engine.synthesize(line)
    fmt = str(audio_format or "wav").lower().lstrip(".")
    if fmt not in _MEDIA_TYPES:
        fmt = "wav"
    path = surf_dir / f"{token}.{fmt}"
    path.write_bytes(audio_bytes)
    return token, fmt, _MEDIA_TYPES[fmt]


def surface_audio_path(token: str) -> Path | None:
    if not _TOKEN_RE.match(token):
        return None
    surf_dir = surface_dir()
    for ext in _MEDIA_TYPES:
        candidate = surf_dir / f"{token}.{ext}"
        if candidate.is_file():
            return candidate
    return None


def surface_media_type(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return _MEDIA_TYPES.get(ext, "application/octet-stream")


async def synthesize_surface_audio_async(text: str) -> tuple[str, str, str]:
    import asyncio

    return await asyncio.to_thread(synthesize_surface_audio, text)
