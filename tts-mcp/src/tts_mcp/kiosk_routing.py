"""Route say playback to Koyori's Room kiosk when Surface is primary."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def kiosk_routing_enabled() -> bool:
    return os.getenv("PRESENCE_SAY_KIOSK_ROUTING", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def presence_ui_base_url() -> str:
    base = os.getenv("PRESENCE_UI_URL", "http://127.0.0.1:8090").strip().rstrip("/")
    return base or "http://127.0.0.1:8090"


def fetch_kiosk_primary_active(*, timeout: float = 2.0) -> bool:
    url = f"{presence_ui_base_url()}/api/v1/ui-config"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("kiosk routing: ui-config unavailable: %s", exc)
        return False
    if not body.get("kiosk_primary_enabled", True):
        return False
    return bool(body.get("kiosk_primary_active"))


def delegate_say_to_kiosk(text: str, *, timeout: float = 8.0) -> tuple[bool, str, int]:
    line = text.strip()
    if not line:
        return False, "empty text", 0
    url = f"{presence_ui_base_url()}/api/v1/tts/room-say"
    payload = json.dumps({"text": line}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        return False, f"http {exc.code}: {detail or exc.reason}", 0
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc), 0
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return True, "routed", 0
    listeners = int(body.get("sse_listeners") or 0)
    if body.get("ok"):
        return True, str(body.get("detail") or "routed to kiosk"), listeners
    return False, str(body.get("detail") or "room-say rejected"), listeners


def should_route_local_say_to_kiosk(
    *,
    play_audio: bool,
    use_local: bool,
) -> bool:
    if not kiosk_routing_enabled() or not play_audio or not use_local:
        return False
    return fetch_kiosk_primary_active()
