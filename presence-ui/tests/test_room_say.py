"""room_say API and SSE routing for MCP say → kiosk."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import presence_ui.services.outbound_kiosk as outbound_kiosk
from presence_ui.main import create_app
from presence_ui.services.outbound_sse import publish_room_say, stream_room_inbound


@pytest.fixture(autouse=True)
def _reset_kiosk_presence() -> None:
    outbound_kiosk._kiosk_last_seen = 0.0
    outbound_kiosk._kiosk_sse_connections = 0
    yield
    outbound_kiosk._kiosk_last_seen = 0.0
    outbound_kiosk._kiosk_sse_connections = 0


def test_room_say_api_requires_kiosk_primary() -> None:
    client = TestClient(create_app())
    response = client.post("/api/v1/tts/room-say", json={"text": "やあ"})
    assert response.status_code == 409


def test_room_say_api_publishes_when_kiosk_active(monkeypatch: pytest.MonkeyPatch) -> None:
    from presence_ui.services.outbound_kiosk import note_kiosk_seen

    note_kiosk_seen()
    client = TestClient(create_app())
    response = client.post("/api/v1/tts/room-say", json={"text": "まー、聞こえる？"})
    assert response.status_code == 200
    assert response.json()["ok"] is True


@pytest.mark.asyncio
async def test_publish_room_say_reaches_kiosk_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_KIOSK_PRIMARY", "1")
    outbound_kiosk.note_kiosk_seen()

    kiosk_gen = stream_room_inbound(catch_up=[], client_id="kiosk")
    pc_gen = stream_room_inbound(catch_up=[], client_id="web-pc")
    kiosk_q: asyncio.Queue[str] = asyncio.Queue()
    pc_q: asyncio.Queue[str] = asyncio.Queue()

    async def read_kiosk() -> None:
        async for chunk in kiosk_gen:
            await kiosk_q.put(chunk)
            if "room_say" in chunk and "るな" in chunk:
                return

    async def read_pc() -> None:
        async for chunk in pc_gen:
            await pc_q.put(chunk)

    kiosk_task = asyncio.create_task(read_kiosk())
    pc_task = asyncio.create_task(read_pc())
    await asyncio.sleep(0.05)
    publish_room_say({"text": "るなの声で say", "source": "say"})
    first = await asyncio.wait_for(kiosk_q.get(), timeout=2.0)
    assert "connected" in first
    second = await asyncio.wait_for(kiosk_q.get(), timeout=2.0)
    assert "room_say" in second
    assert "るな" in second

    pc_chunks: list[str] = []
    try:
        while True:
            pc_chunks.append(await asyncio.wait_for(pc_q.get(), timeout=0.3))
    except asyncio.TimeoutError:
        pass
    assert not any("room_say" in chunk for chunk in pc_chunks)

    kiosk_task.cancel()
    pc_task.cancel()
