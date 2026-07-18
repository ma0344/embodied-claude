"""SPONT-B1 / S1 — OL6 outbound concern + tick hook."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from interaction_orchestrator_mcp.schemas import (
    CommitmentSummary,
    InteractionContext,
    LoopDueForCheck,
    ResponseContract,
    ResponsePlan,
)

from presence_ui.gateway import ol6_outbound
from presence_ui.gateway.direct_actions import DirectActionOutcome


def _ctx() -> InteractionContext:
    return InteractionContext(
        ts="2026-07-17T06:20:00+00:00",
        local_time="2026-07-17T15:20:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-07-17T06:20:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": None,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block="",
    )


def _plan() -> ResponsePlan:
    return ResponsePlan(
        primary_move="act_autonomously",
        why_this_move="test",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={
            "level": "low",
            "allowed_actions": ["observe_room"],
            "forbidden_actions": [],
        },
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )


def _due(*, trigger: str = "post_deadline_first_turn") -> LoopDueForCheck:
    return LoopDueForCheck(
        loop_id="loop-1",
        topic="15時までに申請書を仕上げる",
        until_phrase="15時まで",
        resolved_date="2026-07-17",
        trigger=trigger,  # type: ignore[arg-type]
    )


def test_compute_ol6_concern_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRESENCE_OL6_OUTBOUND_STAKES", raising=False)
    monkeypatch.delenv("PRESENCE_OL6_OUTBOUND_CARE", raising=False)
    concern = ol6_outbound.compute_ol6_concern(_due())
    assert concern == pytest.approx(0.64)


def test_build_ol6_check_line() -> None:
    line = ol6_outbound.build_ol6_check_line(_due())
    assert "申請書" in line
    assert "片付いた" in line


@pytest.mark.asyncio
async def test_maybe_fire_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND", "0")
    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]
    result = await ol6_outbound.maybe_fire_ol6_outbound(
        MagicMock(), person_id="ma", ctx=ctx, plan=_plan()
    )
    assert result is None


@pytest.mark.asyncio
async def test_maybe_fire_skips_when_commitment_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND", "1")
    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]
    ctx.commitments_due = [
        CommitmentSummary(
            commitment_id="c1",
            text="remind",
            due_at="2026-07-17T15:00:00+09:00",
            status="active",
        )
    ]
    result = await ol6_outbound.maybe_fire_ol6_outbound(
        MagicMock(), person_id="ma", ctx=ctx, plan=_plan()
    )
    assert result is None


@pytest.mark.asyncio
async def test_maybe_fire_skips_ol7_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND", "1")
    ctx = _ctx()
    ctx.loops_due_for_check = [_due(trigger="ol7_return_signal")]
    result = await ol6_outbound.maybe_fire_ol6_outbound(
        MagicMock(), person_id="ma", ctx=ctx, plan=_plan()
    )
    assert result is None


@pytest.mark.asyncio
async def test_check_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD", "0.9")
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_STAKES", "0.8")
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_CARE", "0.8")
    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]
    outcome = await ol6_outbound.check_open_loop_outbound_direct(
        MagicMock(),
        person_id="ma",
        ctx=ctx,
        plan=_plan(),
        skip_presence=True,
    )
    assert outcome.ok is False
    assert "below threshold" in outcome.summary


@pytest.mark.asyncio
async def test_check_presence_false_does_not_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD", "0.5")
    stores = MagicMock()
    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]

    async def _absent() -> MagicMock:
        return MagicMock(present=False, reason="near camera absent")

    monkeypatch.setattr(
        "presence_ui.services.speak_presence.companion_present_for_speak",
        _absent,
    )
    monkeypatch.setattr(
        ol6_outbound,
        "boundary_allows",
        lambda *a, **k: (True, []),
    )

    outcome = await ol6_outbound.check_open_loop_outbound_direct(
        stores,
        person_id="ma",
        ctx=ctx,
        plan=_plan(),
        skip_presence=False,
    )
    assert outcome.ok is False
    stores.relationship.mark_loop_check_asked.assert_not_called()


@pytest.mark.asyncio
async def test_check_success_marks_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD", "0.5")
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_STAKES", "0.8")
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_CARE", "0.8")
    stores = MagicMock()
    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]

    monkeypatch.setattr(
        ol6_outbound,
        "boundary_allows",
        lambda *a, **k: (True, []),
    )
    monkeypatch.setattr(
        ol6_outbound,
        "enqueue_outbound_nudge",
        lambda *a, **k: MagicMock(
            ok=True, nudge_id="n1", channels=["room_inbound"], reason=""
        ),
    )
    monkeypatch.setattr(ol6_outbound, "voice_local_enabled", lambda: False)
    monkeypatch.setattr(
        "presence_ui.services.outbound_kiosk.should_deliver_pc_local",
        lambda: False,
    )

    outcome = await ol6_outbound.check_open_loop_outbound_direct(
        stores,
        person_id="ma",
        ctx=ctx,
        plan=_plan(),
        skip_presence=True,
    )
    assert outcome.ok is True
    assert outcome.action == "check_open_loop"
    assert "片付いた" in outcome.summary
    stores.relationship.mark_loop_check_asked.assert_called_once()
    kwargs = stores.relationship.mark_loop_check_asked.call_args.kwargs
    assert kwargs["loop_id"] == "loop-1"
    assert "片付いた" in kwargs["ask_snippet"]


@pytest.mark.asyncio
async def test_enqueue_fail_does_not_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD", "0.5")
    stores = MagicMock()
    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]
    monkeypatch.setattr(
        ol6_outbound,
        "boundary_allows",
        lambda *a, **k: (True, []),
    )
    monkeypatch.setattr(
        ol6_outbound,
        "enqueue_outbound_nudge",
        lambda *a, **k: MagicMock(ok=False, nudge_id=None, channels=[], reason="cooldown"),
    )

    outcome = await ol6_outbound.check_open_loop_outbound_direct(
        stores,
        person_id="ma",
        ctx=ctx,
        plan=_plan(),
        skip_presence=True,
    )
    assert outcome.ok is False
    stores.relationship.mark_loop_check_asked.assert_not_called()


@pytest.mark.asyncio
async def test_autonomous_tick_prefers_ol6_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from presence_ui.gateway import autonomous_tick

    monkeypatch.setenv("PRESENCE_GATEWAY_DIRECT_ACTIONS", "1")
    monkeypatch.setattr(autonomous_tick, "direct_actions_enabled", lambda: True)

    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.relationship.close_stale_open_loops.return_value = None
    monkeypatch.setattr(autonomous_tick, "get_stores", lambda: stores)

    ctx = _ctx()
    ctx.loops_due_for_check = [_due()]
    plan = _plan()
    monkeypatch.setattr(autonomous_tick, "compose_interaction_context", lambda *a, **k: ctx)
    monkeypatch.setattr(autonomous_tick, "enrich_interaction_context", lambda c, **k: c)
    monkeypatch.setattr(autonomous_tick, "plan_response", lambda *a, **k: plan)
    monkeypatch.setattr(autonomous_tick, "apply_somatic_plan_side_effects", lambda **k: None)
    monkeypatch.setattr(autonomous_tick, "quiet_from_context", lambda c: False)

    ol6 = DirectActionOutcome(
        ok=True,
        action="check_open_loop",
        summary="まー、申請書のやつ、もう片付いた？",
    )
    monkeypatch.setattr(
        "presence_ui.gateway.ol6_outbound.maybe_fire_ol6_outbound",
        AsyncMock(return_value=ol6),
    )
    execute = AsyncMock()
    monkeypatch.setattr(autonomous_tick, "execute_autonomous_plan", execute)
    monkeypatch.setattr(
        autonomous_tick,
        "apply_pulse_schedule",
        lambda **k: MagicMock(next_wake_at="2026-07-17T16:00:00+09:00"),
    )

    result = await autonomous_tick.run_autonomous_tick(person_id="ma")
    assert result.ok is True
    assert result.primary_move == "check_open_loop"
    assert result.action == "check_open_loop"
    execute.assert_not_called()
