"""USB outside camera — name-based device selection for look_outside."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_usb_lock = asyncio.Lock()


def usb_camera_enabled() -> bool:
    """USB outside camera is retired — look_outside uses Tapo window preset only."""
    legacy = os.getenv("PRESENCE_USB_CAMERA_ENABLED", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if legacy:
        logger.warning(
            "PRESENCE_USB_CAMERA_ENABLED is set but USB outside camera is retired; "
            "use Tapo window preset (look_outside / mode=window)"
        )
    return False


def usb_camera_name_hint() -> str:
    """Substring match for outside camera (ma-home default: Logitech QuickCam)."""
    raw = os.getenv("USB_CAMERA_NAME", "").strip()
    if raw:
        return raw
    return "QuickCam"


def usb_camera_fallback_index() -> int:
    raw = os.getenv("USB_CAMERA_INDEX", "0").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def resolve_usb_camera_index() -> int:
    from usb_webcam_mcp.devices import resolve_camera_index

    name = usb_camera_name_hint()
    index = resolve_camera_index(name_hint=name, fallback_index=usb_camera_fallback_index())
    return index


def resolved_usb_camera_label() -> str:
    from usb_webcam_mcp.devices import list_camera_devices

    index = resolve_usb_camera_index()
    for dev in list_camera_devices():
        if dev.index == index:
            return dev.name
    return f"index {index}"


def _capture_sync(
    *,
    camera_index: int,
    camera_name: str | None,
    width: int | None,
    height: int | None,
) -> bytes:
    from usb_webcam_mcp.server import capture_from_camera

    return capture_from_camera(
        camera_index,
        width,
        height,
        camera_name=camera_name,
    )


def _jpeg_to_capture_result(jpeg_bytes: bytes, *, file_path: str | None) -> object:
    from wifi_cam_mcp.camera import CaptureResult

    from PIL import Image

    img = Image.open(io.BytesIO(jpeg_bytes))
    width, height = img.size
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return CaptureResult(
        image_base64=base64.standard_b64encode(jpeg_bytes).decode("utf-8"),
        file_path=file_path,
        timestamp=timestamp,
        width=width,
        height=height,
    )


async def capture_usb_frame(
    *,
    save_to_file: bool = False,
    camera_index: int | None = None,
) -> object:
    """Capture one JPEG frame from USB webcam; returns wifi-cam CaptureResult."""
    name_hint = usb_camera_name_hint()
    fallback = usb_camera_fallback_index() if camera_index is None else camera_index
    width_raw = os.getenv("USB_CAMERA_WIDTH", "").strip()
    height_raw = os.getenv("USB_CAMERA_HEIGHT", "").strip()
    width = int(width_raw) if width_raw.isdigit() else None
    height = int(height_raw) if height_raw.isdigit() else None

    async with _usb_lock:
        jpeg_bytes = await asyncio.to_thread(
            _capture_sync,
            camera_index=fallback,
            camera_name=name_hint,
            width=width,
            height=height,
        )

    file_path: str | None = None
    if save_to_file:
        out_dir = Path.home() / ".claude" / "captures" / "usb"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"usb_{ts}.jpg"
        path.write_bytes(jpeg_bytes)
        file_path = str(path)

    result = _jpeg_to_capture_result(jpeg_bytes, file_path=file_path)
    logger.info(
        "USB capture name_hint=%r device=%s %dx%d saved=%s",
        name_hint,
        resolved_usb_camera_label(),
        result.width,
        result.height,
        bool(file_path),
    )
    return result
