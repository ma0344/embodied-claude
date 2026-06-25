"""MEM-8f / OL-ARCHIVE — archival remember vs open-loop follow-up."""

from relationship_mcp.inference import (
    extract_archive_remember_content,
    is_archive_remember_utterance,
)

def test_archive_remember_extracts_topic_content() -> None:
    text = "さっきの仕事の話、覚えておいてね"
    assert extract_archive_remember_content(text) == "さっきの仕事の話"
    assert is_archive_remember_utterance(text) is True


def test_follow_up_remember_still_creates_open_loop(store) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="PR review 明日やるの覚えといて",
        ts="2026-04-15T19:20:00+09:00",
        source_event_id="evt_follow_up",
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
    assert loops[0].topic == "pr review"


def test_archive_remember_does_not_create_open_loop(store) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="さっきの仕事の話、覚えておいてね",
        ts="2026-06-25T12:00:00+09:00",
        source_event_id="evt_archive",
    )
    assert store.list_open_loops(person_id="ma") == []


def test_close_loops_after_remember_save_closes_legacy_loop(store) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    utterance = "さっきの仕事の話、覚えておいてね"
    store.db.execute(
        """
        INSERT INTO open_loops(
            loop_id, person_id, topic, status, source_event_id, updated_at, detail_json
        )
        VALUES (?, ?, ?, 'open', ?, ?, ?)
        """,
        (
            "loop_legacy_archive",
            "ma",
            utterance[:48],
            "evt_old",
            "2026-06-20T10:00:00+09:00",
            '{"kind":"future_task_or_question"}',
        ),
    )
    assert len(store.list_open_loops(person_id="ma")) == 1

    closed = store.close_loops_after_remember_save(
        person_id="ma",
        utterance=utterance,
        saved_content="さっきの仕事の話",
        ts="2026-06-25T12:01:00+09:00",
        source_event_id="evt_remember",
    )
    assert len(closed) == 1
    assert store.list_open_loops(person_id="ma") == []


def test_imperative_only_remember_can_still_open_loop(store) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="これ覚えといて",
        ts="2026-06-25T12:00:00+09:00",
        source_event_id="evt_imperative",
    )
    loops = store.list_open_loops(person_id="ma")
    assert len(loops) == 1
