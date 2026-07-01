"""Tests for GAPI-2s calendar keyword search within a read window."""

from __future__ import annotations

import pytest

from presence_ui.gapi.calendar_client import CalendarEvent
from presence_ui.gateway.calendar_read_search import (
    extract_quoted_search_fallback,
    filter_events_by_search_query,
    resolve_calendar_search_query,
    sanitize_calendar_search_query,
)
from presence_ui.gateway.calendar_read_window import resolve_prefetch_window

ANCHOR = "2026-07-01T12:00:00+09:00"
TZ = "Asia/Tokyo"


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("今年の今日以降で「ピアサポ」が含まれる予定を全部教えて", "ピアサポ"),
        ("『研修』の予定", "研修"),
        ("今年の温泉の予定全部教えて", None),
        ("今年のピアサポの予定を全部教えて", None),
        ("今年の今日以降のピアサポの予定を全部教えて", None),
        ("「『ピアサポ』」みたいな入れ子", None),
        ("「ピアサポ", None),
        ("今日の予定は？", None),
    ],
)
def test_extract_quoted_search_fallback(utterance: str, expected: str | None) -> None:
    assert extract_quoted_search_fallback(utterance) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("来月 東口", "東口"),
        ("来月の東口", "東口"),
        ("東口", "東口"),
        ("来月", None),
        (None, None),
    ],
)
def test_sanitize_calendar_search_query(raw: str | None, expected: str | None) -> None:
    assert sanitize_calendar_search_query(raw) == expected


def test_resolve_search_query_e4b_before_quoted_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from presence_ui.gateway.calendar_read_stage import CalendarReadSearchExtract

    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_stage.run_calendar_read_search_extract",
        lambda **kwargs: CalendarReadSearchExtract(
            search_query="ピアサポ",
            reason="e4b",
        ),
    )
    utterance = "今年の今日以降のピアサポの予定を全部教えて"
    assert resolve_calendar_search_query(utterance) == "ピアサポ"


def test_resolve_search_query_quoted_when_e4b_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_stage.run_calendar_read_search_extract",
        lambda **kwargs: None,
    )
    utterance = "今年の今日以降で「ピアサポ」が含まれる予定を全部教えて"
    assert resolve_calendar_search_query(utterance) == "ピアサポ"


def test_filter_events_by_search_query() -> None:
    events = [
        CalendarEvent(
            calendar_id="primary",
            calendar_label="main",
            event_id="1",
            summary="ピアサポ専門研修",
            start="2026-08-01T10:00:00+09:00",
            end="2026-08-01T12:00:00+09:00",
        ),
        CalendarEvent(
            calendar_id="primary",
            calendar_label="main",
            event_id="2",
            summary="理事会",
            start="2026-08-02T10:00:00+09:00",
            end="2026-08-02T12:00:00+09:00",
        ),
    ]
    filtered = filter_events_by_search_query(events, "ピアサポ")
    assert len(filtered) == 1
    assert "ピアサポ" in filtered[0].summary


@pytest.fixture(autouse=True)
def disable_e4b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_READ_WINDOW_E4B", "0")
    monkeypatch.setenv("PRESENCE_GAPI_READ_SEARCH_E4B", "0")


def test_resolve_prefetch_window_year_from_today_with_quoted_fallback() -> None:
    window = resolve_prefetch_window(
        "今年の今日以降で「ピアサポ」が含まれる予定を全部教えて",
        anchor_iso=ANCHOR,
        tz_name=TZ,
    )
    assert window.resolution == "deterministic"
    assert window.search_query == "ピアサポ"
    assert window.start.date().isoformat() == "2026-07-01"


def test_resolve_prefetch_window_no_search_without_e4b_or_quotes() -> None:
    window = resolve_prefetch_window(
        "今年の温泉の予定全部教えて",
        anchor_iso=ANCHOR,
        tz_name=TZ,
    )
    assert window.resolution == "deterministic"
    assert window.search_query is None
