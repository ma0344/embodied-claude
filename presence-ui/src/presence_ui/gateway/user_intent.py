"""IBF intent resolution — what まー wants (not MCP tool names)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from interaction_orchestrator_mcp.schemas import ResponsePlan

_SPEECH = re.compile(
    r"(?:\bsay\b|喋|しゃべ|シャベ|声で|読み上げ|しゃべって|喋って|話して)",
    re.IGNORECASE,
)
_EXPLICIT_SAY = re.compile(r"\bsay\b", re.IGNORECASE)

_SILENT_MOVES = frozenset({"stay_silent", "defer", "quietly_prepare", "write_private_reflection"})


@dataclass(frozen=True, slots=True)
class UserIntent:
    wants_speech: bool
    explicit_say: bool


@dataclass(frozen=True, slots=True)
class EffectiveTurnBody:
    gateway_speak_after_reply: bool
    speak_action_note: str | None = None


def ibf_gateway_speak_enabled() -> bool:
    return os.getenv("PRESENCE_IBF_GATEWAY_SPEAK", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def resolve_user_intent(text: str) -> UserIntent:
    """Rule-based intent for explicit body requests (v0: speech)."""
    line = (text or "").strip()
    if not line:
        return UserIntent(wants_speech=False, explicit_say=False)
    wants = bool(_SPEECH.search(line))
    explicit = bool(_EXPLICIT_SAY.search(line))
    return UserIntent(wants_speech=wants, explicit_say=explicit)


def merge_intent_with_plan(
    *,
    intent: UserIntent,
    plan: ResponsePlan,
) -> EffectiveTurnBody:
    """Combine まーの要求 with plan/boundary — plan can veto gateway speak."""
    if not intent.wants_speech:
        return EffectiveTurnBody(gateway_speak_after_reply=False)

    if plan.primary_move in _SILENT_MOVES:
        return EffectiveTurnBody(
            gateway_speak_after_reply=False,
            speak_action_note=(
                "[Action] User asked for speech but social plan selected "
                f"{plan.primary_move}. Reply in text only; do NOT call mcp__tts__say."
            ),
        )

    quiet = bool(plan.boundary and plan.boundary.quiet_hours_active)
    if quiet:
        return EffectiveTurnBody(
            gateway_speak_after_reply=False,
            speak_action_note=(
                "[Action] User asked for speech but quiet hours are active. "
                "Text reply only; gateway will not play audio."
            ),
        )

    forbidden = set(plan.initiative.forbidden_actions or [])
    if "talk_to_companion" in forbidden or "camera_speaker_audio" in forbidden:
        return EffectiveTurnBody(
            gateway_speak_after_reply=False,
            speak_action_note=(
                "[Action] Speech is forbidden this turn (boundary/initiative). "
                "Do NOT call mcp__tts__say."
            ),
        )

    if plan.voice and plan.voice.speak is False and not intent.explicit_say:
        return EffectiveTurnBody(gateway_speak_after_reply=False)

    return EffectiveTurnBody(
        gateway_speak_after_reply=True,
        speak_action_note=(
            "[Action] Gateway will speak your reply on Surface after you finish. "
            "Do NOT call mcp__tts__say — text reply only, then gateway handles audio."
        ),
    )
