"""Tests for STM episode summarization and closure (MEM-2)."""

from __future__ import annotations

from social_core.stm import StmStore
from social_core.stm_episode import is_trivial_turn, sanitize_episode_summary_text, summarize_episode_turns


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


def test_summarize_episode_turns_strips_gateway_wrapped_ma_message():
    enriched = """[gateway_turn_context — not for the user]
[Social context]
[interaction_context]
phase=chat

晩ごはん食べ終わった"""
    turns = [
        {"sender": "ma", "message": enriched},
        {"sender": "koyori", "message": "お疲れさま、ゆっくりしといて"},
    ]
    summary = summarize_episode_turns(turns)
    assert summary is not None
    assert "gateway_turn_context" not in summary
    assert "晩ごはん" in summary
    assert "お疲れさま" in summary


def test_sanitize_episode_summary_text_removes_gateway_blocks():
    polluted = """【会話の一区切り】
まー: [gateway_turn_context — not for the user]
[Social context]
[interaction_context]
Calendar 2026年6月20日

おるよ～
こより: おるよ～！まー、お疲れさま。"""
    cleaned = sanitize_episode_summary_text(polluted)
    assert "gateway_turn_context" not in cleaned
    assert "おるよ" in cleaned
    assert "お疲れさま" in cleaned
    assert "[Social context]" not in cleaned


def test_sanitize_episode_summary_text_drops_koyori_echo():
    polluted = """【会話の一区切り】
まー: おるよ〜 おはよう。
こより: おるよ〜 おはよう。"""
    cleaned = sanitize_episode_summary_text(polluted)
    assert "まー: おるよ〜 おはよう。" in cleaned
    assert "こより: おるよ〜 おはよう。" not in cleaned


def test_summarize_episode_turns_drops_koyori_echo():
    turns = [
        {"sender": "koyori", "message": "まー、おる？"},
        {"sender": "ma", "message": "おるよ〜 おはよう。"},
        {"sender": "koyori", "message": "おるよ〜 おはよう。"},
    ]
    summary = summarize_episode_turns(turns)
    assert summary is not None
    assert "こより: おるよ〜 おはよう。" not in summary
    assert "まー: おるよ〜 おはよう。" in summary


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


def test_repair_episode_close_summaries(social_db):
    stm = StmStore(social_db)
    polluted = """【会話の一区切り】
まー: [gateway_turn_context — not for the user]
[Social context]

おるよ～
こより: お疲れさま"""
    entry = stm.append(
        summary=polluted,
        kind="episode_close",
        source="episode_summary",
        person_id="ma",
        session_id="sess_repair",
        ts="2026-06-16T20:00:00+09:00",
        timezone="Asia/Tokyo",
    )
    assert "gateway_turn_context" in entry.summary
    scanned, updated = stm.repair_episode_close_summaries()
    assert scanned >= 1
    assert updated >= 1
    fixed = stm.get_entry(entry.entry_id)
    assert fixed is not None
    assert "gateway_turn_context" not in fixed.summary
    assert "おるよ" in fixed.summary
