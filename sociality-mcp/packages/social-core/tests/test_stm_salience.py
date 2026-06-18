"""Tests for STM salience metadata (MEM-5b)."""

from __future__ import annotations

import json

from social_core.stm import StmStore
from social_core.stm_salience import (
    build_stm_salience_metadata,
    match_open_loop_ids,
    salience_from_experience_row,
)


def test_match_open_loop_ids_by_topic_fragment():
    loops = [("loop_weather", "明日の天気")]
    matched = match_open_loop_ids("松本市の天気を調べた", loops)
    assert matched == ["loop_weather"]


def test_build_salience_includes_emotion_and_topics():
    meta = build_stm_salience_metadata(
        summary="まーの家は長野県松本市にある",
        kind="episode_close",
        source="episode_summary",
        importance=3,
    )
    assert meta["emotion_tag"] == "moved"
    assert "residence" in meta["topics"]


def test_mirror_experience_writes_salience_metadata(social_db):
    stm = StmStore(social_db)
    with social_db.transaction() as conn:
        conn.execute(
            "INSERT INTO persons(person_id, canonical_name, created_at, updated_at) "
            "VALUES ('ma', 'まー', '2026-06-18T10:00:00+00:00', '2026-06-18T10:00:00+00:00')"
        )
        conn.execute(
            """
            INSERT INTO open_loops(loop_id, person_id, topic, status, updated_at)
            VALUES ('loop1', 'ma', '明日の天気', 'open', '2026-06-18T10:00:00+00:00')
            """
        )
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
                "exp_sal",
                "2026-06-18T10:00:00+00:00",
                "ma",
                "open_loop_progress",
                "明日の松本市の天気は晴れ",
                None,
                None,
                None,
                "{}",
                "{}",
                json.dumps({"miss_companion": 0.7}),
                "",
                "",
                "{}",
                3,
                "public",
                "2026-06-18T10:00:00+00:00",
            ),
        )
    entry = stm.mirror_experience("exp_sal")
    assert entry is not None
    row = social_db.fetchone(
        "SELECT metadata_json FROM stm_entries WHERE entry_id = ?",
        (entry.entry_id,),
    )
    meta = json.loads(row[0])
    assert meta["dominant_desire"] == "miss_companion"
    assert meta["emotion_tag"]
    assert "loop1" in meta.get("open_loop_ids", [])


def test_salience_from_experience_row_parses_desires():
    row = {
        "summary": "ヘルパーのお仕事について話した",
        "kind": "open_loop_progress",
        "importance": 4,
        "desires_before_json": "{}",
        "desires_after_json": json.dumps({"care_for_ma": 0.8}),
    }
    meta = salience_from_experience_row(row)
    assert meta["dominant_desire"] == "care_for_ma"
    assert meta["desire_level"] == 0.8
