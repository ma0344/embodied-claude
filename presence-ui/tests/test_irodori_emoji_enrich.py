"""Tests for Irodori TTS emoji enrich (e4b Stage-2)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from presence_ui.gateway.irodori_emoji_allowlist import IRODORI_EMOJI_ALLOWLIST
from presence_ui.gateway.irodori_emoji_enrich import (
    clear_irodori_emoji_cache_for_tests,
    enrich_irodori_emoji,
    parse_irodori_emoji_response,
    prepare_irodori_tts_line,
    sanitize_irodori_emojis,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_irodori_emoji_cache_for_tests()


def test_sanitize_drops_disallowed_emoji() -> None:
    raw = "まー😊おはよう🚀やで"
    cleaned = sanitize_irodori_emojis(raw)
    assert "😊" in cleaned
    assert "🚀" not in cleaned
    assert "まー" in cleaned


def test_sanitize_keeps_zwj_emoji() -> None:
    raw = "うーん😮‍💨しんどいわ"
    cleaned = sanitize_irodori_emojis(raw)
    assert "😮‍💨" in cleaned


def test_parse_irodori_emoji_response() -> None:
    out = parse_irodori_emoji_response(
        '{"tts_input":"まー😊おはよう"}',
        fallback="plain",
    )
    assert out == "まー😊おはよう"


def test_parse_falls_back_on_bad_json() -> None:
    assert parse_irodori_emoji_response("not json", fallback="plain") == "plain"


def test_enrich_calls_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_IRODORI_EMOJI_ENRICH", "1")
    with patch(
        "presence_ui.gateway.irodori_emoji_enrich.run_classifier_turn",
        return_value='{"tts_input":"まー😊おはよう"}',
    ) as mock_turn:
        out = enrich_irodori_emoji("まー、おはよう")
    assert out == "まー😊おはよう"
    mock_turn.assert_called_once()


def test_prepare_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_IRODORI_EMOJI_ENRICH", "0")
    with patch(
        "presence_ui.gateway.irodori_emoji_enrich.run_classifier_turn",
    ) as mock_turn:
        out = prepare_irodori_tts_line("まー、おはよう")
    assert out == "まー、おはよう"
    mock_turn.assert_not_called()


def test_prepare_skips_when_not_irodori(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_IRODORI_EMOJI_ENRICH", "1")
    with (
        patch(
            "presence_ui.gateway.irodori_emoji_enrich._irodori_is_default_engine",
            return_value=False,
        ),
        patch(
            "presence_ui.gateway.irodori_emoji_enrich.run_classifier_turn",
        ) as mock_turn,
    ):
        out = prepare_irodori_tts_line("まー、おはよう")
    assert out == "まー、おはよう"
    mock_turn.assert_not_called()


def test_prepare_uses_module_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_IRODORI_EMOJI_ENRICH", "1")
    with (
        patch(
            "presence_ui.gateway.irodori_emoji_enrich._irodori_is_default_engine",
            return_value=True,
        ),
        patch(
            "presence_ui.gateway.irodori_emoji_enrich.run_classifier_turn",
            return_value='{"tts_input":"まー😊"}',
        ) as mock_turn,
    ):
        first = prepare_irodori_tts_line("まー")
        second = prepare_irodori_tts_line("まー")
    assert first == second == "まー😊"
    assert mock_turn.call_count == 1


def test_allowlist_non_empty() -> None:
    assert "😊" in IRODORI_EMOJI_ALLOWLIST
    assert len(IRODORI_EMOJI_ALLOWLIST) >= 40
