"""Tests for GAPI-2b/2s calendar read e4b prompts."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from presence_ui.gateway.calendar_read_stage_prompts import (
    build_calendar_read_search_system,
    build_calendar_read_window_system,
    build_calendar_read_window_task,
)


def test_window_system_prompt_clarifies_no_calendar_data_needed() -> None:
    as_of = datetime(2026, 6, 10, 21, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    system = build_calendar_read_window_system(as_of=as_of)
    assert "カレンダーの中身" in system
    assert "search_query" in system
    assert "拒否" in system


def test_window_task_includes_utterance_and_scope() -> None:
    task = build_calendar_read_window_task(
        utterance="今年の今日以降で「ピアサポ」が含まれる予定を全部教えて"
    )
    assert "ピアサポ" in task
    assert "時制とキーワード" in task


def test_search_system_prompt_exists() -> None:
    assert "search_query" in build_calendar_read_search_system()
