"""A4c+ surface TTS — synthesize API and cached audio files."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
from presence_ui.services.tts_surface import (
    _text_token,
    surface_audio_path,
    surface_tts_enabled,
    synthesize_surface_audio,
)


def test_surface_tts_enabled_requires_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOICEVOX_URL", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("PRESENCE_OUTBOUND_SURFACE_TTS", "1")
    assert surface_tts_enabled() is False

    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")
    assert surface_tts_enabled() is True

    monkeypatch.setenv("PRESENCE_OUTBOUND_SURFACE_TTS", "0")
    assert surface_tts_enabled() is False


def test_synthesize_surface_audio_caches(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    calls: list[str] = []

    class FakeEngine:
        def synthesize(self, text: str, **_kwargs):
            calls.append(text)
            return b"RIFFfake", "wav"

    monkeypatch.setattr("presence_ui.services.tts_surface._build_engine", lambda: FakeEngine())

    token1, fmt1, media1 = synthesize_surface_audio("まー、おる？")
    token2, fmt2, media2 = synthesize_surface_audio("  まー、おる？  ")

    assert token1 == token2 == _text_token("まー、おる？")
    assert fmt1 == fmt2 == "wav"
    assert media1 == media2 == "audio/wav"
    assert len(calls) == 1
    assert (tmp_path / f"{token1}.wav").is_file()
    assert surface_audio_path(token1) == tmp_path / f"{token1}.wav"


def test_surface_audio_path_rejects_invalid_token(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    assert surface_audio_path("../etc/passwd") is None
    assert surface_audio_path("not-a-token") is None


def test_tts_surface_api(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_TTS_SURFACE_DIR", str(tmp_path))
    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")

    class FakeEngine:
        def synthesize(self, text: str, **_kwargs):
            return b"RIFFfake", "wav"

    monkeypatch.setattr("presence_ui.services.tts_surface._build_engine", lambda: FakeEngine())

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


def test_ui_config_exposes_surface_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")
    body = TestClient(create_app()).get("/api/v1/ui-config").json()
    assert body["outbound_surface_tts_enabled"] is True
    assert body["surface_tts_synthesize_path"] == "/api/v1/tts/surface"
