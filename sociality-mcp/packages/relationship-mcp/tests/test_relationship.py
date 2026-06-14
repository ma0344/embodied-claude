"""Tests for relationship abstractions."""

from relationship_mcp.store import RelationshipStore, _commitment_label


def test_alias_matching_works(store):
    store.upsert_person(
        person_id="ma",
        canonical_name="山口政佳",
        aliases=["まーちゃん", "まー","まーさん"],
        role="companion",
    )

    assert store.resolve_person_id("まー") == "ma"
    assert store.resolve_person_id("まーちゃん") == "ma"


def test_commitments_survive_restart(tmp_path):
    db_path = tmp_path / "social.db"
    first = RelationshipStore(db_path)
    first.upsert_person(person_id="ma", canonical_name="山口政佳", aliases=[], role="companion")
    created = first.create_commitment(
        person_id="ma",
        text="remind about dentist tomorrow morning",
        due_at="2026-04-16T08:00:00+09:00",
        source="conversation",
    )
    first.close()

    second = RelationshipStore(db_path)
    model = second.get_person_model(person_id="ma")
    second.close()

    assert any(commitment.id == created["commitment_id"] for commitment in model.active_commitments)


def test_repeated_mentions_of_future_task_create_open_loop(store):
    store.upsert_person(person_id="ma", canonical_name="山口政佳", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="voice",
        direction="human_to_ai",
        text="明日の PR review 忘れんようにしたい",
        ts="2026-04-15T19:12:00+09:00",
    )
    store.ingest_interaction(
        person_id="ma",
        channel="voice",
        direction="human_to_ai",
        text="PR review 明日やるの覚えといて",
        ts="2026-04-15T19:20:00+09:00",
    )
    loops = store.list_open_loops(person_id="ma")

    assert len(loops) == 1
    assert loops[0].topic == "pr review"


def test_agent_utterance_does_not_create_open_loop(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="ai_to_human",
        text="まー、どないしたん？急に呼んでびっくりしたわ。",
        ts="2026-04-15T19:12:00+09:00",
    )
    assert store.list_open_loops(person_id="ma") == []


def test_dismiss_closes_pr_review_loop_without_creating_new(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.ingest_interaction(
        person_id="ma",
        channel="chat",
        direction="human_to_ai",
        text="PR review 明日やるの覚えといて",
        ts="2026-04-15T19:20:00+09:00",
    )
    closed = store.note_human_utterance_for_loops(
        person_id="ma",
        text="あ、PRのレビューは中止になったの。その予定は忘れて。",
        ts="2026-06-14T16:36:00+09:00",
        source_event_id="evt_dismiss_1",
    )
    assert closed.closed_loops == ["pr review"]
    assert store.list_open_loops(person_id="ma") == []


def test_dismiss_cancels_matching_commitment(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    created = store.create_commitment(
        person_id="ma",
        text="remind ma about PR review tomorrow",
        due_at="2026-06-15T09:00:00+09:00",
        source="conversation",
    )
    outcome = store.note_human_utterance_for_loops(
        person_id="ma",
        text="PRのレビューは中止。その予定は忘れて。",
        ts="2026-06-14T16:40:00+09:00",
        source_event_id="evt_dismiss_commit",
    )
    assert outcome.cancelled_commitments == [_commitment_label("remind ma about PR review tomorrow")]
    model = store.get_person_model(person_id="ma")
    assert all(c.id != created["commitment_id"] for c in model.active_commitments)


def test_recall_question_does_not_create_open_loop(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="煎餅の話、覚えてる？",
        ts="2026-06-14T16:50:00+09:00",
        source_event_id="evt_recall_1",
    )
    assert store.list_open_loops(person_id="ma") == []


def test_recall_noise_loop_gets_closed_on_next_recall_utterance(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    with store.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO open_loops(
                loop_id, person_id, topic, status, source_event_id, updated_at, detail_json
            )
            VALUES ('loop_senbei', 'ma', ?, 'open', 'evt_old', '2026-06-14T00:00:00+00:00', '{}')
            """,
            ("煎餅の話、覚えてる",),
        )
    outcome = store.note_human_utterance_for_loops(
        person_id="ma",
        text="明日の会議、覚えておいて",
        ts="2026-06-14T16:51:00+09:00",
        source_event_id="evt_recall_2",
    )
    assert "煎餅の話、覚えてる" in outcome.closed_loops
    topics = [loop.topic for loop in store.list_open_loops(person_id="ma")]
    assert "煎餅の話、覚えてる" not in topics


def test_dismiss_does_not_create_open_loop_from_review_keyword(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.note_human_utterance_for_loops(
        person_id="ma",
        text="あ、PRのレビューは中止になったの。その予定は忘れて。",
        ts="2026-06-14T16:36:00+09:00",
        source_event_id="evt_dismiss_2",
    )
    assert store.list_open_loops(person_id="ma") == []


def test_note_human_utterance_for_loops_without_duplicate_event(store):
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    closed = store.note_human_utterance_for_loops(
        person_id="ma",
        text="PR review 明日やるの覚えといて",
        ts="2026-04-15T19:20:00+09:00",
        source_event_id="evt_room_1",
    )
    loops = store.list_open_loops(person_id="ma")
    assert closed.closed_loops == []
    assert closed.cancelled_commitments == []
    assert len(loops) == 1
    assert loops[0].topic == "pr review"


def test_completed_commitment_disappears_from_active_list(store):
    store.upsert_person(person_id="ma", canonical_name="山口政佳", aliases=[], role="companion")
    created = store.create_commitment(
        person_id="ma",
        text="remind about dentist tomorrow morning",
        due_at="2026-04-16T08:00:00+09:00",
        source="conversation",
    )
    store.complete_commitment(created["commitment_id"])
    model = store.get_person_model(person_id="ma")

    assert all(commitment.id != created["commitment_id"] for commitment in model.active_commitments)


def test_person_model_stays_compact_and_followup_uses_same_day_disclosure(store):
    store.upsert_person(
        person_id="ma", canonical_name="山口政佳", aliases=["まーちゃん","まー","まーさん"], role="companion"
    )
    store.record_boundary(
        person_id="ma",
        kind="communication",
        rule="quiet_after_midnight",
        source_text="夜中は静かめで頼む",
    )
    store.ingest_interaction(
        person_id="ma",
        channel="voice",
        direction="human_to_ai",
        text="今日は会議多くて疲れた",
        ts="2026-04-15T19:12:00+09:00",
    )
    model = store.get_person_model(person_id="ma")
    suggestions = store.suggest_followup(person_id="ma", context="evening_checkin")

    assert "今日は会議多くて疲れた" not in model.relationship_summary
    assert len(model.relationship_summary) < 120
    preference_texts = [pref.text for pref in model.salient_preferences]
    assert "prefers gentle brief nudges while working" in preference_texts
    for pref in model.salient_preferences:
        assert 0.0 <= pref.confidence <= 1.0
        assert pref.source in {"explicit", "inferred", "seeded"}
    boundary_pref = next(
        (p for p in model.salient_preferences if "nudges while working" in p.text), None
    )
    assert boundary_pref is not None
    assert boundary_pref.evidence  # evidence list must not be empty
    assert "会議多くて疲れた" in suggestions[0].text
