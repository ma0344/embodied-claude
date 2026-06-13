"""Room progress / activity NDJSON helpers."""

from __future__ import annotations

from presence_ui.gateway.room_events import (
    activities_from_sdk_message,
    activity_for_tool_use,
    encode_event,
    progress_event,
    register_tool_uses,
)


def test_progress_event_shape() -> None:
    evt = progress_event(phase="composing", label="文脈を集めてる…")
    assert evt["type"] == "room_progress"
    assert evt["label"] == "文脈を集めてる…"


def test_encode_event_is_ndjson_line() -> None:
    raw = encode_event(progress_event(phase="replying", label="考えてる"))
    assert raw.endswith(b"\n")
    assert b"room_progress" in raw


def test_activity_for_remember_tool() -> None:
    evt = activity_for_tool_use(
        "mcp__memory__remember",
        {"content": "明日は買い物"},
    )
    assert evt is not None
    assert evt["kind"] == "remember"
    assert "明日" in evt["detail"]


def test_activities_from_assistant_tool_use() -> None:
    data = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "id": "tu-1", "name": "mcp__wifi-cam__see", "input": {}},
            ],
        },
    }
    events = activities_from_sdk_message(data)
    assert len(events) == 1
    assert events[0]["kind"] == "see"


def test_activities_from_tool_result_with_name_map() -> None:
    assistant = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu-2",
                    "name": "mcp__memory__remember",
                    "input": {"content": "saved"},
                },
            ],
        },
    }
    tool_names: dict[str, str] = {}
    register_tool_uses(assistant, tool_names)
    user = {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu-2",
                    "content": "Memory saved!\nID: abc",
                },
            ],
        },
    }
    events = activities_from_sdk_message(user, tool_names=tool_names)
    assert len(events) == 1
    assert events[0]["label"] == "記憶に保存した"
