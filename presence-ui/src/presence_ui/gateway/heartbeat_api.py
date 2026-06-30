"""Gateway Heartbeat API — compose/plan/finalize without MCP tools (BIO-6)."""

from __future__ import annotations

from typing import Any

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import (
    ComposeInteractionContextInput,
    InteractionContext,
    PlanResponseInput,
    ResponsePlan,
)
from pydantic import BaseModel, Field

from presence_ui.deps import get_stores
from presence_ui.gateway.context_limits import full_compose_max_chars, lite_compose_max_chars
from presence_ui.heartbeat.record import finalize_chat_turn
from presence_ui.services.somatic_context import enrich_interaction_context


class ComposePlanRequest(BaseModel):
    person_id: str = "ma"
    channel: str = "chat"
    user_text: str | None = None
    session_id: str | None = None
    include_private: bool = True
    lite: bool = False


class ComposePlanResponse(BaseModel):
    ok: bool = True
    ctx: dict[str, Any]
    plan: dict[str, Any]
    plan_move: str


class FinalizeTurnRequest(BaseModel):
    person_id: str = "ma"
    session_id: str | None = None
    user_text: str
    reply_text: str = ""
    plan: dict[str, Any] | None = None
    ctx: dict[str, Any] | None = None


class FinalizeTurnResponse(BaseModel):
    ok: bool = True
    interpretation_shift_ids: list[str] = Field(default_factory=list)


def compose_plan_body(body: ComposePlanRequest) -> ComposePlanResponse:
    stores = get_stores()
    max_chars = full_compose_max_chars()
    if body.lite:
        max_chars = min(max_chars, lite_compose_max_chars())

    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=body.person_id,
            channel=body.channel,  # type: ignore[arg-type]
            user_text=body.user_text,
            session_id=body.session_id,
            claude_session_resume=bool(body.session_id),
            include_private=body.include_private,
            max_chars=max_chars,
        ),
        social_state_store=stores.social_state,
        relationship_store=stores.relationship,
        joint_attention_store=stores.joint_attention,
        boundary_store=stores.boundary,
        self_narrative_store=stores.self_narrative,
        orchestrator_store=stores.orchestrator,
        policy_timezone=stores.policy_timezone,
    )
    ctx = enrich_interaction_context(
        ctx,
        channel=body.channel,
        user_text=body.user_text,
    )
    plan = plan_response(
        PlanResponseInput(
            interaction_context=ctx,
            user_text=body.user_text,
        )
    )
    return ComposePlanResponse(
        ctx=ctx.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
        plan_move=plan.primary_move,
    )


def finalize_turn_body(body: FinalizeTurnRequest) -> FinalizeTurnResponse:
    plan_obj: ResponsePlan | None = None
    ctx_obj: InteractionContext | None = None
    if body.plan:
        plan_obj = ResponsePlan.model_validate(body.plan)
    if body.ctx:
        ctx_obj = InteractionContext.model_validate(body.ctx)

    shift_ids = finalize_chat_turn(
        person_id=body.person_id,
        session_id=body.session_id,
        user_text=body.user_text,
        reply_text=body.reply_text,
        plan=plan_obj,
        ctx=ctx_obj,
    )
    return FinalizeTurnResponse(interpretation_shift_ids=shift_ids)
