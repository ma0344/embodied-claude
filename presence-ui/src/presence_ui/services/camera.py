"""Wi-Fi camera snapshot via wifi-cam-mcp (direct TapoCamera import)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from presence_ui.schemas import CameraSnapshotResponse

logger = logging.getLogger(__name__)

_camera = None
_camera_error: str | None = None
_camera_lock = asyncio.Lock()
_backoff_until: float = 0.0
_BACKOFF_SECONDS = float(os.getenv("PRESENCE_CAMERA_BACKOFF_SECONDS", "45"))


async def _reset_camera() -> None:
    global _camera, _camera_error
    if _camera is not None:
        try:
            await _camera.disconnect()
        except Exception:
            pass
    _camera = None
    _camera_error = None


async def _get_camera():
    global _camera, _camera_error
    if _camera is not None:
        return _camera
    if _camera_error is not None:
        raise RuntimeError(_camera_error)

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig, ServerConfig

    config = CameraConfig.from_env()
    server_config = ServerConfig.from_env()
    _camera = TapoCamera(config, server_config.capture_dir)
    return _camera


async def fetch_camera_snapshot() -> CameraSnapshotResponse:
    global _backoff_until
    preset = os.getenv("PRESENCE_CAMERA_PRESET_LABEL", "current")
    timeout_s = float(os.getenv("PRESENCE_CAMERA_TIMEOUT_SECONDS", "8"))

    if time.monotonic() < _backoff_until:
        return CameraSnapshotResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_preset=preset,
            error="camera unavailable (cooldown after recent failure)",
        )

    async with _camera_lock:
        try:
            camera = await _get_camera()

            async def _capture():
                return await camera.capture_image(save_to_file=True)

            result = await asyncio.wait_for(_capture(), timeout=timeout_s)
            return CameraSnapshotResponse(
                timestamp=result.timestamp or datetime.now(timezone.utc).isoformat(),
                image_base64=result.image_base64,
                image_url=None,
                width=result.width,
                height=result.height,
                camera_preset=preset,
            )
        except Exception as exc:
            _backoff_until = time.monotonic() + _BACKOFF_SECONDS
            await _reset_camera()
            logger.warning("Camera snapshot failed (backoff %.0fs): %s", _BACKOFF_SECONDS, exc)
            return CameraSnapshotResponse(
                timestamp=datetime.now(timezone.utc).isoformat(),
                camera_preset=preset,
                error=str(exc),
            )
