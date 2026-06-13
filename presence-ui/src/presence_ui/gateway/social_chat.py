"""POST /api/chat interceptor — apply sociality before forwarding to Claude Code."""

from __future__ import annotations

import json
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
    detect_remember_intent,
    memory_saved_prompt_note,
    persist_remember_intent,
)
from presence_ui.gateway.room_events import activity_event
from presence_ui.services.llm import build_social_prompt_prefix

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


def _ingest_human(*, person_id: str, session_id: str | None, text: str) -> None:
    stores = get_stores()
    stores.social_state.ingest_social_event(
        {
            "ts": utc_now(),
            "source": "room",
            "kind": "human_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        }
    )


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


def intercept_chat_request(*, payload: dict, person_id: str = "ma") -> ChatInterceptResult:
    """Run compose/plan; enrich message or block forward on silent moves."""
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("message must not be empty")

    session_id = payload.get("sessionId")
    session_key = str(session_id) if session_id else None

    _ingest_human(person_id=person_id, session_id=session_key, text=message)

    gateway_events: list[dict[str, Any]] = []
    memory_notes: list[str] = []
    remember_intent = detect_remember_intent(message)
    if remember_intent:
        gateway_events.append(
            activity_event(
                kind="remember",
                label="記憶に保存してる…",
                detail=remember_intent.content[:120],
            )
        )
        outcome = persist_remember_intent(remember_intent)
        if outcome.ok:
            label = "もう覚えてある" if outcome.duplicate else "記憶に保存した"
            gateway_events.append(
                activity_event(kind="remember", label=label, detail=outcome.content[:120], ok=True)
            )
        else:
            gateway_events.append(
                activity_event(
                    kind="remember",
                    label="記憶の保存に失敗",
                    detail=outcome.error or "unknown",
                    ok=False,
                )
            )
        memory_notes.append(memory_saved_prompt_note(outcome))

    stores = get_stores()
    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id,
            channel="chat",
            user_text=message,
            session_id=session_key,
            claude_session_resume=bool(session_key),
            include_private=True,
            max_chars=10000,
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

    prefix = build_social_prompt_prefix(ctx=ctx, plan=plan)
    if memory_notes:
        note = "\n\n".join(memory_notes)
        prefix = f"{prefix}\n\n{note}" if prefix else note
    enriched = payload.copy()
    enriched["message"] = message
    if prefix:
        enriched["appendSystemPrompt"] = prefix
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
