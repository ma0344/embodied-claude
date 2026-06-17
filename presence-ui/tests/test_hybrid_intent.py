"""Tests for C12 hybrid intent router."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from presence_ui.gateway.hybrid_intent import (
    resolve_hybrid_intent,
    should_try_llm_fallback,
)
from presence_ui.gateway.user_intent import resolve_user_intent


def test_should_not_llm_on_greeting() -> None:
    rules = resolve_user_intent("おはよう")
    assert should_try_llm_fallback("おはよう", rules) is False


def test_should_llm_on_ambiguous_desk() -> None:
    rules = resolve_user_intent("デスク周りどう？")
    assert rules.wants_observe is False
    assert should_try_llm_fallback("デスク周りどう？", rules) is True


def test_rules_path_explicit_say() -> None:
    with patch("presence_ui.gateway.hybrid_intent.classify_with_llm") as mock_llm:
        hybrid = resolve_hybrid_intent("何か say でしゃべって")
    mock_llm.assert_not_called()
    assert hybrid.source == "rules"
    assert hybrid.user_intent.wants_speech is True


def test_llm_fallback_observe_desk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_LLM_INTENT_FALLBACK", "1")
    with (
        patch("presence_ui.gateway.hybrid_intent.lm_studio_available", return_value=True),
        patch(
            "presence_ui.gateway.hybrid_intent.classify_with_llm",
            return_value=(["observe_desk"], 1.0, "{}"),
        ),
    ):
        hybrid = resolve_hybrid_intent("デスク周りどう？")
    assert hybrid.source == "llm"
    assert hybrid.see_intent is not None
    assert hybrid.see_intent.mode == "desk"
    assert hybrid.user_intent.wants_observe is True


def test_llm_fallback_ptz_left(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_LLM_INTENT_FALLBACK", "1")
    with (
        patch("presence_ui.gateway.hybrid_intent.lm_studio_available", return_value=True),
        patch(
            "presence_ui.gateway.hybrid_intent.classify_with_llm",
            return_value=(["ptz_left"], 1.0, "{}"),
        ),
    ):
        hybrid = resolve_hybrid_intent("ちょっと左")
    assert hybrid.ptz_intent is not None
    assert hybrid.ptz_intent.direction == "left"


def test_llm_strips_chat_when_body_present() -> None:
    from presence_ui.gateway.intent_labels import normalize_intent_labels

    assert normalize_intent_labels(["chat", "speech"]) == ["speech"]
