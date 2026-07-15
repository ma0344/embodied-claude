"""Tests for gateway direct actions (A3)."""

from __future__ import annotations

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from interaction_orchestrator_mcp.schemas import (
    CommitmentSummary,
    InteractionContext,
    ResponseContract,
    ResponsePlan,
)
from PIL import Image

from presence_ui.gateway import direct_actions, social_chat
from presence_ui.schemas import NearCameraSnapshotResponse
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


def test_reflection_body_omits_injection_blocks() -> None:
    ctx = _ctx()
    ctx = ctx.model_copy(
        update={
            "compact_prompt_block": "[gateway_turn_context]\n[desires] observe_room\n[/desires]",
            "prompt_summary": "quiet night summary",
            "open_loops": [
                {"loop_id": "l1", "topic": "明日のヘルパー", "status": "open", "updated_at": None}
            ],
        }
    )
    plan = _plan(allowed=["write_private_reflection"])
    body = direct_actions._reflection_body(ctx, plan)
    assert "[desires]" not in body
    assert "gateway_turn_context" not in body
    assert "quiet night summary" not in body
    assert "test move" in body
    assert "明日のヘルパー" in body


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

    class FakeOutcome:
        ok = True
        capture = FakeCapture()
        error = None

    with (
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new=AsyncMock(return_value=FakeOutcome()),
        ),
        patch(
            "presence_ui.services.room_scene.log_room_tick_signal",
            return_value=None,
        ),
        patch(
            "presence_ui.services.vision_capture.describe_existing_capture",
            new=AsyncMock(),
        ) as describe_mock,
        patch(
            "presence_ui.services.vision_capture.remember_vision_capture",
        ) as remember_mock,
    ):
        outcome = await direct_actions.observe_room_direct(stores, person_id="ma")

    assert outcome.ok is True
    assert outcome.action == "camera_look_around"
    assert outcome.desire_satisfied == "observe_room"
    assert "OBS-TICK-0" in outcome.summary
    describe_mock.assert_not_called()
    remember_mock.assert_not_called()
    stores.orchestrator.record_agent_experience.assert_called_once()


@pytest.mark.asyncio
async def test_observe_room_direct_empty_captures_shows_hint() -> None:
    stores = MagicMock()

    class FailOutcome:
        ok = False
        capture = None
        error = "camera unavailable (cooldown)"

    with (
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new=AsyncMock(return_value=FailOutcome()),
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
    stores.orchestrator.record_agent_experience.assert_called_once()
    affliction = stores.orchestrator.record_agent_experience.call_args[0][0]
    assert affliction.kind == "body_affliction"


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

    class FakeOutcome:
        ok = True
        capture = FakeCapture()
        error = None

    ctx = _ctx(dominant="observe_room")
    plan = _plan(move="act_autonomously", allowed=["camera_look_around"])

    with (
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new=AsyncMock(return_value=FakeOutcome()),
        ),
        patch(
            "presence_ui.services.room_scene.log_room_tick_signal",
            return_value=None,
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
async def test_look_near_direct_records_near_eye_scene() -> None:
    stores = MagicMock()
    stores.orchestrator.record_agent_experience.return_value = {"experience_id": "e1"}
    stores.social_state.ingest_social_event.return_value = {"event_id": "s1"}

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(buf, format="JPEG")
    snap = NearCameraSnapshotResponse(
        timestamp="2026-07-14T05:00:00+00:00",
        image_base64=base64.standard_b64encode(buf.getvalue()).decode("ascii"),
        width=64,
        height=64,
        source="koyori",
        path="/latest.jpg",
        caption="眼鏡の男性が座っている",
        url="http://koyori.test:8765/latest.jpg",
    )

    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new=AsyncMock(return_value=snap),
        ),
        patch(
            "presence_ui.gateway.deterministic_memory.persist_remember_intent",
        ) as remember,
    ):
        remember.return_value = MagicMock(ok=True)
        outcome = await direct_actions.look_near_direct(stores, person_id="ma")

    assert outcome.ok is True
    assert outcome.action == "look_near"
    assert outcome.desire_satisfied is None
    assert "Near-eye" in outcome.summary
    stores.social_state.ingest_social_event.assert_called_once()
    payload = stores.social_state.ingest_social_event.call_args.args[0]["payload"]
    assert payload["sensor"] == "near_eye"
    assert payload["source"] == "koyori"


@pytest.mark.asyncio
async def test_outbound_ping_reply_plan_avoids_clingy_tone() -> None:
    plan = _plan(move="act_autonomously", allowed=["talk_to_companion"])
    user_text, say_plan = direct_actions._outbound_ping_reply_plan(plan)

    assert "会いたさ" not in user_text
    assert "見張り" in user_text
    assert plan.must_avoid == []
    assert len(say_plan.must_avoid) == len(direct_actions._OUTBOUND_PING_MUST_AVOID)
    assert any("clingy or possessive" in item for item in say_plan.must_avoid)


@pytest.mark.asyncio
async def test_execute_smoke_action_miss_companion_boundary_deny() -> None:
    stores = MagicMock()
    stores.boundary.evaluate_action.return_value = MagicMock(
        decision="deny",
        reasons=["quiet hours are active"],
    )
    ctx = _ctx(dominant="miss_companion")
    plan = _plan(move="act_autonomously", allowed=["talk_to_companion"])

    present = MagicMock()
    present.present = True
    present.reason = "present_near"
    with patch(
        "presence_ui.services.speak_presence.companion_present_for_speak",
        new_callable=AsyncMock,
        return_value=present,
    ):
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
    assert enqueue_mock.call_args.kwargs["kiosk_say"] is True


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
        patch(
            "presence_ui.services.outbound_kiosk.kiosk_primary_active",
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
    assert enqueue_mock.call_args.kwargs["kiosk_say"] is True


@pytest.mark.asyncio
async def test_remind_commitment_direct_junk_title_fallback() -> None:
    stores = MagicMock()
    stores.relationship.complete_commitment.return_value = {"commitment_id": "c3"}
    ctx = _ctx()
    ctx.commitments_due = [
        CommitmentSummary(
            commitment_id="c3",
            text="の打合せの10分前にして",
            due_at="2026-06-16T21:08:00+09:00",
            status="active",
            speak_line=None,
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
            return_value=MagicMock(ok=True, nudge_id="n3", channels=["kiosk"]),
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
    assert enqueue_mock.call_args.kwargs["text"] == "まー、リマインドの時間やで"


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
