"""A4c+ surface TTS — synthesize API and cached audio files."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
from presence_ui.repo_env import tts_configured
from presence_ui.services.tts_surface import (
    _build_engine,
    _text_token,
    surface_audio_path,
    surface_tts_enabled,
    synthesize_surface_audio,
)


def test_surface_tts_enabled_requires_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOICEVOX_URL", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("IRODORI_URL", "")  # disable irodori default
    monkeypatch.setenv("PRESENCE_OUTBOUND_SURFACE_TTS", "1")
    assert surface_tts_enabled() is False

    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    assert surface_tts_enabled() is True

    monkeypatch.setenv("IRODORI_URL", "")
    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")
    assert surface_tts_enabled() is True

    monkeypatch.setenv("PRESENCE_OUTBOUND_SURFACE_TTS", "0")
    assert surface_tts_enabled() is False


def test_synthesize_surface_audio_caches(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    calls: list[str] = []

    class FakeEngine:
        def synthesize(self, text: str, **_kwargs):
            calls.append(text)
            return b"RIFFfake", "wav"

    monkeypatch.setattr("presence_ui.services.tts_surface._build_engine", lambda: FakeEngine())
    monkeypatch.setattr(
        "presence_ui.services.tts_surface._resolved_engine_name",
        lambda: "irodori",
    )

    token1, fmt1, media1 = synthesize_surface_audio("まー、おる？")
    token2, fmt2, media2 = synthesize_surface_audio("  まー、おる？  ")

    assert token1 == token2 == _text_token("まー、おる？", engine_name="irodori")
    assert fmt1 == fmt2 == "wav"
    assert media1 == media2 == "audio/wav"
    assert len(calls) == 1
    assert (tmp_path / f"{token1}.wav").is_file()
    assert surface_audio_path(token1) == tmp_path / f"{token1}.wav"


def test_cache_key_includes_engine_name() -> None:
    aivis_token = _text_token("同じ文", engine_name="voicevox")
    irodori_token = _text_token("同じ文", engine_name="irodori")
    assert aivis_token != irodori_token


def test_surface_audio_path_rejects_invalid_token(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    assert surface_audio_path("../etc/passwd") is None
    assert surface_audio_path("not-a-token") is None


def test_tts_surface_api(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")

    class FakeEngine:
        def synthesize(self, text: str, **_kwargs):
            return b"RIFFfake", "wav"

    monkeypatch.setattr("presence_ui.services.tts_surface._build_engine", lambda: FakeEngine())
    monkeypatch.setattr(
        "presence_ui.services.tts_surface._resolved_engine_name",
        lambda: "irodori",
    )

    client = TestClient(create_app())
    synth = client.post("/api/v1/tts/surface", json={"text": "こよりやで"})
    assert synth.status_code == 200
    body = synth.json()
    assert body["ok"] is True
    assert body["content_type"] == "audio/wav"
    assert body["audio_url"].startswith("/api/v1/tts/surface/")

    audio = client.get(body["audio_url"])
    assert audio.status_code == 200
    assert audio.content == b"RIFFfake"


def test_tts_surface_api_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_SURFACE_TTS", "0")
    client = TestClient(create_app())
    response = client.post("/api/v1/tts/surface", json={"text": "test"})
    assert response.status_code == 503


def test_surface_tts_ready_checks_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")

    class DownEngine:
        def is_available(self) -> bool:
            return False

    monkeypatch.setattr("presence_ui.services.tts_surface._build_engine", lambda: DownEngine())
    from presence_ui.services.tts_surface import surface_tts_ready, surface_tts_status

    assert surface_tts_ready() is False
    status = surface_tts_status()
    assert "not running" in status
    assert "start-irodori-tts.ps1" in status


def test_surface_tts_status_hints_aivis_for_voicevox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H3: voicevox engine → Aivis start hint."""
    monkeypatch.setenv("IRODORI_URL", "")
    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "voicevox")

    class DownEngine:
        def is_available(self) -> bool:
            return False

    monkeypatch.setattr("presence_ui.services.tts_surface._build_engine", lambda: DownEngine())
    monkeypatch.setattr(
        "presence_ui.services.tts_surface._resolved_engine_name",
        lambda: "voicevox",
    )
    from presence_ui.services.tts_surface import surface_tts_status

    status = surface_tts_status()
    assert "start-aivis-tts.ps1" in status
    assert "start-irodori-tts.ps1" not in status


def test_ui_config_exposes_surface_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")
    body = TestClient(create_app()).get("/api/v1/ui-config").json()
    assert body["outbound_surface_tts_enabled"] is True
    assert body["surface_tts_synthesize_path"] == "/api/v1/tts/surface"


def test_synthesize_surface_audio_rejects_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    """E-04: whitespace-only text → ValueError('empty text')."""
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", "/tmp/unused-tts-surface")
    with pytest.raises(ValueError, match="empty text"):
        synthesize_surface_audio("  ")


def test_synthesize_surface_audio_wraps_http_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E-03: engine HTTPError → RuntimeError from synthesize_surface_audio."""
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")

    class BoomEngine:
        def synthesize(self, text: str, **_kwargs):
            raise HTTPError(
                "http://127.0.0.1:8088/v1/audio/speech",
                500,
                "Internal Server Error",
                hdrs=None,
                fp=None,
            )

    monkeypatch.setattr(
        "presence_ui.services.tts_surface._build_engine", lambda: BoomEngine()
    )
    monkeypatch.setattr(
        "presence_ui.services.tts_surface._resolved_engine_name",
        lambda: "irodori",
    )
    with pytest.raises(RuntimeError, match="TTS synthesis failed"):
        synthesize_surface_audio("こよりやで")


def test_synthesize_surface_audio_wraps_url_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E-03: engine URLError → RuntimeError (not reachable)."""
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "http://127.0.0.1:8088")

    class TimeoutEngine:
        def synthesize(self, text: str, **_kwargs):
            raise URLError("timed out")

    monkeypatch.setattr(
        "presence_ui.services.tts_surface._build_engine", lambda: TimeoutEngine()
    )
    monkeypatch.setattr(
        "presence_ui.services.tts_surface._resolved_engine_name",
        lambda: "irodori",
    )
    with pytest.raises(RuntimeError, match="not reachable"):
        synthesize_surface_audio("こよりやで")


def test_build_engine_no_silent_fallback_to_voicevox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-07: TTS_DEFAULT_ENGINE=irodori with empty IRODORI_URL must not use VV."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("TTS_DEFAULT_ENGINE", "irodori")
    monkeypatch.setenv("IRODORI_URL", "")
    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")
    with pytest.raises(RuntimeError, match="irodori"):
        _build_engine()


def test_tts_configured_true_when_irodori_url_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E-05: unset IRODORI_URL defaults to :8088 → configured."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("VOICEVOX_URL", raising=False)
    monkeypatch.delenv("IRODORI_URL", raising=False)
    assert tts_configured() is True
