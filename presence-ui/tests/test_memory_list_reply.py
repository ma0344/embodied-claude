"""Memory list direct reply formatting."""

from __future__ import annotations

from presence_ui.gateway.deterministic_memory import format_memory_list_reply


def test_format_memory_list_reply_empty() -> None:
    text = format_memory_list_reply([], limit=10, oldest_first=False)
    assert "空" in text


def test_format_memory_list_reply_numbered() -> None:
    rows = [
        {
            "id": "1",
            "content": "hello",
            "timestamp": "2026-06-12",
            "category": "daily",
            "emotion": "neutral",
        }
    ]
    text = format_memory_list_reply(rows, limit=10, oldest_first=False)
    assert "1." in text
    assert "hello" in text
