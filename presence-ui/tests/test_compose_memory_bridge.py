"""MEM-8h bridge hook — route gate + recall."""

from __future__ import annotations

from unittest.mock import patch

from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    ResponseContract,
)

from presence_ui.gateway.compose_memory_bridge import (
    maybe_enrich_memory_bridge,
    resolve_memory_retrieve_route,
)


def _ctx() -> InteractionContext:
    return InteractionContext(
        ts="2026-07-03T11:00:00+00:00",
        local_time="2026-07-03T20:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state=AgentStateSummary(ts="2026-07-03T11:00:00+00:00"),
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[interaction_context]\nold",
    )


def test_calendar_route_not_memory_bridge() -> None:
    assert resolve_memory_retrieve_route("明日の予定は？") == "calendar_read"


def test_bridge_disabled_returns_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_MEM8H_BRIDGE", "0")
    ctx = _ctx()
    updated, label = maybe_enrich_memory_bridge(
        ctx,
        user_text="梅干し作ろう",
        max_chars=8000,
        route="memory_bridge",
    )
    assert label is None
    assert updated is ctx


def test_bridge_enriches_umeboshi(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_MEM8H_BRIDGE", "1")

    def fake_recall(*, query: str, n: int = 4, timeout_sec: float = 12.0):
        if "梅干し" in query or "梅" in query:
            return [
                {
                    "content": "まーが梅干しづくりをしようと話していた",
                    "score": 0.82,
                    "timestamp": "2026-07-03T11:00:00+09:00",
                }
            ]
        return []

    with patch(
        "presence_ui.gateway.compose_memory_bridge.http_recall",
        side_effect=fake_recall,
    ):
        updated, label = maybe_enrich_memory_bridge(
            _ctx(),
            user_text="梅干し作ろうかな",
            max_chars=8000,
            route="memory_bridge",
        )

    assert label is not None
    assert "記憶ブリッジ" in label
    assert "[memory_bridge" in updated.compact_prompt_block
    assert "梅干し" in updated.compact_prompt_block
