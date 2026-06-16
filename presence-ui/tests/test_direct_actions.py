"""Tests for gateway direct actions (A3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interaction_orchestrator_mcp.schemas import (
    CommitmentSummary,
    InteractionContext,
    ResponseContract,
    ResponsePlan,
)
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


def test_outbound_nudge_speak_disabled_when_kiosk_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "presence_ui.services.outbound_kiosk.kiosk_primary_active",
        lambda: True,
    )
    assert direct_actions.outbound_nudge_speak_enabled(want_speak=True) is False
    assert direct_actions.outbound_nudge_speak_enabled(want_speak=False) is False


def test_outbound_nudge_speak_enabled_when_kiosk_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "presence_ui.services.outbound_kiosk.kiosk_primary_active",
        lambda: False,
    )
    assert direct_actions.outbound_nudge_speak_enabled(want_speak=True) is True


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


@pytest.mark.asyncio
async def test_remind_commitment_direct_kiosk_primary_skips_outbound_speak() -> None:
    stores = MagicMock()
    stores.relationship.complete_commitment.return_value = {"commitment_id": "c1"}
    ctx = _ctx()
    ctx.commitments_due = [
        CommitmentSummary(
            commitment_id="c1",
            text="reminder",
            due_at="2026-06-16T19:50:00+09:00",
            status="active",
            speak_line="まー、時間やで",
            delivery="say",
        )
    ]
    plan = _plan(allowed=["remind_commitment"])

    with (
        patch(
            "presence_ui.gateway.direct_actions.boundary_allows",
            return_value=(True, []),
        ),
        patch(
            "presence_ui.gateway.direct_actions.enqueue_outbound_nudge",
            return_value=MagicMock(ok=True, nudge_id="n1", channels=["kiosk"]),
        ) as enqueue_mock,
        patch(
            "presence_ui.gateway.direct_actions.voice_local_enabled",
            return_value=False,
        ),
        patch(
            "presence_ui.services.outbound_kiosk.kiosk_primary_active",
            return_value=True,
        ),
        patch(
            "presence_ui.services.kiosk_say.deliver_speak_to_kiosk",
            return_value=(1, "say_1", "/api/v1/tts/surface/abc"),
        ) as kiosk_say_mock,
    ):
        outcome = await direct_actions.remind_commitment_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    assert outcome.ok is True
    enqueue_mock.assert_called_once()
    assert enqueue_mock.call_args.kwargs["speak"] is False
    kiosk_say_mock.assert_called_once_with("まー、時間やで", source="reminder")


@pytest.mark.asyncio
async def test_remind_commitment_direct_uses_speak_line_metadata() -> None:
    stores = MagicMock()
    stores.relationship.complete_commitment.return_value = {"commitment_id": "c1"}
    ctx = _ctx()
    ctx.commitments_due = [
        CommitmentSummary(
            commitment_id="c1",
            text="10分後リマインド",
            due_at="2026-06-16T18:14:00+09:00",
            status="active",
            speak_line="まー、時間やで！！",
            delivery="say",
        )
    ]
    plan = _plan(allowed=["remind_commitment"])

    with (
        patch(
            "presence_ui.gateway.direct_actions.boundary_allows",
            return_value=(True, []),
        ),
        patch(
            "presence_ui.gateway.direct_actions.enqueue_outbound_nudge",
            return_value=MagicMock(ok=True, nudge_id="n1", channels=["kiosk"]),
        ) as enqueue_mock,
        patch(
            "presence_ui.gateway.direct_actions.voice_local_enabled",
            return_value=False,
        ),
    ):
        outcome = await direct_actions.remind_commitment_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    assert outcome.ok is True
    assert outcome.summary == "まー、時間やで！！"
    enqueue_mock.assert_called_once()
    assert enqueue_mock.call_args.kwargs["text"] == "まー、時間やで！！"
    assert enqueue_mock.call_args.kwargs["speak"] is True


@pytest.mark.asyncio
async def test_remind_commitment_direct_nudge_only_skips_say() -> None:
    stores = MagicMock()
    stores.relationship.complete_commitment.return_value = {"commitment_id": "c2"}
    ctx = _ctx()
    ctx.commitments_due = [
        CommitmentSummary(
            commitment_id="c2",
            text="quiet reminder",
            due_at="2026-06-16T18:14:00+09:00",
            status="active",
            speak_line="まー、そろそろやで",
            delivery="nudge_only",
        )
    ]
    plan = _plan(allowed=["remind_commitment"])

    with (
        patch(
            "presence_ui.gateway.direct_actions.boundary_allows",
            return_value=(True, []),
        ),
        patch(
            "presence_ui.gateway.direct_actions.enqueue_outbound_nudge",
            return_value=MagicMock(ok=True, nudge_id="n2", channels=["kiosk"]),
        ) as enqueue_mock,
        patch(
            "presence_ui.gateway.direct_actions.voice_local_enabled",
            return_value=True,
        ),
        patch(
            "presence_ui.services.tts.speak_text",
            new=AsyncMock(),
        ) as speak_mock,
    ):
        outcome = await direct_actions.remind_commitment_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
        )

    assert outcome.ok is True
    enqueue_mock.assert_called_once()
    assert enqueue_mock.call_args.kwargs["speak"] is False
    speak_mock.assert_not_called()

