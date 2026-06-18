"""Tests for STM episode summarization and closure (MEM-2)."""

from __future__ import annotations

from social_core.stm import StmStore
from social_core.stm_episode import is_trivial_turn, summarize_episode_turns


def test_is_trivial_turn_greetings():
    assert is_trivial_turn("おはよう")
    assert is_trivial_turn("うん")
    assert not is_trivial_turn("カメラはまだ直ってない？")


def test_summarize_episode_turns_skips_noise_only():
    turns = [
        {"sender": "ma", "message": "おはよう"},
        {"sender": "koyori", "message": "おはよう"},
    ]
    assert summarize_episode_turns(turns) is None


def test_summarize_episode_turns_substantive(social_db):
    turns = [
        {"sender": "ma", "message": "カメラはなおった？"},
        {"sender": "koyori", "message": "まだ目が見えへん。電源を確認してほしい"},
    ]
    summary = summarize_episode_turns(turns)
    assert summary is not None
    assert "カメラ" in summary
    assert "まー" in summary
    assert "こより" in summary


def test_close_episode_idempotent(social_db):
    stm = StmStore(social_db)
    turns = [
        {"sender": "ma", "message": "今日の予定は？"},
        {"sender": "koyori", "message": "午後に散歩するって言ってたよ"},
    ]
    summary = summarize_episode_turns(turns)
    assert summary
    first = stm.close_episode(
        summary=summary,
        person_id="ma",
        session_id="sess_ep_1",
        trigger="new_session",
        turn_count=len(turns),
        ts="2026-06-16T20:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert first is not None
    assert first.kind == "episode_close"
    assert first.local_day == "2026-06-16"
    assert first.source == "episode_summary"

    second = stm.close_episode(
        summary=summary,
        person_id="ma",
        session_id="sess_ep_1",
        trigger="new_session",
        turn_count=len(turns),
        timezone="Asia/Tokyo",
    )
    assert second is not None
    assert second.entry_id == first.entry_id
    assert stm.count_for_day(local_day=first.local_day, person_id="ma") == 1
