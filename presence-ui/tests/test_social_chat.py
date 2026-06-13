"""social_chat intercept behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan
from presence_ui.gateway import social_chat


def _minimal_ctx() -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
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
        compact_prompt_block="",
    )


def _minimal_plan() -> ResponsePlan:
    return ResponsePlan(
        primary_move="answer_directly",
        why_this_move="test",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={"use_specific_memory": False, "max_memories_to_surface": 1, "avoid_memory_dump": True},
        initiative={"level": "moderate", "allowed_actions": [], "forbidden_actions": []},
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )


@pytest.fixture
def mock_stores(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.social_state.ingest_social_event.return_value = {"event_id": "evt-1"}
    monkeypatch.setattr(social_chat, "get_stores", lambda: stores)
    monkeypatch.setattr(
        social_chat,
        "compose_interaction_context",
        lambda *args, **kwargs: _minimal_ctx(),
    )
    monkeypatch.setattr(
        social_chat,
        "plan_response",
        lambda *args, **kwargs: _minimal_plan(),
    )
    monkeypatch.setattr(
        social_chat,
        "build_social_prompt_prefix",
        lambda **_: "[ctx]",
    )
    return stores


def test_intercept_injects_accept_edits_when_missing(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def capture_compose(payload, **kwargs):
        captured["payload"] = payload
        return _minimal_ctx()

    monkeypatch.setattr(social_chat, "compose_interaction_context", capture_compose)
    result = social_chat.intercept_chat_request(
        payload={"message": "hello", "requestId": "req-1", "sessionId": "sess-abc"},
        person_id="ma",
    )

    assert result.forward is True
    assert result.payload is not None
    assert result.payload["permissionMode"] == "acceptEdits"
    assert captured["payload"].session_id == "sess-abc"
    assert captured["payload"].claude_session_resume is True


def test_intercept_no_resume_flag_without_session_id(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def capture_compose(payload, **kwargs):
        captured["payload"] = payload
        return _minimal_ctx()

    monkeypatch.setattr(social_chat, "compose_interaction_context", capture_compose)
    social_chat.intercept_chat_request(
        payload={"message": "hello", "requestId": "req-1"},
    )

    assert captured["payload"].claude_session_resume is False


def test_intercept_preserves_explicit_permission_mode(mock_stores: MagicMock) -> None:
    result = social_chat.intercept_chat_request(
        payload={
            "message": "hello",
            "requestId": "req-2",
            "permissionMode": "default",
        },
    )
    assert result.forward is True
    assert result.payload is not None
    assert result.payload["permissionMode"] == "default"
