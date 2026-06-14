"""Tests for named camera preset locations."""

from presence_ui.services.camera_locations import preset_id_for_location


def test_preset_id_for_desk_and_dining(monkeypatch) -> None:
    monkeypatch.setenv("TAPO_MADESK_PRESET", "2")
    monkeypatch.setenv("TAPO_DINING_PRESET", "3")
    assert preset_id_for_location("desk") == "2"
    assert preset_id_for_location("dining") == "3"


def test_preset_id_prefers_presence_env(monkeypatch) -> None:
    monkeypatch.setenv("TAPO_WINDOW_PRESET", "9")
    monkeypatch.setenv("PRESENCE_CAMERA_WINDOW_PRESET", "1")
    assert preset_id_for_location("window") == "1"
