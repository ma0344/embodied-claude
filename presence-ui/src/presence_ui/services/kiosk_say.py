"""Route spoken lines to the Surface kiosk (SSE + poll fallback)."""

from __future__ import annotations

import logging

from presence_ui.services.outbound_kiosk import kiosk_primary_active, note_kiosk_seen
from presence_ui.services.outbound_sse import kiosk_sse_subscriber_count, publish_room_say
from presence_ui.services.room_say_pending import enqueue_room_say, room_say_payload

logger = logging.getLogger(__name__)


def prebuild_surface_audio_url(text: str) -> str | None:
    """Synthesize once on the gateway so the kiosk only fetches audio."""
    line = (text or "").strip()
    if not line:
        return None
    try:
        from presence_ui.services.tts_surface import surface_tts_enabled, synthesize_surface_audio

        if not surface_tts_enabled():
            return None
        token, _fmt, _media = synthesize_surface_audio(line)
        return f"/api/v1/tts/surface/{token}"
    except Exception as exc:
        logger.warning("room_say pre-synth failed: %s", exc)
        return None


def deliver_speak_to_kiosk(text: str, *, source: str = "say") -> tuple[int, str, str | None]:
    """Push TTS text to kiosk listeners. Returns (sse_deliveries, say_id, audio_url)."""
    line = (text or "").strip()
    if not line:
        return 0, "", None

    audio_url = prebuild_surface_audio_url(line)
    item = enqueue_room_say(text=line, source=source, audio_url=audio_url)
    note_kiosk_seen()
    delivered = publish_room_say(room_say_payload(item))
    if delivered == 0 and kiosk_primary_active():
        logger.warning(
            "kiosk say queued (say_id=%s, audio=%s) but no SSE listeners (subscribers=%d)",
            item.say_id,
            "yes" if audio_url else "no",
            kiosk_sse_subscriber_count(),
        )
    return delivered, item.say_id, audio_url
