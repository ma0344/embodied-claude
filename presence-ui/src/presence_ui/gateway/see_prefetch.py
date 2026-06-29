"""Shared camera PTZ + vision prefetch for gateway and native chat."""

from __future__ import annotations

from typing import Any

from presence_ui.deps import PresenceStores
from presence_ui.gateway.direct_actions import direct_actions_enabled
from presence_ui.gateway.room_events import activity_event
from presence_ui.gateway.see_intent import (
    PtzIntent,
    SeeIntent,
    detect_ptz_intent,
    detect_see_intent,
)
from presence_ui.services.camera import camera_move
from presence_ui.services.vision_capture import prefetch_vision_for_chat, vision_prefetch_enabled


def ptz_prefetch_note(*, intent: PtzIntent, ok: bool, detail: str) -> str:
    status = "ok" if ok else "failed"
    directive = (
        "Gateway already moved the camera as requested.\n"
        "Confirm naturally to まー; do NOT call mcp__wifi-cam__look_* again."
        if ok
        else "Camera move FAILED. Tell まー honestly; do NOT claim you moved."
    )
    return (
        "[ptz_prefetch]\n"
        f"direction={intent.direction}\n"
        f"degrees={intent.degrees}\n"
        f"reason={intent.reason}\n"
        f"status={status}\n"
        f"detail={detail[:200]}\n"
        "\n"
        "[Gateway directive — not for the user]\n"
        f"{directive}"
    )


async def prefetch_camera_for_message(
    message: str,
    *,
    see_intent: SeeIntent | None = None,
    ptz_intent: PtzIntent | None = None,
    stores: PresenceStores | None = None,
    person_id: str = "ma",
) -> tuple[str | None, list[dict[str, Any]]]:
    """Run PTZ and/or vision prefetch when the user message implies camera motion or seeing."""
    text = (message or "").strip()
    if not text or not direct_actions_enabled():
        return None, []

    ptz = ptz_intent or detect_ptz_intent(text)
    see: SeeIntent | None = see_intent or detect_see_intent(text)
    if not ptz and not (see and vision_prefetch_enabled()):
        return None, []

    gateway_events: list[dict[str, Any]] = []
    notes: list[str] = []

    if ptz:
        ok, detail = await camera_move(ptz.direction, ptz.degrees)
        gateway_events.append(
            activity_event(
                kind="ptz",
                label="首を動かした" if ok else "首が動かなかった",
                detail=detail[:200],
                ok=ok,
            )
        )
        notes.append(ptz_prefetch_note(intent=ptz, ok=ok, detail=detail))

    if see and vision_prefetch_enabled():
        try:
            result, vision_note = await prefetch_vision_for_chat(
                intent=see,
                user_text=text,
                remember=True,
            )
            detail = result.caption or result.error or result.label
            activity_label = "見た"
            if see.mode == "window":
                activity_label = "外を見た"
            elif see.mode == "desk":
                activity_label = "まーのデスクを見た"
            elif see.mode == "dining":
                activity_label = "ダイニングを見た"
            elif see.mode == "look_around":
                activity_label = "部屋を見た"
            if not result.ok:
                activity_label = "見られなかった"
            gateway_events.append(
                activity_event(
                    kind="see",
                    label=activity_label,
                    detail=(detail or "")[:200],
                    ok=result.ok,
                )
            )
            notes.append(vision_note)
            if stores is not None:
                from presence_ui.services.somatic import maybe_record_eye_affliction

                action = f"see_{see.mode}"
                remedy = "vision_reload" if result.vision_reloaded else None
                maybe_record_eye_affliction(
                    stores,
                    person_id=person_id,
                    action=action,
                    error=result.error,
                    vision=result,
                    capture_failed=not result.ok,
                    remedy=remedy,
                )
        except Exception as exc:  # noqa: BLE001
            notes.append(
                "[vision_prefetch]\n"
                f"error={exc}\n\n"
                "[Gateway directive — not for the user]\n"
                "Camera/vision prefetch failed. Do NOT guess; say capture failed."
            )
            gateway_events.append(
                activity_event(kind="see", label="見られなかった", detail=str(exc)[:120], ok=False)
            )

    if not notes:
        return None, gateway_events
    return "\n\n".join(notes), gateway_events
