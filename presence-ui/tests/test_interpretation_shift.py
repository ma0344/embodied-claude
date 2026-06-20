"""Tests for BIO-7 interpretation shift hook."""

from __future__ import annotations

from unittest.mock import MagicMock

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.heartbeat.interpretation_shift import infer_interpretation_shifts, record_interpretation_shifts


def _ctx(*, boundary_hints: list[str] | None = None) -> InteractionContext:
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
        prompt_summary="test",
        compact_prompt_block="[test]",
        boundary_hints=boundary_hints or [],
    )


def _plan() -> ResponsePlan:
    return ResponsePlan(
        primary_move="answer_directly",  # type: ignore[arg-type]
        why_this_move="ok",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={"level": "low", "allowed_actions": [], "forbidden_actions": []},
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
    )


def test_infer_shift_on_user_correction() -> None:
    shifts = infer_interpretation_shifts(
        person_id="ma",
        user_text="それは違う。夜は静かにして",
        reply_text="わかった、夜は黙るね",
        ctx=_ctx(),
        plan=_plan(),
    )
    assert len(shifts) == 1
    assert "静か" in shifts[0].new_interpretation or "夜" in shifts[0].topic


def test_infer_shift_skips_neutral_chat() -> None:
    shifts = infer_interpretation_shifts(
        person_id="ma",
        user_text="今日の天気どう？",
        reply_text="晴れてるよ",
        ctx=_ctx(),
        plan=_plan(),
    )
    assert shifts == []


def test_infer_shift_skips_compose_policy_boundary_hints_only() -> None:
    """maybe_interruptible hints must not record every turn as interpretation shift."""
    shifts = infer_interpretation_shifts(
        person_id="ma",
        user_text="おはようこより。返事がおそくなったね。",
        reply_text="ごめんね、今はゆっくりしてるよ",
        ctx=_ctx(boundary_hints=["availability is ambivalent; prefer bounded replies"]),
        plan=_plan(),
    )
    assert shifts == []


def test_record_interpretation_shifts_dedupes() -> None:
    user_text = "夜は静かにして"
    shifts = infer_interpretation_shifts(
        person_id="ma",
        user_text=user_text,
        reply_text="",
        ctx=_ctx(),
        plan=_plan(),
    )
    assert shifts
    stores = MagicMock()
    stores.orchestrator.recent_interpretation_shifts.return_value = [
        MagicMock(
            topic=shifts[0].topic,
            new_interpretation=shifts[0].new_interpretation,
        )
    ]
    from unittest.mock import patch

    with patch("presence_ui.deps.get_stores", return_value=stores):
        ids = record_interpretation_shifts(
            person_id="ma",
            user_text=user_text,
            reply_text="",
            ctx=_ctx(),
            plan=_plan(),
        )
    assert ids == []
    stores.orchestrator.record_interpretation_shift.assert_not_called()
