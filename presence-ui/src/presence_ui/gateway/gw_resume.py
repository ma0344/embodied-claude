"""GW Claude --resume — post-surface internal turns on the same session."""

from __future__ import annotations

import asyncio
import logging

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponsePlan

from presence_ui.deps import get_stores
from presence_ui.gateway.aozora import load_reading_state, passage_needs_reflect
from presence_ui.gateway.gw_silent import gw_after_chat_enabled, gw_s1_claude_enabled

logger = logging.getLogger(__name__)


def _reflect_post_chat_in_worker(
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
):
    """Run PAUSE reflect on the worker thread (SQLite via thread-local get_stores)."""
    from presence_ui.gateway.direct_actions import reflect_on_aozora_passage_direct

    return reflect_on_aozora_passage_direct(
        get_stores(),
        person_id=person_id,
        ctx=ctx,
        plan=plan,
    )


async def run_post_chat_internal_turn(
    *,
    session_id: str,
    person_id: str,
    ctx: InteractionContext | None,
    plan: ResponsePlan | None,
    reply_text: str,
) -> None:
    """Background internal turn N+1 after surface chat (same Claude JSONL session)."""
    if not gw_after_chat_enabled() or not gw_s1_claude_enabled():
        return
    sid = (session_id or "").strip()
    if not sid or not (reply_text or "").strip():
        return
    if ctx is None or plan is None:
        return

    state = load_reading_state()
    if state.phase != "pause" or not passage_needs_reflect(state):
        return

    resume_ctx = ctx.model_copy(update={"session_id": sid})
    try:
        outcome = await asyncio.to_thread(
            _reflect_post_chat_in_worker,
            person_id=person_id,
            ctx=resume_ctx,
            plan=plan,
        )
        if outcome.ok:
            logger.info(
                "GW post-chat PAUSE via Claude resume session=%s detail=%s",
                sid[:8],
                outcome.detail,
            )
        else:
            logger.info(
                "GW post-chat PAUSE skipped/failed session=%s: %s",
                sid[:8],
                outcome.summary,
            )
    except Exception as exc:
        logger.warning("GW post-chat internal turn failed: %s", exc)
