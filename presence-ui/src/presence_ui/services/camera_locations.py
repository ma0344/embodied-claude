"""Named camera presets (window, desk, dining) for gateway see / capture."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

PresetLocation = Literal["window", "desk", "dining"]


@dataclass(frozen=True, slots=True)
class CameraLocation:
    key: PresetLocation
    label_ja: str
    capture_label: str
    env_keys: tuple[str, ...]


CAMERA_LOCATIONS: dict[PresetLocation, CameraLocation] = {
    "window": CameraLocation(
        key="window",
        label_ja="窓/外",
        capture_label="--- Window / Outside View ---",
        env_keys=(
            "PRESENCE_CAMERA_WINDOW_PRESET",
            "TAPO_WINDOW_PRESET",
            "TAPO_LOOK_OUTSIDE_PRESET",
        ),
    ),
    "desk": CameraLocation(
        key="desk",
        label_ja="まーのデスク",
        capture_label="--- Ma's Desk View ---",
        env_keys=(
            "PRESENCE_CAMERA_DESK_PRESET",
            "TAPO_MADESK_PRESET",
            "TAPO_MA_DESK_PRESET",
        ),
    ),
    "dining": CameraLocation(
        key="dining",
        label_ja="ダイニング",
        capture_label="--- Dining View ---",
        env_keys=(
            "PRESENCE_CAMERA_DINING_PRESET",
            "TAPO_DINING_PRESET",
        ),
    ),
}


def preset_id_for_location(location: PresetLocation) -> str | None:
    spec = CAMERA_LOCATIONS.get(location)
    if spec is None:
        return None
    for env_key in spec.env_keys:
        raw = os.getenv(env_key, "").strip()
        if raw:
            return raw
    return None


def is_preset_location(mode: str) -> bool:
    return mode in CAMERA_LOCATIONS
