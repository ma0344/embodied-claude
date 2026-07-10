"""Tests for TTS engines."""

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from tts_mcp.engines.elevenlabs import ElevenLabsEngine, _split_sentences
from tts_mcp.engines.irodori import IrodoriEngine
from tts_mcp.engines.voicevox import VoicevoxEngine


class TestSplitSentences:
    """Tests for sentence splitting."""

    def test_japanese_sentences(self):
        text = "こんにちは。元気ですか？はい！"
        result = _split_sentences(text)
        assert result == ["こんにちは。", "元気ですか？", "はい！"]

    def test_english_sentences(self):
        text = "Hello world. How are you? Great!"
        result = _split_sentences(text)
        assert result == ["Hello world.", "How are you?", "Great!"]

    def test_single_sentence(self):
        text = "Hello"
        result = _split_sentences(text)
        assert result == ["Hello"]

    def test_empty_string(self):
        result = _split_sentences("")
        assert result == []


class TestElevenLabsEngine:
    """Tests for ElevenLabs engine."""

    def test_engine_name(self):
        engine = ElevenLabsEngine(api_key="test")
        assert engine.engine_name == "elevenlabs"

    def test_is_available_with_key(self):
        engine = ElevenLabsEngine(api_key="test-key")
        assert engine.is_available() is True

    def test_is_available_without_key(self):
        engine = ElevenLabsEngine(api_key="")
        assert engine.is_available() is False

    def test_synthesize_calls_client(self):
        engine = ElevenLabsEngine(api_key="test")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = b"fake-audio"
        engine._client = mock_client

        audio_bytes, fmt = engine.synthesize("hello")
        assert audio_bytes == b"fake-audio"
        assert fmt == "mp3"
        mock_client.text_to_speech.convert.assert_called_once()

    def test_synthesize_with_overrides(self):
        engine = ElevenLabsEngine(api_key="test")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = b"audio"
        engine._client = mock_client

        engine.synthesize("hello", voice_id="custom", model_id="v2")
        call_kwargs = mock_client.text_to_speech.convert.call_args
        assert call_kwargs.kwargs["voice_id"] == "custom"
        assert call_kwargs.kwargs["model_id"] == "v2"


class TestVoicevoxEngine:
    """Tests for VOICEVOX engine."""

    def test_engine_name(self):
        engine = VoicevoxEngine()
        assert engine.engine_name == "voicevox"

    def test_default_url_and_speaker(self):
        engine = VoicevoxEngine()
        assert engine._url == "http://localhost:50021"
        assert engine._speaker == 3

    def test_url_trailing_slash_stripped(self):
        engine = VoicevoxEngine(url="http://localhost:50021/")
        assert engine._url == "http://localhost:50021"

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_is_available_true(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'"0.14.0"'
        mock_urlopen.return_value = mock_resp

        engine = VoicevoxEngine()
        assert engine.is_available() is True

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_is_available_false_on_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        engine = VoicevoxEngine()
        assert engine.is_available() is False

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_synthesize(self, mock_urlopen):
        query_resp = MagicMock()
        query_resp.__enter__ = MagicMock(return_value=query_resp)
        query_resp.__exit__ = MagicMock(return_value=False)
        query_resp.read.return_value = json.dumps({"speedScale": 1.0}).encode()

        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"RIFF-fake-wav"

        mock_urlopen.side_effect = [query_resp, synth_resp]

        engine = VoicevoxEngine(speaker=1)
        audio_bytes, fmt = engine.synthesize("テスト")

        assert audio_bytes == b"RIFF-fake-wav"
        assert fmt == "wav"
        assert mock_urlopen.call_count == 2

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_synthesize_with_speed_scale(self, mock_urlopen):
        query_resp = MagicMock()
        query_resp.__enter__ = MagicMock(return_value=query_resp)
        query_resp.__exit__ = MagicMock(return_value=False)
        query_resp.read.return_value = json.dumps(
            {"speedScale": 1.0, "pitchScale": 0.0}
        ).encode()

        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"wav-data"

        mock_urlopen.side_effect = [query_resp, synth_resp]

        engine = VoicevoxEngine()
        engine.synthesize("テスト", speed_scale=1.5, pitch_scale=0.1)

        # Check that the synthesis request body has modified speedScale
        synth_call = mock_urlopen.call_args_list[1]
        req = synth_call[0][0]
        body = json.loads(req.data)
        assert body["speedScale"] == 1.5
        assert body["pitchScale"] == 0.1


class TestIrodoriEngine:
    """Tests for Irodori engine."""

    def test_engine_name(self):
        engine = IrodoriEngine()
        assert engine.engine_name == "irodori"

    def test_defaults(self):
        engine = IrodoriEngine()
        assert engine._url == "http://127.0.0.1:8088"
        assert engine._voice == "none"
        assert engine._num_steps == 24
        assert engine._model == "irodori-tts"
        assert engine._timeout_sec == 120.0

    def test_empty_voice_becomes_none(self):
        engine = IrodoriEngine(voice="")
        assert engine._voice == "none"

    def test_url_trailing_slash_stripped(self):
        engine = IrodoriEngine(url="http://127.0.0.1:8088/")
        assert engine._url == "http://127.0.0.1:8088"

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_is_available_true(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_urlopen.return_value = mock_resp

        engine = IrodoriEngine()
        assert engine.is_available() is True
        req = mock_urlopen.call_args[0][0]
        assert req.full_url.endswith("/health")

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_is_available_false_on_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        engine = IrodoriEngine()
        assert engine.is_available() is False

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_is_available_false_on_http_error(self, mock_urlopen):
        """E-02: health HTTPError → not available."""
        mock_urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8088/health", 503, "Unavailable", hdrs=None, fp=None
        )
        engine = IrodoriEngine()
        assert engine.is_available() is False

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_is_available_false_on_timeout(self, mock_urlopen):
        """E-02: health URLError/timeout → not available."""
        mock_urlopen.side_effect = URLError("timed out")
        engine = IrodoriEngine()
        assert engine.is_available() is False

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_synthesize(self, mock_urlopen):
        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"RIFF-irodori-wav"
        mock_urlopen.return_value = synth_resp

        engine = IrodoriEngine()
        audio_bytes, fmt = engine.synthesize("テスト")

        assert audio_bytes == b"RIFF-irodori-wav"
        assert fmt == "wav"
        req = mock_urlopen.call_args[0][0]
        assert req.full_url.endswith("/v1/audio/speech")
        body = json.loads(req.data)
        assert body == {
            "model": "irodori-tts",
            "input": "テスト",
            "voice": "none",
            "response_format": "wav",
            "irodori": {"num_steps": 24},
        }

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_synthesize_with_overrides(self, mock_urlopen):
        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"wav"
        mock_urlopen.return_value = synth_resp

        engine = IrodoriEngine()
        engine.synthesize("hi", voice="", num_steps=16)
        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert body["voice"] == "none"
        assert body["irodori"]["num_steps"] == 16

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_synthesize_with_voice_profile(self, mock_urlopen):
        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"wav"
        mock_urlopen.return_value = synth_resp

        engine = IrodoriEngine(
            voice="koyori",
            seed=8787384312565159089,
            cfg_scale_caption=10.0,
            cfg_scale_speaker=2.0,
        )
        engine.synthesize("こんにちは")
        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert body["voice"] == "koyori"
        assert body["irodori"] == {
            "num_steps": 24,
            "seed": 8787384312565159089,
            "cfg_scale_caption": 10.0,
            "cfg_scale_speaker": 2.0,
        }
        assert engine.cache_profile() == "koyori:24:8787384312565159089:10.0:2.0"
        assert body["response_format"] == "wav"

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_synthesize_propagates_http_error(self, mock_urlopen):
        """E-03: synth HTTP 500 propagates (not swallowed)."""
        mock_urlopen.side_effect = HTTPError(
            "http://127.0.0.1:8088/v1/audio/speech",
            500,
            "Internal Server Error",
            hdrs=None,
            fp=None,
        )
        engine = IrodoriEngine()
        with pytest.raises(HTTPError) as exc_info:
            engine.synthesize("テスト")
        assert exc_info.value.code == 500

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_synthesize_propagates_url_error_timeout(self, mock_urlopen):
        """E-03: synth URLError/timeout propagates."""
        mock_urlopen.side_effect = URLError("timed out")
        engine = IrodoriEngine()
        with pytest.raises(URLError):
            engine.synthesize("テスト")

    @patch("tts_mcp.engines.irodori.urllib.request.urlopen")
    def test_health_ok_synth_http_error_separated(self, mock_urlopen):
        """E-15: /health OK does not hide synth 5xx failure."""
        health_resp = MagicMock()
        health_resp.__enter__ = MagicMock(return_value=health_resp)
        health_resp.__exit__ = MagicMock(return_value=False)
        health_resp.read.return_value = b'{"status":"ok"}'

        mock_urlopen.side_effect = [
            health_resp,
            HTTPError(
                "http://127.0.0.1:8088/v1/audio/speech",
                500,
                "Internal Server Error",
                hdrs=None,
                fp=None,
            ),
        ]
        engine = IrodoriEngine()
        assert engine.is_available() is True
        with pytest.raises(HTTPError) as exc_info:
            engine.synthesize("テスト")
        assert exc_info.value.code == 500
        assert mock_urlopen.call_count == 2
        assert mock_urlopen.call_args_list[0][0][0].full_url.endswith("/health")
        assert mock_urlopen.call_args_list[1][0][0].full_url.endswith(
            "/v1/audio/speech"
        )
