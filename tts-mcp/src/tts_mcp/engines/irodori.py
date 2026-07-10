"""Irodori TTS engine (OpenAI-compatible /v1/audio/speech)."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT_SEC = 3.0


class IrodoriEngine:
    """Irodori TTS engine (local HTTP API on :8088 by default)."""

    def __init__(
        self,
        url: str = "http://127.0.0.1:8088",
        voice: str = "none",
        num_steps: int = 24,
        model: str = "irodori-tts",
        timeout_sec: float = 120.0,
        *,
        seed: int | None = None,
        cfg_scale_caption: float | None = None,
        cfg_scale_speaker: float | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._voice = voice if voice.strip() else "none"
        self._num_steps = num_steps
        self._model = model
        self._timeout_sec = timeout_sec
        self._seed = seed
        self._cfg_scale_caption = cfg_scale_caption
        self._cfg_scale_speaker = cfg_scale_speaker

    @property
    def engine_name(self) -> str:
        return "irodori"

    def cache_profile(self) -> str:
        """Stable label for surface TTS cache keys (voice + inference opts)."""
        parts = [
            self._voice,
            str(self._num_steps),
            str(self._seed),
            str(self._cfg_scale_caption),
            str(self._cfg_scale_speaker),
        ]
        return ":".join(parts)

    def is_available(self) -> bool:
        """Check if Irodori TTS is running (GET /health)."""
        try:
            req = urllib.request.Request(f"{self._url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=_HEALTH_TIMEOUT_SEC) as resp:
                resp.read()
            return True
        except Exception:
            return False

    def _irodori_payload(self, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "num_steps": int(kwargs.get("num_steps", self._num_steps)),
        }
        seed = kwargs.get("seed", self._seed)
        if seed is not None:
            payload["seed"] = int(seed)
        cfg_caption = kwargs.get("cfg_scale_caption", self._cfg_scale_caption)
        if cfg_caption is not None:
            payload["cfg_scale_caption"] = float(cfg_caption)
        cfg_speaker = kwargs.get("cfg_scale_speaker", self._cfg_scale_speaker)
        if cfg_speaker is not None:
            payload["cfg_scale_speaker"] = float(cfg_speaker)
        return payload

    def synthesize(self, text: str, **kwargs: Any) -> tuple[bytes, str]:
        """Synthesize text via POST /v1/audio/speech.

        Kwargs:
            voice: Override voice name (empty → none).
            num_steps: Override diffusion steps.
            seed: Override random seed.
            cfg_scale_caption: Override caption CFG scale.
            cfg_scale_speaker: Override speaker CFG scale.

        Returns:
            Tuple of (wav_bytes, 'wav').
        """
        voice = kwargs.get("voice", self._voice)
        if not str(voice).strip():
            voice = "none"
        model = kwargs.get("model", self._model)

        body = json.dumps(
            {
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": "wav",
                "irodori": self._irodori_payload(**kwargs),
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self._url}/v1/audio/speech",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout_sec) as resp:
            wav_bytes = resp.read()
        return wav_bytes, "wav"
