"""Surface direct LM message building and flags."""

from __future__ import annotations

import pytest
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, SessionTurn

from presence_ui.gateway.surface_direct import surface_direct_enabled, surface_use_claude
from presence_ui.services.llm import build_surface_chat_messages


def _ctx(*, history: list[SessionTurn] | None = None) -> InteractionContext:
    return InteractionContext(
        person_id="ma",
        channel="chat",
        session_id="sess-1",
        session_history=history or [],
        response_contract=ResponseContract(),
    )


def test_surface_direct_enabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_SURFACE_DIRECT", raising=False)
    monkeypatch.delenv("PRESENCE_SURFACE_USE_CLAUDE", raising=False)
    assert surface_direct_enabled() is True
    assert surface_use_claude() is False


def test_surface_use_claude_disables_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_SURFACE_USE_CLAUDE", "1")
    assert surface_direct_enabled() is False


def test_build_surface_chat_messages_skips_duplicate_current_user() -> None:
    history = [
        SessionTurn(sender="ma", text="昨日の話", timestamp="t1", message_id="1"),
        SessionTurn(sender="koyori", text="うん", timestamp="t2", message_id="2"),
        SessionTurn(sender="ma", text="続き", timestamp="t3", message_id="3"),
    ]
    messages = build_surface_chat_messages(
        enriched_user="[gateway_turn_context]\nplan\n\n続き",
        raw_user="続き",
        session_history=history,
    )
    assert messages[0]["role"] == "system"
    assert "[Gateway — stable]" in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"].startswith("[gateway_turn_context]")
    user_contents = [m["content"] for m in messages if m["role"] == "user"]
    assert len(user_contents) == 2
    assert user_contents[-1].endswith("続き")
    assert "昨日の話" in user_contents[0]
