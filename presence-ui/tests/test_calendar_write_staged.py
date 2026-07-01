"""Tests for GAPI-2w calendar write Stage1 gate."""

from __future__ import annotations

import pytest

from presence_ui.gateway.calendar_write_flow import should_run_calendar_write


def test_should_run_calendar_write_requires_stage1_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_CONFIRM", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE_STAGED", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_write_flow.classify_calendar_write_stage1",
        lambda **kwargs: "calendar_write",
    )
    assert should_run_calendar_write("来週火曜、カレンダー入れといて") is True


def test_should_run_calendar_write_skips_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_CONFIRM", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE_STAGED", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_write_flow.classify_calendar_write_stage1",
        lambda **kwargs: "calendar_read",
    )
    assert should_run_calendar_write("来週の予定は？") is False
