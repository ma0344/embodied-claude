"""Autonomous tick — compose/plan/execute without Claude MCP body tools."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import (
    ComposeInteractionContextInput,
    InteractionContext,
    PlanResponseInput,
    ResponsePlan,
)
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.gateway.direct_actions import (
    direct_actions_enabled,
    execute_autonomous_plan,
)
from presence_ui.heartbeat.schedule import apply_pulse_schedule
from presence_ui.services.somatic_context import (
    apply_somatic_plan_side_effects,
    enrich_interaction_context,
    quiet_from_context,
)


@dataclass(slots=True)
class AutonomousTickResult:
    ok: bool
    primary_move: str
    action: str
    summary: str
    detail: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    plan: ResponsePlan | None = None
    ctx: InteractionContext | None = None
    next_wake_at: str | None = None


def _pulse_reason_suffix(summary: str | None) -> str:
    text = (summary or "").strip()
    if not text:
        return ""
    try:
        from wifi_cam_mcp.vision import caption_looks_corrupt

        if caption_looks_corrupt(text):
            return "vision caption unavailable"
    except ImportError:
        pass
    return text[:60]


async def run_autonomous_tick(
    *,
    person_id: str = "ma",
    trigger: str | None = None,
    speech_text: str | None = None,
    smoke_action: str | None = None,
) -> AutonomousTickResult:
    if not direct_actions_enabled():
        return AutonomousTickResult(
            ok=False,
            primary_move="disabled",
            action="none",
            summary="PRESENCE_GATEWAY_DIRECT_ACTIONS is off.",
        )

    allow_smoke = os.getenv("PRESENCE_ALLOW_SMOKE_ACTION", "1").lower() not in {
        "0",
        "false",
        "no",
    }
    if smoke_action and not allow_smoke:
        return AutonomousTickResult(
            ok=False,
            primary_move="denied",
            action="none",
            summary="smoke_action requires PRESENCE_ALLOW_SMOKE_ACTION=1",
        )

    stores = get_stores()
    try:
        from presence_ui.gateway.calendar_expectations import (
            calendar_lookahead_enabled,
            refresh_calendar_expectations,
        )

        if calendar_lookahead_enabled():
            refresh_calendar_expectations()
    except Exception:
        pass
    try:
        stores.relationship.close_stale_open_loops(
            person_id=person_id,
            as_of=utc_now(),
            timezone=stores.policy_timezone,
        )
    except Exception:
        pass
    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id,
            channel="autonomous",
            user_text=None,
            autonomous_trigger=trigger or "gateway_tick",
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
    ctx = enrich_interaction_context(ctx, channel="autonomous", user_text=None)
    plan = plan_response(
        PlanResponseInput(interaction_context=ctx, user_text=None),
    )
    apply_somatic_plan_side_effects(
        primary_move=plan.primary_move,
        channel="autonomous",
        quiet_active=quiet_from_context(ctx),
        local_time=ctx.local_time,
        timezone=ctx.timezone,
        user_text=None,
    )

    if smoke_action:
        from presence_ui.gateway.direct_actions import execute_smoke_action

        outcome = await execute_smoke_action(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            smoke_action=smoke_action,
            speech_text=speech_text,
        )
        primary = f"smoke:{smoke_action}"
    else:
        from presence_ui.gateway.ol6_outbound import maybe_fire_ol6_outbound

        ol6_outcome = await maybe_fire_ol6_outbound(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
        )
        if ol6_outcome is not None and ol6_outcome.ok:
            outcome = ol6_outcome
            primary = "check_open_loop"
        else:
            outcome = await execute_autonomous_plan(
                stores,
                person_id=person_id,
                ctx=ctx,
                plan=plan,
                speech_text=speech_text,
            )
            primary = plan.primary_move

    pulse = apply_pulse_schedule(
        channel="autonomous",
        plan=plan,
        ctx=ctx,
        action=outcome.action,
        reason_suffix=_pulse_reason_suffix(outcome.summary),
    )

    return AutonomousTickResult(
        ok=outcome.ok,
        primary_move=primary,
        action=outcome.action,
        summary=outcome.summary,
        detail=outcome.detail,
        events=outcome.events,
        plan=plan,
        ctx=ctx,
        next_wake_at=pulse.next_wake_at,
    )
