"""UserAction meal encode + dinner retrieve (MEM-8h UA-1 / R0 / R1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from interaction_orchestrator_mcp.schemas import (
    AgentStateSummary,
    InteractionContext,
    RelevantMemoryRef,
    ResponseContract,
)
from relationship_mcp.store import RelationshipStore

from presence_ui.gateway.user_action_meal import (
    collect_meal_mentionable_cards,
    demote_legacy_meal_records,
    looks_like_dinner_cue,
    maybe_enrich_user_action_meals,
    try_encode_user_action_meal,
)


@pytest.fixture
def store(tmp_path: Path) -> RelationshipStore:
    relationship_store = RelationshipStore(tmp_path / "social.db")
    yield relationship_store
    relationship_store.close()


def _ctx(**kwargs) -> InteractionContext:
    base = dict(
        ts="2026-07-18T19:00:00+09:00",
        local_time="2026-07-18 19:00",
        timezone="Asia/Tokyo",
        person_id="ma",
        agent_state=AgentStateSummary(ts="2026-07-18T19:00:00+09:00"),
        open_loops=[],
        relevant_memories=[],
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="[interaction_context]\nold",
    )
    base.update(kwargs)
    return InteractionContext(**base)


def test_self_report_inserts_confirmed(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    result = try_encode_user_action_meal(
        store,
        person_id="ma",
        text="カレー食べたよ",
        ts="2026-07-18T20:10:00+09:00",
        source_event_id="ev1",
    )
    assert result.route == "self_report"
    assert result.object == "カレー"
    rows = store.list_confirmed(person_id="ma", kind="meal")
    assert len(rows) == 1
    assert rows[0].action_date == "2026-07-18"


def test_plan_upserts_intended_not_confirmed(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    result = try_encode_user_action_meal(
        store,
        person_id="ma",
        text="今日の夜はカレーにするわ",
        ts="2026-07-18T17:00:00+09:00",
    )
    assert result.route == "plan"
    assert store.list_confirmed(person_id="ma", kind="meal") == []
    intended = store.list_active_intended(
        person_id="ma", kind="meal", now="2026-07-18T17:30:00+09:00"
    )
    assert len(intended) == 1
    assert intended[0].object == "カレー"


def test_confirm_from_intended(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    try_encode_user_action_meal(
        store,
        person_id="ma",
        text="晩御飯は蕎麦にしよう",
        ts="2026-07-18T17:00:00+09:00",
    )
    result = try_encode_user_action_meal(
        store,
        person_id="ma",
        text="うん",
        ts="2026-07-18T20:00:00+09:00",
    )
    assert result.route == "confirm"
    assert result.object == "蕎麦"
    rows = store.list_confirmed(person_id="ma", kind="meal")
    assert len(rows) == 1
    assert rows[0].status == "confirmed"


def test_mention_only_does_not_write(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    for text in (
        "カレーの話してたな",
        "最近カレー食べた気がする",
        "蕎麦食べたい",
        "カレー食べた？",
        "夜はカレーの動画にする",
    ):
        result = try_encode_user_action_meal(
            store,
            person_id="ma",
            text=text,
            ts="2026-07-18T12:00:00+09:00",
        )
        assert result.route == "none", text
    assert store.list_confirmed(person_id="ma", kind="meal") == []
    assert store.list_active_intended(person_id="ma", kind="meal") == []


def test_uun_does_not_confirm(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    try_encode_user_action_meal(
        store,
        person_id="ma",
        text="晩御飯はカレーにするわ",
        ts="2026-07-18T17:00:00+09:00",
    )
    result = try_encode_user_action_meal(
        store,
        person_id="ma",
        text="ううん",
        ts="2026-07-18T20:00:00+09:00",
    )
    assert result.route == "none"
    assert store.list_confirmed(person_id="ma", kind="meal") == []


def test_multi_intended_bare_un_is_fail_closed(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.upsert_intended(
        person_id="ma", kind="meal", object="カレー", ts="2026-07-18T17:00:00+09:00"
    )
    store.upsert_intended(
        person_id="ma", kind="meal", object="蕎麦", ts="2026-07-18T17:05:00+09:00"
    )
    result = try_encode_user_action_meal(
        store,
        person_id="ma",
        text="うん",
        ts="2026-07-18T20:00:00+09:00",
    )
    assert result.route == "none"
    assert store.list_confirmed(person_id="ma", kind="meal") == []


def test_outside_allowlist_never_writes(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    result = try_encode_user_action_meal(
        store,
        person_id="ma",
        text="ハンバーグ食べたよ",
        ts="2026-07-18T20:00:00+09:00",
    )
    assert result.route == "none"


def test_dinner_retrieve_cards(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.insert_confirmed(
        person_id="ma",
        kind="meal",
        object="蕎麦",
        action_date="2026-07-01",
        ts="2026-07-01T19:00:00+09:00",
    )
    with store.db.transaction() as connection:
        connection.execute(
            """
            INSERT INTO open_loops(loop_id, person_id, topic, status, updated_at, detail_json)
            VALUES (?, ?, ?, 'closed', ?, '{}')
            """,
            ("loop_cook1", "ma", "カレーを作った", "2026-07-10T18:00:00+09:00"),
        )
    assert looks_like_dinner_cue("今晚の晩御飯どうする")
    cards = collect_meal_mentionable_cards(store, person_id="ma", limit=5)
    texts = [c[0] for c in cards]
    assert any("食べた記録" in t and "蕎麦" in t for t in texts)
    assert any("作った記録" in t and "カレー" in t for t in texts)
    assert all("intended" not in t for t in texts)


def test_intended_not_mentionable(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="うどん",
        ts="2026-07-18T17:00:00+09:00",
    )
    cards = collect_meal_mentionable_cards(store, person_id="ma")
    assert cards == []


def test_r1_demotes_legacy_when_ua_present() -> None:
    ua = RelevantMemoryRef(
        memory_id=None,
        content="まーは直近で7月1日に麺類（蕎麦）を食べた記録がある",
        relevance=0.9,
        use_policy="mentionable",
        reason="user_action_meal",
    )
    legacy = RelevantMemoryRef(
        memory_id=None,
        content="まーは直近で6月1日にカレーを食べた記録がある",
        relevance=0.8,
        use_policy="mentionable",
        reason="memory_bridge_fact_row",
    )
    out = demote_legacy_meal_records([ua, legacy], has_ua_meal=True)
    assert out[0].reason == "user_action_meal"
    assert out[1].use_policy == "do_not_surface"
    assert out[1].reason == "legacy_meal_record_demoted_for_ua"


def test_maybe_enrich_injects_on_dinner_cue(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.insert_confirmed(
        person_id="ma",
        kind="meal",
        object="カレー",
        action_date="2026-07-15",
        ts="2026-07-15T19:00:00+09:00",
    )
    updated, label = maybe_enrich_user_action_meals(
        _ctx(),
        user_text="今晚の晩御飯どうする？",
        max_chars=4000,
        relationship=store,
    )
    assert label is not None
    assert any(m.reason == "user_action_meal" for m in updated.relevant_memories)
    assert any("カレー" in (line or "") for line in updated.memory_bridge_lines)
