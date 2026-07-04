"""Native chat surface-direct SSE path (no ClaudeAgent)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway import ccs_integration, social_chat
from presence_ui.gateway.social_chat import ChatInterceptResult


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


@pytest.mark.asyncio
async def test_surface_native_chat_uses_direct_lm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_CCS_PASSWORD", "test-poc-pw")
    monkeypatch.setenv("PRESENCE_SURFACE_DIRECT", "1")
    monkeypatch.delenv("PRESENCE_SURFACE_USE_CLAUDE", raising=False)

    async def fake_intercept(**kwargs):
        return ChatInterceptResult(
            forward=True,
            payload={"message": "[gateway_turn_context]\nctx\n\nやあ"},
            plan_move="answer_directly",
            user_text="やあ",
            plan=_minimal_plan(),
            ctx=_minimal_ctx(),
            session_id="sess-surface",
        )

    generate = AsyncMock(return_value="やあ、まー")
    agent_ctor = MagicMock()

    monkeypatch.setattr(social_chat, "intercept_chat_request_async", fake_intercept)
    monkeypatch.setattr(
        "presence_ui.gateway.native_chat_router.generate_surface_reply",
        generate,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.native_chat_router.ClaudeAgent",
        agent_ctor,
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
        json={"prompt": "やあ", "session_id": "sess-surface"},
    )
    assert resp.status_code == 200
    assert "やあ、まー" in resp.text
    assert '"claude_session": false' in resp.text
    assert '"direct": true' in resp.text
    agent_ctor.assert_not_called()
    generate.assert_awaited_once()
