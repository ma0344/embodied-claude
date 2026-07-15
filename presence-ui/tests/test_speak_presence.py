"""Speak / miss_companion presence gate (方針 B')."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from presence_ui.gateway import direct_actions
from presence_ui.schemas import NearCameraSnapshotResponse
from presence_ui.services import speak_presence
from presence_ui.services.camera import CaptureOutcome
from presence_ui.services.speak_presence import SpeakPresenceResult


def _near_snap(
    *, image: str | None = "img", error: str | None = None
) -> NearCameraSnapshotResponse:
    return NearCameraSnapshotResponse(
        timestamp="2026-07-14T00:00:00+00:00",
        image_base64=image,
        source="koyori",
        path="/see",
        error=error,
    )


def _far_outcome(*, ok: bool = True, image: str | None = "far-img") -> CaptureOutcome:
    capture = MagicMock()
    capture.image_base64 = image
    return CaptureOutcome(ok=ok, capture=capture if ok else None, error=None if ok else "cam down")


@pytest.mark.asyncio
async def test_t1_near_present_skips_far() -> None:
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(),
        ) as near_mock,
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new_callable=AsyncMock,
        ) as far_mock,
    ):
        result = await speak_presence.companion_present_for_speak()

    assert result == SpeakPresenceResult(
        present=True,
        reason="present_near",
        source="near",
        near_status="present",
        far_status="skipped",
    )
    near_mock.assert_awaited_once()
    far_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_t2_near_absent_far_present() -> None:
    detect = AsyncMock(side_effect=[False, True])
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(),
        ),
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new_callable=AsyncMock,
            return_value=_far_outcome(),
        ) as far_mock,
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            detect,
        ),
    ):
        result = await speak_presence.companion_present_for_speak()

    assert result.present is True
    assert result.reason == "present_far"
    assert result.source == "far"
    assert result.near_status == "absent"
    assert result.far_status == "present"
    far_mock.assert_awaited_once()
    assert far_mock.await_args.args[0] == "dining"


@pytest.mark.asyncio
async def test_t3_both_absent() -> None:
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(),
        ),
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new_callable=AsyncMock,
            return_value=_far_outcome(),
        ),
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        result = await speak_presence.companion_present_for_speak()

    assert result.present is False
    assert result.reason == "absent"
    assert result.source == "none"
    assert result.near_status == "absent"
    assert result.far_status == "absent"


@pytest.mark.asyncio
async def test_t4_near_fail_far_present() -> None:
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(image=None, error="down"),
        ),
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new_callable=AsyncMock,
            return_value=_far_outcome(),
        ),
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        result = await speak_presence.companion_present_for_speak()

    assert result.present is True
    assert result.reason == "present_far"
    assert result.near_status == "fail"
    assert result.far_status == "present"


@pytest.mark.asyncio
async def test_t5_both_fail() -> None:
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(image=None, error="near down"),
        ),
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new_callable=AsyncMock,
            return_value=_far_outcome(ok=False),
        ),
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            new_callable=AsyncMock,
        ) as detect,
    ):
        result = await speak_presence.companion_present_for_speak()

    assert result.present is False
    assert result.reason == "cameras_unavailable"
    assert result.near_status == "fail"
    assert result.far_status == "fail"
    detect.assert_not_awaited()


@pytest.mark.asyncio
async def test_t6_near_absent_far_fail() -> None:
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(),
        ),
        patch(
            "presence_ui.services.camera.capture_for_mode",
            new_callable=AsyncMock,
            return_value=_far_outcome(ok=False),
        ),
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        result = await speak_presence.companion_present_for_speak()

    assert result.present is False
    assert result.reason == "absent_or_far_fail"
    assert result.near_status == "absent"
    assert result.far_status == "fail"


@pytest.mark.asyncio
async def test_t7_no_side_effects_near_fresh_describe_false() -> None:
    with (
        patch(
            "presence_ui.services.near_camera.fetch_near_camera_snapshot",
            new_callable=AsyncMock,
            return_value=_near_snap(),
        ) as near_mock,
        patch(
            "presence_ui.services.speak_presence.detect_person_present",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("presence_ui.gateway.memory_http.http_remember") as remember,
        patch("presence_ui.services.near_camera.save_near_camera_jpeg") as save_jpeg,
    ):
        await speak_presence.companion_present_for_speak()

    near_mock.assert_awaited_once_with(fresh=True, describe=False)
    remember.assert_not_called()
    save_jpeg.assert_not_called()


@pytest.mark.asyncio
async def test_t10_vl_non_json_or_missing_present_is_fail() -> None:
    assert await speak_presence.detect_person_present("") is None

    with patch(
        "presence_ui.services.speak_presence._extract_json_object",
        return_value=None,
    ):
        # Force HTTP path to succeed with junk content, then parse fails
        async def _fake_post(*_a, **_k):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "choices": [{"message": {"content": "not json"}}],
            }
            return resp

        with (
            patch("wifi_cam_mcp.vision.lm_studio_settings", return_value=("http://x", "m", "t")),
            patch("wifi_cam_mcp.vision.resize_image_base64", return_value="resized"),
            patch("wifi_cam_mcp.vision._lm_auth_headers", return_value={}),
            patch("httpx.AsyncClient") as client_cls,
        ):
            client = AsyncMock()
            client.post = AsyncMock(side_effect=_fake_post)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            client_cls.return_value = client
            assert await speak_presence.detect_person_present("abc") is None

    with patch(
        "presence_ui.services.speak_presence._extract_json_object",
        return_value={"present": "yes"},
    ):

        async def _fake_post2(*_a, **_k):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "choices": [{"message": {"content": '{"present":"yes"}'}}],
            }
            return resp

        with (
            patch("wifi_cam_mcp.vision.lm_studio_settings", return_value=("http://x", "m", "t")),
            patch("wifi_cam_mcp.vision.resize_image_base64", return_value="resized"),
            patch("wifi_cam_mcp.vision._lm_auth_headers", return_value={}),
            patch("httpx.AsyncClient") as client_cls,
        ):
            client = AsyncMock()
            client.post = AsyncMock(side_effect=_fake_post2)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            client_cls.return_value = client
            assert await speak_presence.detect_person_present("abc") is None


def _ctx_plan():
    from interaction_orchestrator_mcp.schemas import (
        InteractionContext,
        ResponseContract,
        ResponsePlan,
    )

    ctx = InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": "miss_companion",
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="quiet night",
        compact_prompt_block="[desires] miss_companion high",
    )
    plan = ResponsePlan(
        primary_move="act_autonomously",  # type: ignore[arg-type]
        why_this_move="test",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={
            "level": "low",
            "allowed_actions": ["talk_to_companion"],
            "forbidden_actions": [],
        },
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )
    return ctx, plan


@pytest.mark.asyncio
async def test_t8_talk_gate_false_skips_outbound_tts_desire() -> None:
    stores = MagicMock()
    ctx, plan = _ctx_plan()
    denied = SpeakPresenceResult(
        present=False,
        reason="absent",
        source="none",
        near_status="absent",
        far_status="absent",
    )
    with (
        patch(
            "presence_ui.services.speak_presence.companion_present_for_speak",
            new_callable=AsyncMock,
            return_value=denied,
        ),
        patch(
            "presence_ui.gateway.direct_actions.boundary_allows",
            return_value=(True, []),
        ) as boundary,
        patch(
            "presence_ui.gateway.direct_actions.enqueue_outbound_nudge",
        ) as enqueue,
        patch(
            "presence_ui.services.tts.speak_text",
            new_callable=AsyncMock,
        ) as speak,
    ):
        outcome = await direct_actions.talk_to_companion_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
            text="まー、おる？",
        )

    assert outcome.ok is False
    assert outcome.detail == "absent"
    assert outcome.desire_satisfied is None
    assert outcome.events and outcome.events[0].get("ok") is False
    boundary.assert_not_called()
    enqueue.assert_not_called()
    speak.assert_not_awaited()
    stores.orchestrator.record_agent_experience.assert_not_called()


@pytest.mark.asyncio
async def test_t9_talk_gate_true_success_path() -> None:
    stores = MagicMock()
    ctx, plan = _ctx_plan()
    allowed = SpeakPresenceResult(
        present=True,
        reason="present_near",
        source="near",
        near_status="present",
        far_status="skipped",
    )
    with (
        patch(
            "presence_ui.services.speak_presence.companion_present_for_speak",
            new_callable=AsyncMock,
            return_value=allowed,
        ),
        patch(
            "presence_ui.gateway.direct_actions.boundary_allows",
            return_value=(True, []),
        ),
        patch(
            "presence_ui.gateway.direct_actions.enqueue_outbound_nudge",
            return_value=MagicMock(ok=True, nudge_id="n1", channels=["kiosk"], reason=None),
        ) as enqueue,
        patch(
            "presence_ui.gateway.direct_actions.voice_local_enabled",
            return_value=False,
        ),
        patch(
            "presence_ui.gateway.direct_actions.default_surface_channels",
            return_value=["kiosk"],
        ),
        patch(
            "presence_ui.gateway.direct_actions.outbound_nudge_speak_enabled",
            return_value=False,
        ),
    ):
        outcome = await direct_actions.talk_to_companion_direct(
            stores,
            person_id="ma",
            ctx=ctx,
            plan=plan,
            text="まー、おる？",
        )

    assert outcome.ok is True
    assert outcome.desire_satisfied == "miss_companion"
    assert outcome.summary == "まー、おる？"
    enqueue.assert_called_once()
