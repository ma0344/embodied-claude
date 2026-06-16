"""In-memory pending queue for room_say (kiosk poll fallback)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from social_core import utc_now

from presence_ui.services.outbound_kiosk import is_kiosk_client

_MAX_ITEMS = 20


@dataclass(frozen=True, slots=True)
class RoomSayItem:
    say_id: str
    ts: str
    text: str
    source: str
    audio_url: str | None = None


_items: list[RoomSayItem] = []
_acked: set[tuple[str, str]] = set()  # (say_id, client_id)


def enqueue_room_say(
    *,
    text: str,
    source: str = "say",
    audio_url: str | None = None,
) -> RoomSayItem:
    item = RoomSayItem(
        say_id=f"say_{uuid.uuid4().hex[:16]}",
        ts=utc_now(),
        text=text.strip(),
        source=source,
        audio_url=audio_url,
    )
    _items.append(item)
    if len(_items) > _MAX_ITEMS:
        del _items[0 : len(_items) - _MAX_ITEMS]
    return item


def list_pending_room_say(
    *,
    client_id: str,
    since: str | None = None,
    limit: int = 10,
) -> list[RoomSayItem]:
    client_id = client_id.strip()
    if not is_kiosk_client(client_id):
        return []
    out: list[RoomSayItem] = []
    for item in _items:
        if (item.say_id, client_id) in _acked:
            continue
        if since and item.ts <= since:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out


def ack_room_say(*, say_id: str, client_id: str) -> bool:
    say_id = say_id.strip()
    client_id = client_id.strip()
    if not say_id or not client_id:
        return False
    if not any(row.say_id == say_id for row in _items):
        return False
    _acked.add((say_id, client_id))
    return True


def room_say_payload(item: RoomSayItem) -> dict[str, str]:
    payload = {
        "say_id": item.say_id,
        "ts": item.ts,
        "text": item.text,
        "source": item.source,
    }
    if item.audio_url:
        payload["audio_url"] = item.audio_url
    return payload
