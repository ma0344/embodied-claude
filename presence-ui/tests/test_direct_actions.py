"""Tests for gateway direct actions (A3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan
from presence_ui.gateway import direct_actions, social_chat
from presence_ui.services.llm import build_social_turn_delta
from presence_ui.services.vision_capture import VisionCaptureResult


def _vision_result(*, caption: str = "room looks fine") -> VisionCaptureResult:
    return VisionCaptureResult(
        ok=True,
        mode="look_around",
        label="center",
        mcp_text="caption text",
        caption=caption,
        file_path="/tmp/cap.jpg",
        remember_ok=True,
    )


def _ctx(*, dominant: str | None = None) -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {"observe_room": 0.8} if dominant else {},
            "discomforts": {},
            "dominant_desire": dominant,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="quiet night",
        compact_prompt_block="[desires] observe_room high",
    )


def _plan(*, move: str = "write_private_reflection", allowed: list[str] | None = None) -> ResponsePlan:
    return ResponsePlan(
        primary_move=move,  # type: ignore[arg-type]
        why_this_move="test move",
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
        boundary={"quiet_hours_active": True, "privacy_sensitive": False, "notes": []},
    )


def test_write_private_reflection_direct_persists() -> None:
    stores = MagicMock()
    stores.orchestrator.append_private_reflection.return_value = MagicMock(
        experience_id="ref_test"
    )
    ctx = _ctx()
    plan = _plan()
    outcome = direct_actions.write_private_reflection_direct(
        stores,
        person_id="ma",
        ctx=ctx,
        plan=plan,
        body="Night note.",
    )
    assert outcome.ok is True
    assert outcome.action == "write_private_reflection"
    stores.orchestrator.append_private_reflection.assert_called_once()
    stores.orchestrator.record_agent_experience.assert_called_once()


def test_build_social_turn_delta_private_reflection_no_mcp() -> None:
    plan = _plan()
    delta = build_social_turn_delta(ctx=_ctx(), plan=plan)
    assert "mcp__sociality__append_private_reflection" not in delta
    assert "Gateway will save" in delta


@pytest.mark.asyncio
async def test_observe_room_direct_with_mock_camera() -> None:
    stores = MagicMock()
    stores.social_state.ingest_social_event.return_value = {"event_id": "e1"}

    class FakeCapture:
        file_path = "/tmp/cap.jpg"
        image_base64 = "abc"
        timestamp = "2026-06-14T15:00:00"
        width = 640
        height = 480

    fake_vision = _vision_result()

    with (
        patch(
            "presence_ui.services.camera.camera_look_around",
            new=AsyncMock(return_value=[FakeCapture(), FakeCapture()]),
        ),
        patch(
            "presence_ui.services.vision_capture.describe_existing_capture",
            new=AsyncMock(return_value=fake_vision),
        ),
        patch(
            "presence_ui.services.vision_capture.remember_vision_capture",
            return_value=True,
        ),
    ):
        outcome = await direct_actions.observe_room_direct(stores, person_id="ma")

    assert outcome.ok is True
    assert outcome.action == "camera_look_around"
    assert outcome.desire_satisfied == "observe_room"
    stores.orchestrator.record_agent_experience.assert_called_once()


@pytest.mark.asyncio
async def test_observe_room_direct_empty_captures_shows_hint() -> None:
    stores = MagicMock()
    with (
        patch(
            "presence_ui.services.camera.camera_look_around",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "presence_ui.services.camera.camera_failure_hint",
            return_value="camera unavailable (cooldown)",
        ),
    ):
        outcome = await direct_actions.observe_room_direct(stores, person_id="ma")

    assert outcome.ok is False
    assert "cooldown" in outcome.summary
    assert outcome.detail == "camera unavailable (cooldown)"


@pytest.mark.asyncio
async def test_execute_autonomous_plan_silent_move() -> None:
    stores = MagicMock()
    plan = _plan(move="stay_silent")
    outcome = await direct_actions.execute_autonomous_plan(
        stores,
        person_id="ma",
        ctx=_ctx(),
        plan=plan,
    )
    assert outcome.ok is True
    assert outcome.action == "stay_silent"


@pytest.mark.asyncio
async def test_execute_smoke_action_observe_room() -> None:
    stores = MagicMock()
    stores.social_state.ingest_social_event.return_value = {"event_id": "e1"}

    class FakeCapture:
        file_path = "/tmp/cap.jpg"
        image_base64 = "abc"
        timestamp = "2026-06-14T15:00:00"
        width = 640
        height = 480

    ctx = _ctx(dominant="observe_room")
    plan = _plan(move="act_autonomously", allowed=["camera_look_around"])

    with (
        patch(
            "presence_ui.services.camera.camera_look_around",
            new=AsyncMock(return_value=[FakeCapture()]),
        ),
        patch(
            "presence_ui.services.vision_capture.describe_existing_capture",
            new=AsyncMock(return_value=_vision_result()),
        ),
        patch(
            "presence_ui.services.vision_capture.remember_vision_capture",
            return_value=True,
        ),
        patch(
            "presence_ui.gateway.direct_actions.satisfy_desire_direct",
            return_value=(True, "observe_room"),
        ),
    ):
        outcome = await direct_actions.execute_smoke_action(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
            smoke_action="observe_room",
        )

    assert outcome.ok is True
    assert outcome.action == "camera_look_around"


@pytest.mark.asyncio
async def test_execute_smoke_action_miss_companion_boundary_deny() -> None:
    stores = MagicMock()
    stores.boundary.evaluate_action.return_value = MagicMock(
        decision="deny",
        reasons=["quiet hours are active"],
    )
    ctx = _ctx(dominant="miss_companion")
    plan = _plan(move="act_autonomously", allowed=["talk_to_companion"])

    outcome = await direct_actions.execute_smoke_action(
        stores,
        person_id="ma",
        ctx=ctx,
        plan=plan,
        smoke_action="miss_companion",
        speech_text="test",
    )
    assert outcome.ok is False
    assert outcome.action == "talk_to_companion"


def test_intercept_private_reflection_skips_claude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.social_state.ingest_social_event.return_value = {"event_id": "evt-1"}
    monkeypatch.setattr(social_chat, "get_stores", lambda: stores)
    monkeypatch.setenv("PRESENCE_GATEWAY_DIRECT_ACTIONS", "1")

    ctx = _ctx()
    plan = _plan()

    monkeypatch.setattr(
        social_chat,
        "compose_interaction_context",
        lambda *args, **kwargs: ctx,
    )
    monkeypatch.setattr(
        social_chat,
        "plan_response",
        lambda *args, **kwargs: plan,
    )
    monkeypatch.setattr(
        social_chat,
        "write_private_reflection_direct",
        lambda *args, **kwargs: direct_actions.DirectActionOutcome(
            ok=True,
            action="write_private_reflection",
            summary="saved",
        ),
    )

    result = social_chat.intercept_chat_request(
        payload={"message": "hello", "sessionId": "s1"},
        person_id="ma",
    )
    assert result.forward is False
    assert result.direct_action_summary == "saved"
