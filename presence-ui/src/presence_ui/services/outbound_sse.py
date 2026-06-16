"""In-process SSE hub for instant room_inbound delivery (A4b+)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from presence_ui.services.outbound import OutboundPendingItem
from presence_ui.services.outbound_kiosk import (
    is_kiosk_client,
    note_kiosk_seen,
    kiosk_sse_connected,
    should_deliver_to_client,
)

_listeners: dict[asyncio.Queue[dict[str, Any]], str] = {}
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


def publish_room_inbound(payload: dict[str, Any]) -> None:
    """Notify SSE clients allowed for current kiosk-primary policy."""
    global _loop
    loop = _loop
    if loop is None or not _listeners:
        return
    for queue, client_id in list(_listeners.items()):
        if not should_deliver_to_client(client_id):
            continue
        loop.call_soon_threadsafe(_safe_put, queue, payload)


def _safe_put(queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass


async def subscribe(client_id: str) -> asyncio.Queue[dict[str, Any]]:
    global _loop
    _loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
    client_id = client_id.strip()
    _listeners[queue] = client_id
    if is_kiosk_client(client_id):
        kiosk_sse_connected(1)
    return queue


def unsubscribe(queue: asyncio.Queue[dict[str, Any]], client_id: str) -> None:
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
                payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds())
            except asyncio.TimeoutError:
                if kiosk:
                    note_kiosk_seen()
                yield ": heartbeat\n\n"
                continue
            yield format_sse("room_inbound", payload)
    finally:
        unsubscribe(queue, client_id)
