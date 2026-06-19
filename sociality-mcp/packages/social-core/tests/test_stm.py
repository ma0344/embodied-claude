"""Tests for STM store (MEM-1)."""

from __future__ import annotations

from social_core.stm import (
    STM_AUTO_MIRROR_KINDS,
    StmEntry,
    StmStore,
    build_stm_prompt_block,
    local_day_for_ts,
)


def test_flush_wm_turns_creates_dialogue_entries(social_db):
    stm = StmStore(social_db)
    turns = [
        {"sender": "ma", "message": "おはよう", "timestamp": "2026-06-16T00:10:00+09:00"},
        {"sender": "koyori", "message": "おはよう、まー", "timestamp": "2026-06-16T00:10:05+09:00"},
    ]
    entries = stm.flush_wm_turns(
        turns=turns,
        person_id="ma",
        session_id="sess_test",
        trigger="session_end",
        timezone="Asia/Tokyo",
    )
    assert len(entries) == 2
    assert entries[0].source == "wm_flush"
    assert entries[0].kind == "wm_turn_ma"
    assert "おはよう" in entries[0].summary
    assert entries[1].kind == "wm_turn_koyori"

    recent = stm.recent(person_id="ma", limit=10)
    assert len(recent) == 2
    assert recent[0].entry_id == entries[1].entry_id


def test_mirror_experience_skips_low_importance(social_db):
    stm = StmStore(social_db)
    with social_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_experiences(
                experience_id, ts, person_id, kind, summary,
                private_summary, public_summary, why,
                felt_state_json, desires_before_json, desires_after_json,
                related_event_ids, related_memory_ids, artifacts_json,
                importance, privacy_level, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exp_low",
                "2026-06-16T01:00:00+00:00",
                "ma",
                "reply",
                "short reply",
                None,
                None,
                None,
                "{}",
                "{}",
                "{}",
                "",
                "",
                "{}",
                2,
                "public",
                "2026-06-16T01:00:00+00:00",
            ),
        )
    assert stm.mirror_experience("exp_low") is None
    assert stm.count_for_day(local_day="2026-06-16", person_id="ma") == 0


def test_mirror_experience_auto_kind(social_db):
    stm = StmStore(social_db)
    kind = next(iter(STM_AUTO_MIRROR_KINDS))
    with social_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_experiences(
                experience_id, ts, person_id, kind, summary,
                private_summary, public_summary, why,
                felt_state_json, desires_before_json, desires_after_json,
                related_event_ids, related_memory_ids, artifacts_json,
                importance, privacy_level, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exp_auto",
                "2026-06-16T02:00:00+00:00",
                "ma",
                kind,
                "boundary respected",
                None,
                None,
                None,
                "{}",
                "{}",
                "{}",
                "",
                "",
                "{}",
                1,
                "public",
                "2026-06-16T02:00:00+00:00",
            ),
        )
    entry = stm.mirror_experience("exp_auto")
    assert entry is not None
    assert entry.source == "experience_mirror"
    assert entry.experience_id == "exp_auto"
    assert entry.kind == kind


def test_append_anchors_relative_dates(social_db):
    stm = StmStore(social_db)
    entry = stm.append(
        summary="明日の天気を確認した",
        kind="open_loop_progress",
        source="experience_mirror",
        ts="2026-06-18T22:00:00+09:00",
        person_id="ma",
    )
    assert entry.summary.startswith("2026年6月19日")
    assert "明日" not in entry.summary


def test_mirror_experience_high_importance(social_db):
    stm = StmStore(social_db)
    with social_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_experiences(
                experience_id, ts, person_id, kind, summary,
                private_summary, public_summary, why,
                felt_state_json, desires_before_json, desires_after_json,
                related_event_ids, related_memory_ids, artifacts_json,
                importance, privacy_level, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exp_hi",
                "2026-06-16T03:00:00+00:00",
                "ma",
                "note",
                "important moment",
                None,
                None,
                None,
                "{}",
                "{}",
                "{}",
                "",
                "",
                "{}",
                5,
                "public",
                "2026-06-16T03:00:00+00:00",
            ),
        )
    entry = stm.mirror_experience("exp_hi")
    assert entry is not None
    assert entry.importance == 5


def test_mirror_experience_idempotent(social_db):
    stm = StmStore(social_db)
    with social_db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_experiences(
                experience_id, ts, person_id, kind, summary,
                private_summary, public_summary, why,
                felt_state_json, desires_before_json, desires_after_json,
                related_event_ids, related_memory_ids, artifacts_json,
                importance, privacy_level, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exp_dup",
                "2026-06-16T04:00:00+00:00",
                "ma",
                "interpretation_shift",
                "shift noted",
                None,
                None,
                None,
                "{}",
                "{}",
                "{}",
                "",
                "",
                "{}",
                3,
                "public",
                "2026-06-16T04:00:00+00:00",
            ),
        )
    first = stm.mirror_experience("exp_dup")
    second = stm.mirror_experience("exp_dup")
    assert first is not None
    assert second is None
    assert stm.count_for_day(
        local_day=local_day_for_ts(first.ts, "Asia/Tokyo"),
        person_id="ma",
    ) == 1


def test_build_stm_prompt_block():
    entries = [
        StmEntry(
            entry_id="stm_1",
            ts="2026-06-16T10:00:00+09:00",
            local_day="2026-06-16",
            person_id="ma",
            source="wm_flush",
            kind="wm_turn_ma",
            summary="まー: こんにちは",
            session_id="s1",
            experience_id=None,
            turn_index=0,
            importance=3,
            dreamed_at=None,
            created_at="2026-06-16T10:00:00+09:00",
        )
    ]
    block = build_stm_prompt_block(entries)
    assert "[stm_recent]" in block
    assert "こんにちは" in block
