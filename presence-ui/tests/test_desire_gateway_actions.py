"""Tests for gateway web search and memory helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from interaction_orchestrator_mcp.schemas import (
    InteractionContext,
    OpenLoopSummary,
    ResponseContract,
    ResponsePlan,
)

from presence_ui.gateway import direct_actions, web_search


def _ctx(
    *,
    dominant: str | None = None,
    loops: list[OpenLoopSummary] | None = None,
) -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": dominant,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="identity thread",
        compact_prompt_block="[desires] test",
        open_loops=loops or [],
    )


def _plan(*, allowed: list[str] | None = None) -> ResponsePlan:
    return ResponsePlan(
        primary_move="act_autonomously",  # type: ignore[arg-type]
        why_this_move="curious",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={
            "level": "low",
            "allowed_actions": allowed or [],
            "forbidden_actions": [],
        },
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )


def test_pick_browse_query_prefers_open_loop() -> None:
    ctx = _ctx(
        loops=[
            OpenLoopSummary(
                loop_id="l1",
                topic="心血管AIの論文",
                status="open",
            )
        ]
    )
    assert web_search.pick_browse_query(ctx) == "心血管AIの論文"


@pytest.mark.asyncio
async def test_web_search_direct_remembers_and_satisfies() -> None:
    stores = MagicMock()
    ctx = _ctx(dominant="browse_curiosity")
    plan = _plan(allowed=["web_search"])

    with (
        patch(
            "presence_ui.gateway.direct_actions.ddg_instant_answer",
            new=AsyncMock(return_value=("answer text", "query text")),
        ),
        patch(
            "presence_ui.gateway.direct_actions.http_remember",
            return_value={"ok": True, "id": "m1"},
        ),
        patch(
            "presence_ui.gateway.direct_actions.satisfy_desire_direct",
            return_value=(True, "browse_curiosity"),
        ) as satisfy_mock,
    ):
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    assert outcome.ok is True
    assert outcome.action == "web_search"
    assert outcome.desire_satisfied == "browse_curiosity"
    satisfy_mock.assert_called_once()
    stores.orchestrator.record_agent_experience.assert_called()


def test_think_or_discuss_topic_direct() -> None:
    stores = MagicMock()
    stores.orchestrator.append_private_reflection.return_value = MagicMock(
        experience_id="ref1"
    )
    ctx = _ctx(dominant="cognitive_load")
    plan = _plan(allowed=["think_or_discuss_topic"])

    outcome = direct_actions.think_or_discuss_topic_direct(
        stores,
        person_id="ma",
        ctx=ctx,
        plan=plan,
    )
    assert outcome.ok is True
    assert outcome.action == "think_or_discuss_topic"
    assert outcome.desire_satisfied == "cognitive_load"


def test_recall_memories_direct() -> None:
    stores = MagicMock()
    stores.orchestrator.append_private_reflection.return_value = MagicMock(
        experience_id="ref2"
    )
    ctx = _ctx(dominant="identity_coherence")
    plan = _plan(allowed=["recall_memories"])

    with patch(
        "presence_ui.gateway.direct_actions.http_recall",
        return_value=[{"content": "昔の約束を覚えている"}],
    ):
        outcome = direct_actions.recall_memories_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    assert outcome.ok is True
    assert outcome.action == "recall_memories"
    assert outcome.desire_satisfied == "identity_coherence"
    assert stores.orchestrator.record_agent_experience.call_count >= 2
