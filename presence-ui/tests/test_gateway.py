"""Gateway proxy and social chat intercept tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_reports_gateway_mode(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["details"]["mode"] == "gateway"


def test_legacy_webui_project_path_redirects_to_root(client: TestClient) -> None:
    response = client.get(
        "/projects/C:/Users/ma/src/embodied-claude",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_get_projects_proxies_unchanged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"projects": [{"path": "C:/repo", "encodedName": "C--repo"}]}

    async def fake_proxy_get(path: str):
        assert path == "/api/projects"
        from fastapi.responses import JSONResponse

        return JSONResponse(content=payload)

    monkeypatch.setattr("presence_ui.main.proxy_get", fake_proxy_get)
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == payload


def test_get_histories_proxies_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_proxy_get(path: str):
        assert path == "/api/projects/C--repo/histories"
        from fastapi.responses import JSONResponse

        return JSONResponse(content={"conversations": []})

    monkeypatch.setattr("presence_ui.main.proxy_get", fake_proxy_get)
    response = client.get("/api/projects/C--repo/histories")
    assert response.status_code == 200


def test_post_chat_silent_does_not_forward(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from presence_ui.gateway.social_chat import ChatInterceptResult

    monkeypatch.setattr(
        "presence_ui.main.intercept_chat_request",
        lambda **_: ChatInterceptResult(forward=False, plan_move="stay_silent"),
    )
    forward = AsyncMock()
    monkeypatch.setattr("presence_ui.main.proxy_post_stream_filtered", forward)

    response = client.post(
        "/api/chat",
        json={"message": "hello", "requestId": "req-1"},
    )
    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.strip().split("\n") if line]
    assert lines[0]["type"] == "social_silent"
    forward.assert_not_called()


def test_post_chat_forwards_enriched_payload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from presence_ui.gateway.social_chat import ChatInterceptResult

    enriched = {
        "message": "hello",
        "appendSystemPrompt": "[ctx]",
        "requestId": "req-2",
        "sessionId": "abc",
    }

    monkeypatch.setattr(
        "presence_ui.main.intercept_chat_request",
        lambda **_: ChatInterceptResult(forward=True, payload=enriched, user_text="hello"),
    )

    async def fake_filtered(path: str, payload: dict, *, user_text: str):
        assert path == "/api/chat"
        assert payload == enriched
        assert user_text == "hello"

        async def gen():
            yield b'{"type":"done"}\n'

        from starlette.responses import StreamingResponse

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    monkeypatch.setattr("presence_ui.main.proxy_post_stream_filtered", fake_filtered)
    response = client.post("/api/chat", json={"message": "hello", "requestId": "req-2"})
    assert response.status_code == 200
