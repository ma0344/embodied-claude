"""LM Studio vision model reload helpers."""

import time

import pytest

from wifi_cam_mcp import lm_studio_models as lsm


def test_model_ids_match_suffix() -> None:
    assert lsm.model_ids_match("qwen2.5-vl-3b-instruct", "qwen/qwen2.5-vl-3b-instruct")
    assert lsm.model_ids_match("qwen/qwen2.5-vl-3b-instruct", "qwen2.5-vl-3b-instruct")


def test_find_model_entry_by_key() -> None:
    models = [
        {
            "key": "qwen/qwen2.5-vl-3b-instruct",
            "loaded_instances": [{"id": "qwen/qwen2.5-vl-3b-instruct", "config": {}}],
        }
    ]
    entry = lsm.find_model_entry(models, "qwen2.5-vl-3b-instruct")
    assert entry is not None
    assert entry["key"] == "qwen/qwen2.5-vl-3b-instruct"


def test_reload_cooldown_blocks_rapid_reloads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lsm, "_last_vision_reload_monotonic", time.monotonic())
    monkeypatch.setenv("WIFI_CAM_VISION_RELOAD_COOLDOWN_SEC", "300")
    assert lsm.reload_cooldown_allows() is False


def test_reload_cooldown_allows_after_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lsm, "_last_vision_reload_monotonic", time.monotonic() - 400)
    monkeypatch.setenv("WIFI_CAM_VISION_RELOAD_COOLDOWN_SEC", "300")
    assert lsm.reload_cooldown_allows() is True
