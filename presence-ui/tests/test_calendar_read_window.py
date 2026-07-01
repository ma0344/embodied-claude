"""Tests for GAPI-2b calendar read window resolution (no network / no e4b)."""

from __future__ import annotations

import pytest

from presence_ui.gateway.calendar_read_window import resolve_prefetch_window

ANCHOR = "2026-06-10T21:00:00+09:00"
TZ = "Asia/Tokyo"


@pytest.fixture(autouse=True)
def disable_e4b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_READ_WINDOW_E4B", "0")


def _start_end(window) -> tuple[str, str]:
    return (
        window.start.date().isoformat(),
        (window.end.date() - __import__("datetime").timedelta(days=1)).isoformat(),
    )


@pytest.mark.parametrize(
    ("utterance", "start", "end", "resolution"),
    [
        ("明後日の予定を教えて", "2026-06-12", "2026-06-12", "deterministic"),
        ("昨日の予定はどうなっていた？", "2026-06-09", "2026-06-09", "deterministic"),
        ("来週の予定は？", "2026-06-14", "2026-06-20", "deterministic"),
        ("来月の予定は？", "2026-07-01", "2026-07-31", "deterministic"),
        ("今後一か月の予定は？", "2026-07-01", "2026-07-31", "deterministic"),
        ("今日から一か月の間の予定は？", "2026-06-10", "2026-07-09", "deterministic"),
        ("来年の予定は？", "2027-01-01", "2027-12-31", "deterministic"),
        ("明日から一週間の予定は", "2026-06-11", "2026-06-17", "deterministic"),
        ("来週の火曜は予定ある？", "2026-06-16", "2026-06-16", "deterministic"),
        ("今日の予定は？", "2026-06-10", "2026-06-10", "deterministic"),
    ],
)
def test_resolve_prefetch_window_deterministic(
    utterance: str,
    start: str,
    end: str,
    resolution: str,
) -> None:
    window = resolve_prefetch_window(
        utterance,
        anchor_iso=ANCHOR,
        tz_name=TZ,
    )
    assert window.resolution == resolution
    assert _start_end(window) == (start, end)


def test_resolve_prefetch_window_ambiguous() -> None:
    window = resolve_prefetch_window(
        "来週中に終わらせたい予定は？",
        anchor_iso=ANCHOR,
        tz_name=TZ,
    )
    assert window.resolution == "ambiguous"
    assert "来週中" in window.ambiguous_phrases


def test_resolve_prefetch_window_fallback_without_temporal_cue() -> None:
    window = resolve_prefetch_window(
        "カレンダーの予定を全部見せて",
        anchor_iso=ANCHOR,
        tz_name=TZ,
        fallback_day_range=["today", "tomorrow"],
    )
    assert window.resolution == "fallback"
    assert window.range_label == "today,tomorrow"


def test_parse_calendar_read_window_response() -> None:
    from presence_ui.gateway.calendar_read_stage import parse_calendar_read_window_response

    parsed = parse_calendar_read_window_response(
        '{"start":"2026-06-17T00:00:00+09:00",'
        '"end":"2026-06-23T23:59:59+09:00",'
        '"search_query":"ピアサポ",'
        '"reason":"来週"}',
        tz_name=TZ,
    )
    assert parsed is not None
    assert parsed.start.date().isoformat() == "2026-06-17"
    assert parsed.end.hour == 23
    assert parsed.search_query == "ピアサポ"


def test_parse_calendar_read_search_response() -> None:
    from presence_ui.gateway.calendar_read_stage import parse_calendar_read_search_response

    parsed = parse_calendar_read_search_response(
        '{"search_query":"ピアサポ","reason":"鍵括弧"}'
    )
    assert parsed is not None
    assert parsed.search_query == "ピアサポ"
    assert parse_calendar_read_search_response('{"search_query":null,"reason":"なし"}') is not None


def test_e4b_search_fallback_when_regex_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    from presence_ui.gateway.calendar_read_stage import CalendarReadSearchExtract

    monkeypatch.setenv("PRESENCE_GAPI_READ_WINDOW_E4B", "1")
    monkeypatch.setenv("PRESENCE_GAPI_READ_SEARCH_E4B", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_stage.run_calendar_read_search_extract",
        lambda **kwargs: CalendarReadSearchExtract(
            search_query="ピアサポ",
            reason="mock",
        ),
    )
    window = resolve_prefetch_window(
        "今年の今日以降でピアサポっぽいやつ全部",
        anchor_iso="2026-07-01T12:00:00+09:00",
        tz_name=TZ,
    )
    assert window.search_query == "ピアサポ"
    assert window.start.date().isoformat() == "2026-07-01"


def test_e4b_path_when_deterministic_misses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_READ_WINDOW_E4B", "1")
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_read_window.run_calendar_read_window_extract",
        lambda **kwargs: type(
            "E",
            (),
            {
                "start": __import__("datetime").datetime.fromisoformat(
                    "2026-08-01T00:00:00+09:00"
                ),
                "end": __import__("datetime").datetime.fromisoformat(
                    "2026-08-31T23:59:59+09:00"
                ),
                "reason": "mock",
                "search_query": None,
            },
        )(),
    )
    window = resolve_prefetch_window(
        "八月の予定は？",
        anchor_iso=ANCHOR,
        tz_name=TZ,
    )
    assert window.resolution == "e4b"
    assert window.start.month == 8
