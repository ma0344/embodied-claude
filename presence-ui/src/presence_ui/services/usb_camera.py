"""ma-home USB webcam capture for outside/window view (Logitech QuickCam, etc.)."""

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
    return os.getenv("PRESENCE_USB_CAMERA_ENABLED", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def usb_camera_index() -> int:
    raw = os.getenv("USB_CAMERA_INDEX", "1").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def _capture_sync(*, camera_index: int, width: int | None, height: int | None) -> bytes:
    from usb_webcam_mcp.server import capture_from_camera

    return capture_from_camera(camera_index=camera_index, width=width, height=height)


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
    idx = usb_camera_index() if camera_index is None else camera_index
    width_raw = os.getenv("USB_CAMERA_WIDTH", "").strip()
    height_raw = os.getenv("USB_CAMERA_HEIGHT", "").strip()
    width = int(width_raw) if width_raw.isdigit() else None
    height = int(height_raw) if height_raw.isdigit() else None

    async with _usb_lock:
        jpeg_bytes = await asyncio.to_thread(
            _capture_sync,
            camera_index=idx,
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
        "USB capture index=%d %dx%d saved=%s",
        idx,
        result.width,
        result.height,
        bool(file_path),
    )
    return result
