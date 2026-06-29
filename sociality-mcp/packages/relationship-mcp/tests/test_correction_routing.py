"""Tests for close_open_loops_matching_topic (SHIFT-R2)."""

from __future__ import annotations

from relationship_mcp.store import RelationshipStore


def test_close_open_loops_matching_topic(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.apply_ol_gate_decision(
        person_id="ma",
        ts="2026-06-28T08:00:00+09:00",
        source_event_id="evt_seed",
        source_text="明日松本の話をする",
        create_open_loop=True,
        try_ol5_close=False,
        loop_topic="2026年6月29日は 松本の話",
        action_terms=["松本"],
        completion_verbs=[],
        detail={"kind": "ol_gate", "resolved_date": "2026-06-29"},
        timezone="Asia/Tokyo",
    )
    outcome = store.close_open_loops_matching_topic(
        person_id="ma",
        topic_hint="松本",
        ts="2026-06-28T09:00:00+09:00",
        source_event_id="evt_close",
        source_text="松本の話はもういい",
    )
    assert len(outcome.closed_loops) == 1
    assert "松本" in outcome.closed_loops[0]
