"""Gateway speak_text edge cases (Irodori migration)."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

import pytest

from presence_ui.services.tts import speak_text


@pytest.mark.asyncio
async def test_speak_text_rejects_empty() -> None:
    """E-04: empty / whitespace → (False, 'empty text')."""
    ok, detail = await speak_text("")
    assert ok is False
    assert detail == "empty text"

    ok2, detail2 = await speak_text("   \t  ")
    assert ok2 is False
    assert detail2 == "empty text"


@pytest.mark.asyncio
async def test_speak_text_synth_http_error_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-03: synthesize HTTPError → (False, reason)."""
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    class BoomEngine:
        def synthesize(self, text: str, **_kwargs):
            raise HTTPError(
                "http://127.0.0.1:8088/v1/audio/speech",
                500,
                "Internal Server Error",
                hdrs=None,
                fp=None,
            )

    def _fake_from_env():
        from tts_mcp.config import IrodoriConfig, PlaybackConfig, TTSConfig

        return TTSConfig(
            default_engine="irodori",
            elevenlabs=None,
            irodori=IrodoriConfig(
                url="http://127.0.0.1:8088",
                voice="none",
                num_steps=24,
                model="irodori-tts",
                timeout_sec=120.0,
            ),
            voicevox=None,
            playback=PlaybackConfig.from_env(),
        )

    monkeypatch.setattr("tts_mcp.config.TTSConfig.from_env", _fake_from_env)
    monkeypatch.setattr(
        "tts_mcp.engines.irodori.IrodoriEngine",
        lambda **_kwargs: BoomEngine(),
    )

    ok, detail = await speak_text("こよりやで")
    assert ok is False
    assert "500" in detail or "Internal Server Error" in detail or "HTTP" in detail


@pytest.mark.asyncio
async def test_speak_text_synth_url_error_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-03: synthesize URLError → (False, reason)."""
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    class TimeoutEngine:
        def synthesize(self, text: str, **_kwargs):
            raise URLError("timed out")

    def _fake_from_env():
        from tts_mcp.config import IrodoriConfig, PlaybackConfig, TTSConfig

        return TTSConfig(
            default_engine="irodori",
            elevenlabs=None,
            irodori=IrodoriConfig(
                url="http://127.0.0.1:8088",
                voice="none",
                num_steps=24,
                model="irodori-tts",
                timeout_sec=120.0,
            ),
            voicevox=None,
            playback=PlaybackConfig.from_env(),
        )

    monkeypatch.setattr("tts_mcp.config.TTSConfig.from_env", _fake_from_env)
    monkeypatch.setattr(
        "tts_mcp.engines.irodori.IrodoriEngine",
        lambda **_kwargs: TimeoutEngine(),
    )

    ok, detail = await speak_text("こよりやで")
    assert ok is False
    assert "timed out" in detail or "URLError" in detail


@pytest.mark.asyncio
async def test_speak_text_no_silent_fallback_to_voicevox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-07: irodori default + empty IRODORI_URL must not hit :10101."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "")
    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")

    opened: list[str] = []

    def _tracking_urlopen(req, *args, **kwargs):
        url = getattr(req, "full_url", None) or getattr(req, "get_full_url", lambda: str(req))()
        opened.append(str(url))
        raise AssertionError(f"unexpected urlopen: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _tracking_urlopen)
    monkeypatch.setattr(
        "tts_mcp.engines.voicevox.urllib.request.urlopen",
        _tracking_urlopen,
    )

    ok, detail = await speak_text("こよりやで")
    assert ok is False
    assert "irodori" in detail
    assert "unavailable" in detail
    assert not any("10101" in u for u in opened)
