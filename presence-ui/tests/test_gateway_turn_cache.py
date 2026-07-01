"""Tests for per-turn gateway e4b deduplication."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from presence_ui.gateway.calendar_read_flow import should_run_calendar_read
from presence_ui.gateway.calendar_read_window import resolve_prefetch_window
from presence_ui.gateway.calendar_write_flow import should_run_calendar_write
from presence_ui.gateway.gateway_turn_cache import gateway_turn_cache_scope
from presence_ui.gateway.temp_c_staged import run_stage1_classify


def test_gateway_turn_cache_dedupes_stage1_and_calendar_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_READ_STAGED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE_STAGED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_CONFIRM", "1")
    stage1_calls = 0
    window_calls = 0

    def fake_stage1_turn(**kwargs: object) -> str:
        nonlocal stage1_calls
        stage1_calls += 1
        return (
            '{"utterance":"今後の東口の予定を全部教えて",'
            '"utterance_kind":"calendar_read","close_shape":null,'
            '"action_terms":[],"completion_verbs":[]}'
        )

    def fake_window_extract(**kwargs: object) -> object:
        nonlocal window_calls
        from presence_ui.gateway.calendar_read_stage import CalendarReadWindowExtract

        window_calls += 1
        tz = ZoneInfo("Asia/Tokyo")
        return CalendarReadWindowExtract(
            start=datetime(2026, 7, 1, tzinfo=tz),
            end=datetime(2026, 12, 31, 23, 59, 59, tzinfo=tz),
            reason="test",
            search_query="東口",
        )

    monkeypatch.setattr(
        "presence_ui.gateway.temp_c_staged.run_classifier_turn",
        fake_stage1_turn,
    )
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_window.run_calendar_read_window_extract",
        fake_window_extract,
    )

    utterance = "今後の東口の予定を全部教えて"
    anchor = "2026-07-01T22:22:54+09:00"
    with gateway_turn_cache_scope():
        assert should_run_calendar_read(utterance) is True
        assert should_run_calendar_write(utterance) is False
        w1 = resolve_prefetch_window(
            utterance,
            anchor_iso=anchor,
            tz_name="Asia/Tokyo",
            fallback_day_range=["today", "tomorrow"],
        )
        w2 = resolve_prefetch_window(
            utterance,
            anchor_iso=anchor,
            tz_name="Asia/Tokyo",
            fallback_day_range=["today", "tomorrow"],
        )
        assert run_stage1_classify(utterance=utterance) is not None
    assert stage1_calls == 1
    assert window_calls == 1
    assert w1.search_query == "東口"
    assert w2.search_query == "東口"


def test_gateway_turn_cache_dedupes_calendar_search_across_anchors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_READ_WINDOW_E4B", "1")
    monkeypatch.setenv("PRESENCE_GAPI_READ_SEARCH_E4B", "1")
    search_calls = 0

    def fake_classifier_turn(**kwargs: object) -> str:
        nonlocal search_calls
        search_calls += 1
        return '{"search_query":"来月 東口","reason":"test"}'

    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_stage.run_classifier_turn",
        fake_classifier_turn,
    )

    utterance = "来月の東口の予定は？"
    with gateway_turn_cache_scope():
        w1 = resolve_prefetch_window(
            utterance,
            anchor_iso="2026-07-01T23:13:45+09:00",
            tz_name="Asia/Tokyo",
            fallback_day_range=["today", "tomorrow"],
        )
        w2 = resolve_prefetch_window(
            utterance,
            anchor_iso="2026-07-01T23:13:46+09:00",
            tz_name="Asia/Tokyo",
            fallback_day_range=["today", "tomorrow"],
        )
    assert search_calls == 1
    assert w1.search_query == "東口"
    assert w2.search_query == "東口"


def test_gateway_turn_cache_off_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    calls = 0

    def fake_turn(**kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return (
            '{"utterance":"来週の予定は？","utterance_kind":"calendar_read",'
            '"close_shape":null,"action_terms":[],"completion_verbs":[]}'
        )

    monkeypatch.setattr(
        "presence_ui.gateway.temp_c_staged.run_classifier_turn",
        fake_turn,
    )
    run_stage1_classify(utterance="来週の予定は？")
    run_stage1_classify(utterance="来週の予定は？")
    assert calls == 2
