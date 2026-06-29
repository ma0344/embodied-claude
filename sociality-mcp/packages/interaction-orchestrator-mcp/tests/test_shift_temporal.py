"""Tests for interpretation_shift temporal inject filtering."""

from __future__ import annotations

from datetime import date

from interaction_orchestrator_mcp.recall_query import (
    is_temporal_question,
    temporal_schedule_contract_enabled,
)
from interaction_orchestrator_mcp.schemas import InterpretationShiftSummary
from interaction_orchestrator_mcp.shift_temporal import (
    append_bare_greeting_plan_constraints,
    append_shift_plan_constraints,
    effective_shift_domain,
    effective_shift_resolved_date,
    filter_injectable_shifts,
    is_schedule_like_shift,
    is_shift_domain_injectable,
    is_shift_temporally_stale,
    parse_first_jp_date,
    prepare_shifts_for_inject,
    relativize_shift_for_inject,
)


def _shift(**kwargs) -> InterpretationShiftSummary:
    defaults = {
        "shift_id": "shft_test",
        "ts": "2026-06-27T08:00:00+09:00",
        "topic": "today schedule",
        "old_interpretation": "default",
        "new_interpretation": "今日は入浴介助で15時位まで",
        "trigger": "ma clarified",
        "confidence": 0.9,
        "resolved_date": "2026-06-27",
    }
    defaults.update(kwargs)
    return InterpretationShiftSummary(**defaults)


def test_parse_first_jp_date() -> None:
    assert parse_first_jp_date("2026年6月27日は入浴介助") == date(2026, 6, 27)


def test_effective_shift_resolved_date_prefers_stored() -> None:
    shift = _shift(resolved_date="2026-06-27", new_interpretation="anchored text")
    assert (
        effective_shift_resolved_date(shift, tz_name="Asia/Tokyo") == date(2026, 6, 27)
    )


def test_stale_schedule_shift_filtered() -> None:
    shift = _shift()
    assert is_shift_temporally_stale(
        shift,
        as_of_ts="2026-06-28T08:00:00+09:00",
        tz_name="Asia/Tokyo",
    )


def test_same_day_shift_not_stale() -> None:
    shift = _shift()
    assert not is_shift_temporally_stale(
        shift,
        as_of_ts="2026-06-27T20:00:00+09:00",
        tz_name="Asia/Tokyo",
    )


def test_non_schedule_shift_never_stale() -> None:
    shift = _shift(
        new_interpretation="policy purpose is the rule, not sample wording",
        resolved_date=None,
        topic="late-night behavior",
    )
    assert not is_shift_temporally_stale(
        shift,
        as_of_ts="2026-06-28T08:00:00+09:00",
        tz_name="Asia/Tokyo",
    )


def test_filter_injectable_shifts_drops_stale() -> None:
    fresh = _shift(resolved_date="2026-06-28", ts="2026-06-28T08:00:00+09:00")
    stale = _shift()
    kept = filter_injectable_shifts(
        [stale, fresh],
        as_of_ts="2026-06-28T08:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert kept == [fresh]


def test_world_fact_shift_not_injectable() -> None:
    shift = _shift(
        domain="world_fact",
        topic="Matsumoto city HP",
        new_interpretation="Info is on the city website, not prefecture",
        resolved_date=None,
    )
    assert not is_shift_domain_injectable(shift)


def test_legacy_user_correction_trigger_inferred_world_fact() -> None:
    shift = _shift(
        domain=None,
        trigger="gateway post-reply hook (user_correction)",
        topic="違うみたい。松本市のHP",
    )
    assert effective_shift_domain(shift) == "world_fact"
    assert not is_shift_domain_injectable(shift)


def test_boundary_shift_injectable() -> None:
    shift = _shift(
        domain="boundary",
        new_interpretation="Do not speak after quiet hours unless asked",
        resolved_date=None,
        topic="quiet hours",
    )
    assert is_shift_domain_injectable(shift)


def test_filter_injectable_shifts_drops_world_fact() -> None:
    behavioral = _shift(
        domain="rule",
        topic="quiet hours",
        new_interpretation="policy purpose is the rule, not sample wording",
        resolved_date=None,
    )
    world = _shift(
        domain="world_fact",
        topic="Matsumoto HP",
        new_interpretation="Check city website",
        resolved_date=None,
    )
    kept = filter_injectable_shifts(
        [world, behavioral],
        as_of_ts="2026-06-28T08:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert kept == [behavioral]


def test_relativize_shift_for_inject() -> None:
    shift = _shift(
        new_interpretation="2026年6月28日、角煮を作る",
        resolved_date="2026-06-28",
        ts="2026-06-27T20:00:00+09:00",
    )
    out = relativize_shift_for_inject(
        shift,
        as_of_ts="2026-06-28T08:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert out.new_interpretation.startswith("今日")
    assert "2026年6月28日" not in out.new_interpretation


def test_prepare_shifts_for_inject_filters_and_relativizes() -> None:
    stale = _shift()
    fresh = _shift(
        new_interpretation="2026年6月28日、角煮を作る",
        resolved_date="2026-06-28",
        ts="2026-06-27T20:00:00+09:00",
    )
    kept = prepare_shifts_for_inject(
        [stale, fresh],
        as_of_ts="2026-06-28T08:00:00+09:00",
        tz_name="Asia/Tokyo",
    )
    assert len(kept) == 1
    assert kept[0].new_interpretation.startswith("今日")


def test_is_schedule_like_shift() -> None:
    policy = _shift(
        new_interpretation="policy purpose is the rule, not sample wording",
        resolved_date=None,
        topic="late-night behavior",
    )
    schedule = _shift()
    assert not is_schedule_like_shift(policy, tz_name="Asia/Tokyo")
    assert is_schedule_like_shift(schedule, tz_name="Asia/Tokyo")


def test_append_bare_greeting_plan_constraints_open_loops() -> None:
    must_include: list[str] = []
    must_avoid: list[str] = []
    append_bare_greeting_plan_constraints(
        must_include=must_include,
        must_avoid=must_avoid,
        open_loop_topics=["お昼→書類", "散歩", "書類15時まで"],
    )
    joined = " ".join(must_include)
    assert "bare greeting" in joined
    assert "[open_loops]" in joined
    assert "each open loop" in joined
    assert "書類15時まで" in joined
    assert "do NOT volunteer" not in joined
    assert any("dream_digest" in item for item in must_avoid)


def test_append_shift_plan_constraints_compact_policy() -> None:
    shift = _shift(
        new_interpretation="policy purpose (protect sleep) is the rule",
        resolved_date=None,
        topic="late-night behavior",
    )
    must_include: list[str] = []
    must_avoid: list[str] = []
    append_shift_plan_constraints(
        must_include=must_include,
        must_avoid=must_avoid,
        shifts=[shift],
        user_text="夜中どうする？",
        primary_move="answer_directly",
        tz_name="Asia/Tokyo",
        is_bare_greeting=lambda _t: False,
        is_temporal_question=is_temporal_question,
        temporal_schedule_contract_enabled=temporal_schedule_contract_enabled,
    )
    joined = " ".join(must_include)
    assert "do not regress" in joined
    assert "protect sleep" not in joined
    assert "OLD" not in joined


def test_append_shift_plan_constraints_schedule_on_temporal_q() -> None:
    shift = _shift(
        new_interpretation="今日、角煮を作る",
        resolved_date="2026-06-28",
    )
    must_include: list[str] = []
    must_avoid: list[str] = []
    append_shift_plan_constraints(
        must_include=must_include,
        must_avoid=must_avoid,
        shifts=[shift],
        user_text="今日の予定は？",
        primary_move="answer_directly",
        tz_name="Asia/Tokyo",
        is_bare_greeting=lambda _t: False,
        is_temporal_question=is_temporal_question,
        temporal_schedule_contract_enabled=temporal_schedule_contract_enabled,
    )
    joined = " ".join(must_include)
    assert "interpretation_shift schedule" in joined
    assert "角煮" in joined
