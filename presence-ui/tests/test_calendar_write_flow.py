"""Tests for GAPI-7b calendar confirm flow (no network / no e4b)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from presence_ui.gateway.calendar_pending import (
    CalendarPendingRecord,
    is_calendar_affirmation,
    is_calendar_denial,
    pending_from_resolved,
    save_pending,
    clear_pending,
    load_pending,
    format_calendar_confirm_block,
)
from presence_ui.gateway.calendar_resolve import format_confirm_summary_ja, resolve_start_end_phrases
from presence_ui.gateway.calendar_stage import (
    CalendarStageExtract,
    compute_missing_fields,
    parse_calendar_stage2_response,
)
from presence_ui.gateway.calendar_write_flow import process_calendar_turn_sync


def test_parse_calendar_stage2_create() -> None:
    raw = (
        '{"action":"create","calendar_id":"primary","topic":"久恵さん信大",'
        '"start_phrase":"明日10時","end_phrase":"明日12時","missing_fields":[],'
        '"confidence":0.9}'
    )
    parsed = parse_calendar_stage2_response(raw)
    assert parsed is not None
    assert parsed.action == "create"
    assert parsed.topic == "久恵さん信大"
    assert compute_missing_fields(parsed) == ()


def test_resolve_start_end_phrases() -> None:
    anchor = "2026-06-29T10:00:00+09:00"
    resolved = resolve_start_end_phrases(
        start_phrase="明日10時",
        end_phrase="12時",
        anchor_iso=anchor,
        tz_name="Asia/Tokyo",
    )
    assert resolved is not None
    assert resolved.start.hour == 10
    assert resolved.end.hour == 12


def test_resolve_colon_time_and_explicit_month_day() -> None:
    anchor = "2026-06-29T10:00:00+09:00"
    resolved = resolve_start_end_phrases(
        start_phrase="7月6日10：00",
        end_phrase="16：00",
        anchor_iso=anchor,
        tz_name="Asia/Tokyo",
    )
    assert resolved is not None
    assert resolved.start == datetime(2026, 7, 6, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert resolved.end == datetime(2026, 7, 6, 16, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_affirm_and_deny() -> None:
    assert is_calendar_affirmation("OK")
    assert is_calendar_affirmation("うん")
    assert is_calendar_denial("やめ")
    assert not is_calendar_affirmation("明日の予定は？")


def test_confirm_block_format() -> None:
    tz = ZoneInfo("Asia/Tokyo")
    start = datetime(2026, 6, 30, 10, 0, tzinfo=tz)
    end = datetime(2026, 6, 30, 12, 0, tzinfo=tz)
    summary = format_confirm_summary_ja(
        action="create", topic="久恵さん信大", start=start, end=end
    )
    record = CalendarPendingRecord(
        person_id="ma",
        status="awaiting_confirm",
        action="create",
        calendar_id="primary",
        topic="久恵さん信大",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
        match_label="",
        event_id=None,
        event_calendar_id=None,
        event_summary=None,
        old_start=None,
        old_end=None,
        missing_fields=[],
        source_utterance="test",
        confirm_summary_ja=summary,
        created_at="2026-06-29T10:00:00+09:00",
    )
    block = format_calendar_confirm_block(record)
    assert "[calendar_confirm_pending]" in block
    assert "入れていい" in block or "confirm" in block.lower()


def test_process_calendar_turn_affirm_executes(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("PRESENCE_GAPI_ENABLED", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_WRITE", "1")
    monkeypatch.setenv("PRESENCE_GAPI_CALENDAR_CONFIRM", "1")

    tz = ZoneInfo("Asia/Tokyo")
    start = datetime(2026, 6, 30, 10, 0, tzinfo=tz)
    end = datetime(2026, 6, 30, 12, 0, tzinfo=tz)
    from presence_ui.gateway.calendar_stage import CalendarResolvedDraft, ResolvedRange

    draft = CalendarResolvedDraft(
        action="create",
        calendar_id="primary",
        topic="久恵さん信大",
        range=ResolvedRange(start=start, end=end, day=start.date()),
    )
    record = pending_from_resolved(
        person_id="ma",
        source_utterance="orig",
        draft=draft,
        created_at="2026-06-29T10:00:00+09:00",
    )
    path = tmp_path / "calendar_pending.json"
    monkeypatch.setattr(
        "presence_ui.gateway.calendar_pending._pending_path",
        lambda: path,
    )
    save_pending(record)

    monkeypatch.setattr(
        "presence_ui.gateway.calendar_write.execute_pending_calendar_sync",
        lambda _r: ("[calendar_write_result]\nstatus=ok\n[/calendar_write_result]", "ok"),
    )
    outcome = process_calendar_turn_sync(person_id="ma", message="OK")
    assert outcome.write_block is not None
    assert "status=ok" in outcome.write_block
    assert load_pending(person_id="ma") is None
