"""MEM-5 STM scoring tests."""

from __future__ import annotations

from social_core.stm import StmEntry
from social_core.stm_scoring import score_stm_entry


def _entry(**kwargs) -> StmEntry:
    base = dict(
        entry_id="stm_test1",
        ts="2026-06-18T18:00:00+09:00",
        local_day="2026-06-18",
        person_id="ma",
        source="episode_summary",
        kind="episode_close",
        summary="",
        session_id="sess-1",
        experience_id=None,
        turn_index=None,
        importance=3,
        dreamed_at=None,
        created_at="2026-06-18T09:00:00+00:00",
    )
    base.update(kwargs)
    return StmEntry(**base)


def test_residence_episode_promotes():
    entry = _entry(
        summary="【会話の一区切り】\nまー: 家は長野県の松本市だよ。",
    )
    result = score_stm_entry(entry)
    assert result.decision == "promote"
    assert "residence" in result.topics


def test_greeting_only_episode_holds():
    entry = _entry(summary="【会話の一区切り】\nこより: おはよう、まー。")
    result = score_stm_entry(entry)
    assert result.decision == "hold"


def test_private_reflection_holds_even_with_high_score():
    entry = _entry(
        source="experience_mirror",
        kind="agent_private_reflection",
        summary="（自律の思考メモ） dominant desire tick",
        metadata_json='{"emotion_tag":"moved","importance":4,"desire_level":0.9}',
    )
    result = score_stm_entry(entry)
    assert result.decision == "hold"


def test_duplicate_open_loop_merge():
    weather_a = _entry(
        entry_id="a",
        source="experience_mirror",
        kind="open_loop_progress",
        summary="明日の天気は晴れみたい",
        session_id=None,
    )
    weather_b = _entry(
        entry_id="b",
        source="experience_mirror",
        kind="open_loop_progress",
        summary="松本市だと晴れ時々曇りの予報",
        session_id=None,
        ts="2026-06-18T19:00:00+09:00",
    )
    day = [weather_a, weather_b]
    older = score_stm_entry(weather_a, day_entries=day)
    newer = score_stm_entry(weather_b, day_entries=day)
    assert older.decision == "merge"
    assert newer.decision in {"promote", "hold"}
