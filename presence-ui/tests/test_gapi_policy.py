"""Tests for GAPI policy and calendar window (no network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from presence_ui.gapi.calendar_client import prefetch_window_bounds
from presence_ui.gapi.policy import load_google_policy


def test_load_google_policy_from_example(tmp_path: Path) -> None:
    example = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "configs"
        / "gapi-policy.example.toml"
    )
    policy = load_google_policy(example)
    assert policy.enabled is True
    assert policy.prefetch_day_range == ["today", "tomorrow"]
    readable = policy.readable_calendars()
    assert len(readable) >= 1
    assert readable[0].id == "primary"


def test_prefetch_window_today_and_tomorrow() -> None:
    time_min, time_max = prefetch_window_bounds(
        day_range=["today", "tomorrow"],
        timezone="Asia/Tokyo",
        as_of=date(2026, 6, 27),
    )
    assert time_min.isoformat().startswith("2026-06-27T00:00:00")
    assert time_max.isoformat().startswith("2026-06-29T00:00:00")
