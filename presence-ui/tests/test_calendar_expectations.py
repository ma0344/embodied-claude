"""SPONT-B2 — silent calendar expectations (know ≠ speak)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from interaction_orchestrator_mcp.schemas import (
    InteractionContext,
    ResponseContract,
)

from presence_ui.gapi.calendar_client import CalendarEvent
from presence_ui.gateway import calendar_expectations as ce


def _ctx(**kwargs) -> InteractionContext:
    base = dict(
        ts="2026-07-17T01:00:00+00:00",
        local_time="2026-07-17T10:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-07-17T01:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": None,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[desires]\nok",
    )
    base.update(kwargs)
    return InteractionContext(**base)


def test_format_expectation_block_marks_background_only() -> None:
    block = ce.format_expectation_block(
        [
            ce.ExpectationCard(
                event_id="e1",
                summary="入浴介助",
                start="2026-07-17T10:30:00+09:00",
                end="2026-07-17T11:00:00+09:00",
                calendar_label="work",
            )
        ],
        timezone="Asia/Tokyo",
        hours=6,
    )
    assert "[calendar_expectations — background only]" in block
    assert "know≠speak" in block
    assert "入浴介助" in block
    assert "calendar_prefetch" not in block


def test_cards_from_events_respects_limit() -> None:
    events = [
        CalendarEvent(
            calendar_id="c",
            calendar_label="work",
            event_id=f"e{i}",
            summary=f"evt{i}",
            start="2026-07-17T10:00:00+09:00",
            end="2026-07-17T11:00:00+09:00",
        )
        for i in range(10)
    ]
    cards = ce.cards_from_events(events, limit=3)
    assert len(cards) == 3
    assert cards[0].summary == "evt0"


def test_inject_adds_avoid_when_not_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "expectations.json"
    monkeypatch.setenv("PRESENCE_CALENDAR_EXPECTATIONS_PATH", str(path))
    ce.save_expectations(
        cards=[
            ce.ExpectationCard(
                event_id="e1",
                summary="会議",
                start="2026-07-17T11:00:00+09:00",
                end="2026-07-17T12:00:00+09:00",
            )
        ],
        timezone="Asia/Tokyo",
        hours=6,
        status="ok",
        path=path,
    )
    out = ce.inject_calendar_expectations(_ctx(), user_text="おはよう", channel="autonomous")
    assert "[calendar_expectations — background only]" in out.compact_prompt_block
    assert any("calendar_expectations" in a for a in out.response_contract.avoid)


def test_inject_omits_block_and_avoid_when_events_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "expectations.json"
    monkeypatch.setenv("PRESENCE_CALENDAR_EXPECTATIONS_PATH", str(path))
    ce.save_expectations(
        cards=[],
        timezone="Asia/Tokyo",
        hours=6,
        status="ok",
        path=path,
    )
    base = _ctx()
    out = ce.inject_calendar_expectations(base, user_text="おはよう", channel="autonomous")
    assert "[calendar_expectations" not in out.compact_prompt_block
    assert out.compact_prompt_block == base.compact_prompt_block
    assert out.response_contract.avoid == base.response_contract.avoid


def test_inject_skips_avoid_when_schedule_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "expectations.json"
    monkeypatch.setenv("PRESENCE_CALENDAR_EXPECTATIONS_PATH", str(path))
    ce.save_expectations(
        cards=[
            ce.ExpectationCard(
                event_id="e1",
                summary="会議",
                start="2026-07-17T11:00:00+09:00",
                end="2026-07-17T12:00:00+09:00",
            )
        ],
        timezone="Asia/Tokyo",
        hours=6,
        status="ok",
        path=path,
    )
    out = ce.inject_calendar_expectations(
        _ctx(), user_text="今日の予定ある？", channel="chat"
    )
    assert "[calendar_expectations" in out.compact_prompt_block
    assert not any("calendar_expectations" in a for a in out.response_contract.avoid)


def test_refresh_respects_min_interval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "expectations.json"
    monkeypatch.setenv("PRESENCE_CALENDAR_EXPECTATIONS_PATH", str(path))
    monkeypatch.setenv("PRESENCE_CALENDAR_LOOKAHEAD", "1")
    monkeypatch.setenv("PRESENCE_CALENDAR_LOOKAHEAD_MIN_INTERVAL_MINUTES", "30")
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")

    now = datetime(2026, 7, 17, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    path.write_text(
        json.dumps(
            {
                "updated_at": now.isoformat(),
                "timezone": "Asia/Tokyo",
                "lookahead_hours": 6,
                "status": "ok",
                "events": [],
            }
        ),
        encoding="utf-8",
    )

    # Force skip path without calling Google
    assert ce._should_skip_refresh(path, now=now + timedelta(minutes=5))
    assert not ce._should_skip_refresh(path, now=now + timedelta(minutes=31))


def test_refresh_disabled_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_CALENDAR_LOOKAHEAD", "0")
    assert ce.refresh_calendar_expectations() is None
