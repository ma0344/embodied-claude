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


def _text_token(text: str, *, engine_name: str = "") -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    material = f"{engine_name}:{collapsed}" if engine_name else collapsed
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return digest[:16]


def _resolved_engine_name() -> str:
    from presence_ui.repo_env import load_repo_env

    load_repo_env(force=True)
    from tts_mcp.config import TTSConfig

    return TTSConfig.from_env().resolve_engine(None)


def _build_engine():
    from presence_ui.repo_env import load_repo_env

    load_repo_env(force=True)
    from tts_mcp.config import TTSConfig
    from tts_mcp.engines.elevenlabs import ElevenLabsEngine

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
    if engine_name == "irodori" and config.irodori:
        from tts_mcp.config import build_irodori_engine

        return build_irodori_engine(config.irodori)
    if engine_name == "voicevox" and config.voicevox:
        from tts_mcp.engines.voicevox import VoicevoxEngine

        vv = config.voicevox
        return VoicevoxEngine(url=vv.url, speaker=vv.speaker)
    raise RuntimeError(
        f"engine {engine_name!r} unavailable "
        "(check TTS_DEFAULT_ENGINE and matching URL/API key; "
        "no silent fallback to another engine)"
    )


def surface_tts_engine_url() -> str | None:
    """Configured TTS HTTP endpoint (for status messages)."""
    from presence_ui.repo_env import load_repo_env

    load_repo_env()
    try:
        from tts_mcp.config import TTSConfig

        config = TTSConfig.from_env()
        name = config.resolve_engine(None)
        if name == "irodori" and config.irodori:
            return config.irodori.url
        if name == "voicevox" and config.voicevox:
            return config.voicevox.url
        if name == "elevenlabs":
            return "elevenlabs"
    except Exception:
        pass
    irodori = os.getenv("IRODORI_URL")
    if irodori is None:
        return "http://127.0.0.1:8088"
    if irodori.strip():
        return irodori.rstrip("/")
    url = os.getenv("VOICEVOX_URL", "").strip()
    return url or None


def surface_tts_ready() -> bool:
    """True when a configured engine responds (not just env vars set)."""
    if not surface_tts_enabled():
        return False
    try:
        engine = _build_engine()
        is_available = getattr(engine, "is_available", None)
        if callable(is_available):
            return bool(is_available())
    except Exception:
        return False
    return False


def surface_tts_status() -> str:
    if not surface_tts_enabled():
        return "surface TTS disabled"
    url = surface_tts_engine_url()
    if not url:
        return "TTS not configured (set IRODORI_URL, VOICEVOX_URL, or ELEVENLABS_API_KEY)"
    if surface_tts_ready():
        return f"TTS ready ({url})"
    try:
        engine_name = _resolved_engine_name()
    except Exception:
        engine_name = ""
    if engine_name == "voicevox":
        hint = "start Aivis: scripts/start-aivis-tts.ps1"
    elif engine_name == "elevenlabs":
        hint = "check ELEVENLABS_API_KEY"
    else:
        hint = "start Irodori: scripts/start-irodori-tts.ps1"
    return f"TTS engine not running ({url}) — {hint}"


def _engine_cache_label() -> str:
    try:
        engine_name = _resolved_engine_name()
    except Exception:
        return ""
    if engine_name != "irodori":
        return engine_name
    try:
        engine = _build_engine()
        profile = getattr(engine, "cache_profile", None)
        if callable(profile):
            return f"irodori:{profile()}"
    except Exception:
        pass
    return engine_name


def synthesize_surface_audio(text: str) -> tuple[str, str, str]:
    """Return (token, audio_format, content_type). Writes cached file under surface_dir."""
    from presence_ui.gateway.irodori_emoji_enrich import prepare_irodori_tts_line

    line = prepare_irodori_tts_line(text.strip())
    if not line:
        raise ValueError("empty text")

    engine_label = _engine_cache_label()
    token = _text_token(line, engine_name=engine_label)
    surf_dir = surface_dir()
    for ext, media in _MEDIA_TYPES.items():
        candidate = surf_dir / f"{token}.{ext}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return token, ext, media

    engine = _build_engine()
    try:
        audio_bytes, audio_format = engine.synthesize(line)
    except Exception as exc:
        # HTTPError is an OSError subclass — catch before generic OSError so 5xx
        # is reported as synthesis failure, not "not reachable".
        if type(exc).__name__ == "HTTPError":
            url = surface_tts_engine_url()
            hint = f" ({url})" if url else ""
            raise RuntimeError(f"TTS synthesis failed{hint}: {exc}") from exc
        if isinstance(exc, OSError) or type(exc).__name__ == "URLError":
            url = surface_tts_engine_url() or "TTS engine"
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(f"TTS engine not reachable at {url}: {reason}") from exc
        url = surface_tts_engine_url()
        hint = f" ({url})" if url else ""
        raise RuntimeError(f"TTS synthesis failed{hint}: {exc}") from exc
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
