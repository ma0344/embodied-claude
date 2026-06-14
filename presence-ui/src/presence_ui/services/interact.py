"""Chat send flow: ingest → compose → plan → act → record."""

from __future__ import annotations

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import (
    ComposeInteractionContextInput,
    PlanResponseInput,
    RecordAgentExperienceInput,
)
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.schemas import ChatMessage, ChatSendResponse
from presence_ui.gateway.room_ingest import ingest_agent_turn, ingest_human_turn
from presence_ui.services.llm import generate_koyori_reply
from presence_ui.services.sessions import get_session, touch_session

_SILENT_MOVES = frozenset({"stay_silent", "defer", "quietly_prepare"})
_SPEAKING_MOVES = frozenset(
    {
        "answer_directly",
        "answer_with_empathy",
        "ask_one_clarifying_question",
        "act_autonomously",
        "compose_letter",
        "post_socially_after_review",
    }
)


def _ingest_human_message(*, person_id: str, session_id: str, text: str, ts: str) -> str:
    return ingest_human_turn(
        person_id=person_id,
        session_id=session_id,
        text=text,
        ts=ts,
    )


def _ingest_koyori_message(*, person_id: str, session_id: str, text: str, ts: str) -> str:
    return ingest_agent_turn(
        person_id=person_id,
        session_id=session_id,
        text=text,
        ts=ts,
    )


def _compose_and_plan(
    *,
    person_id: str,
    session_id: str,
    text: str,
):
    stores = get_stores()
    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id,
            channel="chat",
            user_text=text,
            session_id=session_id,
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
            user_text=text,
        )
    )
    return ctx, plan


def _record_response(
    *,
    person_id: str,
    session_id: str,
    summary: str,
    ts: str,
    related_event_ids: list[str] | None = None,
) -> None:
    stores = get_stores()
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=ts,
            person_id=person_id,
            kind="agent_response",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=related_event_ids or [],
        )
    )


async def handle_chat_send(
    *,
    message: str,
    session_id: str,
    person_id: str = "ma",
) -> ChatSendResponse:
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if get_session(session_id=session_id, person_id=person_id) is None:
        raise ValueError(f"unknown session: {session_id}")

    ts = utc_now()
    user_event_id = _ingest_human_message(
        person_id=person_id, session_id=session_id, text=text, ts=ts
    )
    user_message = ChatMessage(
        sender="ma",
        message=text,
        timestamp=ts,
        message_id=user_event_id,
        session_id=session_id,
    )
    touch_session(session_id=session_id, person_id=person_id, first_human_text=text)

    ctx, plan = _compose_and_plan(
        person_id=person_id,
        session_id=session_id,
        text=text,
    )

    if plan.primary_move in _SILENT_MOVES:
        return ChatSendResponse(
            session_id=session_id,
            user_message=user_message,
            koyori_message=None,
            silent=True,
            plan_move=plan.primary_move,
        )

    if plan.primary_move not in _SPEAKING_MOVES:
        return ChatSendResponse(
            session_id=session_id,
            user_message=user_message,
            koyori_message=None,
            silent=True,
            plan_move=plan.primary_move,
        )

    reply_text = await generate_koyori_reply(user_text=text, ctx=ctx, plan=plan)
    reply_ts = utc_now()
    koyori_event_id = _ingest_koyori_message(
        person_id=person_id,
        session_id=session_id,
        text=reply_text,
        ts=reply_ts,
    )
    koyori_message = ChatMessage(
        sender="koyori",
        message=reply_text,
        timestamp=reply_ts,
        message_id=koyori_event_id,
        session_id=session_id,
    )
    touch_session(session_id=session_id, person_id=person_id)
    _record_response(
        person_id=person_id,
        session_id=session_id,
        summary=reply_text,
        ts=reply_ts,
        related_event_ids=[user_event_id, koyori_event_id],
    )

    return ChatSendResponse(
        session_id=session_id,
        user_message=user_message,
        koyori_message=koyori_message,
        silent=False,
        plan_move=plan.primary_move,
    )
