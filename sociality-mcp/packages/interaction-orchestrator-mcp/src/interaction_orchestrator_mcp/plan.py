"""plan_response — pick a social move and the constraints around it."""

from __future__ import annotations

import re
from typing import Any

from .memory_bridge import append_memory_bridge_plan_constraints
from .recall_query import (
    extract_schedule_facts,
    is_temporal_question,
    temporal_schedule_contract_enabled,
)
from .schemas import (
    BoundaryHint,
    InitiativeHint,
    InteractionContext,
    MemoryUseHint,
    PlanResponseInput,
    PrimaryMove,
    ResponsePlan,
    ToneHint,
    VoiceHint,
)
from .shift_temporal import append_bare_greeting_plan_constraints, append_shift_plan_constraints

# Quiet hours: inward desires may still run (private DB / recall only).
_QUIET_INWARD_DESIRES = frozenset(
    {"cognitive_load", "identity_coherence", "literary_wander"}
)

_BARE_GREETING_RE = re.compile(
    r"^(?:"
    r"おはよ(?:う(?:さん|う|ございます)?)?|"
    r"おはよう(?:さん|う|ございます)?|"
    r"こんにちは|こんばんは|"
    r"ただいま|おやすみ|"
    r"hi|hello|hey|morning|good\s+morning"
    r")[!！?？。.…~\s]*$",
    re.I,
)


def _is_bare_greeting(user_text: str) -> bool:
    return bool(_BARE_GREETING_RE.match((user_text or "").strip()))


def inward_evening_from_context(ctx: InteractionContext) -> bool:
    """20:00–05:59 local — matches desire_updater literary allostasis (LW-2).

    ``quiet_hours`` in socialPolicy may start at midnight; evening literary
    wandering should still win over observe/web before that.
    """
    raw = (ctx.local_time or ctx.ts or "").strip()
    if not raw:
        return False
    try:
        from datetime import datetime

        local = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return local.hour >= 20 or local.hour < 6


def inward_autonomous_window(*, ctx: InteractionContext, quiet_active: bool) -> bool:
    return quiet_active or inward_evening_from_context(ctx)


def plan_response(payload: PlanResponseInput) -> ResponsePlan:
    """Compute a response plan from an interaction context.

    The logic is intentionally deterministic and shallow: it picks the
    strongest applicable rule and exposes it. The caller (Claude) is then
    responsible for composing actual language under these constraints.
    """

    ctx = payload.interaction_context
    social = ctx.social_state or {}
    phase = str(social.get("interaction_phase") or "idle")
    availability = str(social.get("availability") or "unknown")
    # Quiet = either policy clock-time quiet hours, OR social state itself
    # has already classified the person as do_not_interrupt (e.g. because the
    # most recent evidence lands inside the policy's late-night window).
    quiet_active = (
        any("quiet hours are active" in hint for hint in ctx.boundary_hints)
        or availability == "do_not_interrupt"
    )
    inward = inward_autonomous_window(ctx=ctx, quiet_active=quiet_active)

    user_text = (payload.user_text or "").strip()
    is_autonomous = not user_text

    primary_move, why = _pick_primary_move(
        ctx=ctx,
        user_text=user_text,
        phase=phase,
        availability=availability,
        quiet_active=quiet_active,
        inward_active=inward,
        is_autonomous=is_autonomous,
    )

    tone = _pick_tone(primary_move=primary_move, quiet_active=quiet_active)
    memory_use = _pick_memory_use(primary_move=primary_move, ctx=ctx)
    initiative = _pick_initiative(
        primary_move=primary_move,
        quiet_active=quiet_active,
        inward_active=inward,
        ctx=ctx,
    )
    boundary = _pick_boundary(ctx=ctx, quiet_active=quiet_active)
    voice = _pick_voice(primary_move=primary_move, quiet_active=quiet_active)

    must_include, must_avoid = _pick_must_lists(
        primary_move=primary_move,
        ctx=ctx,
        user_text=user_text,
    )

    followup = _pick_followup(
        primary_move=primary_move,
        ctx=ctx,
        user_text=user_text,
    )

    return ResponsePlan(
        primary_move=primary_move,
        why_this_move=why,
        tone=tone,
        memory_use=memory_use,
        relationship_use={
            "reference_open_loops": bool(ctx.open_loops),
            "reference_commitments": bool(ctx.commitments_due),
        },
        initiative=initiative,
        boundary=boundary,
        voice=voice,
        must_include=must_include,
        must_avoid=must_avoid,
        followup_action=followup,
    )


def _pick_primary_move(
    *,
    ctx: InteractionContext,
    user_text: str,
    phase: str,
    availability: str,
    quiet_active: bool,
    inward_active: bool,
    is_autonomous: bool,
) -> tuple[PrimaryMove, str]:
    if is_autonomous:
        if inward_active:
            dominant = ctx.agent_state.dominant_desire
            if dominant in _QUIET_INWARD_DESIRES or inward_evening_from_context(ctx):
                return (
                    "act_autonomously",
                    "Inward window — literary / private moves over outward camera or web.",
                )
            return (
                "write_private_reflection",
                "Autonomous tick during inward hours — prefer a private note over any speech.",
            )
        if ctx.commitments_due:
            return (
                "act_autonomously",
                "Due commitment(s) — remind companion before other autonomous moves.",
            )
        if ctx.agent_state.dominant_desire:
            return (
                "act_autonomously",
                "Autonomous tick with a dominant desire — one bounded action fits.",
            )
        return (
            "quietly_prepare",
            "Autonomous tick with no strong signal — prepare quietly without nudging.",
        )

    if phase == "awaiting_reply":
        return (
            "answer_directly",
            "The human has a recent direct question; a reply is socially appropriate.",
        )
    if availability == "do_not_interrupt" and quiet_active:
        return (
            "defer",
            "Policy quiet hours plus do_not_interrupt availability — defer non-urgent moves.",
        )
    if availability == "do_not_interrupt":
        return (
            "stay_silent",
            "Availability signals do_not_interrupt; staying silent avoids social cost.",
        )
    if ctx.loops_due_for_check and user_text:
        return (
            "answer_directly",
            "Post-deadline open loop — greet or reply and naturally check if the task is done.",
        )
    if user_text.endswith(("?", "？")) or "どう" in user_text or "教えて" in user_text:
        return (
            "answer_directly",
            "The user message reads as a question; a direct answer is the right move.",
        )
    if len(user_text) < 8 and phase != "ongoing":
        return (
            "ask_one_clarifying_question",
            "Short opaque input with no ongoing context — a single clarifying question helps.",
        )
    return (
        "answer_directly",
        "Default: respond directly with the prepared response contract.",
    )


def _pick_tone(*, primary_move: PrimaryMove, quiet_active: bool) -> ToneHint:
    warmth = 0.55
    directness = 0.75
    playfulness = 0.2
    pace: str = "steady"
    if primary_move == "answer_directly":
        directness = 0.85
    if primary_move == "answer_with_empathy":
        warmth = 0.8
        directness = 0.55
    if primary_move == "write_private_reflection":
        warmth = 0.45
        directness = 0.6
        playfulness = 0.1
        pace = "slow"
    if primary_move == "stay_silent":
        warmth = 0.3
        directness = 0.3
        playfulness = 0.1
        pace = "slow"
    if quiet_active:
        playfulness = min(playfulness, 0.15)
        pace = "slow"
    return ToneHint(warmth=warmth, directness=directness, playfulness=playfulness, pace=pace)


def _pick_memory_use(
    *, primary_move: PrimaryMove, ctx: InteractionContext
) -> MemoryUseHint:
    mentionable = [m for m in ctx.relevant_memories if m.use_policy == "mentionable"]
    has_mentionable = bool(mentionable)

    if primary_move in {"write_private_reflection", "compose_letter"}:
        return MemoryUseHint(
            use_specific_memory=has_mentionable or bool(ctx.relevant_memories),
            max_memories_to_surface=min(3, max(1, len(ctx.relevant_memories) or 2)),
            avoid_memory_dump=True,
        )
    if has_mentionable:
        # Surface hits directly; let the model quote them.
        return MemoryUseHint(
            use_specific_memory=True,
            max_memories_to_surface=min(3, len(mentionable)),
            avoid_memory_dump=True,
        )
    if ctx.open_loops or ctx.commitments_due:
        return MemoryUseHint(
            use_specific_memory=True,
            max_memories_to_surface=2,
            avoid_memory_dump=True,
        )
    return MemoryUseHint(
        use_specific_memory=False,
        max_memories_to_surface=1,
        avoid_memory_dump=True,
    )


def _pick_initiative(
    *,
    primary_move: PrimaryMove,
    quiet_active: bool,
    inward_active: bool,
    ctx: InteractionContext,
) -> InitiativeHint:
    forbidden: list[str] = []
    allowed: list[str] = []
    level: str = "moderate"

    if inward_active:
        forbidden.extend(
            [
                "camera_speaker_audio",
                "speak_loudly",
                "public_post_without_review",
                "nudge_human",
            ]
        )
        allowed.extend(
            ["write_private_reflection", "compose_letter", "quietly_observe"]
        )
        level = "low"

    if primary_move == "act_autonomously":
        if ctx.commitments_due and not inward_active:
            allowed.append("remind_commitment")
        dominant = ctx.agent_state.dominant_desire
        if not inward_active:
            if dominant == "look_outside":
                allowed.append("camera_look_outside")
            if dominant == "observe_room":
                allowed.append("camera_look_around")
            if dominant == "browse_curiosity":
                allowed.append("web_search")
        if inward_active:
            allowed.append("read_aozora_passage")
            allowed.append("reflect_on_aozora_passage")
            allowed.append("close_aozora_reading")
            allowed.append("think_or_discuss_topic")
            allowed.append("web_search")  # LW-7 followup_query + inward fallback
        if dominant == "identity_coherence":
            allowed.append("recall_memories")
        if dominant == "cognitive_load" and not inward_active:
            allowed.append("think_or_discuss_topic")
        if dominant == "miss_companion":
            if inward_active:
                allowed.append("write_private_reflection")
                forbidden.append("talk_to_companion")
            else:
                allowed.append("talk_to_companion")
        level = "low" if inward_active else "moderate"

    if primary_move == "stay_silent":
        level = "none"
    if primary_move == "defer":
        level = "low"

    escalation = (ctx.somatic_state or {}).get("escalation") or {}
    esc_level = str(escalation.get("level") or "none")
    if esc_level == "critical" and not quiet_active:
        allowed.append("request_human_help")
        allowed.append("nudge_human")
        level = "high"
    elif esc_level == "elevated" and primary_move in {
        "answer_directly",
        "answer_with_empathy",
        "act_autonomously",
    }:
        allowed.append("request_human_help")

    # de-duplicate while preserving order
    seen = set()
    allowed = [a for a in allowed if not (a in seen or seen.add(a))]
    seen.clear()
    forbidden = [a for a in forbidden if not (a in seen or seen.add(a))]
    return InitiativeHint(level=level, allowed_actions=allowed, forbidden_actions=forbidden)


def _pick_boundary(
    *, ctx: InteractionContext, quiet_active: bool
) -> BoundaryHint:
    notes: list[str] = []
    privacy_sensitive = False
    for hint in ctx.boundary_hints:
        notes.append(hint)
        if "privacy" in hint.lower():
            privacy_sensitive = True
    return BoundaryHint(
        quiet_hours_active=quiet_active,
        privacy_sensitive=privacy_sensitive,
        notes=notes,
    )


def _pick_voice(*, primary_move: PrimaryMove, quiet_active: bool) -> VoiceHint | None:
    if quiet_active or primary_move in {
        "stay_silent",
        "defer",
        "write_private_reflection",
        "compose_letter",
    }:
        return VoiceHint(speak=False, channel="local", max_sentences=0)
    if primary_move in {"answer_directly", "answer_with_empathy"}:
        return VoiceHint(speak=False, channel="local", max_sentences=3)
    return None


def _pick_must_lists(
    *,
    primary_move: PrimaryMove,
    ctx: InteractionContext,
    user_text: str,
) -> tuple[list[str], list[str]]:
    must_include: list[str] = []
    must_avoid = list(ctx.response_contract.avoid)

    if primary_move == "answer_directly":
        must_include.append("direct, contract-aware answer")
    schedule_answer = (
        extract_schedule_facts(
            user_text,
            [m.content for m in ctx.relevant_memories if m.use_policy == "mentionable"]
            + list((ctx.person_model or {}).get("profile_gists") or []),
        )
        if user_text
        and is_temporal_question(user_text)
        and temporal_schedule_contract_enabled()
        else []
    )
    if ctx.session_history and primary_move in {
        "answer_directly",
        "answer_with_empathy",
        "ask_one_clarifying_question",
    }:
        must_include.append(
            "continue THIS room's thread — reference preceding turns in session_history; "
            "do not cold-start or impersonate a different persona"
        )
    if ctx.memory_bridge_lines:
        append_memory_bridge_plan_constraints(
            must_include=must_include,
            bridge_lines=ctx.memory_bridge_lines,
            bridge_keywords=ctx.memory_bridge_keywords,
            primary_move=primary_move,
        )
    user_stripped = (user_text or "").strip()
    bare_greeting = _is_bare_greeting(user_stripped)
    today_open_topics = [loop.topic[:80] for loop in ctx.open_loops if loop.topic.strip()]

    if ctx.open_loops and primary_move in {"answer_directly", "write_private_reflection"}:
        if not schedule_answer and not bare_greeting:
            must_include.append("reference at least one concrete open loop if relevant")
    pending_dates = [loop for loop in ctx.open_loops if loop.needs_date_confirmation]
    if pending_dates and primary_move in {
        "answer_directly",
        "answer_with_empathy",
        "ask_one_clarifying_question",
    }:
        samples = [
            ", ".join(loop.ambiguous_phrases) or loop.topic[:60]
            for loop in pending_dates[:2]
        ]
        must_include.append(
            "open loop has ambiguous date — ask まー one short question for the "
            f"concrete day (e.g. {samples[0]}); do not infer or anchor yourself"
        )
    if (
        user_stripped
        and is_temporal_question(user_stripped)
        and temporal_schedule_contract_enabled()
        and primary_move in {"answer_directly", "answer_with_empathy"}
    ):
        must_avoid.append(
            "adding schedule items from dream_digest, overnight_inner_voice, "
            "relevant_memories, or interpretation_shifts unless they appear in [open_loops]"
        )
        if today_open_topics:
            joined = "; ".join(today_open_topics[:6])
            must_include.append(
                "temporal schedule question — answer from [open_loops] only: "
                f"{joined}; do not add ghost items from dream or recall"
            )
    if bare_greeting and primary_move != "stay_silent":
        append_bare_greeting_plan_constraints(
            must_include=must_include,
            must_avoid=must_avoid,
            open_loop_topics=today_open_topics,
        )
    elif ctx.agent_state.recent_interpretation_shifts and primary_move != "stay_silent":
        append_shift_plan_constraints(
            must_include=must_include,
            must_avoid=must_avoid,
            shifts=ctx.agent_state.recent_interpretation_shifts,
            user_text=user_text,
            primary_move=primary_move,
            tz_name=ctx.timezone or "Asia/Tokyo",
            is_bare_greeting=_is_bare_greeting,
            is_temporal_question=is_temporal_question,
            temporal_schedule_contract_enabled=temporal_schedule_contract_enabled,
        )
    elif ctx.agent_state.interpretation_shifts >= 1 and primary_move != "stay_silent":
        must_include.append(
            "respect the most recent interpretation shift (do not regress to old interpretation)"
        )
    if primary_move == "write_private_reflection":
        must_include.extend(
            [
                "write as Koyori inner voice (first person うち/私; felt sense OK)",
                "explain why this was a reflection, not a nudge",
            ]
        )
        must_avoid.extend(
            [
                "paste compact_prompt_block or injection tags verbatim",
                "tool names, MCP identifiers, or [gateway_turn_context] blocks",
            ]
        )
    if not user_text and primary_move != "stay_silent":
        must_avoid.append("responding as if the human just spoke")
    somatic = ctx.somatic_state or {}
    pending = somatic.get("pending_unreported") or []
    if pending and primary_move != "stay_silent":
        summaries = [str(p.get("summary") or "")[:80] for p in pending[:3] if p.get("summary")]
        if summaries:
            if primary_move == "write_private_reflection":
                must_include.append(
                    "private reflection may note overnight body state briefly: "
                    + " / ".join(summaries)
                )
            elif primary_move in {"answer_directly", "answer_with_empathy"}:
                must_include.append(
                    "if natural, mention recent body issues to まー in one short line: "
                    + " / ".join(summaries)
                )
    escalation = somatic.get("escalation") or {}
    esc_level = str(escalation.get("level") or "none")
    if esc_level in {"elevated", "critical"} and primary_move != "stay_silent":
        organs = ", ".join(
            str(item.get("organ_ja") or item.get("organ") or "")
            for item in (escalation.get("organs_affected") or [])[:3]
            if item
        )
        if esc_level == "critical":
            must_include.append(
                "health_safety: multiple organs failing"
                + (f" ({organs})" if organs else "")
                + " — explicitly ask まー to check systems in one urgent short line"
            )
        elif primary_move in {"answer_directly", "answer_with_empathy"}:
            must_include.append(
                "multiple body issues detected — ask まー for help if self-remedy failed"
            )
    if (
        user_text
        and is_temporal_question(user_text)
        and temporal_schedule_contract_enabled()
        and primary_move in {"answer_directly", "answer_with_empathy"}
    ):
        schedule_facts = schedule_answer
        if schedule_facts:
            must_include.append(
                "temporal schedule question — state the saved schedule directly: "
                f"{schedule_facts[0]}; do NOT say the date is unknown"
            )
            must_avoid.append(
                "meta narration like （記憶を検索中） or pretending to search memory"
            )
    if (
        ctx.loops_due_for_check
        and user_text
        and primary_move in {"answer_directly", "answer_with_empathy"}
    ):
        due = ctx.loops_due_for_check[0]
        if due.trigger == "ol7_return_signal":
            cue = due.source_utterance or "戻り"
            prompt = (
                "OL7 return-signal — naturally confirm if this task is done "
                f"(one short question): {due.topic[:100]} "
                f"(まー's cue: {cue[:40]})"
            )
        else:
            until = due.until_phrase or "deadline passed"
            prompt = (
                "OL6 post-deadline loop — naturally ask if this task is done "
                f"(one short question): {due.topic[:100]} (until {until})"
            )
        if bare_greeting:
            must_include.append(
                f"{prompt} — weave into the greeting; do not skip the check"
            )
        else:
            must_include.append(prompt)
        must_avoid.append(
            "interrogating every open loop — only the post-deadline item above"
        )
    return must_include, must_avoid


def _pick_followup(
    *, primary_move: PrimaryMove, ctx: InteractionContext, user_text: str = ""
) -> dict[str, Any] | None:
    if (
        ctx.loops_due_for_check
        and user_text
        and primary_move in {"answer_directly", "answer_with_empathy"}
    ):
        due = ctx.loops_due_for_check[0]
        return {
            "kind": "loop_check_asked",
            "loop_id": due.loop_id,
            "topic": due.topic[:120],
            "until_phrase": due.until_phrase,
            "trigger": due.trigger,
            "source_utterance": due.source_utterance,
        }
    if primary_move == "act_autonomously" and ctx.agent_state.dominant_desire:
        return {
            "kind": "satisfy_desire",
            "desire_name": ctx.agent_state.dominant_desire,
            "note": "Call satisfy_desire once after the bounded action completes.",
        }
    if primary_move in {"write_private_reflection", "compose_letter"}:
        return {
            "kind": "record_agent_experience",
            "experience_kind": (
                "agent_private_reflection"
                if primary_move == "write_private_reflection"
                else "agent_file_created"
            ),
        }
    return None
