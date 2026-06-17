"""Tests for IBF user intent resolution."""

from __future__ import annotations

from interaction_orchestrator_mcp.schemas import (
    BoundaryHint,
    InitiativeHint,
    ResponsePlan,
    ToneHint,
    VoiceHint,
)

from presence_ui.gateway.user_intent import (
    merge_intent_with_plan,
    resolve_user_intent,
)


def _plan(
    *,
    move: str = "answer_directly",
    quiet: bool = False,
    forbidden: list[str] | None = None,
    speak: bool = False,
) -> ResponsePlan:
    return ResponsePlan(
        primary_move=move,  # type: ignore[arg-type]
        why_this_move="test",
        tone=ToneHint(warmth=0.5, directness=0.7, playfulness=0.2, pace="steady"),
        memory_use={
            "use_specific_memory": False,
            "max_memories_to_surface": 1,
            "avoid_memory_dump": True,
        },
        initiative=InitiativeHint(
            level="moderate",
            allowed_actions=[],
            forbidden_actions=forbidden or [],
        ),
        boundary=BoundaryHint(
            quiet_hours_active=quiet,
            privacy_sensitive=False,
            notes=[],
        ),
        voice=VoiceHint(speak=speak, channel="local", max_sentences=3),
    )


def test_resolve_speech_from_say_keyword() -> None:
    intent = resolve_user_intent("何か say でしゃべって")
    assert intent.wants_speech is True
    assert intent.explicit_say is True


def test_resolve_speech_from_shaberu() -> None:
    intent = resolve_user_intent("ちょっと喋ってみて")
    assert intent.wants_speech is True


def test_merge_allows_gateway_speak_when_explicit() -> None:
    intent = resolve_user_intent("say で")
    plan = _plan(speak=False)
    body = merge_intent_with_plan(intent=intent, plan=plan)
    assert body.gateway_speak_after_reply is True
    assert body.speak_action_note
    assert "Do NOT call mcp__tts__say" in body.speak_action_note


def test_merge_blocks_speak_on_quiet_hours() -> None:
    intent = resolve_user_intent("say で喋って")
    plan = _plan(quiet=True)
    body = merge_intent_with_plan(intent=intent, plan=plan)
    assert body.gateway_speak_after_reply is False
    assert "quiet hours" in (body.speak_action_note or "")


def test_merge_blocks_speak_on_stay_silent() -> None:
    intent = resolve_user_intent("声で")
    plan = _plan(move="stay_silent")
    body = merge_intent_with_plan(intent=intent, plan=plan)
    assert body.gateway_speak_after_reply is False
