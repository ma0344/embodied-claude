"""Speak / miss_companion presence gate — near first, far rescue, fail-closed.

Side-effect free: no remember, experience, scene_parse, save JPEG, desire, or caption persist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import httpx

from presence_ui.gateway.llm_intent import _extract_json_object

logger = logging.getLogger(__name__)

PresencePathStatus = Literal["present", "absent", "fail", "skipped"]
PresenceSource = Literal["near", "far", "none"]

_PRESENT_USER_TEXT = (
    "この画像に人が映っているか判定してください。"
    "JSONのみで答えてください。"
    '{"present":true} または {"present":false}'
)


@dataclass(frozen=True, slots=True)
class SpeakPresenceResult:
    present: bool
    reason: str  # present_near | present_far | absent | cameras_unavailable | absent_or_far_fail
    source: str  # "near" | "far" | "none"
    near_status: str  # present | absent | fail | skipped
    far_status: str  # present | absent | fail | skipped


def _deny_reason(near_status: str, far_status: str) -> str:
    if near_status == "fail" and far_status == "fail":
        return "cameras_unavailable"
    if near_status == "absent" and far_status == "fail":
        return "absent_or_far_fail"
    # absent+absent, fail+absent, and any residual → absent
    return "absent"


async def detect_person_present(image_base64: str) -> bool | None:
    """VL present check. True/False from JSON ``present`` bool; None = fail."""
    if not image_base64 or not str(image_base64).strip():
        return None
    try:
        from wifi_cam_mcp.vision import (
            _lm_auth_headers,
            lm_studio_settings,
            resize_image_base64,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("speak_presence: vision import failed: %s", exc)
        return None

    try:
        base, model, token = lm_studio_settings()
        image_b64 = resize_image_base64(image_base64, max_side=768)
        headers = _lm_auth_headers(token)
        payload = {
            "model": model,
            "max_tokens": 48,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PRESENT_USER_TEXT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("speak_presence: VL HTTP failed: %s", exc)
        return None

    choices = data.get("choices") or []
    if not choices:
        return None
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        raw = "\n".join(p for p in parts if p).strip()
    elif isinstance(content, str):
        raw = content.strip()
    else:
        return None

    parsed = _extract_json_object(raw)
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("present")
    if not isinstance(value, bool):
        return None
    return value


def _status_from_present(value: bool | None) -> PresencePathStatus:
    if value is True:
        return "present"
    if value is False:
        return "absent"
    return "fail"


async def _check_near_presence() -> PresencePathStatus:
    from presence_ui.services.near_camera import fetch_near_camera_snapshot

    try:
        snap = await fetch_near_camera_snapshot(fresh=True, describe=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("speak_presence near fetch failed: %s", exc)
        return "fail"
    if snap.error or not snap.image_base64:
        return "fail"
    return _status_from_present(await detect_person_present(snap.image_base64))


async def _check_far_presence() -> PresencePathStatus:
    from presence_ui.services.camera import capture_for_mode
    from presence_ui.services.room_scene import DEFAULT_TICK_VIEW

    try:
        outcome = await capture_for_mode(DEFAULT_TICK_VIEW)
    except Exception as exc:  # noqa: BLE001
        logger.warning("speak_presence far capture failed: %s", exc)
        return "fail"
    if not outcome.ok or outcome.capture is None:
        return "fail"
    image_b64 = getattr(outcome.capture, "image_base64", None)
    if not image_b64:
        return "fail"
    return _status_from_present(await detect_person_present(image_b64))


async def companion_present_for_speak() -> SpeakPresenceResult:
    """Gate speak: near OR far. Near first; far only if near absent/fail. Fail-closed."""
    near_status = await _check_near_presence()
    if near_status == "present":
        result = SpeakPresenceResult(
            present=True,
            reason="present_near",
            source="near",
            near_status="present",
            far_status="skipped",
        )
        logger.info(
            "speak_presence reason=%s near=%s far=%s",
            result.reason,
            result.near_status,
            result.far_status,
        )
        return result

    far_status = await _check_far_presence()
    if far_status == "present":
        result = SpeakPresenceResult(
            present=True,
            reason="present_far",
            source="far",
            near_status=near_status,
            far_status="present",
        )
        logger.info(
            "speak_presence reason=%s near=%s far=%s",
            result.reason,
            result.near_status,
            result.far_status,
        )
        return result

    reason = _deny_reason(near_status, far_status)
    result = SpeakPresenceResult(
        present=False,
        reason=reason,
        source="none",
        near_status=near_status,
        far_status=far_status,
    )
    logger.info(
        "speak_presence reason=%s near=%s far=%s",
        result.reason,
        result.near_status,
        result.far_status,
    )
    return result
