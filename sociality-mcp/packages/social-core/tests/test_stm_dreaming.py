"""Tests for STM dreaming helpers (MEM-3)."""

from __future__ import annotations

from social_core.stm import StmEntry, StmStore
from social_core.stm_dreaming import build_dream_digest, should_promote_stm_to_ltm


def _entry(**overrides) -> StmEntry:
    base = {
        "entry_id": "stm_x",
        "ts": "2026-06-16T10:00:00+09:00",
        "local_day": "2026-06-16",
        "person_id": "ma",
        "source": "episode_summary",
        "kind": "episode_close",
        "summary": "まーと天気の話をした",
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
