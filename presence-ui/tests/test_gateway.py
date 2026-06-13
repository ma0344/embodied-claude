"""Gateway proxy and social chat intercept tests."""

from __future__ import annotations

import json

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
    async def fake_stream(**_kwargs):
        yield (
            '{"type":"room_progress","phase":"composing","label":"composing"}\n'
        ).encode()
        yield b'{"type":"social_silent","plan_move":"stay_silent"}\n'
        yield b'{"type":"done"}\n'

    monkeypatch.setattr("presence_ui.main.stream_gateway_chat", fake_stream)

    response = client.post(
        "/api/chat",
        json={"message": "hello", "requestId": "req-1"},
    )
    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.strip().split("\n") if line]
    assert lines[0]["type"] == "room_progress"
    assert any(line.get("type") == "social_silent" for line in lines)


def test_post_chat_forwards_enriched_payload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_stream(**_kwargs):
        yield (
            '{"type":"room_progress","phase":"composing","label":"composing"}\n'
        ).encode()
        yield (
            '{"type":"room_progress","phase":"replying","label":"replying"}\n'
        ).encode()
        yield b'{"type":"done"}\n'

    monkeypatch.setattr("presence_ui.main.stream_gateway_chat", fake_stream)
    response = client.post("/api/chat", json={"message": "hello", "requestId": "req-2"})
    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.strip().split("\n") if line]
    assert lines[0]["type"] == "room_progress"
    assert any(line.get("phase") == "replying" for line in lines)


def test_post_chat_rejects_empty_message(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": "  ", "requestId": "req-3"})
    assert response.status_code == 400
