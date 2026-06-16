"""Kiosk-primary outbound routing — Surface alive → suppress ma-home PC delivery."""

from __future__ import annotations

import os
import time

KIOSK_CLIENT_ID = "kiosk"

_kiosk_last_seen: float = 0.0
_kiosk_sse_connections: int = 0


def kiosk_primary_enabled() -> bool:
    return os.getenv("PRESENCE_OUTBOUND_KIOSK_PRIMARY", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def kiosk_grace_seconds() -> float:
    return max(30.0, float(os.getenv("PRESENCE_OUTBOUND_KIOSK_GRACE_SEC", "90")))


def is_kiosk_client(client_id: str) -> bool:
    return client_id.strip() == KIOSK_CLIENT_ID


def note_kiosk_seen() -> None:
    global _kiosk_last_seen
    _kiosk_last_seen = time.monotonic()


def kiosk_sse_connected(delta: int) -> None:
    global _kiosk_sse_connections
    _kiosk_sse_connections = max(0, _kiosk_sse_connections + delta)
    if delta > 0:
        note_kiosk_seen()


def kiosk_primary_active() -> bool:
    """True when kiosk SSE is connected or seen recently (grace)."""
    if not kiosk_primary_enabled():
        return False
    if _kiosk_sse_connections > 0:
        return True
    if _kiosk_last_seen <= 0:
        return False
    return (time.monotonic() - _kiosk_last_seen) < kiosk_grace_seconds()


def should_deliver_to_client(client_id: str) -> bool:
    if not kiosk_primary_active():
        return True
    return is_kiosk_client(client_id)


def should_deliver_pc_local() -> bool:
    """Win toast, voice_local, and non-kiosk browser/poll delivery."""
    return not kiosk_primary_active()
