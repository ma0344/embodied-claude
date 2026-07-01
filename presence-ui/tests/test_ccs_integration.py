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
    from presence_ui.services.llm import (
        SOUL_VOICE_ANCHOR,
        build_gateway_stable_append,
        load_soul_core,
    )

    monkeypatch.setattr(
        social_chat,
        "detect_memory_list_request",
        lambda text: None,
    )
    monkeypatch.setattr(
        social_chat,
        "detect_soul_read_request",
        lambda text: False,
    )
    factory = ccs_integration.make_ccs_config_factory(person_id="ma")
    cfg = factory(ChatRequest(prompt="hello", session_id="sess-1"))

    assert cfg.append_system_prompt == build_gateway_stable_append()
    assert SOUL_VOICE_ANCHOR in (cfg.append_system_prompt or "")
    core = load_soul_core()
    if core:
        assert "うち" in core
    assert cfg.permission_mode == "acceptEdits"


def test_intercept_skips_compose_for_soul_read(
    mock_stores: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    soul = tmp_path / "SOUL.md"
    soul.write_text("うちはこより。関西弁。", encoding="utf-8")
    monkeypatch.setenv("PRESENCE_SOUL_PATH", str(soul))
    compose_calls: list[object] = []

    def track_compose(*args, **kwargs):
        compose_calls.append(kwargs)
        return _minimal_ctx()

    monkeypatch.setattr(social_chat, "compose_interaction_context", track_compose)
    result = social_chat.intercept_chat_request(
        payload={"message": "./SOUL.mdを読んでみて"},
        person_id="ma",
    )
    assert result.forward is True
    assert compose_calls == []
    assert result.payload is not None
    assert "[soul_prefetch" in (result.payload.get("message") or "")
    assert "関西弁" in (result.payload.get("message") or "")


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


def test_default_agent_config_uses_chat_surface_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PRESENCE_CHAT_USE_REPO_ROOT", raising=False)
    monkeypatch.delenv("PRESENCE_CHAT_WORKING_DIR", raising=False)
    cfg = ccs_integration.default_agent_config()
    assert cfg.working_dir.endswith("koyori-surface") or cfg.working_dir.endswith(
        "koyori-surface\\"
    )


def test_chat_working_dir_repo_root_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_CHAT_USE_REPO_ROOT", "1")
    assert ccs_integration.chat_working_dir() == ccs_integration.embodied_repo_root()


def test_default_agent_config_uses_qat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    cfg = ccs_integration.default_agent_config()
    assert cfg.model == "google/gemma-4-12b-qat"
    assert cfg.env is not None
    assert cfg.env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "google/gemma-4-12b-qat"


def test_default_agent_config_strict_mcp_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from presence_ui.gateway import kiosk_mcp

    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers": {"system-temperature": {"command": "echo", "args": ["t"]}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(kiosk_mcp, "embodied_repo_root", lambda: tmp_path)
    monkeypatch.setenv("PRESENCE_STRICT_MCP_CONFIG", "1")
    cfg = ccs_integration.default_agent_config(working_dir=tmp_path)
    assert cfg.strict_mcp_config is True
    assert cfg.mcp_config_path
    assert "mcp-kiosk.runtime.json" in cfg.mcp_config_path


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
