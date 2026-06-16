"""Outbound nudge queue — chat_push + voice_surface delivery to room browsers (A4 MVP)."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from social_core import utc_now

from presence_ui.deps import PresenceStores

OutboundChannel = Literal["chat_push", "voice_surface", "voice_local", "silent"]

DEFAULT_SURFACE_CHANNELS: tuple[OutboundChannel, ...] = ("chat_push", "voice_surface")


def _cooldown_text_minutes() -> int:
    return max(1, int(os.getenv("PRESENCE_OUTBOUND_COOLDOWN_TEXT_MINUTES", "240")))


def _cooldown_min_interval_minutes() -> int:
    """Minimum gap between any two nudges. Default 0 = off (text fingerprint still applies)."""
    return max(0, int(os.getenv("PRESENCE_OUTBOUND_COOLDOWN_MIN_INTERVAL_MINUTES", "0")))


def normalize_nudge_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed.casefold()


def nudge_text_fingerprint(text: str) -> str:
    return normalize_nudge_text(text)


def default_surface_channels() -> list[OutboundChannel]:
    raw = os.getenv("PRESENCE_OUTBOUND_SURFACE_CHANNELS", "chat_push,voice_surface")
    channels: list[OutboundChannel] = []
    for part in raw.split(","):
        key = part.strip()
        if key in {"chat_push", "voice_surface", "voice_local", "silent"}:
            channels.append(key)  # type: ignore[arg-type]
    return channels or list(DEFAULT_SURFACE_CHANNELS)


def voice_local_enabled() -> bool:
    return os.getenv("PRESENCE_OUTBOUND_VOICE_LOCAL", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def outbound_web_speech_suppress_on_localhost() -> bool:
    """Skip kiosk Web Speech on localhost when the gateway already plays voice_local."""
    if not voice_local_enabled():
        return False
    from presence_ui.repo_env import tts_configured

    return tts_configured()


@dataclass(frozen=True, slots=True)
class OutboundEnqueueResult:
    ok: bool
    nudge_id: str | None = None
    reason: str = ""
    channels: tuple[OutboundChannel, ...] = ()
    skipped_cooldown: bool = False


@dataclass(frozen=True, slots=True)
class OutboundPendingItem:
    nudge_id: str
    ts: str
    person_id: str | None
    text: str
    speak: bool
    channels: list[str]
    desire: str | None = None


def _parse_nudge_row(row: Any) -> OutboundPendingItem | None:
    nudge_id = str(row["nudge_id"] or "")
    text = str(row["text"] or "").strip()
    if not nudge_id or not text:
        return None
    try:
        channels = json.loads(row["channels_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        channels = []
    if not isinstance(channels, list):
        channels = []
    return OutboundPendingItem(
        nudge_id=nudge_id,
        ts=str(row["ts"]),
        person_id=row["person_id"],
        text=text,
        speak=bool(row["speak"]),
        channels=[str(ch) for ch in channels],
        desire=str(row["desire"]) if row["desire"] else None,
    )


def _recent_nudge_rows(
    stores: PresenceStores,
    *,
    person_id: str,
    since_ts: str,
    limit: int = 50,
) -> list[Any]:
    rows = stores.db.fetchall(
        """
        SELECT ts, text_fingerprint, desire
        FROM outbound_nudges
        WHERE (person_id = ? OR person_id IS NULL)
          AND ts >= ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (person_id, since_ts, limit),
    )
    return list(rows)


def check_nudge_cooldown(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    desire: str | None = None,
) -> tuple[bool, str]:
    """Return (allowed, reason). Blocks duplicate text; optional min interval between any nudges."""
    del desire  # kept for call-site compatibility; spam guard is text + min-interval only
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    text_since = (now - timedelta(minutes=_cooldown_text_minutes())).isoformat()
    fingerprint = nudge_text_fingerprint(text)

    for row in _recent_nudge_rows(stores, person_id=person_id, since_ts=text_since):
        if row["text_fingerprint"] == fingerprint:
            return False, f"duplicate nudge text within {_cooldown_text_minutes()}m"

    min_interval = _cooldown_min_interval_minutes()
    if min_interval > 0:
        interval_since = (now - timedelta(minutes=min_interval)).isoformat()
        recent = _recent_nudge_rows(stores, person_id=person_id, since_ts=interval_since, limit=1)
        if recent:
            return False, f"nudge cooldown: wait {min_interval}m between outbound messages"

    return True, ""


def enqueue_outbound_nudge(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    speak: bool = True,
    channels: list[OutboundChannel] | None = None,
    desire: str | None = None,
    experience_id: str | None = None,
    skip_cooldown: bool = False,
) -> OutboundEnqueueResult:
    line = text.strip()
    if not line:
        return OutboundEnqueueResult(ok=False, reason="empty text")

    if not skip_cooldown:
        allowed, reason = check_nudge_cooldown(
            stores, person_id=person_id, text=line, desire=desire
        )
        if not allowed:
            return OutboundEnqueueResult(
                ok=False,
                reason=reason,
                skipped_cooldown=True,
            )

    channel_list = list(channels or default_surface_channels())
    if not channel_list or channel_list == ["silent"]:
        return OutboundEnqueueResult(ok=False, reason="no delivery channels")

    nudge_id = f"nudge_{uuid.uuid4().hex[:16]}"
    ts = utc_now()
    now = utc_now()
    with stores.db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO outbound_nudges(
                nudge_id, ts, person_id, text, speak, channels_json,
                desire, text_fingerprint, experience_id, delivered_at,
                delivered_channels_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nudge_id,
                ts,
                person_id,
                line,
                1 if speak else 0,
                json.dumps(channel_list, ensure_ascii=False),
                desire,
                nudge_text_fingerprint(line),
                experience_id,
                None,
                None,
                now,
            ),
        )

    from presence_ui.services.outbound_push import send_outbound_push

    push_ok, push_detail = send_outbound_push(text=line)
    if push_detail and push_detail != "no push targets configured":
        import logging

        logging.getLogger(__name__).info(
            "outbound push nudge_id=%s ok=%s detail=%s",
            nudge_id,
            push_ok,
            push_detail,
        )

    publish_enqueued_nudge(
        nudge_id=nudge_id,
        ts=ts,
        person_id=person_id,
        text=line,
        speak=bool(speak),
        channels=channel_list,
        desire=desire,
    )

    return OutboundEnqueueResult(
        ok=True,
        nudge_id=nudge_id,
        channels=tuple(channel_list),
    )


def publish_enqueued_nudge(
    *,
    nudge_id: str,
    ts: str,
    person_id: str,
    text: str,
    speak: bool,
    channels: list[str],
    desire: str | None,
) -> None:
    from presence_ui.services.outbound_sse import pending_item_payload, publish_room_inbound

    item = OutboundPendingItem(
        nudge_id=nudge_id,
        ts=ts,
        person_id=person_id,
        text=text,
        speak=speak,
        channels=channels,
        desire=desire,
    )
    publish_room_inbound(pending_item_payload(item))


def list_pending_outbound(
    stores: PresenceStores,
    *,
    person_id: str,
    client_id: str,
    since: str | None = None,
    limit: int = 20,
) -> list[OutboundPendingItem]:
    client_id = client_id.strip()
    if not client_id:
        return []
    clauses = [
        "(n.person_id = ? OR n.person_id IS NULL)",
        "a.nudge_id IS NULL",
    ]
    params: list[Any] = [client_id, person_id]
    if since:
        clauses.append("n.ts > ?")
        params.append(since)
    limit_val = min(max(limit, 1), 100)
    rows = stores.db.fetchall(
        f"""
        SELECT n.nudge_id, n.ts, n.person_id, n.text, n.speak, n.channels_json, n.desire
        FROM outbound_nudges n
        LEFT JOIN outbound_nudge_client_acks a
          ON a.nudge_id = n.nudge_id AND a.client_id = ?
        WHERE {' AND '.join(clauses)}
        ORDER BY n.ts ASC
        LIMIT ?
        """,
        (*params, limit_val),
    )
    items: list[OutboundPendingItem] = []
    for row in rows:
        parsed = _parse_nudge_row(row)
        if parsed is not None:
            items.append(parsed)
    return items


def ack_outbound_delivery(
    stores: PresenceStores,
    *,
    nudge_id: str,
    client_id: str,
    channels: list[str] | None = None,
) -> bool:
    nudge_id = nudge_id.strip()
    client_id = client_id.strip()
    if not nudge_id or not client_id:
        return False
    row = stores.db.fetchone(
        "SELECT nudge_id FROM outbound_nudges WHERE nudge_id = ? LIMIT 1",
        (nudge_id,),
    )
    if row is None:
        return False
    now = utc_now()
    with stores.db.transaction() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO outbound_nudge_client_acks(
                nudge_id, client_id, channels_json, acked_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                nudge_id,
                client_id,
                json.dumps(channels or [], ensure_ascii=False),
                now,
            ),
        )
    return True


def outbound_delivery_artifacts(
    *,
    nudge_id: str,
    channels: list[str],
    speak: bool,
    delivered_local: bool,
) -> list[dict[str, Any]]:
    delivered = {ch: ch != "voice_local" for ch in channels}
    if "voice_local" in channels:
        delivered["voice_local"] = delivered_local
    return [
        {
            "type": "outbound",
            "nudge_id": nudge_id,
            "channels": channels,
            "speak": speak,
            "delivered": delivered,
        }
    ]
