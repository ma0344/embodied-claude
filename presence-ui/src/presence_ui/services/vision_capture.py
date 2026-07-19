"""Gateway camera capture + LM Studio vision (MCP-compatible text)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from presence_ui.gateway.deterministic_memory import RememberIntent, persist_remember_intent
from presence_ui.gateway.see_intent import SeeIntent, SeeMode
from presence_ui.services.camera import (
    CaptureOutcome,
    camera_failure_hint,
    capture_for_mode,
)
from presence_ui.services.camera_locations import CAMERA_LOCATIONS

logger = logging.getLogger(__name__)


def vision_prefetch_enabled() -> bool:
    from presence_ui.gateway.direct_actions import direct_actions_enabled

    if not direct_actions_enabled():
        return False
    return os.getenv("PRESENCE_GATEWAY_VISION_PREFETCH", "1").lower() not in {
        "0",
        "false",
        "no",
    }


@dataclass(slots=True)
class VisionCaptureResult:
    ok: bool
    mode: SeeMode | str
    label: str
    mcp_text: str
    caption: str | None
    file_path: str | None
    error: str | None = None
    remember_ok: bool = False
    vision_corrupt: bool = False
    vision_reloaded: bool = False
    image_base64: str | None = None


async def capture_and_describe(*, mode: SeeMode, label: str = "") -> VisionCaptureResult:
    """Capture with optional PTZ, vision-describe, return MCP-shaped text."""
    try:
        from wifi_cam_mcp.vision import (
            describe_image_outcome,
            format_capture_text,
            vision_describe_enabled,
        )
    except ImportError as exc:
        return VisionCaptureResult(
            ok=False,
            mode=mode,
            label=label or mode,
            mcp_text="",
            caption=None,
            file_path=None,
            error=f"wifi_cam_mcp.vision unavailable ({exc}). Run sync-presence-deps + restart.",
        )

    outcome: CaptureOutcome = await capture_for_mode(mode)
    if not outcome.ok or not outcome.capture:
        hint = outcome.error or camera_failure_hint() or "capture failed"
        return VisionCaptureResult(
            ok=False,
            mode=mode,
            label=label or mode,
            mcp_text="",
            caption=None,
            file_path=None,
            error=hint,
        )

    capture = outcome.capture
    view_label = outcome.view_label or label or mode
    caption: str | None = None
    vision_corrupt = False
    vision_reloaded = False
    if vision_describe_enabled() and capture.image_base64:
        describe_out = await describe_image_outcome(capture.image_base64)
        caption = describe_out.caption
        vision_corrupt = describe_out.saw_corrupt
        vision_reloaded = describe_out.reloaded

    mcp_text = format_capture_text(capture, view_label, vision_caption=caption)
    return VisionCaptureResult(
        ok=True,
        mode=mode,
        label=view_label,
        mcp_text=mcp_text,
        caption=caption,
        file_path=capture.file_path,
        vision_corrupt=vision_corrupt,
        vision_reloaded=vision_reloaded,
        image_base64=capture.image_base64 or None,
    )


async def describe_existing_capture(
    capture: object,
    *,
    mode: str,
    label: str,
    extra_line: str = "",
) -> VisionCaptureResult:
    """Vision-describe an existing CaptureResult (e.g. center frame from look_around)."""
    try:
        from wifi_cam_mcp.vision import (
            describe_image_outcome,
            format_capture_text,
            vision_describe_enabled,
        )
    except ImportError as exc:
        return VisionCaptureResult(
            ok=False,
            mode=mode,
            label=label,
            mcp_text="",
            caption=None,
            file_path=getattr(capture, "file_path", None),
            error=f"wifi_cam_mcp.vision unavailable ({exc}). Run sync-presence-deps + restart.",
        )

    caption: str | None = None
    vision_corrupt = False
    vision_reloaded = False
    image_b64 = getattr(capture, "image_base64", None)
    if vision_describe_enabled() and image_b64:
        describe_out = await describe_image_outcome(image_b64)
        caption = describe_out.caption
        vision_corrupt = describe_out.saw_corrupt
        vision_reloaded = describe_out.reloaded
    mcp_text = format_capture_text(capture, label, vision_caption=caption)
    if extra_line.strip():
        mcp_text = f"{mcp_text}\n{extra_line.strip()}"
    return VisionCaptureResult(
        ok=True,
        mode=mode,
        label=label,
        mcp_text=mcp_text,
        caption=caption,
        file_path=getattr(capture, "file_path", None),
        vision_corrupt=vision_corrupt,
        vision_reloaded=vision_reloaded,
    )


def observation_summary_from_vision(result: VisionCaptureResult) -> str:
    """Human-readable summary for experiences; never store bare '?' captions."""
    caption = (result.caption or "").strip()
    if caption:
        try:
            from wifi_cam_mcp.vision import caption_looks_corrupt

            if caption_looks_corrupt(caption):
                caption = ""
        except ImportError:
            pass
    if caption:
        return caption[:240]
    if result.file_path:
        return "画像は撮れたが、LM Studio の視覚説明を取得できなかった"
    if result.error:
        return (result.error or "vision failed")[:240]
    snippet = (result.mcp_text or "").strip()
    if snippet and not snippet.startswith("---"):
        return snippet[:240]
    return "視界キャプチャ（説明なし）"


def vision_ltm_remember_enabled() -> bool:
    """Whether raw VISION mcp_text may be written to conversational LTM.

    Default **off** (``PRESENCE_VISION_LTM_REMEMBER=0``). Live see still uses
    ``vision_prefetch``; historical LTM dumps are not wanted.
    """
    return os.getenv("PRESENCE_VISION_LTM_REMEMBER", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def remember_vision_capture(result: VisionCaptureResult) -> bool:
    if not result.ok or not result.mcp_text.strip():
        return False
    if not vision_ltm_remember_enabled():
        logger.info(
            "vision LTM remember skipped (PRESENCE_VISION_LTM_REMEMBER off; "
            "live path uses vision_prefetch)"
        )
        result.remember_ok = False
        return False
    outcome = persist_remember_intent(
        RememberIntent(content=result.mcp_text, category="observation")
    )
    result.remember_ok = outcome.ok
    return outcome.ok


def vision_prefetch_note(
    result: VisionCaptureResult,
    *,
    intent: SeeIntent,
    user_text: str,
) -> str:
    """Build turn_delta block for pattern A (chat intercept)."""
    if not result.ok:
        err = result.error or "capture failed"
        return (
            "[vision_prefetch]\n"
            f"mode={intent.mode}\n"
            f"reason={intent.reason}\n"
            f"user_text={user_text[:200]}\n"
            f"error={err}\n"
            "\n"
            "[Gateway directive — not for the user]\n"
            "Camera capture failed. Tell まー honestly; do NOT guess the scene.\n"
            "Do NOT call mcp__wifi-cam__see or look_around."
        )

    body = result.mcp_text.strip()
    return (
        "[vision_prefetch]\n"
        f"mode={intent.mode}\n"
        f"reason={intent.reason}\n"
        f"trigger={user_text[:240]}\n"
        f"remember={'ok' if result.remember_ok else 'skipped'}\n"
        "\n"
        f"{body}\n"
        "\n"
        "[Gateway directive — not for the user]\n"
        "Gateway already captured the camera view above (MCP-equivalent text).\n"
        "Answer まー from VISION_CAPTION only when present; never invent details.\n"
        "Do NOT call mcp__wifi-cam__see, look_around, mcp__usb-webcam__see, "
        "or other camera tools.\n"
        "Reply naturally in Koyori voice; do not mention gateway_turn_context."
    )


VISION_PREFETCH_DIRECTIVE_ONLY = (
    "[Gateway directive — not for the user]\n"
    "Do NOT call mcp__wifi-cam__see or look_around (vision_prefetch is in this turn)."
)


def surface_vision_error_note(
    *,
    intent: SeeIntent,
    user_text: str,
    error: str,
) -> str:
    return (
        "[vision_prefetch]\n"
        f"mode={intent.mode}\n"
        f"reason={intent.reason}\n"
        f"user_text={user_text[:200]}\n"
        f"error={error}\n"
        "\n"
        "[Gateway directive — not for the user]\n"
        "Camera capture failed. Tell まー honestly; do NOT guess the scene.\n"
        "Do NOT call mcp__wifi-cam__see or look_around."
    )


async def capture_for_surface_multimodal(
    *,
    mode: SeeMode,
    label: str = "",
    remember: bool = True,
) -> tuple[VisionCaptureResult, str | None]:
    """Capture Tapo frame for surface 12b multimodal — no e4b describe."""
    outcome: CaptureOutcome = await capture_for_mode(mode)
    view_label = outcome.view_label or label or mode
    if not outcome.ok or not outcome.capture:
        hint = outcome.error or camera_failure_hint() or "capture failed"
        return (
            VisionCaptureResult(
                ok=False,
                mode=mode,
                label=view_label,
                mcp_text="",
                caption=None,
                file_path=None,
                error=hint,
            ),
            None,
        )

    capture = outcome.capture
    image_b64 = getattr(capture, "image_base64", None)
    if not image_b64:
        return (
            VisionCaptureResult(
                ok=False,
                mode=mode,
                label=view_label,
                mcp_text="",
                caption=None,
                file_path=getattr(capture, "file_path", None),
                error="capture had no image bytes",
            ),
            None,
        )

    from presence_ui.services.chat_image import prepare_chat_image_data_url

    try:
        data_url = prepare_chat_image_data_url(image_base64=image_b64, image_mime="image/jpeg")
    except ValueError as exc:
        return (
            VisionCaptureResult(
                ok=False,
                mode=mode,
                label=view_label,
                mcp_text="",
                caption=None,
                file_path=getattr(capture, "file_path", None),
                error=str(exc),
            ),
            None,
        )

    mcp_text = ""
    try:
        from wifi_cam_mcp.vision import format_capture_text

        mcp_text = format_capture_text(capture, view_label, vision_caption=None)
    except ImportError:
        path = getattr(capture, "file_path", None) or "unknown"
        mcp_text = f"--- {view_label} ---\nfile={path}"

    result = VisionCaptureResult(
        ok=True,
        mode=mode,
        label=view_label,
        mcp_text=mcp_text,
        caption=None,
        file_path=getattr(capture, "file_path", None),
    )
    if remember:
        remember_vision_capture(result)
    return result, data_url


async def prefetch_vision_for_chat(
    *,
    intent: SeeIntent,
    user_text: str,
    remember: bool = True,
) -> tuple[VisionCaptureResult, str]:
    """Run capture + describe; optionally remember; return (result, turn_delta note)."""
    label_map: dict[SeeMode, str] = {
        "current": "--- Current View ---",
        "look_around": "--- Center View (room scan) ---",
    }
    for key, spec in CAMERA_LOCATIONS.items():
        label_map[key] = spec.capture_label  # type: ignore[literal-required]
    result = await capture_and_describe(mode=intent.mode, label=label_map.get(intent.mode, ""))
    if remember and result.ok:
        remember_vision_capture(result)
    note = vision_prefetch_note(result, intent=intent, user_text=user_text)
    return result, note
