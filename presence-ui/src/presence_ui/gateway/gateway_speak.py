"""IBF speak flow — deliver assistant reply to kiosk without LLM tool selection."""

from __future__ import annotations

import logging

from presence_ui.gateway.direct_actions import boundary_allows, direct_actions_enabled
from presence_ui.gateway.user_intent import ibf_gateway_speak_enabled

logger = logging.getLogger(__name__)


async def deliver_gateway_speak_after_reply(
    *,
    text: str,
    person_id: str,
) -> tuple[bool, str]:
    """Play reply on Surface via room-say when IBF gateway speak is enabled."""
    if not ibf_gateway_speak_enabled() or not direct_actions_enabled():
        return False, "ibf gateway speak disabled"

    line = (text or "").strip()
    if not line:
        return False, "empty reply"

    from presence_ui.deps import get_stores

    stores = get_stores()
    allowed, reasons = boundary_allows(
        stores, action_type="say", person_id=person_id, urgency="low"
    )
    if not allowed:
        logger.info("gateway speak skipped (boundary): %s", "; ".join(reasons))
        return False, "boundary denied"

    try:
        from presence_ui.services.kiosk_say import deliver_speak_to_kiosk

        delivered, say_id, audio_url = deliver_speak_to_kiosk(line, source="chat")
        detail = f"say_id={say_id} listeners={delivered} audio={'yes' if audio_url else 'no'}"
        return True, detail
    except Exception as exc:  # noqa: BLE001
        logger.warning("gateway speak failed: %s", exc)
        return False, str(exc)
