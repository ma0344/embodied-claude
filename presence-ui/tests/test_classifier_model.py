"""PFC-1 — classifier model split (PRESENCE_CLASSIFIER_*)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.services.llm import _lm_classifier_settings, _lm_studio_settings


@pytest.fixture(autouse=True)
def _clear_classifier_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_CLASSIFIER_MODEL", raising=False)
    monkeypatch.delenv("PRESENCE_CLASSIFIER_BASE_URL", raising=False)
    monkeypatch.delenv("PRESENCE_LLM_MODEL", raising=False)
    monkeypatch.setenv("CLAUDE_MODEL", "google/gemma-4-12b-qat")


def test_lm_classifier_settings_falls_back_to_surface() -> None:
    base, model, _token = _lm_classifier_settings()
    chat_base, chat_model, _ = _lm_studio_settings()
    assert base == chat_base
    assert model == chat_model


def test_lm_classifier_settings_uses_e4b_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_CLASSIFIER_MODEL", "google/gemma-4-e4b")
    monkeypatch.setenv("PRESENCE_CLASSIFIER_BASE_URL", "http://127.0.0.1:1235")
    base, model, _token = _lm_classifier_settings()
    assert model == "google/gemma-4-e4b"
    assert base == "http://127.0.0.1:1235"


def test_run_classifier_turn_posts_classifier_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_CLASSIFIER_MODEL", "google/gemma-4-e4b")
    captured: dict = {}

    def fake_post(_self, url, *, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"utterance_kind":"greeting"}'}}],
        }
        return response

    with (
        patch(
            "presence_ui.gateway.gw_silent.lm_studio_available",
            return_value=True,
        ),
        patch("httpx.Client.post", fake_post),
    ):
        result = run_classifier_turn(
            system="classifier system",
            user="こんにちは",
            log_label="test classifier",
        )

    assert result == '{"utterance_kind":"greeting"}'
    assert captured["json"]["model"] == "google/gemma-4-e4b"
    assert captured["url"].endswith("/v1/chat/completions")


def test_run_classifier_turn_surface_scope_ignores_classifier_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_CLASSIFIER_MODEL", "google/gemma-4-e4b")
    monkeypatch.setenv("PRESENCE_LLM_MODEL", "google/gemma-4-12b-qat")
    captured: dict = {}

    def fake_post(_self, url, *, json, headers):
        captured["json"] = json
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": '{"next_move":"advance"}'}}],
        }
        return response

    with (
        patch(
            "presence_ui.gateway.gw_silent.lm_studio_available",
            return_value=True,
        ),
        patch("httpx.Client.post", fake_post),
    ):
        run_classifier_turn(
            system="GW-S1",
            user="pause task",
            model_scope="surface",
            log_label="GW-S1",
        )

    assert captured["json"]["model"] == "google/gemma-4-12b-qat"
