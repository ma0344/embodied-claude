"""Tests for MEM-8b conditional compose stage-2 recall."""

from __future__ import annotations

from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    RelevantMemoryRef,
    ResponseContract,
)
from interaction_orchestrator_mcp.stage2_recall import (
    build_stage2_recall_queries,
    count_mentionable,
    http_items_to_memory_refs,
    merge_memory_refs,
    refresh_interaction_context_memories,
    should_run_compose_recall_stage2,
)

GISTS = [
    "まーの仕事は「ねっとわん」。水曜午前に行ってる。",
]


def _episode(content: str = "【会話の区切り】\n" + ("長いログ\n" * 20)) -> RelevantMemoryRef:
    return RelevantMemoryRef(
        memory_id="ep1",
        content=content,
        relevance=0.9,
        use_policy="background_only",
        reason="episodic",
    )


def _fact(content: str) -> RelevantMemoryRef:
    return RelevantMemoryRef(
        memory_id="f1",
        content=content,
        relevance=0.85,
        use_policy="mentionable",
    )


class TestShouldRunStage2:
    def test_skips_when_mentionable_present(self) -> None:
        run, trigger = should_run_compose_recall_stage2(
            user_text="今日のニュースどう？",
            relevant_memories=[_fact("牛丼480円")],
        )
        assert not run
        assert trigger is None

    def test_temporal_with_only_episodes(self) -> None:
        run, trigger = should_run_compose_recall_stage2(
            user_text="ねっとわん いつ",
            relevant_memories=[_episode()],
        )
        assert run
        assert trigger == "temporal_thin"

    def test_calendar_stock_skips_stage2(self) -> None:
        run, trigger = should_run_compose_recall_stage2(
            user_text="明日の予定って何か入ってたっけ？",
            relevant_memories=[_episode()],
        )
        assert not run
        assert trigger is None

    def test_recall_utterance(self) -> None:
        run, trigger = should_run_compose_recall_stage2(
            user_text="煎餅のこと覚えてる？",
            relevant_memories=[],
            is_recall_utterance=True,
        )
        assert run
        assert trigger == "recall_utterance"


class TestStage2Queries:
    def test_temporal_adds_schedule_queries(self) -> None:
        queries = build_stage2_recall_queries(
            user_text="ねっとわん いつ",
            profile_gists=GISTS,
            trigger="temporal_thin",
        )
        joined = " ".join(queries)
        assert "水曜" in joined or "スケジュール" in joined


class TestMergeAndRefresh:
    def test_merge_dedupes_by_content(self) -> None:
        merged = merge_memory_refs(
            [_fact("A")],
            [_fact("A"), _fact("B")],
        )
        assert len(merged) == 2

    def test_http_items_promote_fact_for_temporal(self) -> None:
        refs = http_items_to_memory_refs(
            [{"content": "まーのねっとわん勤務は水曜午前", "score": 0.8}],
            temporal=True,
        )
        assert refs
        assert "水曜" in refs[0].content

    def test_refresh_updates_mentionable_count_in_summary(self) -> None:
        ctx = InteractionContext(
            ts="2026-07-03T11:00:00+00:00",
            local_time="2026-07-03T20:00:00+09:00",
            timezone="Asia/Tokyo",
            agent_state=AgentStateSummary(ts="2026-07-03T11:00:00+00:00"),
            response_contract=ResponseContract(),
            prompt_summary="Relevant memories: 1 (mentionable: 0).",
            compact_prompt_block="[interaction_context]\nold",
            relevant_memories=[_episode()],
        )
        updated = refresh_interaction_context_memories(
            ctx,
            relevant_memories=[_fact("ねっとわんは水曜午前")],
            user_text="ねっとわん いつ",
            max_chars=8000,
        )
        assert count_mentionable(updated.relevant_memories) == 1
        assert "mentionable: 1" in updated.prompt_summary
        assert "水曜" in updated.compact_prompt_block
