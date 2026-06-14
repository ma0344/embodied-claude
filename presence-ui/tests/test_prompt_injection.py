"""Gateway KV-stable prompt injection."""

from __future__ import annotations

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponseContract, ResponsePlan

from presence_ui.gateway.prompt_injection import (
    apply_gateway_prompt_injection,
    kv_stable_append_enabled,
)
from presence_ui.services.llm import GATEWAY_STABLE_APPEND, prepend_gateway_turn_context


def _minimal_ctx(*, block: str = "[interaction_context]\nphase=chat") -> InteractionContext:
    return InteractionContext(
        ts="2026-06-10T12:00:00+00:00",
        local_time="2026-06-10T21:00:00+09:00",
        timezone="Asia/Tokyo",
        agent_state={
            "ts": "2026-06-10T12:00:00+00:00",
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


def _minimal_plan(*, move: str = "answer_directly") -> ResponsePlan:
    return ResponsePlan(
        primary_move=move,
        why_this_move="because test",
        tone={"warmth": 0.5, "directness": 0.7, "playfulness": 0.2, "pace": "steady"},
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative={"level": "moderate", "allowed_actions": [], "forbidden_actions": []},
        boundary={"quiet_hours_active": False, "privacy_sensitive": False, "notes": []},
        must_include=["mention 中標津"],
    )


def test_kv_stable_append_default_on(monkeypatch) -> None:
    monkeypatch.delenv("PRESENCE_KV_STABLE_APPEND", raising=False)
    assert kv_stable_append_enabled() is True


def test_stable_append_constant_across_turns() -> None:
    ctx1 = _minimal_ctx(block="[interaction_context]\nturn1 memories")
    ctx2 = _minimal_ctx(block="[interaction_context]\nturn2 different")
    plan = _minimal_plan()
    from presence_ui.services.llm import build_social_turn_delta

    delta1 = build_social_turn_delta(ctx=ctx1, plan=plan)
    delta2 = build_social_turn_delta(ctx=ctx2, plan=plan)
    _, append1 = apply_gateway_prompt_injection(user_text="hello", turn_delta=delta1)
    _, append2 = apply_gateway_prompt_injection(user_text="world", turn_delta=delta2)
    assert append1 == GATEWAY_STABLE_APPEND
    assert append2 == GATEWAY_STABLE_APPEND
    assert append1 == append2


def test_stable_mode_puts_delta_in_user_message() -> None:
    message, append = apply_gateway_prompt_injection(
        user_text="こんばんは",
        turn_delta="[Social context]\nphase=chat",
    )
    assert append == GATEWAY_STABLE_APPEND
    assert message.startswith("[gateway_turn_context")
    assert message.endswith("こんばんは")
    assert "[Social context]" in message


def test_legacy_mode_puts_delta_in_append(monkeypatch) -> None:
    monkeypatch.setenv("PRESENCE_KV_STABLE_APPEND", "0")
    message, append = apply_gateway_prompt_injection(
        user_text="こんばんは",
        turn_delta="[Social context]\ndynamic",
    )
    assert message == "こんばんは"
    assert append == "[Social context]\ndynamic"


def test_prepend_gateway_turn_context_empty_delta() -> None:
    assert prepend_gateway_turn_context(user_text="hi", delta="") == "hi"
