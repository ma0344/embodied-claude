"""POST /api/chat interceptor — apply sociality before forwarding to Claude Code."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import (
    ComposeInteractionContextInput,
    PlanResponseInput,
    RecordAgentExperienceInput,
)
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.gateway.deterministic_memory import (
    detect_memory_list_request,
    detect_personal_fact_intent,
    detect_remember_intent,
    fetch_memory_list,
    memory_list_prefetch_note,
    memory_saved_prompt_note,
    persist_remember_intent,
)
from presence_ui.gateway.direct_actions import (
    direct_actions_enabled,
    write_private_reflection_direct,
)
from presence_ui.gateway.room_events import progress_event
from presence_ui.gateway.room_ingest import ingest_human_turn_async
from presence_ui.gateway.open_loop_dismiss import dismiss_note, dismiss_progress_label
from presence_ui.gateway.prompt_injection import apply_gateway_prompt_injection
from presence_ui.services.llm import build_social_turn_delta

# write_private_reflection must still reach Claude Code so it can call
# mcp__sociality__append_private_reflection (voice.speak=false in the plan).
_SILENT_MOVES = frozenset({"stay_silent", "defer", "quietly_prepare"})

# Kiosk (:8090) has no webui permission UI; auto-accept edits within allow rules.
_DEFAULT_PERMISSION_MODE = "acceptEdits"


@dataclass(slots=True)
class ChatInterceptResult:
    forward: bool
    payload: dict | None = None
    plan_move: str | None = None
    user_text: str | None = None
    gateway_events: list[dict[str, Any]] = field(default_factory=list)
    direct_action_summary: str | None = None


def _ingest_human_sync(*, person_id: str, session_id: str | None, text: str):
    from presence_ui.gateway.room_ingest import ingest_human_turn

    _event_id, outcome = ingest_human_turn(
        person_id=person_id, session_id=session_id, text=text
    )
    return outcome


def _record_experience(*, person_id: str, summary: str) -> None:
    stores = get_stores()
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_response",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
        )
    )


def intercept_chat_request(
    *,
    payload: dict,
    person_id: str = "ma",
    lite: bool = False,
    vision_prefetch: str | None = None,
) -> ChatInterceptResult:
    """Sync wrapper (tests / thread offload). Native chat uses async variant."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            intercept_chat_request_async(
                payload=payload,
                person_id=person_id,
                lite=lite,
                vision_prefetch=vision_prefetch,
            )
        )
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("message must not be empty")
    session_id = payload.get("sessionId")
    session_key = str(session_id) if session_id else None
    dismiss_outcome = _ingest_human_sync(
        person_id=person_id, session_id=session_key, text=message
    )
    return _finish_intercept_chat_request(
        payload=payload,
        person_id=person_id,
        lite=lite,
        vision_prefetch=vision_prefetch,
        message=message,
        session_key=session_key,
        dismiss_outcome=dismiss_outcome,
    )


async def intercept_chat_request_async(
    *,
    payload: dict,
    person_id: str = "ma",
    lite: bool = False,
    vision_prefetch: str | None = None,
) -> ChatInterceptResult:
    """Run compose/plan; enrich message or block forward on silent moves."""
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("message must not be empty")

    session_id = payload.get("sessionId")
    session_key = str(session_id) if session_id else None
    dismiss_outcome = (
        await ingest_human_turn_async(
            person_id=person_id, session_id=session_key, text=message
        )
    )[1]
    return _finish_intercept_chat_request(
        payload=payload,
        person_id=person_id,
        lite=lite,
        vision_prefetch=vision_prefetch,
        message=message,
        session_key=session_key,
        dismiss_outcome=dismiss_outcome,
    )


def _finish_intercept_chat_request(
    *,
    payload: dict,
    person_id: str,
    lite: bool,
    vision_prefetch: str | None,
    message: str,
    session_key: str | None,
    dismiss_outcome,
) -> ChatInterceptResult:
    compose_max_chars = (
        int(os.getenv("PRESENCE_LITE_COMPOSE_MAX_CHARS", "1200"))
        if lite
        else 10000
    )

    gateway_events: list[dict[str, Any]] = []
    memory_notes: list[str] = []
    if dismiss_outcome.any:
        memory_notes.append(
            dismiss_note(
                closed_loops=dismiss_outcome.closed_loops,
                cancelled_commitments=dismiss_outcome.cancelled_commitments,
            )
        )
        gateway_events.append(
            progress_event(
                phase="relationship",
                label=dismiss_progress_label(
                    closed_loops=dismiss_outcome.closed_loops,
                    cancelled_commitments=dismiss_outcome.cancelled_commitments,
                ),
            )
        )
    remember_intent = detect_remember_intent(message) or detect_personal_fact_intent(message)
    if remember_intent:
        outcome = persist_remember_intent(remember_intent)
        if outcome.ok:
            label = "もう覚えてある" if outcome.duplicate else "記憶に保存した"
            gateway_events.append(
                progress_event(phase="remember", label=label)
            )
        else:
            gateway_events.append(
                progress_event(phase="remember", label="記憶の保存に失敗")
            )
        memory_notes.append(memory_saved_prompt_note(outcome))

    list_request = detect_memory_list_request(message)
    if list_request:
        rows = fetch_memory_list(
            limit=list_request.limit,
            oldest_first=list_request.oldest_first,
        )
        memory_notes.append(
            memory_list_prefetch_note(
                rows,
                limit=list_request.limit,
                oldest_first=list_request.oldest_first,
            )
        )
        gateway_events.append(
            progress_event(phase="memory_list", label=f"記憶 {len(rows)} 件を読み込んだ")
        )

    if list_request and memory_notes:
        turn_delta = "\n\n".join(memory_notes)
        turn_delta = (
            f"{turn_delta}\n\n"
            "[Gateway directive — not for the user]\n"
            "Memory list is in [memory_list_prefetch] above. "
            "Do NOT call MCP/Skill. Show the numbered list as your reply."
        )
        enriched_message, append_prompt = apply_gateway_prompt_injection(
            user_text=message,
            turn_delta=turn_delta,
        )
        enriched = payload.copy()
        enriched["message"] = enriched_message
        if append_prompt:
            enriched["appendSystemPrompt"] = append_prompt
        if not enriched.get("permissionMode"):
            enriched["permissionMode"] = _DEFAULT_PERMISSION_MODE
        return ChatInterceptResult(
            forward=True,
            payload=enriched,
            plan_move="answer_directly",
            user_text=message,
            gateway_events=gateway_events,
        )

    stores = get_stores()
    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id,
            channel="chat",
            user_text=message,
            session_id=session_key,
            claude_session_resume=bool(session_key),
            include_private=not lite,
            max_chars=compose_max_chars,
        ),
        social_state_store=stores.social_state,
        relationship_store=stores.relationship,
        joint_attention_store=stores.joint_attention,
        boundary_store=stores.boundary,
        self_narrative_store=stores.self_narrative,
        orchestrator_store=stores.orchestrator,
        policy_timezone=stores.policy_timezone,
    )
    plan = plan_response(
        PlanResponseInput(
            interaction_context=ctx,
            user_text=message,
        )
    )

    if plan.primary_move in _SILENT_MOVES:
        return ChatInterceptResult(
            forward=False,
            plan_move=plan.primary_move,
            user_text=message,
            gateway_events=gateway_events,
        )

    if (
        direct_actions_enabled()
        and plan.primary_move == "write_private_reflection"
    ):
        stores = get_stores()
        outcome = write_private_reflection_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
        )
        gateway_events.extend(outcome.events)
        return ChatInterceptResult(
            forward=False,
            plan_move=plan.primary_move,
            user_text=message,
            gateway_events=gateway_events,
            direct_action_summary=outcome.summary,
        )

    turn_delta = build_social_turn_delta(ctx=ctx, plan=plan)
    if memory_notes:
        note = "\n\n".join(memory_notes)
        turn_delta = f"{turn_delta}\n\n{note}" if turn_delta else note
    if lite and turn_delta:
        cap = int(os.getenv("PRESENCE_LITE_APPEND_MAX_CHARS", "2500"))
        if len(turn_delta) > cap:
            turn_delta = turn_delta[: cap - 1].rstrip() + "…"
    extra_append = ""
    if remember_intent and memory_notes and "[memory_save_failed]" in memory_notes[0]:
        extra_append = (
            "[Gateway directive — not for the user]\n"
            "Remember save FAILED. Do NOT say you saved or 刻み込んだ; tell the user it failed."
        )
    enriched_message, append_prompt = apply_gateway_prompt_injection(
        user_text=message,
        turn_delta=turn_delta,
        extra_append=extra_append,
    )
    if vision_prefetch:
        # After user utterance — KV-friendly (variable caption at tail, like stable append).
        enriched_message = f"{enriched_message.rstrip()}\n\n{vision_prefetch.strip()}"
    enriched = payload.copy()
    enriched["message"] = enriched_message
    if append_prompt:
        enriched["appendSystemPrompt"] = append_prompt
    if not enriched.get("permissionMode"):
        enriched["permissionMode"] = _DEFAULT_PERMISSION_MODE

    return ChatInterceptResult(
        forward=True,
        payload=enriched,
        plan_move=plan.primary_move,
        user_text=message,
        gateway_events=gateway_events,
    )


async def stream_silent_response(*, plan_move: str) -> AsyncIterator[bytes]:
    """NDJSON stream when sociality blocks forwarding to Claude Code."""
    chunk = json.dumps({"type": "social_silent", "plan_move": plan_move}, ensure_ascii=False)
    yield (chunk + "\n").encode("utf-8")
    yield b'{"type":"done"}\n'


async def stream_direct_action_response(
    *,
    plan_move: str,
    summary: str,
) -> AsyncIterator[bytes]:
    """NDJSON when gateway executed a direct action (no Claude forward)."""
    payload = {
        "type": "gateway_direct",
        "plan_move": plan_move,
        "summary": summary,
    }
    yield (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    yield b'{"type":"done"}\n'
