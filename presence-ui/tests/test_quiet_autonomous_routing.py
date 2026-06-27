"""Quiet-hour autonomous routing — observe_room must not bypass plan (LW-2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway import direct_actions
from presence_ui.gateway.aozora import ReadingState


def _quiet_ctx(*, dominant: str) -> InteractionContext:
    return InteractionContext(
        ts="2026-06-25T13:00:00+00:00",
        local_time="2026-06-25T22:05:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-25T13:00:00+00:00",
            "desires": {dominant: 1.0},
            "discomforts": {dominant: 0.8},
            "dominant_desire": dominant,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="quiet tick",
        compact_prompt_block="[boundary] quiet_hours_active\n[desires] test",
        boundary_hints=["quiet_hours_active"],
    )


def _plan(*, allowed: list[str]) -> ResponsePlan:
    return ResponsePlan(
        primary_move="act_autonomously",  # type: ignore[arg-type]
        why_this_move="quiet inward",
        tone={"warmth": 0.5, "directness": 0.5, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 0,
            "avoid_memory_dump": True,
        },
        initiative={
            "level": "low",
            "allowed_actions": allowed,
            "forbidden_actions": ["nudge_human"],
        },
        boundary={"quiet_hours_active": True, "privacy_sensitive": False, "notes": []},
    )


@pytest.mark.asyncio
async def test_quiet_observe_dominant_does_not_camera_without_allowed() -> None:
    stores = MagicMock()
    ctx = _quiet_ctx(dominant="observe_room")
    plan = _plan(allowed=["write_private_reflection", "quietly_observe"])

    with patch(
        "presence_ui.gateway.direct_actions.observe_room_direct",
        new=AsyncMock(),
    ) as observe_mock:
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    observe_mock.assert_not_called()
    assert outcome.action == "write_private_reflection"


@pytest.mark.asyncio
async def test_evening_browse_dominant_reads_aozora_not_web() -> None:
    stores = MagicMock()
    ctx = InteractionContext(
        ts="2026-06-25T13:20:00+00:00",
        local_time="2026-06-25T22:20:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-25T13:20:00+00:00",
            "desires": {"browse_curiosity": 0.97},
            "discomforts": {"browse_curiosity": 0.67},
            "dominant_desire": "browse_curiosity",
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="evening tick",
        compact_prompt_block="[desires] browse high",
        boundary_hints=[],
    )
    plan = _plan(
        allowed=["read_aozora_passage", "think_or_discuss_topic", "write_private_reflection"]
    )

    with (
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            return_value=ReadingState(phase="read"),
        ),
        patch(
            "presence_ui.gateway.direct_actions.read_aozora_passage_direct",
            new=AsyncMock(
                return_value=direct_actions.DirectActionOutcome(
                    ok=True,
                    action="read_aozora_passage",
                    summary="一節",
                )
            ),
        ) as read_mock,
        patch(
            "presence_ui.gateway.direct_actions.web_search_direct",
            new=AsyncMock(),
        ) as web_mock,
    ):
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    read_mock.assert_called_once()
    web_mock.assert_not_called()
    assert outcome.action == "read_aozora_passage"


@pytest.mark.asyncio
async def test_quiet_literary_wander_reads_aozora() -> None:
    stores = MagicMock()
    ctx = _quiet_ctx(dominant="literary_wander")
    plan = _plan(allowed=["read_aozora_passage", "write_private_reflection"])

    with (
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            return_value=ReadingState(phase="read"),
        ),
        patch(
            "presence_ui.gateway.direct_actions.read_aozora_passage_direct",
            new=AsyncMock(
                return_value=direct_actions.DirectActionOutcome(
                    ok=True,
                    action="read_aozora_passage",
                    summary="一節",
                    desire_satisfied="literary_wander",
                )
            ),
        ) as read_mock,
    ):
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    read_mock.assert_called_once()
    assert outcome.action == "read_aozora_passage"


@pytest.mark.asyncio
async def test_pause_phase_routes_to_reflect_not_read() -> None:
    stores = MagicMock()
    ctx = _quiet_ctx(dominant="literary_wander")
    plan = _plan(
        allowed=["read_aozora_passage", "reflect_on_aozora_passage", "write_private_reflection"]
    )

    with (
        patch(
            "presence_ui.gateway.direct_actions.load_reading_state",
            return_value=ReadingState(
                phase="pause",
                last_passage={
                    "passage_index": 2,
                    "text": "一節",
                    "title": "羅生門",
                },
                last_reflected_passage_index=-1,
            ),
        ),
        patch(
            "presence_ui.gateway.direct_actions.reflect_on_aozora_passage_direct",
            return_value=direct_actions.DirectActionOutcome(
                ok=True,
                action="reflect_on_aozora_passage",
                summary="噛んだ",
                desire_satisfied="cognitive_load",
            ),
        ) as reflect_mock,
        patch(
            "presence_ui.gateway.direct_actions.read_aozora_passage_direct",
            new=AsyncMock(),
        ) as read_mock,
    ):
        outcome = await direct_actions.execute_autonomous_plan(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    reflect_mock.assert_called_once()
    read_mock.assert_not_called()
    assert outcome.action == "reflect_on_aozora_passage"

