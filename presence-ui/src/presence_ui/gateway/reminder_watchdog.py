"""Background poll for due commitments — finer than the 15m Windows scheduled task."""

from __future__ import annotations

import asyncio
import logging
import os

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import ComposeInteractionContextInput, PlanResponseInput
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.gateway.direct_actions import direct_actions_enabled, remind_commitment_direct

logger = logging.getLogger(__name__)

_watchdog_task: asyncio.Task[None] | None = None


def reminder_poll_seconds() -> int:
    return max(15, int(os.getenv("PRESENCE_REMINDER_POLL_SEC", "60")))


def reminder_watchdog_enabled() -> bool:
    return os.getenv("PRESENCE_REMINDER_WATCHDOG", "1").lower() not in {
        "0",
        "false",
        "no",
    }


async def fire_due_reminders_once(*, person_id: str = "ma") -> bool:
    """If any commitment is due, deliver one reminder. Returns True when fired."""
    if not direct_actions_enabled():
        return False

    stores = get_stores()
    as_of = utc_now()
    due = stores.relationship.list_due_commitments(
        person_id=person_id,
        as_of=as_of,
        timezone=stores.policy_timezone,
        limit=1,
    )
    if not due:
        return False

    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id,
            channel="autonomous",
            user_text=None,
            autonomous_trigger="reminder_watchdog",
            include_private=True,
            max_chars=int(os.getenv("PRESENCE_COMPOSE_MAX_CHARS", "10000")),
        ),
        social_state_store=stores.social_state,
        relationship_store=stores.relationship,
        joint_attention_store=stores.joint_attention,
        boundary_store=stores.boundary,
        self_narrative_store=stores.self_narrative,
        orchestrator_store=stores.orchestrator,
        policy_timezone=stores.policy_timezone,
    )
    if not ctx.commitments_due:
        return False

    plan = plan_response(PlanResponseInput(interaction_context=ctx, user_text=None))
    if "remind_commitment" not in (plan.initiative.allowed_actions or []):
        logger.info("reminder_watchdog: boundary/plan blocked remind_commitment")
        return False

    outcome = await remind_commitment_direct(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
    )
    if outcome.ok:
        logger.info("reminder_watchdog: %s", outcome.summary[:120])
    else:
        logger.warning("reminder_watchdog failed: %s", outcome.summary)
    return outcome.ok


async def _reminder_watchdog_loop() -> None:
    interval = reminder_poll_seconds()
    logger.info("reminder watchdog started (every %ds)", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await fire_due_reminders_once()
        except Exception:
            logger.exception("reminder watchdog tick failed")


def start_reminder_watchdog() -> None:
    global _watchdog_task
    if not reminder_watchdog_enabled() or not direct_actions_enabled():
        return
    if _watchdog_task is not None and not _watchdog_task.done():
        return
    _watchdog_task = asyncio.create_task(_reminder_watchdog_loop(), name="reminder_watchdog")


def stop_reminder_watchdog() -> None:
    global _watchdog_task
    if _watchdog_task is None:
        return
    _watchdog_task.cancel()
    _watchdog_task = None
