"""Tapo see → surface 12b multimodal (VIS-SD)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway import ccs_integration, social_chat
from presence_ui.gateway.see_intent import SeeIntent
from presence_ui.gateway.see_prefetch import prefetch_camera_for_message
from presence_ui.gateway.social_chat import ChatInterceptResult
from presence_ui.services.chat_image import (
    CAMERA_SEE_MARKER,
    CAMERA_SEE_VIA_SURFACE_BLOCK,
    prepare_enriched_for_camera_see,
)
from presence_ui.services.llm import build_surface_image_turn_messages
from presence_ui.services.vision_capture import VisionCaptureResult


def _minimal_ctx() -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        session_id="sess-surface",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[interaction_context]\nphase=chat",
    )


def _minimal_plan() -> ResponsePlan:
    return ResponsePlan(
        primary_move="answer_directly",
        why_this_move="test",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={"level": "moderate", "allowed_actions": [], "forbidden_actions": []},
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )


def test_prepare_enriched_for_camera_see_strips_prefetch() -> None:
    enriched = (
        "[gateway_turn_context]\n\n部屋見て\n\n"
        "[vision_prefetch]\nmode=current\n=== VISION_CAPTION ===\n部屋"
    )
    cleaned = prepare_enriched_for_camera_see(enriched, see_mode="current")
    assert "[vision_prefetch]" not in cleaned
    assert CAMERA_SEE_VIA_SURFACE_BLOCK in cleaned
    assert "mode=current" in cleaned


def test_build_surface_image_turn_messages_camera_source() -> None:
    messages = build_surface_image_turn_messages(
        enriched_user=f"[gateway_turn_context]\nplan\n\n部屋見て\n\n{CAMERA_SEE_VIA_SURFACE_BLOCK}",
        raw_user="部屋見て",
        session_history=[],
        image_data_url="data:image/jpeg;base64,abc",
        image_source="camera",
    )
    system = messages[0]["content"]
    assert "Tapo room-camera capture" in system
    assert "attached an image" not in system
    assert messages[1]["content"][0]["type"] == "image_url"


@pytest.mark.asyncio
async def test_prefetch_surface_multimodal_returns_data_url_not_vision_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GATEWAY_DIRECT_ACTIONS", "1")
    result = VisionCaptureResult(
        ok=True,
        mode="current",
        label="--- Current View ---",
        mcp_text="--- Current View ---\nfile=/tmp/x.jpg",
        caption=None,
        file_path="/tmp/x.jpg",
    )
    mock_capture = AsyncMock(return_value=(result, "data:image/jpeg;base64,ZZ"))
    monkeypatch.setattr(
        "presence_ui.gateway.see_prefetch.capture_for_surface_multimodal",
        mock_capture,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.see_prefetch.direct_actions_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.see_prefetch.vision_prefetch_enabled",
        lambda: True,
    )

    vision_note, events, image_url = await prefetch_camera_for_message(
        "部屋見て",
        see_intent=SeeIntent(mode="current", reason="test"),
        surface_multimodal=True,
    )
    assert vision_note is None
    assert image_url == "data:image/jpeg;base64,ZZ"
    assert events
    assert events[-1]["kind"] == "see"
    mock_capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_native_chat_camera_see_via_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_CCS_PASSWORD", "test-poc-pw")
    monkeypatch.setenv("PRESENCE_SURFACE_DIRECT", "1")
    monkeypatch.delenv("PRESENCE_SURFACE_USE_CLAUDE", raising=False)

    async def fake_intercept(**kwargs):
        assert kwargs.get("vision_prefetch") is None
        return ChatInterceptResult(
            forward=True,
            payload={"message": "[gateway_turn_context]\nctx\n\n部屋見て"},
            plan_move="answer_directly",
            user_text="部屋見て",
            plan=_minimal_plan(),
            ctx=_minimal_ctx(),
            session_id="sess-surface",
        )

    generate = AsyncMock(return_value="ええ部屋やな")
    prefetch = AsyncMock(
        return_value=(None, [{"kind": "see", "label": "見た", "ok": True}], "data:image/jpeg;base64,ZZ")
    )

    monkeypatch.setattr(social_chat, "intercept_chat_request_async", fake_intercept)
    monkeypatch.setattr(
        "presence_ui.gateway.native_chat_router.generate_surface_reply",
        generate,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.native_chat_router.prefetch_camera_for_message",
        prefetch,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.native_chat_router.ClaudeAgent",
        MagicMock(),
    )
    monkeypatch.setattr(
        "presence_ui.heartbeat.record.finalize_chat_turn",
        lambda **kwargs: None,
    )

    app = FastAPI()
    ccs_integration.mount_claude_code_server_router(app, person_id="ma")
    client = TestClient(app)
    login = client.post("/api/native/login", json={"password": "test-poc-pw"})
    token = login.json()["token"]
    resp = client.post(
        "/api/native/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": "部屋見て", "session_id": "sess-surface"},
    )
    assert resp.status_code == 200
    assert "ええ部屋やな" in resp.text
    assert '"image_source": "camera"' in resp.text
    generate.assert_awaited_once()
    kwargs = generate.await_args.kwargs
    assert kwargs["image_data_url"] == "data:image/jpeg;base64,ZZ"
    assert kwargs["image_source"] == "camera"
    prefetch.assert_awaited_once()
    assert prefetch.await_args.kwargs.get("surface_multimodal") is True


def test_camera_see_marker_constant() -> None:
    assert CAMERA_SEE_MARKER == "[camera see]"
