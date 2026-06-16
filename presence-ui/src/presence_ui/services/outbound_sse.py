"""In-process SSE hub for room_inbound + room_say delivery."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from presence_ui.services.outbound import OutboundPendingItem
from presence_ui.services.outbound_kiosk import (
    is_kiosk_client,
    kiosk_sse_connected,
    note_kiosk_seen,
    should_deliver_to_client,
)

RoomSseMessage = tuple[str, dict[str, Any]]

_listeners: dict[asyncio.Queue[RoomSseMessage], str] = {}
_loop: asyncio.AbstractEventLoop | None = None


def pending_item_payload(item: OutboundPendingItem) -> dict[str, Any]:
    return {
        "nudge_id": item.nudge_id,
        "ts": item.ts,
        "text": item.text,
        "speak": item.speak,
        "channels": item.channels,
        "desire": item.desire,
    }


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _publish(event: str, payload: dict[str, Any], *, kiosk_only: bool) -> None:
    global _loop
    loop = _loop
    if loop is None or not _listeners:
        return
    message: RoomSseMessage = (event, payload)
    for queue, client_id in list(_listeners.items()):
        if kiosk_only:
            if not is_kiosk_client(client_id):
                continue
        elif not should_deliver_to_client(client_id):
            continue
        loop.call_soon_threadsafe(_safe_put, queue, message)


def publish_room_inbound(payload: dict[str, Any]) -> None:
    _publish("room_inbound", payload, kiosk_only=False)


def publish_room_say(payload: dict[str, Any]) -> None:
    _publish("room_say", payload, kiosk_only=True)


def _safe_put(queue: asyncio.Queue[RoomSseMessage], message: RoomSseMessage) -> None:
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        pass


async def subscribe(client_id: str) -> asyncio.Queue[RoomSseMessage]:
    global _loop
    _loop = asyncio.get_running_loop()
    queue: asyncio.Queue[RoomSseMessage] = asyncio.Queue(maxsize=64)
    client_id = client_id.strip()
    _listeners[queue] = client_id
    if is_kiosk_client(client_id):
        kiosk_sse_connected(1)
    return queue


def unsubscribe(queue: asyncio.Queue[RoomSseMessage], client_id: str) -> None:
    if queue in _listeners:
        del _listeners[queue]
    if is_kiosk_client(client_id):
        kiosk_sse_connected(-1)


def sse_enabled() -> bool:
    import os

    return os.getenv("PRESENCE_OUTBOUND_SSE", "1").lower() not in {"0", "false", "no"}


def heartbeat_seconds() -> float:
    import os

    return max(10.0, float(os.getenv("PRESENCE_OUTBOUND_SSE_HEARTBEAT_SEC", "25")))


async def stream_room_inbound(
    *,
    client_id: str,
    catch_up: list[dict[str, Any]],
) -> AsyncIterator[str]:
    client_id = client_id.strip()
    queue = await subscribe(client_id)
    kiosk = is_kiosk_client(client_id)
    try:
        if kiosk:
            note_kiosk_seen()
        yield format_sse("connected", {"ok": True})
        for item in catch_up:
            yield format_sse("room_inbound", item)
        while True:
            try:
                event_name, payload = await asyncio.wait_for(
                    queue.get(),
                    timeout=heartbeat_seconds(),
                )
            except asyncio.TimeoutError:
                if kiosk:
                    note_kiosk_seen()
                yield ": heartbeat\n\n"
                continue
            yield format_sse(event_name, payload)
    finally:
        unsubscribe(queue, client_id)
