"""Tests for GAPI calendar prefetch intent and router wiring (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from test_social_chat import _minimal_ctx, _minimal_plan

from presence_ui.gapi.calendar_client import CalendarEvent
from presence_ui.gapi.policy import GooglePolicy
from presence_ui.gateway import social_chat
from presence_ui.gateway.calendar_prefetch import (
    detect_calendar_intent,
    format_calendar_prefetch_with_directive,
    looks_like_calendar_query,
    prefetch_calendar_for_message,
)
from presence_ui.gateway.prompt_injection import build_gateway_stable_append


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("おはよう", False),
        ("今日の予定は？", True),
        ("明日のスケジュール教えて", True),
        ("カレンダー入れといて", True),
        ("松本市の様式を調べて", False),
    ],
)
def test_looks_like_calendar_query(text: str, expected: bool) -> None:
    assert looks_like_calendar_query(text) is expected


def test_detect_calendar_intent_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "0")
    assert detect_calendar_intent("今日の予定は？") is False
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_PREFETCH", "1")
    assert detect_calendar_intent("今日の予定は？") is True


def test_format_calendar_prefetch_with_directive() -> None:
    policy = GooglePolicy(
        enabled=True,
        prefetch_day_range=["today", "tomorrow"],
        timezone="Asia/Tokyo",
        calendars=[],
    )
    events = [
        CalendarEvent(
            calendar_id="primary",
            calendar_label="primary",
            event_id="e1",
            summary="会議",
            start="2026-06-29T14:00+09:00",
            end="2026-06-29T15:00+09:00",
        )
    ]
    block = format_calendar_prefetch_with_directive(policy=policy, events=events)
    assert "[calendar_prefetch]" in block
    assert "会議" in block
    assert "authoritative" in block


@pytest.fixture
def mock_stores(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.social_state.ingest_social_event.return_value = {"event_id": "evt-1"}
    monkeypatch.setattr(social_chat, "get_stores", lambda: stores)
    monkeypatch.setattr(
        social_chat,
        "compose_interaction_context",
        lambda *args, **kwargs: _minimal_ctx(),
    )
    monkeypatch.setattr(
        social_chat,
        "plan_response",
        lambda *args, **kwargs: _minimal_plan(),
    )
    return stores


@pytest.mark.asyncio
async def test_prefetch_calendar_skips_casual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    note, events = await prefetch_calendar_for_message("おはよう")
    assert note is None
    assert events == []


def test_intercept_includes_calendar_prefetch(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
    policy = GooglePolicy(enabled=True, timezone="Asia/Tokyo")
    prefetch = format_calendar_prefetch_with_directive(policy=policy, events=[], status="empty")
    result = social_chat.intercept_chat_request(
        payload={"message": "今日の予定は？", "sessionId": "sess-cal"},
        person_id="ma",
        calendar_prefetch=prefetch,
    )
    assert result.forward is True
    msg = result.payload["message"]
    assert "[calendar_prefetch]" in msg
    assert "今日の予定は？" in msg
    assert msg.rfind("[calendar_prefetch]") > msg.rfind("今日の予定は？")
    assert result.payload["appendSystemPrompt"] == build_gateway_stable_append()
