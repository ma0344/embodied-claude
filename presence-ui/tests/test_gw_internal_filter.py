"""Tests for gateway internal history filtering."""

from __future__ import annotations

from presence_ui.gateway.gw_internal_filter import (
    filter_room_visible_messages,
    is_gateway_internal_assistant_reply,
    is_gateway_internal_user_text,
)


def test_gateway_internal_user_marker() -> None:
    text = "[gateway_internal — not for まー]\ntask: pause_reflect\n"
    assert is_gateway_internal_user_text(text) is True


def test_normal_user_not_internal() -> None:
    assert is_gateway_internal_user_text("お昼ご飯は何にしよう") is False


def test_pause_json_assistant_reply() -> None:
    raw = (
        '{"hook":"沈黙","felt":"uneasy","next_move":"advance",'
        '"interest_tags":[],"followup_query":""}'
    )
    assert is_gateway_internal_assistant_reply(raw) is True


def test_normal_assistant_json_not_filtered() -> None:
    assert is_gateway_internal_assistant_reply('{"reply":"こんにちは"}') is False


def test_pause_json_with_markdown_fence() -> None:
    raw = """```json
{
  "hook": "沈黙",
  "felt": "uneasy",
  "next_move": "advance"
}
```"""
    assert is_gateway_internal_assistant_reply(raw) is True


def test_filter_room_visible_messages() -> None:
    rows = [
        {"sender": "ma", "message": "お昼"},
        {"sender": "koyori", "message": "うん"},
        {
            "sender": "koyori",
            "message": '{"hook":"x","felt":"y","next_move":"advance"}',
        },
    ]
    assert len(filter_room_visible_messages(rows)) == 2
