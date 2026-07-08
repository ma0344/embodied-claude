"""Tests for OBS-TICK-1b per-view room scene signals."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from presence_ui.services import room_scene


def _solid_image(color: int) -> Image.Image:
    return Image.new("RGB", (64, 48), (color, color, color))


def _b64(image: Image.Image) -> str:
    buf = BytesIO()
    image.save(buf, format="JPEG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def test_compute_phash_hex_stable() -> None:
    img = _solid_image(128)
    assert room_scene.compute_phash_hex(img) == room_scene.compute_phash_hex(img)


def test_hamming_identical_zero() -> None:
    h = room_scene.compute_phash_hex(_solid_image(200))
    assert room_scene.hamming_hex(h, h) == 0


def test_hamming_different_images() -> None:
    left = Image.new("RGB", (64, 48), (10, 10, 10))
    right = Image.new("RGB", (64, 48), (240, 240, 240))
    for x in range(32):
        for y in range(48):
            right.putpixel((x, y), (10, 10, 10))
    a = room_scene.compute_phash_hex(left)
    b = room_scene.compute_phash_hex(right)
    assert room_scene.hamming_hex(a, b) > 0


def test_grayscale_mae_identical_zero() -> None:
    img = _solid_image(100)
    assert room_scene.grayscale_mae(img, img) == 0.0


def _patch_sources(home: Path, sources: dict[str, Path]):
    def _source(view_id: str) -> Path:
        return sources[view_id]

    return (
        patch.object(room_scene, "presence_ui_home", return_value=home),
        patch.object(room_scene, "baseline_source_image", side_effect=_source),
    )


def test_ensure_all_baselines_registers_three_views(tmp_path: Path) -> None:
    sources = {}
    for view_id in room_scene.VIEW_IDS:
        p = tmp_path / f"{view_id}.jpg"
        _solid_image(90).save(p, format="JPEG")
        sources[view_id] = p

    home = tmp_path / "presence-ui"
    home_patch, source_patch = _patch_sources(home, sources)
    with home_patch, source_patch:
        baselines = room_scene.ensure_all_baselines(force=True)

    assert set(baselines) == set(room_scene.VIEW_IDS)
    for view_id, baseline in baselines.items():
        assert baseline.view_id == view_id
        assert baseline.baseline_id.startswith(view_id)
        assert Path(baseline.anchor_path).is_file()
    assert (home / "room_baselines.json").is_file()


def test_log_room_tick_signal_uses_view_baseline(tmp_path: Path) -> None:
    sources = {}
    for view_id, color in (("window", 40), ("desk", 120), ("dining", 200)):
        p = tmp_path / f"{view_id}.jpg"
        _solid_image(color).save(p, format="JPEG")
        sources[view_id] = p

    home = tmp_path / "presence-ui"
    current = _b64(_solid_image(205))

    home_patch, source_patch = _patch_sources(home, sources)
    with home_patch, source_patch, patch.object(
        room_scene, "obs_tick_1b_enabled", return_value=True
    ):
        room_scene.ensure_all_baselines(force=True)
        row = room_scene.log_room_tick_signal(view_id="dining", image_base64=current)

    assert row is not None
    assert row["view_id"] == "dining"
    assert row["baseline_id"].startswith("dining")
    assert isinstance(row["hamming_baseline"], int)
    assert row["hamming_prev"] is None
    assert isinstance(row["hamming_dct_baseline"], int)
    assert row["hamming_dct_prev"] is None
    assert len(row["phash_dct_hex"]) == 16

    log_path = home / "room_scene_signals.jsonl"
    parsed = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert parsed["view_id"] == "dining"
    assert parsed["encode"] == "signal_only"


def test_log_room_tick_signal_tracks_prev_per_view(tmp_path: Path) -> None:
    sources = {}
    for view_id in room_scene.VIEW_IDS:
        p = tmp_path / f"{view_id}.jpg"
        _solid_image(90).save(p, format="JPEG")
        sources[view_id] = p

    home = tmp_path / "presence-ui"
    home_patch, source_patch = _patch_sources(home, sources)
    with home_patch, source_patch, patch.object(
        room_scene, "obs_tick_1b_enabled", return_value=True
    ):
        room_scene.ensure_all_baselines(force=True)
        first = room_scene.log_room_tick_signal(
            view_id="window", image_base64=_b64(_solid_image(95))
        )
        second = room_scene.log_room_tick_signal(
            view_id="window", image_base64=_b64(_solid_image(95))
        )
        # desk stays independent — first sighting so prev is None
        desk = room_scene.log_room_tick_signal(
            view_id="desk", image_base64=_b64(_solid_image(200))
        )

    assert first["hamming_prev"] is None
    assert second["hamming_prev"] == 0
    assert desk["hamming_prev"] is None


def test_log_room_tick_signal_disabled_returns_none(tmp_path: Path) -> None:
    with patch.object(room_scene, "obs_tick_1b_enabled", return_value=False):
        assert room_scene.log_room_tick_signal(view_id="dining", image_base64="") is None


def test_save_frame_writes_jpg_with_hamming_name(tmp_path: Path) -> None:
    sources = {}
    for view_id in room_scene.VIEW_IDS:
        p = tmp_path / f"{view_id}.jpg"
        _solid_image(90).save(p, format="JPEG")
        sources[view_id] = p

    home = tmp_path / "presence-ui"
    current = _b64(_solid_image(150))
    home_patch, source_patch = _patch_sources(home, sources)
    with (
        home_patch,
        source_patch,
        patch.object(room_scene, "obs_tick_1b_enabled", return_value=True),
        patch.object(room_scene, "room_save_frames_enabled", return_value=True),
    ):
        room_scene.ensure_all_baselines(force=True)
        row = room_scene.log_room_tick_signal(view_id="dining", image_base64=current)

    assert row is not None
    saved = row["capture_path"]
    assert saved is not None
    assert Path(saved).is_file()
    assert Path(saved).name.endswith(".jpg")
    assert "_b" in Path(saved).name and "_dctp" in Path(saved).name
