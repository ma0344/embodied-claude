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
_capture_backoff_until: float = 0.0
_last_preview_snapshot: CameraSnapshotResponse | None = None
_BACKOFF_SECONDS = float(os.getenv("PRESENCE_CAMERA_BACKOFF_SECONDS", "45"))
_PRESET_SETTLE_SECONDS = float(os.getenv("PRESENCE_CAMERA_PRESET_SETTLE_SECONDS", "1.5"))
_CAPTURE_TIMEOUT_SECONDS = float(os.getenv("PRESENCE_CAMERA_TIMEOUT_SECONDS", "15"))
_PREVIEW_SKIP_IF_BUSY = os.getenv("PRESENCE_CAMERA_PREVIEW_SKIP_IF_BUSY", "1").lower() not in {
    "0",
    "false",
    "no",
}


def _camera_save_to_disk() -> bool:
    """Gateway captures default to memory-only; set PRESENCE_CAMERA_SAVE_TO_DISK=1 to keep JPEGs."""
    return os.getenv("PRESENCE_CAMERA_SAVE_TO_DISK", "0").lower() in {"1", "true", "yes"}


def _set_capture_failure(msg: str) -> None:
    global _capture_backoff_until, _camera_last_failure
    _camera_last_failure = msg
    _capture_backoff_until = time.monotonic() + _BACKOFF_SECONDS


def _clear_camera_failure() -> None:
    global _camera_last_failure
    _camera_last_failure = None


def _record_camera_failure(msg: str) -> None:
    global _camera_last_failure
    _camera_last_failure = msg


def _in_capture_backoff() -> bool:
    return time.monotonic() < _capture_backoff_until


async def camera_move(direction: str, degrees: int = 30) -> tuple[bool, str]:
    """Pan/tilt via ONVIF (gateway direct — no MCP required)."""
    async with _camera_lock:
        try:
            from wifi_cam_mcp.camera import Direction

            dir_map = {
                "left": Direction.LEFT,
                "right": Direction.RIGHT,
                "up": Direction.UP,
                "down": Direction.DOWN,
            }
            move_dir = dir_map.get(direction)
            if move_dir is None:
                return False, f"unknown direction: {direction}"

            camera = await _get_camera()
            move = await asyncio.wait_for(camera.move(move_dir, degrees), timeout=15.0)
            if move.success:
                _clear_camera_failure()
                return True, move.message
            return False, move.message
        except TimeoutError:
            return False, "camera move timed out"
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_capture_failure(msg)
            await _reset_camera()
            logger.warning("camera_move(%s) failed: %s", direction, msg)
            return False, msg


@dataclass(slots=True)
class CaptureOutcome:
    ok: bool
    capture: object | None = None
    view_label: str = ""
    preset_id: str | None = None
    error: str | None = None


def camera_failure_hint() -> str | None:
    """Human-readable reason for the most recent camera failure (if any)."""
    if _in_capture_backoff():
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

    from presence_ui.repo_env import load_repo_env

    load_repo_env()

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig, ServerConfig

    config = CameraConfig.from_env()
    server_config = ServerConfig.from_env()
    _camera = TapoCamera(config, server_config.capture_dir)
    return _camera


def _in_backoff() -> bool:
    """Deprecated alias — capture-only cooldown."""
    return _in_capture_backoff()


async def camera_go_to_preset(preset_id: str) -> tuple[bool, str]:
    """Move to an ONVIF preset before capture."""
    async with _camera_lock:
        try:
            camera = await _get_camera()
            move = await asyncio.wait_for(camera.go_to_preset(preset_id), timeout=12.0)
            if not move.success:
                return False, move.message
            await asyncio.sleep(_PRESET_SETTLE_SECONDS)
            _clear_camera_failure()
            return True, move.message
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_capture_failure(msg)
            await _reset_camera()
            logger.warning("Camera go_to_preset failed: %s", msg)
            return False, msg


async def _capture_raw(*, save_to_file: bool = True):
    camera = await _get_camera()

    async def _run():
        return await camera.capture_image(save_to_file=save_to_file)

    timeout_s = _CAPTURE_TIMEOUT_SECONDS
    return await asyncio.wait_for(_run(), timeout=timeout_s)


async def capture_for_mode(mode: SeeMode, *, save_to_file: bool | None = None) -> CaptureOutcome:
    """Capture one frame (or look_around center) with optional window preset."""
    if save_to_file is None:
        save_to_file = _camera_save_to_disk()

    if mode == "window":
        from presence_ui.services.usb_camera import (
            capture_usb_frame,
            resolved_usb_camera_label,
            usb_camera_enabled,
        )

        if usb_camera_enabled():
            try:
                capture = await capture_usb_frame(save_to_file=save_to_file)
                return CaptureOutcome(
                    ok=True,
                    capture=capture,
                    view_label=f"外 (USB: {resolved_usb_camera_label()})",
                )
            except Exception as exc:
                msg = str(exc) or type(exc).__name__
                logger.warning("USB outside capture failed (%s); trying Tapo window preset", msg)

    preset_id: str | None = None
    view_label = "current"
    if is_preset_location(mode):
        preset_id = preset_id_for_location(mode)  # type: ignore[arg-type]
        view_label = CAMERA_LOCATIONS[mode].label_ja  # type: ignore[index]
        if not preset_id:
            logger.warning("%s preset not configured; capturing at current angle", mode)

    if _in_capture_backoff() and not preset_id and mode != "look_around":
        return CaptureOutcome(
            ok=False,
            error=camera_failure_hint() or "camera unavailable (cooldown)",
        )

    async with _camera_lock:
        try:
            if preset_id:
                camera = await _get_camera()
                move = await asyncio.wait_for(camera.go_to_preset(preset_id), timeout=12.0)
                if not move.success:
                    return CaptureOutcome(ok=False, error=move.message, preset_id=preset_id)
                await asyncio.sleep(_PRESET_SETTLE_SECONDS)

            if _in_capture_backoff() and mode != "look_around":
                return CaptureOutcome(
                    ok=False,
                    error=camera_failure_hint() or "camera unavailable (cooldown)",
                    preset_id=preset_id,
                    view_label=view_label,
                )

            if mode == "look_around":
                camera = await _get_camera()

                async def _scan():
                    return await camera.look_around(save_to_file=save_to_file)

                captures = await asyncio.wait_for(
                    _scan(),
                    timeout=float(os.getenv("PRESENCE_CAMERA_LOOKAROUND_TIMEOUT_SECONDS", "45")),
                )
                if not captures:
                    _record_camera_failure("look_around returned no captures")
                    return CaptureOutcome(
                        ok=False,
                        error=_camera_last_failure,
                        view_label="room scan",
                    )
                _clear_camera_failure()
                return CaptureOutcome(
                    ok=True,
                    capture=captures[0],
                    view_label="center (room scan)",
                    preset_id=preset_id,
                )

            result = await _capture_raw(save_to_file=save_to_file)
            _clear_camera_failure()
            return CaptureOutcome(
                ok=True,
                capture=result,
                view_label=view_label,
                preset_id=preset_id,
            )
        except TimeoutError:
            msg = "camera capture timed out"
            if preset_id:
                msg = f"preset {preset_id} reached but capture timed out"
            _set_capture_failure(msg)
            logger.warning("capture_for_mode(%s) failed: %s", mode, msg)
            return CaptureOutcome(ok=False, error=msg, preset_id=preset_id, view_label=view_label)
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_capture_failure(msg)
            await _reset_camera()
            logger.warning("capture_for_mode(%s) failed: %s", mode, msg)
            return CaptureOutcome(ok=False, error=msg, preset_id=preset_id, view_label=view_label)


async def fetch_camera_snapshot() -> CameraSnapshotResponse:
    """UI preview snapshot — base64 only, no disk write (avoids temp dir accumulation)."""
    global _last_preview_snapshot
    preset = os.getenv("PRESENCE_CAMERA_PRESET_LABEL", "current")

    if _PREVIEW_SKIP_IF_BUSY and _camera_lock.locked():
        if _last_preview_snapshot is not None:
            return _last_preview_snapshot
        return CameraSnapshotResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_preset=preset,
            error="camera busy",
        )

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
    response = CameraSnapshotResponse(
        timestamp=result.timestamp or datetime.now(timezone.utc).isoformat(),
        image_base64=result.image_base64,
        image_url=None,
        width=width,
        height=height,
        camera_preset=preset,
    )
    _last_preview_snapshot = response
    return response


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
    async with _camera_lock:
        try:
            camera = await _get_camera()

            async def _scan():
                return await camera.look_around(save_to_file=_camera_save_to_disk())

            captures = await asyncio.wait_for(
                _scan(),
                timeout=float(os.getenv("PRESENCE_CAMERA_LOOKAROUND_TIMEOUT_SECONDS", "45")),
            )
            if captures:
                _clear_camera_failure()
            else:
                _record_camera_failure("look_around returned no captures")
            return captures
        except TimeoutError:
            msg = "camera look_around timed out"
            _set_capture_failure(msg)
            logger.warning("Camera look_around failed (backoff %.0fs): %s", _BACKOFF_SECONDS, msg)
            return []
        except Exception as exc:
            msg = str(exc) or type(exc).__name__
            _set_capture_failure(msg)
            await _reset_camera()
            logger.warning("Camera look_around failed (backoff %.0fs): %s", _BACKOFF_SECONDS, msg)
            return []
