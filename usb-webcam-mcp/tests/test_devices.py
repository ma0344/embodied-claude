"""Tests for USB camera device name resolution."""

from usb_webcam_mcp.devices import (
    UsbCameraDevice,
    parse_dshow_video_devices,
    resolve_camera_index,
)


SAMPLE_FFMPEG = """
[dshow @ 000] DirectShow video devices (some may be both video and audio devices)
[dshow @ 000]  "Nuroum V11"
[dshow @ 000]     Alternative name "@device_pnp_..."
[dshow @ 000]  "Logitech QuickCam Pro 9000"
[dshow @ 000]     Alternative name "@device_pnp_..."
[dshow @ 000] DirectShow audio devices
[dshow @ 000]  "Microphone (Nuroum V11)"
"""


def test_parse_dshow_video_devices() -> None:
    names = parse_dshow_video_devices(SAMPLE_FFMPEG)
    assert names == ["Nuroum V11", "Logitech QuickCam Pro 9000"]


def test_resolve_camera_index_by_name(monkeypatch) -> None:
    devices = (
        UsbCameraDevice(0, "Nuroum V11"),
        UsbCameraDevice(1, "Logitech QuickCam Pro 9000"),
    )
    monkeypatch.setattr(
        "usb_webcam_mcp.devices.list_camera_devices",
        lambda *, refresh=False: devices,
    )
    assert resolve_camera_index(name_hint="QuickCam Pro 9000", fallback_index=0) == 1
    assert resolve_camera_index(name_hint="QuickCam", fallback_index=0) == 1
    assert resolve_camera_index(name_hint="Nuroum", fallback_index=9) == 0


def test_resolve_camera_index_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        "usb_webcam_mcp.devices.list_camera_devices",
        lambda *, refresh=False: (),
    )
    assert resolve_camera_index(name_hint="QuickCam", fallback_index=2) == 2
