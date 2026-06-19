"""Tests for temporal date anchoring (OL1b / OL1c)."""

from __future__ import annotations

from datetime import date

from social_core.date_resolution import (
    anchor_relative_dates_in_text,
    anchor_temporal_in_text,
    calendar_anchor_line,
    format_jp_date,
    is_resolved_date_stale,
    resolve_relative_date,
    resolve_this_weekend,
    stale_from_detail_json,
    sunday_start_week_bounds,
    weekday_in_week,
)

ANCHOR_FRI = "2026-06-19T10:00:00+09:00"


def test_anchor_relative_dates_replaces_tomorrow() -> None:
    anchored, resolved = anchor_relative_dates_in_text(
        "明日は昼ごろからホームヘルパーのお仕事",
        updated_at="2026-06-18T22:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 19)
    assert anchored.startswith("2026年6月19日")
    assert "明日" not in anchored


def test_anchor_relative_dates_preserves_plain_text() -> None:
    text = "松本市の天気を調べた"
    anchored, resolved = anchor_relative_dates_in_text(
        text,
        updated_at="2026-06-19T10:00:00+09:00",
    )
    assert anchored == text
    assert resolved is None


def test_calendar_anchor_line() -> None:
    line = calendar_anchor_line(
        ts="2026-06-19T10:54:11+09:00",
        tz_name="Asia/Tokyo",
    )
    assert line == f"Calendar today (Asia/Tokyo): {format_jp_date(date(2026, 6, 19))}."


def test_stale_from_detail_json_after_event_day() -> None:
    stale = stale_from_detail_json(
        '{"resolved_date":"2026-06-19"}',
        as_of=date(2026, 6, 20),
    )
    assert stale == date(2026, 6, 19)


def test_is_resolved_date_stale_include_today() -> None:
    assert is_resolved_date_stale(date(2026, 6, 19), as_of=date(2026, 6, 19)) is False
    assert (
        is_resolved_date_stale(
            date(2026, 6, 19), as_of=date(2026, 6, 19), include_today=True
        )
        is True
    )


def test_sunday_start_week_bounds_from_friday() -> None:
    bounds = sunday_start_week_bounds(date(2026, 6, 19))
    assert bounds.this_sun == date(2026, 6, 14)
    assert bounds.this_sat == date(2026, 6, 20)
    assert bounds.next_sun == date(2026, 6, 21)
    assert bounds.next_sat == date(2026, 6, 27)
    assert bounds.week2_sun == date(2026, 6, 28)


def test_weekday_in_week_next_tuesday() -> None:
    resolved = weekday_in_week(anchor_day=date(2026, 6, 19), week_offset=1, weekday=1)
    assert resolved == date(2026, 6, 23)


def test_resolve_relative_date_next_week_tuesday() -> None:
    resolved = resolve_relative_date(
        topic="来週の火曜に歯医者",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 23)


def test_anchor_next_week_tuesday_in_text() -> None:
    anchored, resolved = anchor_relative_dates_in_text(
        "来週の火曜に歯医者の予約があるんや",
        updated_at=ANCHOR_FRI,
    )
    assert resolved == date(2026, 6, 23)
    assert "2026年6月23日" in anchored
    assert "来週" not in anchored


def test_resolve_one_week_later() -> None:
    resolved = resolve_relative_date(
        topic="一週間後にもう一度聞いてな",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 26)


def test_resolve_next_month_head() -> None:
    resolved = resolve_relative_date(
        topic="来月の頭に旅行",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 7, 1)


def test_resolve_week_after_next_monday() -> None:
    resolved = resolve_relative_date(
        topic="再来週の月曜から新しいルーティン",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 29)


def test_resolve_this_weekend_from_friday() -> None:
    assert resolve_this_weekend(date(2026, 6, 19)) == date(2026, 6, 20)
    resolved = resolve_relative_date(
        topic="今週末はのんびりしたいな",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 20)


def test_resolve_explicit_month_day_same_year() -> None:
    resolved = resolve_relative_date(
        topic="6月20日の午後にホームヘルパー",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 20)


def test_upcoming_weekday_next_sunday_from_friday() -> None:
    resolved = resolve_relative_date(
        topic="次の日曜日に出かける",
        updated_at=ANCHOR_FRI,
        tz_name="Asia/Tokyo",
    )
    assert resolved == date(2026, 6, 21)


def test_upcoming_weekday_kondo_same_as_tsugi() -> None:
    tsugi = anchor_temporal_in_text(
        "次の日曜日に出かける",
        updated_at=ANCHOR_FRI,
    )
    kondo = anchor_temporal_in_text(
        "今度の日曜日に出かける",
        updated_at=ANCHOR_FRI,
    )
    assert tsugi.text == kondo.text
    assert "2026年6月21日" in tsugi.text


def test_ambiguous_span_needs_confirmation() -> None:
    result = anchor_temporal_in_text(
        "来週中にPRのレビュー終わらせたい",
        updated_at=ANCHOR_FRI,
    )
    assert result.needs_date_confirmation is True
    assert result.resolved_date is None
    assert "来週中" in result.ambiguous_phrases
    assert result.text == "来週中にPRのレビュー終わらせたい"


def test_same_weekday_on_sunday_needs_confirmation() -> None:
    result = anchor_temporal_in_text(
        "今度の日曜日にのんびりしたい",
        updated_at="2026-06-21T10:00:00+09:00",
    )
    assert result.needs_date_confirmation is True
    assert "日曜" in result.ambiguous_phrases[0]


