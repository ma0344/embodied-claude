"""Direct TTS playback for gateway (no MCP spawn)."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def speak_text(text: str, *, speaker: str = "local") -> tuple[bool, str]:
    """Synthesize and play text via tts-mcp engines."""

    line = (text or "").strip()
    if not line:
        return False, "empty text"

    def _run() -> tuple[bool, str]:
        from presence_ui.repo_env import load_repo_env, repo_root

        load_repo_env(force=True)
        try:
            from tts_mcp import playback
            from tts_mcp.config import ServerConfig, TTSConfig
            from tts_mcp.engines.elevenlabs import ElevenLabsEngine
        except ImportError as exc:
            return False, f"tts-mcp not available: {exc}"

        config = TTSConfig.from_env()
        server_config = ServerConfig.from_env()
        if not config.elevenlabs and not config.voicevox:
            hint = repo_root() / "tts-mcp" / ".env"
            return (
                False,
                "no TTS engine configured "
                f"(set ELEVENLABS_API_KEY or VOICEVOX_URL in {hint} "
                "or ~/.config/embodied-claude/presence-ui.local.env)",
            )

        engine_name = config.resolve_engine(None)
        if engine_name == "elevenlabs" and config.elevenlabs:
            engine = ElevenLabsEngine(
                api_key=config.elevenlabs.api_key,
                voice_id=config.elevenlabs.voice_id,
                model_id=config.elevenlabs.model_id,
                output_format=config.elevenlabs.output_format,
            )
        elif engine_name == "voicevox" and config.voicevox:
            from tts_mcp.engines.voicevox import VoicevoxEngine

            vv = config.voicevox
            engine = VoicevoxEngine(url=vv.url, speaker=vv.speaker)
        else:
            return False, f"engine {engine_name!r} unavailable"

        audio_bytes, audio_format = engine.synthesize(line)
        file_path = playback.save_audio(audio_bytes, audio_format, server_config.save_dir)
        pb = config.playback
        use_local = speaker in {"local", "both"}
        use_camera = speaker in {"camera", "both"} and pb.go2rtc_url

        status = "skipped"
        if use_local:
            status = playback.play_audio(
                audio_bytes,
                file_path,
                pb.playback,
                pb.pulse_sink,
                pb.pulse_server,
            )

        camera_status = "not configured"
        if use_camera:
            ok, cam_msg = playback.play_with_go2rtc(
                file_path,
                pb.go2rtc_url,
                pb.go2rtc_stream,
                pb.go2rtc_ffmpeg,
            )
            camera_status = cam_msg
            if ok:
                status = f"{status}; camera ok"

        return True, f"{status}; camera={camera_status}; file={file_path}"

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        logger.warning("speak_text failed: %s", exc)
        return False, str(exc)
