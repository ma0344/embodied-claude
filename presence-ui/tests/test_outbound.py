"""Outbound nudge queue — pending API, ack, cooldown (A4 MVP)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from social_core import SocialDB
from social_core.events import EventStore

from presence_ui.deps import PresenceStores
from presence_ui.main import create_app
from presence_ui.services.outbound import (
    ack_outbound_delivery,
    check_nudge_cooldown,
    enqueue_outbound_nudge,
    list_pending_outbound,
)


def _minimal_stores(db: SocialDB) -> PresenceStores:
    return PresenceStores(
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


def test_enqueue_and_list_pending(tmp_path) -> None:
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    result = enqueue_outbound_nudge(
        stores,
        person_id="ma",
        text="まー、おる？",
        desire="miss_companion",
    )
    assert result.ok is True
    assert result.nudge_id

    pending = list_pending_outbound(stores, person_id="ma", client_id="kiosk")
    assert len(pending) == 1
    assert pending[0].text == "まー、おる？"
    assert pending[0].speak is True
    assert "chat_push" in pending[0].channels


def test_cooldown_blocks_duplicate_text(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_COOLDOWN_TEXT_MINUTES", "240")
    monkeypatch.setenv("PRESENCE_OUTBOUND_COOLDOWN_MIN_INTERVAL_MINUTES", "0")
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    first = enqueue_outbound_nudge(
        stores,
        person_id="ma",
        text="まー、おる？",
        desire="miss_companion",
    )
    assert first.ok is True
    ack_outbound_delivery(stores, nudge_id=first.nudge_id or "", client_id="pc")

    second = enqueue_outbound_nudge(
        stores,
        person_id="ma",
        text="  まー、おる？ ",
        desire="miss_companion",
    )
    assert second.ok is False
    assert second.skipped_cooldown is True


def test_different_text_allowed_while_duplicate_text_blocked(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_COOLDOWN_TEXT_MINUTES", "240")
    monkeypatch.setenv("PRESENCE_OUTBOUND_COOLDOWN_MIN_INTERVAL_MINUTES", "0")
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    first = enqueue_outbound_nudge(
        stores,
        person_id="ma",
        text="まー、おる？",
        desire="miss_companion",
    )
    assert first.ok is True
    ack_outbound_delivery(stores, nudge_id=first.nudge_id or "", client_id="pc")

    second = enqueue_outbound_nudge(
        stores,
        person_id="ma",
        text="なんや、おらんのかいな",
        desire="miss_companion",
    )
    assert second.ok is True

    third = enqueue_outbound_nudge(
        stores,
        person_id="ma",
        text="  まー、おる？ ",
        desire="miss_companion",
    )
    assert third.ok is False
    assert third.skipped_cooldown is True


def test_min_interval_blocks_rapid_different_text(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_COOLDOWN_MIN_INTERVAL_MINUTES", "15")
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    first = enqueue_outbound_nudge(stores, person_id="ma", text="まー、聞こえてる？")
    assert first.ok is True

    allowed, reason = check_nudge_cooldown(
        stores,
        person_id="ma",
        text="全然違う文面やで",
    )
    assert allowed is False
    assert "15m" in reason


def test_ack_removes_from_pending(tmp_path) -> None:
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    result = enqueue_outbound_nudge(stores, person_id="ma", text="テスト")
    assert result.nudge_id
    assert len(list_pending_outbound(stores, person_id="ma", client_id="kiosk")) == 1
    assert ack_outbound_delivery(
        stores, nudge_id=result.nudge_id, client_id="kiosk", channels=["chat_push"]
    )
    assert list_pending_outbound(stores, person_id="ma", client_id="kiosk") == []


def test_ack_per_client_other_clients_still_pending(tmp_path) -> None:
    db = SocialDB(tmp_path / "social.db")
    stores = _minimal_stores(db)
    result = enqueue_outbound_nudge(stores, person_id="ma", text="両方に届けて")
    assert result.nudge_id
    assert ack_outbound_delivery(stores, nudge_id=result.nudge_id, client_id="pc")
    assert list_pending_outbound(stores, person_id="ma", client_id="pc") == []
    pending_kiosk = list_pending_outbound(stores, person_id="ma", client_id="kiosk")
    assert len(pending_kiosk) == 1
    assert pending_kiosk[0].text == "両方に届けて"


def test_outbound_pending_api(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    local = threading.local()

    def get_stores():
        stores = getattr(local, "stores", None)
        if stores is None:
            stores = _minimal_stores(SocialDB(tmp_path / "social.db"))
            local.stores = stores
        return stores

    monkeypatch.setattr("presence_ui.deps.get_stores", get_stores)
    get_stores()
    enqueue_outbound_nudge(get_stores(), person_id="ma", text="Surface へ届けて")

    client = TestClient(create_app())
    response = client.get("/api/v1/outbound/pending?person_id=ma&client_id=kiosk")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["text"] == "Surface へ届けて"


def test_outbound_ack_api(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    local = threading.local()

    def get_stores():
        stores = getattr(local, "stores", None)
        if stores is None:
            stores = _minimal_stores(SocialDB(tmp_path / "social.db"))
            local.stores = stores
        return stores

    monkeypatch.setattr("presence_ui.deps.get_stores", get_stores)
    result = enqueue_outbound_nudge(get_stores(), person_id="ma", text="ack me")
    client = TestClient(create_app())
    ack = client.post(
        "/api/v1/outbound/ack",
        json={"nudge_id": result.nudge_id, "client_id": "pc", "channels": ["chat_push"]},
    )
    assert ack.status_code == 200
    pending = client.get("/api/v1/outbound/pending?person_id=ma&client_id=pc").json()
    assert pending["items"] == []
    pending_kiosk = client.get("/api/v1/outbound/pending?person_id=ma&client_id=kiosk").json()
    assert len(pending_kiosk["items"]) == 1


def test_ui_config_exposes_outbound_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    body = client.get("/api/v1/ui-config").json()
    assert body["outbound_pending_path"] == "/api/v1/outbound/pending"
    assert body["outbound_ack_path"] == "/api/v1/outbound/ack"
    assert body["outbound_stream_path"] == "/api/v1/outbound/stream"
    assert body["outbound_sse_enabled"] is True
    assert body["outbound_poll_ms"] >= 1000
    assert body["outbound_poll_fallback_ms"] >= 5000
    assert "outbound_web_speech_suppress_on_localhost" in body

    monkeypatch.setenv("VOICEVOX_URL", "http://127.0.0.1:10101")
    monkeypatch.setenv("PRESENCE_OUTBOUND_VOICE_LOCAL", "1")
    body2 = TestClient(create_app()).get("/api/v1/ui-config").json()
    assert body2["outbound_web_speech_suppress_on_localhost"] is True


def test_outbound_stream_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OUTBOUND_SSE", "0")
    client = TestClient(create_app())
    response = client.get("/api/v1/outbound/stream?client_id=kiosk")
    assert response.status_code == 404


def test_outbound_stream_requires_client_id() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/outbound/stream")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_stream_room_inbound_catch_up() -> None:
    from presence_ui.services.outbound_sse import stream_room_inbound

    catch_up = [
        {
            "nudge_id": "nudge_test",
            "ts": "2026-01-01T00:00:00+00:00",
            "text": "SSE 即時着信",
            "speak": True,
            "channels": ["chat_push"],
            "desire": None,
        }
    ]
    chunks: list[str] = []
    async for chunk in stream_room_inbound(catch_up=catch_up, client_id="kiosk"):
        chunks.append(chunk)
        if "room_inbound" in chunk:
            break
    body = "".join(chunks)
    assert "event: connected" in body
    assert "event: room_inbound" in body
    assert "SSE 即時着信" in body


@pytest.mark.asyncio
async def test_publish_room_inbound_reaches_subscriber() -> None:
    import asyncio

    from presence_ui.services.outbound_sse import publish_room_inbound, stream_room_inbound

    gen = stream_room_inbound(catch_up=[], client_id="kiosk")
    received: asyncio.Queue[str] = asyncio.Queue()

    async def reader() -> None:
        async for chunk in gen:
            await received.put(chunk)
            if "live push" in chunk:
                return

    task = asyncio.create_task(reader())
    await asyncio.sleep(0.05)
    publish_room_inbound(
        {
            "nudge_id": "nudge_live",
            "ts": "2026-01-01T00:00:01+00:00",
            "text": "live push",
            "speak": True,
            "channels": ["chat_push"],
            "desire": None,
        }
    )
    first = await asyncio.wait_for(received.get(), timeout=2.0)
    assert "connected" in first
    second = await asyncio.wait_for(received.get(), timeout=2.0)
    assert "live push" in second
    task.cancel()
