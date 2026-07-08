"""Tests for USB outside camera routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from presence_ui.services.usb_camera import (
    resolve_usb_camera_index,
    usb_camera_enabled,
    usb_camera_fallback_index,
    usb_camera_name_hint,
)


def test_usb_camera_enabled_is_always_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_USB_CAMERA_ENABLED", raising=False)
    assert usb_camera_enabled() is False
    monkeypatch.setenv("PRESENCE_USB_CAMERA_ENABLED", "1")
    assert usb_camera_enabled() is False


def test_usb_camera_name_default_quickcam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USB_CAMERA_NAME", raising=False)
    assert usb_camera_name_hint() == "QuickCam"


def test_usb_camera_name_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USB_CAMERA_NAME", "Logitech QuickCam Pro 9000")
    assert usb_camera_name_hint() == "Logitech QuickCam Pro 9000"


def test_usb_camera_fallback_index(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USB_CAMERA_INDEX", "2")
    assert usb_camera_fallback_index() == 2


def test_resolve_usb_camera_index_uses_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "usb_webcam_mcp.devices.resolve_camera_index",
        lambda *, name_hint, fallback_index: 1,
    )
    monkeypatch.setenv("USB_CAMERA_NAME", "QuickCam Pro 9000")
    assert resolve_usb_camera_index() == 1


@pytest.mark.asyncio
async def test_capture_for_mode_window_uses_tapo_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_USB_CAMERA_ENABLED", "1")
    tapo_result = MagicMock()
    tapo_result.width = 1920
    tapo_result.height = 1080
    tapo_result.image_base64 = "tapo"
    tapo_result.file_path = None
    tapo_result.timestamp = "20260620_120001"

    with (
        patch("presence_ui.services.camera.preset_id_for_location", return_value="preset-window"),
        patch(
            "presence_ui.services.camera._capture_raw",
            new=AsyncMock(return_value=tapo_result),
        ),
        patch("presence_ui.services.camera._in_capture_backoff", return_value=False),
    ):
        tapo_cam = MagicMock()
        move_result = MagicMock(success=True, message="ok")
        tapo_cam.go_to_preset = AsyncMock(return_value=move_result)
        with patch(
            "presence_ui.services.camera._get_camera",
            new=AsyncMock(return_value=tapo_cam),
        ):
            from presence_ui.services.camera import capture_for_mode

            outcome = await capture_for_mode("window", save_to_file=False)

    assert outcome.ok is True
    assert outcome.capture is tapo_result
    assert "窓" in outcome.view_label
