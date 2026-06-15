"""Display timezone helpers for Koyori's Room UI."""

from __future__ import annotations

import os
from datetime import datetime, timezone


def display_timezone() -> str:
    """IANA timezone for session list / clock (ma-home default: JST)."""
    return os.getenv("PRESENCE_TIMEZONE", "Asia/Tokyo").strip() or "Asia/Tokyo"


def normalize_iso_timestamp(ts: str) -> str:
    """Ensure ISO timestamps parse as UTC when JSONL omits an offset."""
    raw = (ts or "").strip()
    if not raw:
        return ""
    if raw.endswith("Z"):
        return raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()
