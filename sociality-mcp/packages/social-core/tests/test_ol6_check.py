"""Tests for OL6 post-deadline loop check helpers."""

from __future__ import annotations

from social_core.ol6_check import (
    extract_until_phrase,
    is_loop_past_deadline,
    is_ol6_completion_confirm,
    is_ol6_completion_denial,
    loop_due_for_check,
    parse_until_clock,
)


def test_parse_until_clock_japanese() -> None:
    assert parse_until_clock("10時ごろまで") == (10, 0)
    assert parse_until_clock("15時位まで") == (15, 0)
    assert parse_until_clock("15時くらいまで") == (15, 0)


def test_extract_until_phrase_from_detail_and_topic() -> None:
    detail = {"until_phrase": "10時まで"}
    assert extract_until_phrase(detail=detail, topic="掃除") == "10時まで"
    assert extract_until_phrase(detail={}, topic="2026年6月29日 掃除 10時ごろまで") == "10時ごろまで"


def test_is_loop_past_deadline() -> None:
    detail = {"resolved_date": "2026-06-29", "until_phrase": "10時まで"}
    assert is_loop_past_deadline(
        detail=detail,
        topic="掃除",
        as_of_ts="2026-06-29T10:30:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert not is_loop_past_deadline(
        detail=detail,
        topic="掃除",
        as_of_ts="2026-06-29T09:30:00+09:00",
        tz_name="Asia/Tokyo",
    )


def test_loop_due_for_check_skips_after_asked() -> None:
    detail = {
        "resolved_date": "2026-06-29",
        "until_phrase": "10時まで",
        "check_asked_at": "2026-06-29T10:05:00+09:00",
    }
    assert not loop_due_for_check(
        detail=detail,
        topic="掃除",
        as_of_ts="2026-06-29T11:00:00+09:00",
        tz_name="Asia/Tokyo",
    )


def test_ol6_completion_confirm_and_deny() -> None:
    assert is_ol6_completion_confirm("終わったよ")
    assert is_ol6_completion_confirm("できた")
    assert not is_ol6_completion_confirm("今日の予定は？")
    assert is_ol6_completion_denial("まだ")
    assert is_ol6_completion_denial("これからやる")
