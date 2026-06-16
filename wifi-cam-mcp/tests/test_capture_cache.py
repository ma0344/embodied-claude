"""Capture directory retention."""

from __future__ import annotations

import time
from pathlib import Path

from wifi_cam_mcp.capture_cache import prune_capture_dir, prune_tts_surface_dir


def test_prune_capture_dir_by_age(tmp_path: Path) -> None:
    old = tmp_path / "capture_old.jpg"
    new = tmp_path / "capture_new.jpg"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    past = time.time() - 48 * 3600
    old.touch()
    Path(old).chmod(0o644)
    import os

    os.utime(old, (past, past))

    removed = prune_capture_dir(tmp_path, max_age_hours=24, max_files=99)
    assert removed == 1
    assert not old.exists()
    assert new.exists()


def test_prune_capture_dir_by_count(tmp_path: Path) -> None:
    for i in range(5):
        path = tmp_path / f"capture_{i:02d}.jpg"
        path.write_bytes(b"x")
        time.sleep(0.01)

    removed = prune_capture_dir(tmp_path, max_age_hours=0, max_files=2)
    assert removed == 3
    remaining = list(tmp_path.glob("capture_*.jpg"))
    assert len(remaining) == 2


def test_prune_tts_surface_dir(tmp_path: Path) -> None:
    surf = tmp_path / "tts-surface"
    surf.mkdir()
    stale = surf / "abc.wav"
    stale.write_bytes(b"wav")
    past = time.time() - 48 * 3600
    import os

    os.utime(stale, (past, past))

    removed = prune_tts_surface_dir(tmp_path)
    assert removed == 1
    assert not stale.exists()
