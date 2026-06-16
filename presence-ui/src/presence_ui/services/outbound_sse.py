"""In-process SSE hub for instant room_inbound delivery (A4b+)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from presence_ui.services.outbound import OutboundPendingItem

_listeners: set[asyncio.Queue[dict[str, Any]]] = set()
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
    """Notify all connected SSE clients (thread-safe)."""
    global _loop
    loop = _loop
    if loop is None or not _listeners:
        return
    for queue in list(_listeners):
        loop.call_soon_threadsafe(_safe_put, queue, payload)


def _safe_put(queue: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass


async def subscribe() -> asyncio.Queue[dict[str, Any]]:
    global _loop
    _loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
    _listeners.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue[dict[str, Any]]) -> None:
    _listeners.discard(queue)


def sse_enabled() -> bool:
    import os

    return os.getenv("PRESENCE_OUTBOUND_SSE", "1").lower() not in {"0", "false", "no"}


def heartbeat_seconds() -> float:
    import os

    return max(10.0, float(os.getenv("PRESENCE_OUTBOUND_SSE_HEARTBEAT_SEC", "25")))


async def stream_room_inbound(
    *,
    catch_up: list[dict[str, Any]],
) -> AsyncIterator[str]:
    queue = await subscribe()
    try:
        yield format_sse("connected", {"ok": True})
        for item in catch_up:
            yield format_sse("room_inbound", item)
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds())
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue
            yield format_sse("room_inbound", payload)
    finally:
        unsubscribe(queue)
