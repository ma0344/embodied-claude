"""social_chat intercept with KV-stable injection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan
from relationship_mcp.schemas import DismissOutcome

from presence_ui.gateway import social_chat
from presence_ui.gateway.ol7_flow import Ol7IngestResult
from presence_ui.gateway.room_ingest import HumanIngestResult
from presence_ui.services.llm import build_gateway_stable_append


def _noop_ingest(**kwargs) -> HumanIngestResult:
    return HumanIngestResult(
        event_id="evt-test",
        dismiss_outcome=DismissOutcome(),
        ol7=Ol7IngestResult(route="no_op"),
    )


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
        compact_prompt_block="[interaction_context]\nphase=chat",
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
    monkeypatch.setattr("presence_ui.deps.get_stores", lambda: stores)
    monkeypatch.setattr("presence_ui.gateway.room_ingest.get_stores", lambda: stores)
    monkeypatch.setattr(social_chat, "_ingest_human_sync", _noop_ingest)
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
    return stores


def test_intercept_stable_append_in_message_not_dynamic_append(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
    result = social_chat.intercept_chat_request(
        payload={"message": "hello", "sessionId": "sess-abc"},
        person_id="ma",
    )
    assert result.forward is True
    assert result.payload is not None
    assert result.payload["appendSystemPrompt"] == build_gateway_stable_append()
    assert "[gateway_turn_context" in result.payload["message"]
    assert result.payload["message"].endswith("hello")
    assert "[interaction_context]" in result.payload["message"]
    assert result.payload["permissionMode"] == "acceptEdits"


def test_intercept_includes_vision_prefetch(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
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
    prefetch = (
        "[vision_prefetch]\nmode=current\n=== VISION_CAPTION ===\nDesk.\n"
        "[Gateway directive — not for the user]\nDo NOT call mcp__wifi-cam__see."
    )
    result = social_chat.intercept_chat_request(
        payload={"message": "何が見える？", "sessionId": "sess-see"},
        person_id="ma",
        vision_prefetch=prefetch,
    )
    assert result.forward is True
    msg = result.payload["message"] if result.payload else ""
    assert "[vision_prefetch]" in msg
    assert "何が見える？" in msg
    assert msg.index("何が見える？") < msg.index("[vision_prefetch]")
    assert msg.endswith("Do NOT call mcp__wifi-cam__see.")


def test_intercept_injects_accept_edits_when_missing(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_SURFACE_DIRECT", "1")
    monkeypatch.delenv("PRESENCE_SURFACE_USE_CLAUDE", raising=False)
    result = social_chat.intercept_chat_request(
        payload={"message": "hello", "requestId": "req-1", "sessionId": "sess-abc"},
        person_id="ma",
    )

    assert result.forward is True
    assert result.payload is not None
    assert result.payload["permissionMode"] == "acceptEdits"


def test_intercept_claude_resume_omits_transcript_when_legacy_cc(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy CC surface path: session_id → claude_session_resume (compact arc only)."""
    captured: dict = {}

    def capture_compose(payload, **kwargs):
        captured["payload"] = payload
        return _minimal_ctx()

    monkeypatch.setenv("PRESENCE_SURFACE_USE_CLAUDE", "1")
    monkeypatch.setattr(social_chat, "compose_interaction_context", capture_compose)
    social_chat.intercept_chat_request(
        payload={"message": "hello", "requestId": "req-1", "sessionId": "sess-abc"},
        person_id="ma",
    )
    assert captured["payload"].claude_session_resume is True


def test_intercept_surface_direct_includes_transcript_in_compose(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Surface Direct (default): full transcript in compact — no CC JSONL resume."""
    captured: dict = {}

    def capture_compose(payload, **kwargs):
        captured["payload"] = payload
        return _minimal_ctx()

    monkeypatch.setenv("PRESENCE_SURFACE_DIRECT", "1")
    monkeypatch.delenv("PRESENCE_SURFACE_USE_CLAUDE", raising=False)
    monkeypatch.setattr(social_chat, "compose_interaction_context", capture_compose)
    social_chat.intercept_chat_request(
        payload={"message": "hello", "requestId": "req-1", "sessionId": "sess-abc"},
        person_id="ma",
    )
    assert captured["payload"].claude_session_resume is False


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


def test_intercept_includes_inbound_reply_dialogue(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
    result = social_chat.intercept_chat_request(
        payload={
            "message": "うん、聞いてる",
            "sessionId": "sess-inbound",
            "inboundNudge": "まー、ちょっといい？",
            "inboundNudgeId": "nudge-1",
        },
        person_id="ma",
    )
    assert result.forward is True
    msg = result.payload["message"] if result.payload else ""
    assert "[inbound_reply" in msg
    assert "こより: まー、ちょっといい？" in msg
    assert "まー: うん、聞いてる" in msg
    assert "nudge_id=nudge-1" in msg
    assert msg.endswith("うん、聞いてる")


def test_intercept_ordinary_message_reaches_compose(mock_stores):
    """Regression: missing soul_prefetch import caused NameError on every chat POST."""
    result = social_chat.intercept_chat_request(
        payload={"message": "おはよう"},
        person_id="ma",
        lite=True,
    )
    assert result.forward is True
    assert result.payload is not None
