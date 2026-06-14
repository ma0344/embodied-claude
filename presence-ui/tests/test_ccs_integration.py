"""claude-code-server include_router PoC."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from claude_code_server import ChatRequest
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway import ccs_integration, social_chat


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
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
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
        "build_social_turn_delta",
        lambda **_: "[interaction_context]\nphase=chat",
    )
    return stores


def test_config_factory_injects_stable_gateway_append(
    mock_stores: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from presence_ui.services.llm import GATEWAY_STABLE_APPEND

    monkeypatch.setattr(
        social_chat,
        "detect_memory_list_request",
        lambda text: None,
    )
    factory = ccs_integration.make_ccs_config_factory(person_id="ma")
    cfg = factory(ChatRequest(prompt="hello", session_id="sess-1"))

    assert cfg.append_system_prompt == GATEWAY_STABLE_APPEND
    assert cfg.permission_mode == "acceptEdits"


def test_intercept_skips_compose_for_memory_list(
    mock_stores: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose_calls: list[object] = []

    def track_compose(*args, **kwargs):
        compose_calls.append(kwargs)
        return _minimal_ctx()

    monkeypatch.setattr(social_chat, "compose_interaction_context", track_compose)
    result = social_chat.intercept_chat_request(
        payload={"message": "直近10件の記憶リストを出して"},
        person_id="ma",
    )
    assert result.forward is True
    assert compose_calls == []
    assert result.payload is not None
    assert "[memory_list_prefetch]" in (result.payload.get("message") or "")


def test_native_chat_list_bypasses_claude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from presence_ui.gateway import deterministic_memory as dm

    monkeypatch.setenv("PRESENCE_CCS_PASSWORD", "test-poc-pw")
    monkeypatch.setattr(
        dm,
        "fetch_memory_list",
        lambda **kwargs: [
            {
                "id": "1",
                "content": "煎餅が好き",
                "timestamp": "2026-06-12",
                "category": "daily",
                "emotion": "neutral",
            }
        ],
    )
    app = FastAPI()
    ccs_integration.mount_claude_code_server_router(app, person_id="ma")
    client = TestClient(app)
    login = client.post("/api/native/login", json={"password": "test-poc-pw"})
    token = login.json()["token"]
    resp = client.post(
        "/api/native/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": "直近10件の記憶リストを出して"},
    )
    assert resp.status_code == 200
    assert "煎餅が好き" in resp.text
    assert "event: done" in resp.text
    assert '"direct": true' in resp.text
    assert "event: session" not in resp.text
    assert '"claude_session": false' in resp.text


def test_mount_registers_native_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    import presence_ui.main as main_mod

    monkeypatch.setenv("PRESENCE_NATIVE_CHAT", "1")
    app = main_mod.create_app()
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/native/chat" in paths
    assert "/api/native/login" in paths
    assert "/poc/native" in paths


def test_default_agent_config_uses_qat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    cfg = ccs_integration.default_agent_config()
    assert cfg.model == "google/gemma-4-12b-qat"
    assert cfg.env is not None
    assert cfg.env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "google/gemma-4-12b-qat"


def test_native_login_uses_presence_password(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PRESENCE_CCS_PASSWORD", "test-poc-pw")
    app = FastAPI()
    ccs_integration.mount_claude_code_server_router(app, person_id="ma")
    client = TestClient(app)

    bad = client.post("/api/native/login", json={"password": "koyori-poc"})
    assert bad.status_code == 401

    ok = client.post("/api/native/login", json={"password": "test-poc-pw"})
    assert ok.status_code == 200
    assert ok.json().get("token")
