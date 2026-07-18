"""Tests for MEM-8h memory bridge (C + D)."""

from __future__ import annotations

from interaction_orchestrator_mcp.memory_bridge import (
    MemoryBridgeHit,
    apply_memory_bridge_to_context,
    bridge_fact_refs,
    format_bridge_lines,
    hits_from_http_items,
    merge_bridge_hits,
)
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.recall_query import bridge_hit_rank, is_fact_like_row
from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    PlanResponseInput,
    ResponseContract,
)


def _ctx(**updates) -> InteractionContext:
    base = InteractionContext(
        ts="2026-07-03T11:00:00+00:00",
        local_time="2026-07-03T20:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state=AgentStateSummary(ts="2026-07-03T11:00:00+00:00"),
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[interaction_context]\nold",
    )
    return base.model_copy(update=updates)


def test_is_fact_like_row() -> None:
    assert is_fact_like_row("まーが梅干しづくりを提案した")
    assert not is_fact_like_row("【会話の区切り】\n" + ("log\n" * 20))


def test_bridge_hit_rank_prefers_fact_over_episode_snippet() -> None:
    fact_score = bridge_hit_rank(
        "まーが梅干しづくりを提案",
        base_relevance=0.6,
        category="observation",
        importance=4,
    )
    long_score = bridge_hit_rank(
        "まーが梅干しの話を長々としていた " + ("詳細 " * 30),
        base_relevance=0.7,
        category="daily",
    )
    assert fact_score > long_score


def test_hits_from_http_skips_episodic() -> None:
    items = [
        {"content": "【会話の区切り】\n" + ("log\n" * 20), "score": 0.9},
        {
            "content": "まーが梅干しづくりを提案した",
            "score": 0.7,
            "timestamp": "2026-07-03T10:00:00+09:00",
            "category": "observation",
            "importance": 4,
        },
    ]
    hits = hits_from_http_items(items, keyword="梅干し")
    assert len(hits) == 1
    assert "梅干し" in hits[0].content


def test_hits_from_http_skips_literary_agent() -> None:
    items = [
        {
            "content": "青空文庫で読んだ『羅生門』（芥川龍之介）— 下人は",
            "score": 0.99,
            "timestamp": "2026-07-17T21:00:00+09:00",
            "category": "feeling",
        },
        {
            "content": "まーの体調がすぐれない日があった",
            "score": 0.7,
            "timestamp": "2026-07-06T10:00:00+09:00",
            "category": "memory",
        },
    ]
    hits = hits_from_http_items(items, keyword="大丈夫")
    assert len(hits) == 1
    assert "体調" in hits[0].content


def test_hits_from_http_skips_legacy_food_talk() -> None:
    items = [
        {
            "content": "まーが蕎麦の話をした（食事の話題）",
            "score": 0.99,
            "category": "observation",
        },
        {
            "content": "まーは直近で7月1日に麺類（蕎麦）を食べた記録がある",
            "score": 0.8,
            "timestamp": "2026-07-01T12:00:00+09:00",
            "category": "observation",
        },
    ]
    hits = hits_from_http_items(items, keyword="麺類")
    assert len(hits) == 1
    assert "食べた記録" in hits[0].content


def test_hits_from_http_skips_vision_noise() -> None:
    items = [
        {
            "content": (
                "窓/外 Captured image at 20260708_130516 (640x360). "
                "=== VISION_CAPTION === 部屋の奥には"
            ),
            "score": 0.9,
            "category": "observation",
        },
        {
            "content": "まーのデスク === VISION_DESCRIBE_FAILED === LM Studio",
            "score": 0.88,
            "category": "observation",
        },
        {
            "content": "まーは直近で7月1日に麺類（蕎麦）を食べた記録がある",
            "score": 0.7,
            "timestamp": "2026-07-01T12:00:00+09:00",
            "category": "observation",
            "importance": 3,
        },
    ]
    hits = hits_from_http_items(items, keyword="家に")
    assert len(hits) == 1
    assert "食べた記録" in hits[0].content


def test_extract_bridge_keywords_skips_weak_bigrams() -> None:
    from interaction_orchestrator_mcp.memory_bridge import extract_bridge_keywords

    kws = extract_bridge_keywords(
        "家に麺があるから、サッパリ系の冷たいラーメンにするわ"
    )
    assert "家に" not in kws
    assert "家に麺があるから" in kws
    assert any("ラーメン" in k for k in kws)

    noodle = extract_bridge_keywords("麺類かなぁ。。。")
    assert "麺類かなぁ" in noodle
    assert "類か" not in noodle


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


def test_bridge_fact_refs_promote_compact_facts() -> None:
    hits = [
        MemoryBridgeHit(
            keyword="梅干し",
            content="まーが梅干しづくりを提案した",
            timestamp="2026-07-03T10:00:00+09:00",
            score=0.85,
        )
    ]
    refs = bridge_fact_refs(hits, existing_contents=set())
    assert len(refs) == 1
    assert refs[0].use_policy == "mentionable"
    assert refs[0].reason == "memory_bridge_fact_row"


def test_apply_memory_bridge_pins_and_sets_ctx_fields() -> None:
    hits = [
        MemoryBridgeHit(
            keyword="梅干し",
            content="まーが梅干しづくりを提案した",
            timestamp="2026-07-03T10:00:00+09:00",
            score=0.85,
        )
    ]
    updated = apply_memory_bridge_to_context(
        _ctx(),
        bridge_lines=["- 2026-07-03: 梅干しづくりの話"],
        bridge_keywords=["梅干し"],
        bridge_hits=hits,
        user_text="梅干し作ろう",
        max_chars=8000,
    )
    assert "[memory_bridge" in updated.compact_prompt_block
    assert updated.memory_bridge_lines
    assert updated.memory_bridge_keywords == ["梅干し"]
    assert any(m.reason == "memory_bridge_fact_row" for m in updated.relevant_memories)


def test_plan_soft_must_include_for_bridge() -> None:
    ctx = _ctx(
        memory_bridge_lines=["- 2026-07-03: 梅干しづくり"],
        memory_bridge_keywords=["梅干し"],
    )
    plan = plan_response(
        PlanResponseInput(interaction_context=ctx, user_text="梅干し作ろうかな")
    )
    joined = " ".join(plan.must_include)
    assert "memory_bridge (soft)" in joined
    assert "梅干し" in joined


def test_plan_skips_bridge_soft_on_stay_silent() -> None:
    ctx = _ctx(
        memory_bridge_lines=["- 2026-07-03: 梅干し"],
        memory_bridge_keywords=["梅干し"],
        boundary_hints=["quiet hours are active"],
        social_state={"availability": "do_not_interrupt", "interaction_phase": "idle"},
    )
    plan = plan_response(
        PlanResponseInput(interaction_context=ctx, user_text="梅干し")
    )
    assert plan.primary_move in {"stay_silent", "defer"}
    assert not any("memory_bridge (soft)" in item for item in plan.must_include)
