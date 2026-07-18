"""UserAction meal store API (MEM-8h UA-0)."""

from __future__ import annotations

from relationship_mcp.store import RelationshipStore


def test_user_actions_migration_present(store: RelationshipStore) -> None:
    tables = {
        row["name"]
        for row in store.db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "user_actions" in tables
    applied = {row["name"] for row in store.db.fetchall("SELECT name FROM schema_migrations")}
    assert "011_user_actions" in applied


def test_upsert_intended_newer_wins(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    first = store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="カレー",
        ts="2026-07-18T10:00:00+09:00",
        source_event_id="ev1",
    )
    second = store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="カレー",
        ts="2026-07-18T12:00:00+09:00",
        source_event_id="ev2",
    )
    assert first.action_id == second.action_id
    assert second.source_event_id == "ev2"
    assert second.status == "intended"
    active = store.list_active_intended(
        person_id="ma",
        kind="meal",
        now="2026-07-18T13:00:00+09:00",
    )
    assert len(active) == 1
    assert active[0].object == "カレー"


def test_confirm_and_insert_confirmed(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    intended = store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="蕎麦",
        ts="2026-07-18T18:00:00+09:00",
    )
    confirmed = store.confirm(
        action_id=intended.action_id,
        action_date="2026-07-18",
        ts="2026-07-18T20:00:00+09:00",
    )
    assert confirmed is not None
    assert confirmed.status == "confirmed"
    assert confirmed.action_date == "2026-07-18"
    assert store.list_active_intended(person_id="ma", kind="meal") == []

    self_report = store.insert_confirmed(
        person_id="ma",
        kind="meal",
        object="カレー",
        action_date="2026-07-17",
        ts="2026-07-17T21:00:00+09:00",
    )
    assert self_report.status == "confirmed"
    listed = store.list_confirmed(person_id="ma", kind="meal", limit=5)
    assert [row.object for row in listed] == ["蕎麦", "カレー"]


def test_confirm_by_person_kind_object(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="うどん",
        ts="2026-07-18T18:00:00+09:00",
    )
    confirmed = store.confirm(
        person_id="ma",
        kind="meal",
        object="うどん",
        action_date="2026-07-18",
        ts="2026-07-18T21:00:00+09:00",
    )
    assert confirmed is not None
    assert confirmed.object == "うどん"
    assert confirmed.status == "confirmed"


def test_intended_age_excludes_old(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    old_ts = "2026-07-15T12:00:00+09:00"
    store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="ラーメン",
        ts=old_ts,
    )
    now = "2026-07-18T12:00:00+09:00"
    assert store.list_active_intended(person_id="ma", kind="meal", now=now) == []
    store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="ラーメン",
        ts="2026-07-18T10:00:00+09:00",
    )
    active = store.list_active_intended(person_id="ma", kind="meal", now=now)
    assert len(active) == 1


def test_intended_never_in_confirmed_list(store: RelationshipStore) -> None:
    store.upsert_person(person_id="ma", canonical_name="まー", aliases=[], role="companion")
    store.upsert_intended(
        person_id="ma",
        kind="meal",
        object="カレー",
        ts="2026-07-18T12:00:00+09:00",
    )
    assert store.list_confirmed(person_id="ma", kind="meal") == []
