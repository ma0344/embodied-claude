"""Lite mode must keep plan constraints when social context is huge."""

from __future__ import annotations

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway.context_limits import lite_append_max_chars
from presence_ui.gateway.prompt_block_safe import truncate_lite_turn_delta
from presence_ui.services.llm import build_social_turn_delta


def _ctx(*, block: str) -> InteractionContext:
    return InteractionContext(
        ts="2026-06-25T05:00:00+00:00",
        local_time="2026-06-25T14:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-25T05:00:00+00:00",
            "desires": {},
            "discomforts": {},
            "recent_experiences": [],
            "active_arcs": [],
            "private_reflections": 0,
            "interpretation_shifts": 0,
        },
        response_contract=ResponseContract(),
        prompt_summary="test",
        compact_prompt_block=block,
    )


def _plan(*, must: list[str] | None = None) -> ResponsePlan:
    return ResponsePlan(
        primary_move="answer_directly",
        why_this_move="test",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": True,
            "max_memories_to_surface": 2,
            "avoid_memory_dump": True,
        },
        initiative={"level": "moderate", "allowed_actions": [], "forbidden_actions": []},
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
        must_include=must or ["state 水曜午前が定例 directly"],
        must_avoid=["meta narration like （記憶を検索中）"],
    )


def test_build_social_turn_delta_puts_must_include_first() -> None:
    delta = build_social_turn_delta(ctx=_ctx(block="[schedule_facts]\n水曜午前"), plan=_plan())
    assert delta.startswith("[Must include]")
    assert delta.index("[Must include]") < delta.index("[Social context]")


def test_truncate_lite_turn_delta_preserves_must_include() -> None:
    huge = "x" * 5000
    delta = build_social_turn_delta(
        ctx=_ctx(block=f"[schedule_facts]\n水曜午前\n{huge}"),
        plan=_plan(),
    )
    trimmed = truncate_lite_turn_delta(delta, lite_append_max_chars())
    assert "[Must include]" in trimmed
    assert "水曜午前が定例" in trimmed or "水曜午前" in trimmed
    assert "（記憶を検索中）" in trimmed  # in must_avoid
    assert len(trimmed) <= lite_append_max_chars() + 50
