"""Tests for Irodori profile TOML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from tts_mcp.irodori_profile import IrodoriProfile, load_irodori_profile


def test_load_profile(tmp_path: Path) -> None:
    path = tmp_path / "irodori-profile.toml"
    path.write_text(
        """
[profile]
voice = "koyori"
seed = 8787384312565159089
num_steps = 24

[profile.cfg]
text = 3.0
caption = 10.0
speaker = 2.0

[profile.caption]
default = \"\"\"
落ち着いた関西弁。
\"\"\"
""".strip(),
        encoding="utf-8",
    )
    profile = load_irodori_profile(path)
    assert profile is not None
    assert profile.voice == "koyori"
    assert profile.seed == 8787384312565159089
    assert profile.num_steps == 24
    assert profile.cfg_scale_text == 3.0
    assert profile.cfg_scale_caption == 10.0
    assert profile.cfg_scale_speaker == 2.0
    assert profile.caption == "落ち着いた関西弁。"


def test_missing_profile_returns_none(tmp_path: Path) -> None:
    assert load_irodori_profile(tmp_path / "missing.toml") is None


def test_invalid_num_steps_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("[profile]\nnum_steps = 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="num_steps"):
        load_irodori_profile(path)


def test_cache_label_includes_cfg_and_caption() -> None:
    profile = IrodoriProfile(
        voice="koyori",
        seed=1,
        num_steps=24,
        cfg_scale_text=3.0,
        cfg_scale_caption=10.0,
        cfg_scale_speaker=2.0,
        caption="test caption",
    )
    assert "koyori" in profile.cache_label
    assert "10.0" in profile.cache_label
    assert "test caption" in profile.cache_label
