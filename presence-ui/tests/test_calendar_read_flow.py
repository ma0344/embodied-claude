"""Tests for GAPI-2r-S2 calendar read pipeline and Stage1 gate."""

from __future__ import annotations

import pytest

from presence_ui.gateway.calendar_prefetch import (
    calendar_read_cue,
    detect_calendar_intent,
    prefetch_calendar_for_message,
)
from presence_ui.gateway.calendar_read_flow import (
    calendar_read_staged_enabled,
    should_run_calendar_read,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("おはよう", False),
        ("今日の予定は？", True),
        ("明日のスケジュール教えて", True),
        ("カレンダー入れといて", True),
    ],
)
def test_calendar_read_cue(text: str, expected: bool) -> None:
    assert calendar_read_cue(text) is expected


def test_should_run_calendar_read_staged_write_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_READ_STAGED", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_flow.classify_calendar_read_stage1",
        lambda **kwargs: "calendar_write",
    )
    assert should_run_calendar_read("来週火曜、カレンダー入れといて") is False


def test_should_run_calendar_read_staged_confirms_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_READ_STAGED", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_flow.classify_calendar_read_stage1",
        lambda **kwargs: "calendar_read",
    )
    assert should_run_calendar_read("来週の予定は？") is True


def test_should_run_calendar_read_rejects_other_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_READ_STAGED", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_flow.classify_calendar_read_stage1",
        lambda **kwargs: "other",
    )
    assert should_run_calendar_read("今日の予定は？") is False


def test_detect_calendar_intent_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "0")
    assert detect_calendar_intent("今日の予定は？") is False
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_PREFETCH", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_flow.classify_calendar_read_stage1",
        lambda **kwargs: "calendar_read",
    )
    assert detect_calendar_intent("今日の予定は？") is True


@pytest.mark.asyncio
async def test_prefetch_skips_when_stage1_says_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_flow.classify_calendar_read_stage1",
        lambda **kwargs: "other",
    )
    note, events = await prefetch_calendar_for_message("今日の予定は？")
    assert note is None
    assert events == []


def test_calendar_read_staged_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.delenv("PRESENCE_GAPI_CALENDAR_READ_STAGED", raising=False)
    assert calendar_read_staged_enabled() is True
