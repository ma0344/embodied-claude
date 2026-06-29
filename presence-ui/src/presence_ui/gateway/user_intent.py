"""IBF intent resolution — what まー wants (not MCP tool names)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from interaction_orchestrator_mcp.schemas import ResponsePlan

from presence_ui.gateway.deterministic_memory import (
    detect_personal_fact_intent,
    detect_remember_intent,
)
from presence_ui.gateway.search_prefetch import detect_web_search_intent
from presence_ui.gateway.see_intent import detect_ptz_intent, detect_see_intent

_SPEECH = re.compile(
    r"(?:\bsay\b|喋|しゃべ|シャベ|声で|読み上げ|しゃべって|喋って|話して)",
    re.IGNORECASE,
)
_EXPLICIT_SAY = re.compile(r"\bsay\b", re.IGNORECASE)
_REMEMBER = re.compile(
    r"(覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて|"
    r"remember\s+forever|remember\s+this|store\s+this)",
    re.IGNORECASE,
)

_SILENT_MOVES = frozenset({"stay_silent", "defer", "quietly_prepare", "write_private_reflection"})


@dataclass(frozen=True, slots=True)
class UserIntent:
    wants_speech: bool
    explicit_say: bool
    wants_observe: bool
    wants_remember: bool
    wants_web_search: bool = False


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
    """Rule-based intent for explicit body requests (v0: speech / observe / remember)."""
    line = (text or "").strip()
    if not line:
        return UserIntent(
            wants_speech=False,
            explicit_say=False,
            wants_observe=False,
            wants_remember=False,
            wants_web_search=False,
        )
    wants_speech = bool(_SPEECH.search(line))
    explicit_say = bool(_EXPLICIT_SAY.search(line))
    wants_observe = bool(detect_see_intent(line) or detect_ptz_intent(line))
    wants_remember = bool(
        detect_remember_intent(line)
        or detect_personal_fact_intent(line)
        or _REMEMBER.search(line)
    )
    return UserIntent(
        wants_speech=wants_speech,
        explicit_say=explicit_say,
        wants_observe=wants_observe,
        wants_remember=wants_remember,
        wants_web_search=detect_web_search_intent(line),
    )


def _speak_body(*, intent: UserIntent, plan: ResponsePlan) -> tuple[bool, list[str]]:
    if not intent.wants_speech:
        return False, []

    if plan.primary_move in _SILENT_MOVES:
        return False, [
            "[Action] User asked for speech but social plan selected "
            f"{plan.primary_move}. Reply in text only; do NOT call mcp__tts__say."
        ]

    quiet = bool(plan.boundary and plan.boundary.quiet_hours_active)
    if quiet:
        return False, [
            "[Action] User asked for speech but quiet hours are active. "
            "Text reply only; gateway will not play audio."
        ]

    forbidden = set(plan.initiative.forbidden_actions or [])
    if "talk_to_companion" in forbidden or "camera_speaker_audio" in forbidden:
        return False, [
            "[Action] Speech is forbidden this turn (boundary/initiative). "
            "Do NOT call mcp__tts__say."
        ]

    if plan.voice and plan.voice.speak is False and not intent.explicit_say:
        return False, []

    return True, [
        "[Action] Gateway will speak your reply on Surface after you finish. "
        "Do NOT call mcp__tts__say — text reply only, then gateway handles audio."
    ]


def merge_intent_with_plan(
    *,
    intent: UserIntent,
    plan: ResponsePlan,
    vision_prefetch_done: bool = False,
    web_search_prefetch_done: bool = False,
    url_prefetch_done: bool = False,
    calendar_prefetch_done: bool = False,
    calendar_write_done: bool = False,
    calendar_confirm_pending: bool = False,
    remember_saved: bool = False,
) -> EffectiveTurnBody:
    """Combine まーの要求 with plan/boundary — plan can veto gateway body actions."""
    notes: list[str] = []
    gateway_speak, speak_notes = _speak_body(intent=intent, plan=plan)
    notes.extend(speak_notes)

    if vision_prefetch_done:
        notes.append(
            "[Action] Gateway already ran vision_prefetch. "
            "Do NOT call mcp__wifi-cam__see, look_*, or look_around."
        )
    elif intent.wants_observe and plan.primary_move in _SILENT_MOVES:
        notes.append(
            "[Action] User asked to see/move camera but social plan selected "
            f"{plan.primary_move}. Text reply only; do NOT call wifi-cam MCP tools."
        )

    if web_search_prefetch_done:
        notes.append(
            "[Action] Gateway already ran web_search_prefetch. "
            "Do NOT call WebSearch/WebFetch; page facts only from url_prefetch excerpt."
        )

    if url_prefetch_done:
        notes.append(
            "[Action] Gateway already ran url_prefetch. "
            "Describe page contents ONLY from excerpt; do NOT infer from snippets or training data."
        )

    if calendar_prefetch_done:
        notes.append(
            "[Action] Gateway already ran calendar_prefetch. "
            "Use [calendar_prefetch] events as authoritative for schedule; do NOT invent events."
        )

    if calendar_write_done:
        notes.append(
            "[Action] Gateway already ran calendar_write. "
            "Use [calendar_write_result] as authoritative for create/update; "
            "do NOT claim success without status=ok in that block."
        )

    if calendar_confirm_pending:
        notes.append(
            "[Action] Gateway has a pending calendar confirm in [calendar_confirm_pending]. "
            "Ask まー to confirm or clarify; do NOT write until a later OK turn."
        )

    if remember_saved:
        notes.append(
            "[Action] Gateway saved to long-term memory. Do NOT call mcp__memory__remember."
        )
    elif intent.wants_remember and plan.primary_move in _SILENT_MOVES:
        notes.append(
            "[Action] User asked to remember but social plan selected "
            f"{plan.primary_move}. Do NOT claim you saved; text reply only."
        )

    speak_action_note = "\n\n".join(notes) if notes else None
    return EffectiveTurnBody(
        gateway_speak_after_reply=gateway_speak,
        speak_action_note=speak_action_note,
    )
