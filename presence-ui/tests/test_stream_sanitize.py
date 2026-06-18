"""Stream passthrough for room UI chat display."""

from __future__ import annotations

from presence_ui.gateway.stream_sanitize import (
    extract_assistant_speech,
    extract_user_speech,
    passthrough_stream_line,
    sanitize_stream_line,
)
from presence_ui.gateway.user_prompt import (
    plain_user_first_line,
    session_title_from_context,
    strip_enriched_user_prompt,
)


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


def test_strip_enriched_user_prompt_stm_recent_inside_gateway() -> None:
    raw = """[gateway_turn_context — not for the user]
[interaction_context]
phase=chat

[stm_recent]
- (open_loop_progress) 松本市の天気を調べた
- (episode_close) 【会話の一区切り】
こより: おはよう、まー。
まー: そっか、家は松本市だよ。
[/stm_recent]

こんばんは"""
    assert strip_enriched_user_prompt(raw) == "こんばんは"


def test_strip_enriched_user_prompt_real_session_shape() -> None:
    """Regression: MEM-4 stm_recent without [/stm_recent] — tail utterance only."""
    raw = """[gateway_turn_context — not for the user]
[interaction_context]
phase=chat

[stm_recent]
- (open_loop_progress) 松本市の天気
……うん、今日ちょっと疲れちゃったけど、まーの顔を見たら元気出たよ。
こより: 窓から光が入ってるから、今はいいお天気みたいだね。
- (episode_close) 【会話の一区切り】
こより: おはよう、まー。
- (…

こんばんは"""
    assert strip_enriched_user_prompt(raw) == "こんばんは"
    raw2 = raw.replace("こんばんは", "そういえば、僕が今暮らしているのはどこだか話したっけ？")
    assert (
        strip_enriched_user_prompt(raw2)
        == "そういえば、僕が今暮らしているのはどこだか話したっけ？"
    )


def test_strip_enriched_user_prompt_truncated_stm_close_tag() -> None:
    """Regression: truncate_prompt_text leaves ``[/stm_recent]…`` before user tail."""
    raw = """[gateway_turn_context — not for the user]
[interaction_context]
phase=chat

[stm_recent]
- (episode_close) 【会話の一区切り】
こより: まー、おかえり。
……うん、今日ちょっと疲れちゃったけど、まーの顔を見たら元気出たよ。
ゆっくりしようね。
こより: 窓から光が入ってるから、今はいいお天気みたいだね。

明日の天気については、どこの場所のことか教えてくれたら調べてみようか？
[/stm_recent]…

あーびっくりしたわ。"""
    assert strip_enriched_user_prompt(raw) == "あーびっくりしたわ。"


    raw = """[gateway_turn_context — not for the user]
[Social context]

おはよう"""
    assert plain_user_first_line(raw) == "おはよう"
    assert plain_user_first_line("PR review 明日やるの覚えといて") == "PR review 明日やるの覚えといて"


def test_strip_enriched_user_prompt_memory_saved_server() -> None:
    raw = """[memory_saved_server]
FACT: Hook/Gateway already saved this via memory-mcp HTTP (id=abc).
Content: PR review 明日やる
You may briefly confirm — do NOT call mcp__memory__remember again.

PR review 明日やるの覚えといて"""
    assert strip_enriched_user_prompt(raw) == "PR review 明日やるの覚えといて"
    assert plain_user_first_line(raw) == "PR review 明日やるの覚えといて"


def test_session_title_from_context_skips_injection() -> None:
    from presence_ui.schemas import ChatMessage

    messages = [
        ChatMessage(sender="ma", message="おはよう", timestamp="2026-06-14T10:00:00+00:00"),
    ]
    title = session_title_from_context(
        history_title="[gateway_turn_context — not for the user] [Socia",
        messages=messages,
        session_id="abc12345-aaaa-bbbb-cccc-ddddeeeeffff",
    )
    assert title == "おはよう"


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
