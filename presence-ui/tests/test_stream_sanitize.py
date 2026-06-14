"""Stream passthrough for room UI chat display."""

from __future__ import annotations

from presence_ui.gateway.stream_sanitize import (
    extract_assistant_speech,
    extract_user_speech,
    passthrough_stream_line,
    sanitize_stream_line,
)
from presence_ui.gateway.user_prompt import strip_enriched_user_prompt


def test_extract_assistant_speech_keeps_text_blocks_verbatim() -> None:
    msg = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "[excited] うち、聞いてるで！"},
                {"type": "text", "text": "まーの隣にいるで。"},
            ]
        },
    }
    assert extract_assistant_speech(msg) == "[excited] うち、聞いてるで！\nまーの隣にいるで。"


def test_extract_assistant_speech_ignores_thinking_and_tool_use() -> None:
    msg = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "thinking", "thinking": "internal planner note"},
                {"type": "tool_use", "name": "Read", "input": {}},
                {"type": "text", "text": "うち、聞いてるで。"},
            ]
        },
    }
    assert extract_assistant_speech(msg) == "うち、聞いてるで。"


def test_extract_user_speech_uses_user_text_hint() -> None:
    msg = {
        "type": "user",
        "message": {
            "content": [{"type": "text", "text": "[Social context]\nctx\n\nまーの発話"}],
        },
    }
    assert extract_user_speech(msg, user_text="まーの発話") == "まーの発話"


def test_strip_enriched_user_prompt_for_history_fallback() -> None:
    raw = """[recent_room_context session_id=x]
Room arc: 1 turns.
まー: やあ
やあ"""
    assert strip_enriched_user_prompt(raw) == "やあ"


def test_strip_enriched_user_prompt_gateway_turn_context() -> None:
    raw = """[gateway_turn_context — not for the user]
[Social context]
[interaction_context]
phase=chat

こんばんは"""
    assert strip_enriched_user_prompt(raw) == "こんばんは"


def test_passthrough_stream_line_keeps_thinking_only_assistant() -> None:
    line = {
        "type": "claude_json",
        "data": {
            "type": "assistant",
            "message": {
                "content": [{"type": "thinking", "thinking": "hidden"}],
            },
        },
    }
    out = passthrough_stream_line(line, user_text="")
    assert out is not None
    assert out["data"] == line["data"]


def test_passthrough_stream_line_preserves_full_assistant_content() -> None:
    line = {
        "type": "claude_json",
        "data": {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "hidden"},
                    {"type": "text", "text": "[excited] うちやで。"},
                ]
            },
        },
    }
    out = passthrough_stream_line(line, user_text="")
    assert out is not None
    assert out["data"]["message"]["content"] == line["data"]["message"]["content"]


def test_passthrough_stream_line_preserves_user_room_context() -> None:
    enriched = """[recent_room_context session_id=abc]
Room arc: 2 turns.
まー: テスト"""
    line = {
        "type": "claude_json",
        "data": {
            "type": "user",
            "message": {"content": [{"type": "text", "text": enriched}]},
        },
    }
    out = passthrough_stream_line(line, user_text="")
    assert out is not None
    assert out["data"]["message"]["content"][0]["text"] == enriched


def test_passthrough_stream_line_passes_system_init() -> None:
    init_line = {
        "type": "claude_json",
        "data": {"type": "system", "subtype": "init", "session_id": "abc-123"},
    }
    out = passthrough_stream_line(init_line, user_text="hi")
    assert out == {"type": "claude_json", "data": init_line["data"]}


def test_passthrough_stream_line_passes_system_thinking_tokens() -> None:
    thinking_tokens = {
        "type": "claude_json",
        "data": {
            "type": "system",
            "subtype": "thinking_tokens",
            "session_id": "abc-123",
            "estimated_tokens": 1,
        },
    }
    out = passthrough_stream_line(thinking_tokens, user_text="hi")
    assert out == {"type": "claude_json", "data": thinking_tokens["data"]}


def test_passthrough_stream_line_passes_result() -> None:
    line = {
        "type": "claude_json",
        "data": {"type": "result", "subtype": "success", "result": "done"},
    }
    out = passthrough_stream_line(line, user_text="")
    assert out == {"type": "claude_json", "data": line["data"]}


def test_sanitize_stream_line_alias_matches_passthrough() -> None:
    line = {"type": "error", "error": "boom"}
    assert sanitize_stream_line(line, user_text="") == passthrough_stream_line(line, user_text="")
