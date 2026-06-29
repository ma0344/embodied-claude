"""Tests for GAPI calendar write intent, parse, and router wiring (no network)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from test_social_chat import _minimal_ctx, _minimal_plan

from presence_ui.gapi.calendar_client import CalendarEvent, match_event_by_local_start
from presence_ui.gapi.policy import CalendarPolicy, GooglePolicy
from relationship_mcp.schemas import DismissOutcome

from presence_ui.gateway import social_chat
from presence_ui.gateway.calendar_write import (
    _format_write_block,
    detect_calendar_write_intent,
    detect_calendar_write_kind,
    execute_calendar_write_sync,
    looks_like_calendar_create,
    looks_like_calendar_update,
)
from presence_ui.gateway.calendar_write_parse import parse_create, parse_update
from presence_ui.gateway.prompt_injection import build_gateway_stable_append


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "じゃぁ、カレンダーで明日の10時～12時で「久恵さん信大」って予定入れておいて",
            True,
        ),
        ("明日の予定は？", False),
        ("明日14時の予定、16時にずらして", True),
        ("おはよう", False),
    ],
)
def test_looks_like_calendar_create_or_update(
    text: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    assert (
        looks_like_calendar_create(text) or looks_like_calendar_update(text)
    ) is expected


def test_parse_create_user_example() -> None:
    parsed = parse_create(
        "じゃぁ、カレンダーで明日の10時～12時で「久恵さん信大」って予定入れておいて"
    )
    assert parsed is not None
    assert parsed.day_offset == 1
    assert parsed.start_hour == 10 and parsed.end_hour == 12
    assert parsed.title == "久恵さん信大"


def test_parse_update_shift() -> None:
    parsed = parse_update("明日14時の予定、16時にずらして")
    assert parsed is not None
    assert parsed.day_offset == 1
    assert parsed.old_hour == 14 and parsed.new_hour == 16


def test_match_event_by_local_start() -> None:
    tz = ZoneInfo("Asia/Tokyo")
    day = date(2026, 6, 26)
    events = [
        CalendarEvent(
            calendar_id="primary",
            calendar_label="main",
            event_id="e1",
            summary="会議",
            start="2026-06-26T14:00:00+09:00",
            end="2026-06-26T15:00:00+09:00",
        )
    ]
    matched = match_event_by_local_start(
        events, target_day=day, hour=14, minute=0, tz=tz
    )
    assert matched is not None
    assert matched.event_id == "e1"


def test_detect_calendar_write_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "カレンダーで明日10時～11時で「テスト」って予定入れておいて"
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "0")
    assert detect_calendar_write_intent(text) is False
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "0")
    assert detect_calendar_write_intent(text) is False
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    assert detect_calendar_write_intent(text) is True
    assert detect_calendar_write_kind(text).value == "create"


def test_execute_calendar_write_create_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    policy = GooglePolicy(
        enabled=True,
        timezone="Asia/Tokyo",
        calendars=[
            CalendarPolicy(id="primary", allow_create=True, allow_update=True),
        ],
    )
    created = MagicMock()
    created.calendar_id = "primary"
    created.event_id = "evt-1"
    created.summary = "久恵さん信大"
    created.start = "2026-06-26T10:00:00+09:00"
    created.end = "2026-06-26T12:00:00+09:00"
    created.html_link = "https://calendar.google.com/event?eid=1"

    with (
        patch("presence_ui.gateway.calendar_write.load_google_policy", return_value=policy),
        patch("presence_ui.gateway.calendar_write.get_calendar_service", return_value=MagicMock()),
        patch("presence_ui.gateway.calendar_write.create_event", return_value=created),
    ):
        block, status = execute_calendar_write_sync(
            "カレンダーで明日の10時～12時で「久恵さん信大」って予定入れておいて"
        )
    assert status == "ok"
    assert block is not None
    assert "[calendar_write_result]" in block
    assert "久恵さん信大" in block
    assert "status=ok" in block


def test_format_write_block_error() -> None:
    block = _format_write_block(
        action="create",
        status="parse_failed",
        policy=GooglePolicy(enabled=True, timezone="Asia/Tokyo"),
        detail="missing title",
    )
    assert "parse_failed" in block
    assert "Do NOT claim" in block


@pytest.fixture
def mock_stores(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.social_state.ingest_social_event.return_value = {"event_id": "evt-1"}
    monkeypatch.setattr(social_chat, "get_stores", lambda: stores)
    monkeypatch.setattr("presence_ui.deps.get_stores", lambda: stores)
    monkeypatch.setattr("presence_ui.gateway.room_ingest.get_stores", lambda: stores)
    monkeypatch.setattr(
        social_chat,
        "_ingest_human_sync",
        lambda **kwargs: DismissOutcome(),
    )
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


def test_intercept_includes_calendar_write(
    mock_stores: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "1")
    write_block = _format_write_block(
        action="create",
        status="ok",
        policy=GooglePolicy(enabled=True, timezone="Asia/Tokyo"),
        event=MagicMock(
            calendar_id="primary",
            event_id="e1",
            summary="久恵さん信大",
            start="2026-06-26T10:00:00+09:00",
            end="2026-06-26T12:00:00+09:00",
            html_link="",
        ),
    )
    utterance = "カレンダーで明日の10時～12時で「久恵さん信大」って予定入れておいて"
    result = social_chat.intercept_chat_request(
        payload={"message": utterance, "sessionId": "sess-write"},
        person_id="ma",
        calendar_write=write_block,
    )
    assert result.forward is True
    msg = result.payload["message"]
    assert "[calendar_write_result]" in msg
    assert utterance in msg
    assert msg.rfind("[calendar_write_result]") > msg.rfind("久恵さん信大")
    assert result.payload["appendSystemPrompt"] == build_gateway_stable_append()
