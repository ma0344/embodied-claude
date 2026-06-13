"""Deterministic remember intent detection and HTTP persistence."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from presence_ui.gateway import deterministic_memory as dm


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ミッションAのE2Eを覚えておいて", "ミッションAのE2E"),
        ("覚えておいて: 明日は買い物", "明日は買い物"),
        ("remember this: kiosk saves server-side", "kiosk saves server-side"),
        ("hello world", None),
        ("覚えておいて", None),
    ],
)
def test_detect_remember_intent(text: str, expected: str | None) -> None:
    intent = dm.detect_remember_intent(text)
    if expected is None:
        assert intent is None
    else:
        assert intent is not None
        assert intent.content == expected


def test_persist_remember_intent_success() -> None:
    payload = b'{"ok": true, "id": "mem-1", "duplicate": false}'
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response):
        outcome = dm.persist_remember_intent(dm.RememberIntent(content="test fact"))

    assert outcome.ok is True
    assert outcome.memory_id == "mem-1"
    assert outcome.duplicate is False


def test_persist_remember_intent_http_error() -> None:
    import urllib.error

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        outcome = dm.persist_remember_intent(dm.RememberIntent(content="x"))

    assert outcome.ok is False
    assert outcome.error


def test_memory_saved_prompt_note() -> None:
    ok = dm.memory_saved_prompt_note(
        dm.RememberOutcome(ok=True, content="foo", memory_id="id-1")
    )
    assert "[memory_saved_server]" in ok
    assert "Do not call mcp__memory__remember" in ok

    fail = dm.memory_saved_prompt_note(
        dm.RememberOutcome(ok=False, content="foo", error="timeout")
    )
    assert "[memory_save_failed]" in fail
