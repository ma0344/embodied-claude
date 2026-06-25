"""Tests for STM dreaming helpers (MEM-3 / MEM-5c)."""

from __future__ import annotations

from social_core.stm import StmEntry, StmStore
from social_core.stm_dreaming import (
    build_dream_digest,
    emotion_for_ltm,
    entries_to_promote,
    select_episodic_digest_entries,
    should_promote_stm_to_ltm,
)


def _entry(**overrides) -> StmEntry:
    base = {
        "entry_id": "stm_x",
        "ts": "2026-06-16T10:00:00+09:00",
        "local_day": "2026-06-16",
        "person_id": "ma",
        "source": "episode_summary",
        "kind": "episode_close",
        "summary": "まーの家は長野県松本市。天気の話もした",
        "session_id": "sess_1",
        "experience_id": None,
        "turn_index": None,
        "importance": 3,
        "dreamed_at": None,
        "created_at": "2026-06-16T10:00:00+09:00",
    }
    base.update(overrides)
    return StmEntry(**base)


def test_should_promote_episode_summary():
    assert should_promote_stm_to_ltm(_entry()) is True


def test_should_not_promote_raw_wm_turn():
    entry = _entry(source="wm_flush", kind="wm_turn_ma", summary="うん")
    assert should_promote_stm_to_ltm(entry) is False


def test_should_not_promote_greeting_only_episode():
    entry = _entry(summary="【会話の一区切り】\nこより: おはよう、まー。")
    assert should_promote_stm_to_ltm(entry) is False


def test_should_not_promote_private_reflection():
    entry = _entry(
        source="experience_mirror",
        kind="agent_private_reflection",
        summary="（自律の思考メモ） Open loops: 明日の天気",
        metadata_json='{"emotion_tag":"moved","importance":3}',
    )
    assert should_promote_stm_to_ltm(entry) is False


def test_entries_to_promote_dedupes_open_loop_progress():
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
        summary="松本市だと晴れ時々曇り",
        session_id=None,
        ts="2026-06-16T11:00:00+09:00",
    )
    promote = entries_to_promote([weather_a, weather_b])
    assert len(promote) == 1
    assert promote[0].entry_id == "b"


def test_emotion_for_ltm_uses_metadata():
    entry = _entry(metadata_json='{"emotion_tag":"curious"}')
    assert emotion_for_ltm(entry) == "curious"


def test_mark_dreamed_updates_rows(social_db):
    stm = StmStore(social_db)
    entry = stm.append(
        summary="episode text",
        kind="episode_close",
        source="episode_summary",
        person_id="ma",
        session_id="sess_dream",
    )
    assert stm.count_undreamed(person_id="ma", local_day=entry.local_day) == 1
    marked = stm.mark_dreamed([entry.entry_id])
    assert marked == 1
    assert stm.count_undreamed(person_id="ma", local_day=entry.local_day) == 0


def test_build_dream_digest_wraps_entries():
    digest = build_dream_digest([_entry()])
    assert "[dream_digest]" in digest
    assert "天気" in digest


def test_build_dream_digest_excludes_private_reflection():
    episode = _entry(entry_id="ep1", summary="ホームヘルパーが来る話")
    reflection = _entry(
        entry_id="ref1",
        source="experience_mirror",
        kind="agent_private_reflection",
        summary="（自律の思考メモ）深夜の独り言",
        ts="2026-06-16T23:00:00+09:00",
    )
    digest = build_dream_digest([reflection, episode])
    assert "ホームヘルパー" in digest
    assert "agent_private_reflection" not in digest
    assert "深夜の独り言" not in digest


def test_build_dream_digest_prioritizes_episode_before_autonomous():
    auto = _entry(
        entry_id="auto1",
        source="experience_mirror",
        kind="agent_autonomous_action",
        summary="tick: quietly observed",
        ts="2026-06-16T22:00:00+09:00",
    )
    episode = _entry(
        entry_id="ep1",
        summary="まーと散歩の約束",
        ts="2026-06-16T21:00:00+09:00",
    )
    digest = build_dream_digest([auto, episode])
    ep_pos = digest.index("散歩")
    auto_pos = digest.index("quietly")
    assert ep_pos < auto_pos


def test_select_episodic_digest_dedupes_open_loop_topics():
    older = _entry(
        entry_id="a",
        kind="open_loop_progress",
        source="experience_mirror",
        summary="明日の天気は晴れみたい",
        ts="2026-06-16T10:00:00+09:00",
    )
    newer = _entry(
        entry_id="b",
        kind="open_loop_progress",
        source="experience_mirror",
        summary="松本市だと晴れ時々曇り",
        ts="2026-06-16T11:00:00+09:00",
    )
    selected = select_episodic_digest_entries([older, newer])
    assert len(selected) == 1
    assert selected[0].entry_id == "b"


def test_build_dream_digest_note_when_only_private_reflection():
    reflection = _entry(
        kind="agent_private_reflection",
        source="experience_mirror",
        summary="深夜の独り言",
    )
    digest = build_dream_digest([reflection])
    assert "no episodic rows" in digest
    assert "agent_private_reflection" not in digest


def test_build_dream_digest_sanitizes_gateway_polluted_episode_close():
    polluted = """【会話の一区切り】
まー: [gateway_turn_context — not for the user]
[Social context]
[interaction_context]

おるよ～
こより: お疲れさま、ゆっくりしといて。"""
    loop = _entry(
        entry_id="loop1",
        kind="open_loop_progress",
        source="experience_mirror",
        summary="backlog を一緒に整理した",
        ts="2026-06-16T22:00:00+09:00",
    )
    episode = _entry(
        entry_id="ep1",
        summary=polluted,
        ts="2026-06-16T21:00:00+09:00",
    )
    digest = build_dream_digest([loop, episode])
    assert "gateway_turn_context" not in digest
    assert "おるよ" in digest
    assert "backlog" in digest
