"""Tests for MEM-8h-C memory bridge."""

from __future__ import annotations

from interaction_orchestrator_mcp.memory_bridge import (
    MemoryBridgeHit,
    apply_memory_bridge_to_context,
    format_bridge_lines,
    hits_from_http_items,
    merge_bridge_hits,
)
from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    ResponseContract,
)


def test_hits_from_http_skips_episodic() -> None:
    items = [
        {"content": "【会話の区切り】\n" + ("log\n" * 20), "score": 0.9},
        {
            "content": "まーが梅干しづくりを提案した",
            "score": 0.7,
            "timestamp": "2026-07-03T10:00:00+09:00",
        },
    ]
    hits = hits_from_http_items(items, keyword="梅干し")
    assert len(hits) == 1
    assert "梅干し" in hits[0].content


def test_format_bridge_lines_includes_date() -> None:
    hits = [
        MemoryBridgeHit(
            keyword="梅干し",
            content="まーが梅干しづくりを提案",
            timestamp="2026-07-03T10:00:00+09:00",
            score=0.8,
        )
    ]
    lines = format_bridge_lines(hits, tz_name="Asia/Tokyo")
    assert lines[0].startswith("- 2026-07-03:")
    assert "梅干し" in lines[0]


def test_merge_dedupes_existing_compose_memories() -> None:
    hit = MemoryBridgeHit(
        keyword="梅",
        content="same fact",
        timestamp="2026-07-01T00:00:00+00:00",
        score=0.9,
    )
    merged = merge_bridge_hits([[hit]], existing_contents={"same fact"}, max_lines=3)
    assert merged == []


def test_apply_memory_bridge_pins_in_compact() -> None:
    ctx = InteractionContext(
        ts="2026-07-03T11:00:00+00:00",
        local_time="2026-07-03T20:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state=AgentStateSummary(ts="2026-07-03T11:00:00+00:00"),
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[interaction_context]\nold",
    )
    updated = apply_memory_bridge_to_context(
        ctx,
        bridge_lines=["- 2026-07-03: 梅干しづくりの話"],
        user_text="梅干し作ろう",
        max_chars=8000,
    )
    assert "[memory_bridge" in updated.compact_prompt_block
    assert "2026-07-03" in updated.compact_prompt_block
