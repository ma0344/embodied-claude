"""SDK content block extraction tests."""

from __future__ import annotations

from presence_ui.gateway.sdk_content import extract_text_blocks, join_text_blocks


def test_extract_text_blocks_from_string() -> None:
    assert extract_text_blocks("  hello  ") == ["hello"]


def test_extract_text_blocks_skips_non_text() -> None:
    content = [
        {"type": "thinking", "thinking": "nope"},
        {"type": "text", "text": "yes"},
        {"type": "tool_use", "name": "Read", "input": {}},
    ]
    assert join_text_blocks(content) == "yes"
