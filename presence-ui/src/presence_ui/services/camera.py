"""Wi-Fi camera snapshot via wifi-cam-mcp (direct TapoCamera import)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from presence_ui.gateway.see_intent import SeeMode
from presence_ui.schemas import CameraSnapshotResponse
from presence_ui.services.camera_locations import (
    CAMERA_LOCATIONS,
    is_preset_location,
    preset_id_for_location,
)

logger = logging.getLogger(__name__)

_camera = None
_camera_error: str | None = None
_camera_last_failure: str | None = None
_camera_lock = asyncio.Lock()
_backoff_until: float = 0.0
_BACKOFF_SECONDS = float(os.getenv("PRESENCE_CAMERA_BACKOFF_SECONDS", "45"))
_PRESET_SETTLE_SECONDS = float(os.getenv("PRESENCE_CAMERA_PRESET_SETTLE_SECONDS", "1.5"))


@dataclass(slots=True)
class CaptureOutcome:
    ok: bool
    capture: object | None = None
    view_label: str = ""
    preset_id: str | None = None
    error: str | None = None


def camera_failure_hint() -> str | None:
    """Human-readable reason for the most recent camera failure (if any)."""
    if time.monotonic() < _backoff_until:
        return _camera_last_failure or "camera unavailable (cooldown after recent failure)"
    return _camera_last_failure


def window_preset_id() -> str | None:
    return preset_id_for_location("window")


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


def _in_backoff() -> bool:
    return time.monotonic() < _backoff_until


def _set_failure(msg: str) -> None:
    global _backoff_until, _camera_last_failure
    _camera_last_failure = msg
    _backoff_until = time.monotonic() + _BACKOFF_SECONDS


async def camera_go_to_preset(preset_id: str) -> tuple[bool, str]:
    """Move to an ONVIF preset before capture."""
    if _in_backoff():
        return False, camera_failure_hint() or "camera unavailable (cooldown)"

    async with _camera_lock:
        try:
            camera = await _get_camera()
            move = await asyncio.wait_for(camera.go_to_preset(preset_id), timeout=12.0)
            if not move.success:
                return False, move.message
            await asyncio.sleep(_PRESET_SETTLE_SECONDS)
            _camera_last_failure = None
            return True, move.message
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_failure(msg)
            await _reset_camera()
            logger.warning("Camera go_to_preset failed: %s", msg)
            return False, msg


async def _capture_raw(*, save_to_file: bool = True):
    camera = await _get_camera()

    async def _run():
        return await camera.capture_image(save_to_file=save_to_file)

    timeout_s = float(os.getenv("PRESENCE_CAMERA_TIMEOUT_SECONDS", "8"))
    return await asyncio.wait_for(_run(), timeout=timeout_s)


async def capture_for_mode(mode: SeeMode, *, save_to_file: bool = True) -> CaptureOutcome:
    """Capture one frame (or look_around center) with optional window preset."""
    if _in_backoff():
        return CaptureOutcome(
            ok=False,
            error=camera_failure_hint() or "camera unavailable (cooldown)",
        )

    preset_id: str | None = None
    view_label = "current"
    if is_preset_location(mode):
        preset_id = preset_id_for_location(mode)  # type: ignore[arg-type]
        view_label = CAMERA_LOCATIONS[mode].label_ja  # type: ignore[index]
        if not preset_id:
            logger.warning("%s preset not configured; capturing at current angle", mode)

    async with _camera_lock:
        try:
            if preset_id:
                camera = await _get_camera()
                move = await asyncio.wait_for(camera.go_to_preset(preset_id), timeout=12.0)
                if not move.success:
                    return CaptureOutcome(ok=False, error=move.message, preset_id=preset_id)
                await asyncio.sleep(_PRESET_SETTLE_SECONDS)

            if mode == "look_around":
                camera = await _get_camera()

                async def _scan():
                    return await camera.look_around()

                captures = await asyncio.wait_for(
                    _scan(),
                    timeout=float(os.getenv("PRESENCE_CAMERA_LOOKAROUND_TIMEOUT_SECONDS", "45")),
                )
                if not captures:
                    _camera_last_failure = "look_around returned no captures"
                    return CaptureOutcome(
                        ok=False,
                        error=_camera_last_failure,
                        view_label="room scan",
                    )
                _camera_last_failure = None
                return CaptureOutcome(
                    ok=True,
                    capture=captures[0],
                    view_label="center (room scan)",
                    preset_id=preset_id,
                )

            result = await _capture_raw(save_to_file=save_to_file)
            _camera_last_failure = None
            return CaptureOutcome(
                ok=True,
                capture=result,
                view_label=view_label,
                preset_id=preset_id,
            )
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_failure(msg)
            await _reset_camera()
            logger.warning("capture_for_mode(%s) failed: %s", mode, msg)
            return CaptureOutcome(ok=False, error=msg, preset_id=preset_id)


async def fetch_camera_snapshot() -> CameraSnapshotResponse:
    """UI preview snapshot — base64 only, no disk write (avoids temp dir accumulation)."""
    global _backoff_until
    preset = os.getenv("PRESENCE_CAMERA_PRESET_LABEL", "current")
    outcome = await capture_for_mode("current", save_to_file=False)
    if not outcome.ok or not outcome.capture:
        return CameraSnapshotResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_preset=preset,
            error=outcome.error or "capture failed",
        )

    result = outcome.capture
    width = result.width if result.width else None
    height = result.height if result.height else None
    if (not width or not height) and result.image_base64:
        try:
            import base64
            import io

            from PIL import Image

            raw = base64.standard_b64decode(result.image_base64)
            img = Image.open(io.BytesIO(raw))
            width, height = img.size
        except Exception:
            pass
    return CameraSnapshotResponse(
        timestamp=result.timestamp or datetime.now(timezone.utc).isoformat(),
        image_base64=result.image_base64,
        image_url=None,
        width=width,
        height=height,
        camera_preset=preset,
    )


async def fetch_window_snapshot() -> CameraSnapshotResponse:
    """Snapshot after moving to window preset (look_outside)."""
    outcome = await capture_for_mode("window")
    if not outcome.ok or not outcome.capture:
        return CameraSnapshotResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_preset="window",
            error=outcome.error or "capture failed",
        )
    result = outcome.capture
    return CameraSnapshotResponse(
        timestamp=result.timestamp or datetime.now(timezone.utc).isoformat(),
        image_base64=result.image_base64,
        width=result.width or None,
        height=result.height or None,
        camera_preset="window",
    )


async def camera_look_around() -> list:
    """Pan/tilt capture sequence (wifi-cam look_around)."""
    if _in_backoff():
        return []

    async with _camera_lock:
        try:
            camera = await _get_camera()

            async def _scan():
                return await camera.look_around()

            captures = await asyncio.wait_for(
                _scan(),
                timeout=float(os.getenv("PRESENCE_CAMERA_LOOKAROUND_TIMEOUT_SECONDS", "45")),
            )
            if captures:
                global _camera_last_failure
                _camera_last_failure = None
            else:
                _camera_last_failure = "look_around returned no captures"
            return captures
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_failure(msg)
            await _reset_camera()
            logger.warning("Camera look_around failed (backoff %.0fs): %s", _BACKOFF_SECONDS, msg)
            return []
