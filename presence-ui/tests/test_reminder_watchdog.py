"""Tests for reminder watchdog."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from presence_ui.gateway import reminder_watchdog


@pytest.mark.asyncio
async def test_fire_due_reminders_once_skips_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reminder_watchdog, "direct_actions_enabled", lambda: True)
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.relationship.list_due_commitments.return_value = []
    monkeypatch.setattr(reminder_watchdog, "get_stores", lambda: stores)

    fired = await reminder_watchdog.fire_due_reminders_once(person_id="ma")
    assert fired is False


from interaction_orchestrator_mcp.schemas import (
    CommitmentSummary,
    InteractionContext,
    ResponseContract,
    ResponsePlan,
)


def _ctx() -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "dominant_desire": None,
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="quiet night",
        compact_prompt_block="",
    )


def _plan(*, allowed: list[str]) -> ResponsePlan:
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
            "allowed_actions": allowed,
            "forbidden_actions": [],
        },
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )


@pytest.mark.asyncio
async def test_fire_due_reminders_once_calls_remind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reminder_watchdog, "direct_actions_enabled", lambda: True)
    stores = MagicMock()
    stores.policy_timezone = "Asia/Tokyo"
    stores.relationship.list_due_commitments.return_value = [MagicMock(id="c1")]
    monkeypatch.setattr(reminder_watchdog, "get_stores", lambda: stores)

    ctx = _ctx()
    ctx.commitments_due = [
        CommitmentSummary(
            commitment_id="c1",
            text="まー！時間やで！！",
            due_at="2026-06-16T18:35:00+09:00",
            status="active",
            speak_line="まー！時間やで！！",
            delivery="say",
        )
    ]
    plan = _plan(allowed=["remind_commitment"])

    monkeypatch.setattr(reminder_watchdog, "compose_interaction_context", lambda *a, **k: ctx)
    monkeypatch.setattr(reminder_watchdog, "plan_response", lambda *a, **k: plan)
    remind = AsyncMock(
        return_value=MagicMock(ok=True, summary="まー！時間やで！！", action="remind_commitment")
    )
    monkeypatch.setattr(reminder_watchdog, "remind_commitment_direct", remind)

    fired = await reminder_watchdog.fire_due_reminders_once(person_id="ma")
    assert fired is True
    remind.assert_awaited_once()
