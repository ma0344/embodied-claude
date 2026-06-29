"""USB camera discovery by friendly name (Windows DirectShow via ffmpeg)."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

_DEVICE_LINE = re.compile(r'"([^"]+)"')


@dataclass(frozen=True, slots=True)
class UsbCameraDevice:
    index: int
    name: str


def parse_dshow_video_devices(stderr: str) -> list[str]:
    """Parse ffmpeg dshow -list_devices video section (ordered = OpenCV index hint)."""
    names: list[str] = []
    in_video = False
    for line in stderr.splitlines():
        if "DirectShow video devices" in line:
            in_video = True
            continue
        if in_video and "DirectShow audio devices" in line:
            break
        if not in_video:
            continue
        if "Alternative name" in line:
            continue
        match = _DEVICE_LINE.search(line)
        if match:
            names.append(match.group(1).strip())
    return names


def _list_v4l2_names() -> list[str]:
    names: list[str] = []
    base = "/sys/class/video4linux"
    if not os.path.isdir(base):
        return names
    for entry in sorted(os.listdir(base)):
        if not entry.startswith("video"):
            continue
        name_path = os.path.join(base, entry, "name")
        try:
            with open(name_path, encoding="utf-8") as handle:
                names.append(handle.read().strip())
        except OSError:
            continue
    return names


@lru_cache(maxsize=1)
def list_camera_devices(*, refresh: bool = False) -> tuple[UsbCameraDevice, ...]:
    """Return cameras with stable index order (Windows: ffmpeg dshow list)."""
    if refresh:
        list_camera_devices.cache_clear()

    names: list[str] = []
    if sys.platform == "win32":
        names = _list_dshow_names_ffmpeg()
    if not names and sys.platform.startswith("linux"):
        names = _list_v4l2_names()
    if not names:
        names = _probe_opencv_camera_names()
    return tuple(UsbCameraDevice(index=i, name=name) for i, name in enumerate(names))


def _probe_opencv_camera_names(max_cameras: int = 10) -> list[str]:
    import cv2

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    names: list[str] = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            names.append(f"Camera {i}")
            cap.release()
    return names


def _list_dshow_names_ffmpeg() -> list[str]:
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffmpeg dshow list unavailable: %s", exc)
        return []
    text = (proc.stderr or "") + (proc.stdout or "")
    names = parse_dshow_video_devices(text)
    if not names:
        logger.warning("ffmpeg dshow list returned no video devices")
    return names


def resolve_camera_index(
    *,
    name_hint: str | None,
    fallback_index: int = 0,
) -> int:
    """Match substring (case-insensitive) against device names; else fallback index."""
    hint = (name_hint or "").strip()
    devices = list_camera_devices()
    if hint and devices:
        needle = hint.casefold()
        matches = [dev for dev in devices if needle in dev.name.casefold()]
        if len(matches) == 1:
            logger.info(
                "USB camera resolved name=%r -> index=%d (%s)",
                hint,
                matches[0].index,
                matches[0].name,
            )
            return matches[0].index
        if len(matches) > 1:
            chosen = min(matches, key=lambda dev: len(dev.name))
            logger.warning(
                "USB camera name %r matched %d devices; using index=%d (%s)",
                hint,
                len(matches),
                chosen.index,
                chosen.name,
            )
            return chosen.index
        logger.warning(
            "USB camera name %r not found among %s; fallback index=%d",
            hint,
            [dev.name for dev in devices],
            fallback_index,
        )
    elif hint and not devices:
        logger.warning(
            "USB camera name %r set but device list empty; fallback index=%d",
            hint,
            fallback_index,
        )
    return max(0, fallback_index)


def match_camera_name(name_hint: str, device_name: str) -> bool:
    hint = (name_hint or "").strip().casefold()
    if not hint:
        return False
    return hint in (device_name or "").casefold()
