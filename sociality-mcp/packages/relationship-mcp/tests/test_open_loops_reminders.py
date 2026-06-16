"""Tests for OL1 date resolution and OL2 reminder commitments."""

from __future__ import annotations

import json

from relationship_mcp.date_resolution import is_stale, resolve_relative_date
from relationship_mcp.reminder_intent import (
    detect_delivery_mode,
    extract_quoted_speak_line,
    extract_reminder_request,
)


def test_resolve_relative_date_tomorrow():
    resolved = resolve_relative_date(
        topic="明日の PR review",
        updated_at="2026-04-15T19:12:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert resolved is not None
    assert resolved.isoformat() == "2026-04-16"


def test_is_stale_after_resolved_day():
    stale = is_stale(
        topic="明日の会議",
        updated_at="2026-04-15T10:00:00+09:00",
        tz_name="Asia/Tokyo",
        as_of=__import__("datetime").date(2026, 4, 17),
    )
    assert stale is not None
    assert stale.isoformat() == "2026-04-16"


def test_extract_reminder_request_tomorrow_at_ten():
    parsed = extract_reminder_request(
        "明日の10時に会議をリマインドして",
        ts="2026-04-15T19:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert "会議" in parsed.title
    assert "2026-04-16T10:00:00" in parsed.due_at


def test_extract_reminder_request_today_rolls_forward():
    parsed = extract_reminder_request(
        "3時に薬を教えて",
        ts="2026-04-15T19:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert "2026-04-16T03:00:00" in parsed.due_at


def test_extract_reminder_request_ten_minutes_later_with_quote():
    parsed = extract_reminder_request(
        "１０分後に、「まー、時間やで！！」って say でしゃべって教えて",
        ts="2026-06-16T18:04:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert parsed is not None
    assert parsed.speak_line == "まー、時間やで！！"
    assert parsed.delivery == "say"
    assert "2026-06-16T18:14:00" in parsed.due_at


def test_extract_quoted_speak_line():
    assert extract_quoted_speak_line("「お茶飲んで」って言って") == "お茶飲んで"


def test_needs_llm_reminder_parse_when_rule_misses():
    from relationship_mcp.reminder_intent import needs_llm_reminder_parse

    assert needs_llm_reminder_parse("来週の打合せの15分前にリマインドして") is True
    assert needs_llm_reminder_parse("3分後に「まー」と say で教えて") is False
    assert needs_llm_reminder_parse("おはよう") is False


def test_detect_delivery_mode_nudge_only():
    assert detect_delivery_mode("10時にテキストだけでリマインドして") == "nudge_only"


def test_note_human_creates_reminder_commitment(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="明日の9時に歯医者をリマインドして",
        ts="2026-04-15T18:00:00+09:00",
        source_event_id="evt_remind_1",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1
    assert commitments[0].due_at is not None
    assert "2026-04-16T09:00:00" in commitments[0].due_at


def test_note_human_creates_reminder_with_speak_line_metadata(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="10分後に「まー、時間やで」と say で教えて",
        ts="2026-06-16T18:04:00+09:00",
        source_event_id="evt_remind_quote",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1
    assert commitments[0].metadata.get("speak_line") == "まー、時間やで"
    assert commitments[0].metadata.get("delivery") == "say"
    assert "2026-06-16T18:14:00" in commitments[0].due_at


def test_reminder_commitment_dedupes_same_due_at(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="10分後に「A」と教えて",
        ts="2026-06-16T18:04:00+09:00",
        source_event_id="evt_remind_a",
    )
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="10分後に「B」と教えて",
        ts="2026-06-16T18:04:30+09:00",
        source_event_id="evt_remind_b",
    )
    commitments = store.list_active_commitments(person_id="ma")
    assert len(commitments) == 1


def test_close_stale_open_loops_on_ingest(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="明日の会議の準備したい",
        ts="2026-04-15T10:00:00+09:00",
    )
    assert len(store.list_open_loops(person_id="ma")) == 1

    closed = store.close_stale_open_loops(
        person_id="ma",
        as_of="2026-04-17T12:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert len(closed) == 1
    assert store.list_open_loops(person_id="ma") == []


def test_list_due_commitments_within_catch_up_window(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.create_commitment(
        person_id="ma",
        text="standup",
        due_at="2026-04-16T09:00:00+09:00",
        source="test",
        metadata={"speak_line": "まー、standup の時間やで"},
    )
    due = store.list_due_commitments(
        person_id="ma",
        as_of="2026-04-16T09:05:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert len(due) == 1
    assert due[0].text == "standup"
    assert due[0].metadata.get("speak_line") == "まー、standup の時間やで"

    future = store.list_due_commitments(
        person_id="ma",
        as_of="2026-04-15T09:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert future == []


def test_open_loop_detail_has_resolved_date(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="明日は会議がある",
        ts="2026-04-15T10:00:00+09:00",
    )
    row = store.db.fetchone(
        "SELECT detail_json FROM open_loops WHERE person_id = ? AND status = 'open'",
        ("ma",),
    )
    assert row is not None
    detail = json.loads(row["detail_json"])
    assert detail.get("resolved_date") == "2026-04-16"
