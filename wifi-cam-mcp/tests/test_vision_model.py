"""Vision LM model resolution — surface 12b-qat for all describe paths."""

from __future__ import annotations

import pytest

from wifi_cam_mcp.vision import (
    SURFACE_VISION_MODEL_DEFAULT,
    lm_studio_settings,
    resolve_vision_lm_model,
)


@pytest.fixture(autouse=True)
def _clear_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "PRESENCE_VISION_MODEL",
        "PRESENCE_LLM_MODEL",
        "CLAUDE_MODEL",
        "LMSTUDIO_MODEL",
        "LM_STUDIO_VISION_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_vision_lm_model_defaults_to_surface_12b_qat() -> None:
    assert resolve_vision_lm_model() == SURFACE_VISION_MODEL_DEFAULT
    assert SURFACE_VISION_MODEL_DEFAULT == "google/gemma-4-12b-qat"


def test_resolve_vision_lm_model_ignores_legacy_lm_studio_vision_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LM_STUDIO_VISION_MODEL", "google/gemma-4-e4b")
    assert resolve_vision_lm_model() == SURFACE_VISION_MODEL_DEFAULT


def test_resolve_vision_lm_model_prefers_chat_model_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_MODEL", "google/gemma-4-12b-qat")
    assert resolve_vision_lm_model() == "google/gemma-4-12b-qat"


def test_resolve_vision_lm_model_presence_vision_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_VISION_MODEL", "custom/vision-model")
    assert resolve_vision_lm_model() == "custom/vision-model"


def test_lm_studio_settings_uses_resolve_vision_lm_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LM_STUDIO_VISION_MODEL", "google/gemma-4-e4b-qat")
    _base, model, _token = lm_studio_settings()
    assert model == SURFACE_VISION_MODEL_DEFAULT
