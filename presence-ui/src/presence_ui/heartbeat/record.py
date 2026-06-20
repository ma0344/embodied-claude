"""Close the chat turn loop — remember + schedule next wake."""

from __future__ import annotations

import logging

from interaction_orchestrator_mcp.schemas import (
    ExperienceKind,
    InteractionContext,
    RecordAgentExperienceInput,
    ResponsePlan,
)
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.gateway.direct_actions import satisfy_desire_direct
from presence_ui.gateway.room_ingest import ingest_agent_turn
from presence_ui.heartbeat.schedule import apply_pulse_schedule

logger = logging.getLogger(__name__)

_VALID_EXPERIENCE_KINDS: frozenset[str] = frozenset(
    {
        "agent_response",
        "agent_private_reflection",
        "agent_autonomous_action",
        "agent_observation",
        "agent_social_post",
        "agent_file_created",
        "agent_voice_utterance",
        "user_correction",
        "interpretation_shift",
        "desire_satisfied",
        "boundary_respected",
        "open_loop_progress",
    }
)


def _agent_response_experience_summary(*, user_text: str, reply: str) -> str:
    """Audit line for compose — not verbatim reply (avoids mid-sentence continuation)."""
    utterance = " ".join((user_text or "").split())[:100]
    if utterance:
        return f"Replied to まー ({utterance})"
    preview = " ".join((reply or "").split())[:80]
    return f"Replied to まー ({preview}…)" if preview else "Replied to まー"


def finalize_chat_turn(
    *,
    person_id: str,
    session_id: str | None,
    user_text: str,
    reply_text: str,
    plan: ResponsePlan | None,
    ctx: InteractionContext | None,
) -> list[str]:
    """Record agent turn and schedule next pulse after native chat reply."""
    reply = (reply_text or "").strip()
    if not reply:
        if plan and plan.primary_move:
            apply_pulse_schedule(
                channel="chat",
                plan=plan,
                ctx=ctx,
                action=plan.primary_move,
                reason_suffix="silent_or_empty",
            )
        from presence_ui.heartbeat.interpretation_shift import record_interpretation_shifts

        return record_interpretation_shifts(
            person_id=person_id,
            user_text=user_text,
            reply_text=reply_text,
            ctx=ctx,
            plan=plan,
        )

    ts = utc_now()
    try:
        ingest_agent_turn(
            person_id=person_id,
            session_id=session_id,
            text=reply,
            ts=ts,
        )
    except Exception as exc:
        logger.warning("ingest_agent_turn failed: %s", exc)

    stores = get_stores()
    followup = (plan.followup_action if plan else None) or {}
    experience_kind: ExperienceKind = "agent_response"
    if followup.get("kind") == "record_agent_experience":
        candidate = str(followup.get("experience_kind") or experience_kind)
        if candidate in _VALID_EXPERIENCE_KINDS:
            experience_kind = candidate  # type: ignore[assignment]

    summary = _agent_response_experience_summary(user_text=user_text, reply=reply)
    try:
        stores.orchestrator.record_agent_experience(
            RecordAgentExperienceInput(
                ts=ts,
                person_id=person_id,
                kind=experience_kind,
                summary=summary,
                public_summary=summary,
                importance=3,
                privacy_level="relationship",
                related_event_ids=[],
                artifacts=[{"user_text": user_text[:200], "channel": "native_chat"}],
            )
        )
    except Exception as exc:
        logger.warning("record_agent_experience failed: %s", exc)

    if followup.get("kind") == "satisfy_desire":
        desire_name = str(followup.get("desire_name") or "")
        if desire_name:
            try:
                satisfy_desire_direct(
                    desire_name=desire_name,
                    action_summary=summary[:120],
                    person_id=person_id,
                )
            except Exception as exc:
                logger.info("satisfy_desire after chat skipped: %s", exc)

    apply_pulse_schedule(
        channel="chat",
        plan=plan,
        ctx=ctx,
        action="agent_response",
        reason_suffix=reply[:40].replace("\n", " "),
    )

    from presence_ui.heartbeat.interpretation_shift import record_interpretation_shifts

    return record_interpretation_shifts(
        person_id=person_id,
        user_text=user_text,
        reply_text=reply_text,
        ctx=ctx,
        plan=plan,
    )
