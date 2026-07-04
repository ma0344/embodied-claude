"""Gateway compose stage-2 recall hook."""

from __future__ import annotations

from unittest.mock import patch

from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    RelevantMemoryRef,
    ResponseContract,
)

from presence_ui.gateway.compose_recall_stage2 import maybe_enrich_compose_recall_stage2


def _ctx(*, memories: list[RelevantMemoryRef]) -> InteractionContext:
    return InteractionContext(
        ts="2026-07-03T11:00:00+00:00",
        local_time="2026-07-03T20:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state=AgentStateSummary(ts="2026-07-03T11:00:00+00:00"),
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[interaction_context]\nold",
        relevant_memories=memories,
    )


def test_stage2_enriches_temporal_thin_hits() -> None:
    episode = RelevantMemoryRef(
        memory_id="e1",
        content="【会話の区切り】\n" + ("log\n" * 30),
        relevance=0.9,
        use_policy="background_only",
    )
    ctx = _ctx(memories=[episode])

    def fake_recall(*, query: str, n: int = 4, timeout_sec: float = 12.0):
        if "水曜" in query or "スケジュール" in query or "ねっとわん" in query:
            return [{"content": "まーのねっとわん勤務は水曜午前", "score": 0.82}]
        return []

    with patch(
        "presence_ui.gateway.compose_recall_stage2.http_recall",
        side_effect=fake_recall,
    ):
        with patch(
            "presence_ui.gateway.compose_recall_stage2.http_recall_divergent",
            return_value=[],
        ):
            updated, label = maybe_enrich_compose_recall_stage2(
                ctx,
                user_text="ねっとわん いつ",
                max_chars=8000,
            )

    assert label is not None
    assert "temporal" in label
    assert any("水曜" in m.content for m in updated.relevant_memories)
    assert "水曜" in updated.compact_prompt_block


def test_stage2_disabled_returns_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_COMPOSE_RECALL_STAGE2", "0")
    ctx = _ctx(memories=[])
    updated, label = maybe_enrich_compose_recall_stage2(
        ctx,
        user_text="ねっとわん いつ",
        max_chars=8000,
    )
    assert label is None
    assert updated is ctx
