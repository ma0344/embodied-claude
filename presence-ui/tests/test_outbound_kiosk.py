"""Kiosk-primary outbound routing tests."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from presence_ui.main import create_app
import presence_ui.services.outbound_kiosk as outbound_kiosk
from presence_ui.services.outbound_kiosk import (
    is_kiosk_client,
    kiosk_primary_active,
    kiosk_sse_connected,
    note_kiosk_seen,
    should_deliver_pc_local,
    should_deliver_to_client,
)
from presence_ui.services.outbound_push import send_outbound_push
from presence_ui.services.outbound_sse import publish_room_inbound, stream_room_inbound


@pytest.fixture(autouse=True)
def _reset_kiosk_presence() -> None:
    outbound_kiosk._kiosk_last_seen = 0.0
    outbound_kiosk._kiosk_sse_connections = 0
    yield
    outbound_kiosk._kiosk_last_seen = 0.0
    outbound_kiosk._kiosk_sse_connections = 0


def test_is_kiosk_client() -> None:
    assert is_kiosk_client("kiosk") is True
    assert is_kiosk_client("web-abc") is False


def test_kiosk_primary_requires_recent_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_KIOSK_PRIMARY", "1")
    assert kiosk_primary_active() is False
    note_kiosk_seen()
    assert kiosk_primary_active() is True
    kiosk_sse_connected(1)
    assert kiosk_primary_active() is True
    kiosk_sse_connected(-1)
    assert kiosk_primary_active() is True


def test_should_deliver_to_client_when_kiosk_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_KIOSK_PRIMARY", "1")
    note_kiosk_seen()
    assert should_deliver_to_client("kiosk") is True
    assert should_deliver_to_client("web-pc") is False
    assert should_deliver_pc_local() is False


def test_send_outbound_push_skips_win_toast_when_pc_local_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def fake_win(**_kwargs):
        calls.append(True)

    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_URL", "")
    monkeypatch.setenv("PRESENCE_OUTBOUND_PUSHOVER_TOKEN", "")
    monkeypatch.setenv("PRESENCE_OUTBOUND_PUSHOVER_USER", "")
    monkeypatch.setattr("presence_ui.services.outbound_push.sys.platform", "win32")
    monkeypatch.setattr(
        "presence_ui.services.outbound_push._win_toast_script",
        lambda: __import__("pathlib").Path("x.ps1"),
    )
    monkeypatch.setattr("presence_ui.services.outbound_push._show_win_toast", fake_win)

    ok, detail = send_outbound_push(text="まー、おる？", include_pc_local=False)
    assert ok is False
    assert calls == []
    assert "no push targets" in detail

    monkeypatch.setenv("PRESENCE_OUTBOUND_NTFY_URL", "https://ntfy.sh/test")
    monkeypatch.setattr("presence_ui.services.outbound_push._post_ntfy", lambda *a, **k: None)
    ok2, detail2 = send_outbound_push(text="まー、おる？", include_pc_local=False)
    assert ok2 is True
    assert calls == []
    assert "ntfy:ok" in detail2


def test_pending_api_empty_for_pc_when_kiosk_active(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    from social_core import SocialDB
    from social_core.events import EventStore
    from unittest.mock import MagicMock

    from presence_ui.deps import PresenceStores
    from presence_ui.services.outbound import enqueue_outbound_nudge

    local = threading.local()

    def get_stores():
        stores = getattr(local, "stores", None)
        if stores is None:
            db = SocialDB(tmp_path / "social.db")
            stores = PresenceStores(
                db=db,
                events=EventStore(db=db),
                social_state=MagicMock(),
                relationship=MagicMock(),
                joint_attention=MagicMock(),
                boundary=MagicMock(),
                self_narrative=MagicMock(),
                orchestrator=MagicMock(),
                policy_timezone="Asia/Tokyo",
            )
            local.stores = stores
        return stores

    monkeypatch.setattr("presence_ui.deps.get_stores", get_stores)
    monkeypatch.setattr("presence_ui.services.outbound_push.send_outbound_push", lambda **k: (False, ""))
    enqueue_outbound_nudge(get_stores(), person_id="ma", text="キオスク優先")

    client = TestClient(create_app())
    note_kiosk_seen()
    pc = client.get("/api/v1/outbound/pending?person_id=ma&client_id=web-pc")
    assert pc.status_code == 200
    assert pc.json()["items"] == []

    kiosk = client.get("/api/v1/outbound/pending?person_id=ma&client_id=kiosk")
    assert kiosk.status_code == 200
    assert len(kiosk.json()["items"]) == 1


@pytest.mark.asyncio
async def test_publish_skips_non_kiosk_when_kiosk_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_KIOSK_PRIMARY", "1")
    note_kiosk_seen()

    kiosk_gen = stream_room_inbound(catch_up=[], client_id="kiosk")
    pc_gen = stream_room_inbound(catch_up=[], client_id="web-pc")
    kiosk_q: asyncio.Queue[str] = asyncio.Queue()
    pc_q: asyncio.Queue[str] = asyncio.Queue()

    async def read_kiosk() -> None:
        async for chunk in kiosk_gen:
            await kiosk_q.put(chunk)
            if "live" in chunk:
                return

    async def read_pc() -> None:
        async for chunk in pc_gen:
            await pc_q.put(chunk)
            if "live" in chunk:
                return

    kiosk_task = asyncio.create_task(read_kiosk())
    pc_task = asyncio.create_task(read_pc())
    await asyncio.sleep(0.05)
    publish_room_inbound(
        {
            "nudge_id": "n1",
            "ts": "t",
            "text": "live",
            "speak": True,
            "channels": [],
            "desire": None,
        }
    )
    kiosk_second = await asyncio.wait_for(kiosk_q.get(), timeout=2.0)
    assert "connected" in kiosk_second
    kiosk_live = await asyncio.wait_for(kiosk_q.get(), timeout=2.0)
    assert "live" in kiosk_live

    pc_chunks: list[str] = []
    try:
        while True:
            pc_chunks.append(await asyncio.wait_for(pc_q.get(), timeout=0.3))
    except asyncio.TimeoutError:
        pass
    assert not any("live" in chunk for chunk in pc_chunks)

    kiosk_task.cancel()
    pc_task.cancel()
