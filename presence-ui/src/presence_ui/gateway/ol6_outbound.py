"""SPONT-B1 / S1 — OL6 post-deadline check via autonomous tick → outbound.

Human-turn OL6 still works via compose/plan. This module fires the same
concern → check intention → intervention path without waiting for user_text.

See docs/tracks/spontaneity.md § B / S1.
"""

from __future__ import annotations

import logging
import os

from interaction_orchestrator_mcp.schemas import (
    InteractionContext,
    LoopDueForCheck,
    RecordAgentExperienceInput,
    ResponsePlan,
)
from social_core import utc_now
from social_core.ol6_check import PENDING_TRIGGER_OL6

from presence_ui.deps import PresenceStores
from presence_ui.gateway.direct_actions import (
    DirectActionOutcome,
    boundary_allows,
    outbound_nudge_speak_enabled,
)
from presence_ui.gateway.room_events import activity_event, progress_event
from presence_ui.services.outbound import (
    default_surface_channels,
    enqueue_outbound_nudge,
    outbound_delivery_artifacts,
    voice_local_enabled,
)

logger = logging.getLogger(__name__)


def ol6_outbound_enabled() -> bool:
    raw = os.getenv("PRESENCE_OL6_OUTBOUND", "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def concern_threshold() -> float:
    return _env_float("PRESENCE_OL6_OUTBOUND_CONCERN_THRESHOLD", 0.5)


def compute_ol6_concern(
    due: LoopDueForCheck,
    *,
    evidence_gap: float = 1.0,
    urgency: float = 1.0,
) -> float:
    """v0 concern = gap × urgency × stakes × care (S1 post-deadline).

    evidence_gap defaults to 1.0: loop still open ⇒ no completion evidence.
    urgency defaults to 1.0: compose already selected a past-deadline loop.
    """
    _ = due  # reserved for lateness / stakes-by-topic later
    stakes = _env_float("PRESENCE_OL6_OUTBOUND_STAKES", 0.8)
    care = _env_float("PRESENCE_OL6_OUTBOUND_CARE", 0.8)
    gap = max(0.0, min(1.0, evidence_gap))
    urg = max(0.0, min(1.0, urgency))
    stakes = max(0.0, min(1.0, stakes))
    care = max(0.0, min(1.0, care))
    return round(gap * urg * stakes * care, 4)


def _topic_snippet(topic: str, *, max_len: int = 40) -> str:
    text = (topic or "").strip()
    if not text:
        return "さっきの予定"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def build_ol6_check_line(due: LoopDueForCheck) -> str:
    """Deterministic short check-in (no LLM) — S1 tone: 様子伺い."""
    snippet = _topic_snippet(due.topic)
    return f"まー、{snippet} のやつ、もう片付いた？"


def _eligible_due(ctx: InteractionContext) -> LoopDueForCheck | None:
    """First post-deadline OL6 due loop; OL7 return-signal is ingest-driven."""
    dues = list(ctx.loops_due_for_check or [])
    for due in dues:
        if due.trigger == PENDING_TRIGGER_OL6 or due.trigger == "post_deadline_first_turn":
            return due
    return None


async def check_open_loop_outbound_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    due: LoopDueForCheck | None = None,
    text: str | None = None,
    skip_presence: bool = False,
) -> DirectActionOutcome:
    """Outbound one short completion check for a past-deadline open loop."""
    _ = plan
    target = due or _eligible_due(ctx)
    if target is None:
        return DirectActionOutcome(
            ok=False,
            action="check_open_loop",
            summary="No post-deadline open loop due for check.",
        )

    concern = compute_ol6_concern(target)
    theta = concern_threshold()
    if concern < theta:
        return DirectActionOutcome(
            ok=False,
            action="check_open_loop",
            summary=f"Concern {concern:.3f} below threshold {theta:.3f}.",
            detail=f"loop_id={target.loop_id}; concern={concern}",
        )

    if not skip_presence:
        from presence_ui.services.speak_presence import companion_present_for_speak

        presence = await companion_present_for_speak()
        if not presence.present:
            return DirectActionOutcome(
                ok=False,
                action="check_open_loop",
                summary="Companion not present for speak.",
                detail=presence.reason,
                events=[
                    activity_event(
                        kind="say",
                        label="予定の確認ができなかった",
                        detail=presence.reason[:200],
                        ok=False,
                    )
                ],
            )

    allowed, reasons = boundary_allows(
        stores, action_type="say", person_id=person_id, urgency="low"
    )
    if not allowed:
        return DirectActionOutcome(
            ok=False,
            action="check_open_loop",
            summary="Boundary denied say.",
            detail="; ".join(reasons),
            events=[
                activity_event(
                    kind="say",
                    label="予定の確認ができなかった",
                    detail="; ".join(reasons)[:200],
                    ok=False,
                )
            ],
        )

    line = (text or "").strip() or build_ol6_check_line(target)
    channels = default_surface_channels()
    enqueue = enqueue_outbound_nudge(
        stores,
        person_id=person_id,
        text=line,
        speak=outbound_nudge_speak_enabled(want_speak=True),
        kiosk_say=True,
        channels=channels,
        desire="ol6_check",
        skip_cooldown=False,
    )
    if not enqueue.ok:
        return DirectActionOutcome(
            ok=False,
            action="check_open_loop",
            summary=enqueue.reason or "Outbound enqueue failed.",
            detail=enqueue.reason,
            events=[
                activity_event(
                    kind="say",
                    label="予定の確認ができなかった",
                    detail=(enqueue.reason or "cooldown")[:200],
                    ok=False,
                )
            ],
        )

    # Mark only after successful enqueue (one-shot via check_asked_at).
    try:
        stores.relationship.mark_loop_check_asked(
            loop_id=target.loop_id,
            person_id=person_id,
            ts=utc_now(),
            topic=target.topic,
            ask_snippet=line[:120],
            trigger=target.trigger,
        )
    except Exception as exc:
        logger.warning("mark_loop_check_asked failed for %s: %s", target.loop_id, exc)

    from presence_ui.services.outbound_kiosk import should_deliver_pc_local
    from presence_ui.services.tts import speak_text

    spoke_local = False
    speak_detail = ""
    if voice_local_enabled() and should_deliver_pc_local():
        spoke_local, speak_detail = await speak_text(line, speaker="local")

    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_voice_utterance",
            summary=line[:240],
            public_summary=line[:240],
            importance=4,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=outbound_delivery_artifacts(
                nudge_id=enqueue.nudge_id or "",
                channels=list(enqueue.channels),
                speak=True,
                delivered_local=spoke_local,
            ),
        )
    )
    stores.social_state.ingest_social_event(
        {
            "ts": utc_now(),
            "source": "gateway_direct",
            "kind": "agent_utterance",
            "person_id": person_id,
            "confidence": 1.0,
            "payload": {
                "text": line,
                "channel": "outbound",
                "via": "ol6_outbound_check",
                "loop_id": target.loop_id,
                "concern": concern,
                "nudge_id": enqueue.nudge_id,
                "channels": list(enqueue.channels),
            },
        }
    )
    events = [
        progress_event(phase="say", label="予定を確認した"),
        activity_event(
            kind="say",
            label="期限過ぎの予定を確認した",
            detail=line[:120],
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="check_open_loop",
        summary=line,
        detail=speak_detail or f"concern={concern}; {enqueue.nudge_id or ''}",
        events=events,
    )


async def maybe_fire_ol6_outbound(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> DirectActionOutcome | None:
    """Hook for autonomous tick. Returns outcome if attempted; None if skipped."""
    if not ol6_outbound_enabled():
        return None
    if ctx.commitments_due:
        # Reminder path has priority over schedule concern check.
        return None
    due = _eligible_due(ctx)
    if due is None:
        return None
    outcome = await check_open_loop_outbound_direct(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        due=due,
    )
    return outcome
