"""POST /api/chat interceptor — apply sociality before forwarding to Claude Code."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import (
    ComposeInteractionContextInput,
    InteractionContext,
    PlanResponseInput,
    RecordAgentExperienceInput,
    ResponsePlan,
)
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.gateway.calendar_prefetch import (
    calendar_honesty_directive,
    calendar_prefetch_enabled,
    looks_like_calendar_query,
)
from presence_ui.gateway.calendar_write import (
    calendar_write_enabled,
    calendar_write_honesty_directive,
    looks_like_calendar_create,
    looks_like_calendar_update,
)
from presence_ui.gateway.context_limits import (
    full_compose_max_chars,
    lite_append_max_chars,
    lite_compose_max_chars,
)
from presence_ui.gateway.deterministic_memory import (
    RememberOutcome,
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
from presence_ui.gateway.hybrid_intent import HybridBodyIntent, resolve_hybrid_intent
from presence_ui.gateway.ol7_blocks import format_ol7_close_result, format_ol7_pending_block
from presence_ui.gateway.ol7_flow import Ol7IngestResult
from presence_ui.gateway.open_loop_dismiss import dismiss_note, dismiss_progress_label
from presence_ui.gateway.prompt_block_safe import truncate_lite_turn_delta
from presence_ui.gateway.prompt_injection import apply_gateway_prompt_injection
from presence_ui.gateway.room_events import progress_event
from presence_ui.gateway.room_ingest import HumanIngestResult, ingest_human_turn_async
from presence_ui.gateway.self_disclosure_encode import encode_self_disclosure_if_any
from presence_ui.gateway.soul_prefetch import (
    detect_soul_read_request,
    soul_read_prefetch_block,
)
from presence_ui.gateway.user_intent import (
    ibf_gateway_speak_enabled,
    merge_intent_with_plan,
)
from presence_ui.gateway.ws_guard import (
    looks_like_web_search_request,
    web_search_honesty_directive,
    ws_guard_enabled,
)
from presence_ui.heartbeat.schedule import apply_pulse_schedule
from presence_ui.services.llm import build_social_turn_delta
from presence_ui.services.somatic_context import (
    apply_somatic_plan_side_effects,
    enrich_interaction_context,
    quiet_from_context,
)

# write_private_reflection must still reach Claude Code so it can call
# mcp__sociality__append_private_reflection (voice.speak=false in the plan).
_SILENT_MOVES = frozenset({"stay_silent", "defer", "quietly_prepare"})

# Kiosk (:8090) has no webui permission UI; auto-accept edits within allow rules.
_DEFAULT_PERMISSION_MODE = "acceptEdits"

logger = logging.getLogger(__name__)


def _close_archive_remember_loops(
    *,
    person_id: str,
    message: str,
    saved_content: str | None,
) -> list[str]:
    try:
        return get_stores().relationship.close_loops_after_remember_save(
            person_id=person_id,
            utterance=message,
            saved_content=saved_content,
            ts=utc_now(),
        )
    except Exception:
        logger.exception("close_loops_after_remember_save failed")
        return []


def _inbound_reply_dialogue_delta(payload: dict, *, user_reply: str) -> str:
    """Pseudo two-turn dialogue for room-inbound replies (aligns with UI seed message)."""
    nudge = str(payload.get("inboundNudge") or "").strip()
    reply = (user_reply or "").strip()
    if not nudge or not reply:
        return ""
    nudge_id = str(payload.get("inboundNudgeId") or "").strip()
    lines = [
        "[inbound_reply — not for the user]",
        "Conversation so far (you are こより; reply to まー's last line):",
        f"こより: {nudge[:500]}",
        f"まー: {reply[:500]}",
        "Reply as こより with new words only — never echo or mirror まー's exact wording.",
    ]
    if nudge_id:
        lines.insert(1, f"nudge_id={nudge_id}")
    return "\n".join(lines)


@dataclass(slots=True)
class ChatInterceptResult:
    forward: bool
    payload: dict | None = None
    plan_move: str | None = None
    user_text: str | None = None
    gateway_events: list[dict[str, Any]] = field(default_factory=list)
    direct_action_summary: str | None = None
    gateway_speak_after_reply: bool = False
    plan: ResponsePlan | None = None
    ctx: InteractionContext | None = None
    session_id: str | None = None


def _ingest_failure_gateway_events(
    failures: tuple,
) -> list[dict[str, Any]]:
    from presence_ui.gateway.room_events import activity_event

    return [
        activity_event(
            kind="ingest",
            label=f"ingest: {failure.hook}",
            detail=f"{failure.error_type}: {failure.message}",
            ok=False,
        )
        for failure in failures
    ]


def _merge_ingest_hook_events(
    ingest_result: HumanIngestResult,
    events: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if not ingest_result.hook_failures:
        return events
    merged = list(events or [])
    merged.extend(_ingest_failure_gateway_events(ingest_result.hook_failures))
    return merged


def _ingest_human_sync(*, person_id: str, session_id: str | None, text: str) -> HumanIngestResult:
    from presence_ui.gateway.room_ingest import ingest_human_turn

    return ingest_human_turn(
        person_id=person_id,
        session_id=session_id,
        text=text,
        run_llm=True,
    )


def _ol7_loop_topic(*, person_id: str, loop_id: str) -> str:
    for loop in get_stores().relationship.list_open_loops(person_id=person_id, limit=50):
        if loop.id == loop_id:
            return loop.topic
    return loop_id


def _apply_ol7_to_intercept(
    *,
    ol7: Ol7IngestResult | None,
    person_id: str,
    message: str,
    memory_notes: list[str],
    gateway_events: list[dict[str, Any]],
    plan: ResponsePlan | None = None,
) -> ResponsePlan | None:
    if ol7 is None or ol7.route == "no_op":
        return plan
    if ol7.route == "immediate_close" and ol7.closed_topics:
        memory_notes.append(
            format_ol7_close_result(
                closed_topics=list(ol7.closed_topics),
                summary="",
            )
        )
        gateway_events.append(
            progress_event(
                phase="relationship",
                label=f"OL7 close: {ol7.closed_topics[0][:40]}",
            )
        )
        return plan
    if ol7.route == "pending_confirm" and ol7.pending_loop_id and plan is not None:
        topic = _ol7_loop_topic(person_id=person_id, loop_id=ol7.pending_loop_id)
        memory_notes.append(
            format_ol7_pending_block(
                loop_id=ol7.pending_loop_id,
                topic=topic,
                source_utterance=message,
            )
        )
        gateway_events.append(
            progress_event(
                phase="relationship",
                label="OL7 return-signal — confirm before close",
            )
        )
        confirm_line = (
            f"OL7 return-signal — ask ONE short natural question if "
            f"「{topic[:60]}」 is done (do not assume closed yet)"
        )
        must_include = list(plan.must_include)
        if confirm_line not in must_include:
            must_include.append(confirm_line)
        return plan.model_copy(update={"must_include": must_include})
    return plan


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
    web_search_prefetch: str | None = None,
    url_prefetch: str | None = None,
    calendar_prefetch: str | None = None,
    calendar_write: str | None = None,
    calendar_confirm: str | None = None,
    extra_gateway_events: list[dict[str, Any]] | None = None,
    hybrid: HybridBodyIntent | None = None,
) -> ChatInterceptResult:
    """Sync wrapper (tests / thread offload). Native chat uses async variant."""
    import asyncio

    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("message must not be empty")
    session_id = payload.get("sessionId")
    session_key = str(session_id) if session_id else None
    ingest_result = _ingest_human_sync(
        person_id=person_id, session_id=session_key, text=message
    )
    dismiss_outcome = ingest_result.dismiss_outcome
    ol7_result = ingest_result.ol7

    write_block = calendar_write
    confirm_block = calendar_confirm
    cal_events = list(extra_gateway_events or [])
    if write_block is None and confirm_block is None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            from presence_ui.gateway.calendar_write_flow import process_calendar_turn

            cal_outcome = asyncio.run(
                process_calendar_turn(person_id=person_id, message=message)
            )
            write_block = cal_outcome.write_block
            confirm_block = cal_outcome.confirm_block
            cal_events.extend(cal_outcome.progress_events)

    cal_events = _merge_ingest_hook_events(ingest_result, cal_events)

    return _finish_intercept_chat_request(
        payload=payload,
        person_id=person_id,
        lite=lite,
        vision_prefetch=vision_prefetch,
        web_search_prefetch=web_search_prefetch,
        url_prefetch=url_prefetch,
        calendar_prefetch=calendar_prefetch,
        calendar_write=write_block,
        calendar_confirm=confirm_block,
        extra_gateway_events=cal_events or None,
        message=message,
        session_key=session_key,
        dismiss_outcome=dismiss_outcome,
        ol7_result=ol7_result,
        hybrid=hybrid,
    )


async def intercept_chat_request_async(
    *,
    payload: dict,
    person_id: str = "ma",
    lite: bool = False,
    vision_prefetch: str | None = None,
    web_search_prefetch: str | None = None,
    url_prefetch: str | None = None,
    calendar_prefetch: str | None = None,
    calendar_write: str | None = None,
    calendar_confirm: str | None = None,
    extra_gateway_events: list[dict[str, Any]] | None = None,
    hybrid: HybridBodyIntent | None = None,
) -> ChatInterceptResult:
    """Run compose/plan; enrich message or block forward on silent moves."""
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("message must not be empty")

    session_id = payload.get("sessionId")
    session_key = str(session_id) if session_id else None
    ingest_result = await ingest_human_turn_async(
        person_id=person_id, session_id=session_key, text=message
    )
    dismiss_outcome = ingest_result.dismiss_outcome
    ol7_result = ingest_result.ol7

    write_block = calendar_write
    confirm_block = calendar_confirm
    cal_gateway_events = list(extra_gateway_events or [])
    if write_block is None and confirm_block is None:
        from presence_ui.gateway.calendar_write_flow import process_calendar_turn

        cal_outcome = await process_calendar_turn(person_id=person_id, message=message)
        write_block = cal_outcome.write_block
        confirm_block = cal_outcome.confirm_block
        cal_gateway_events.extend(cal_outcome.progress_events)

    cal_gateway_events = _merge_ingest_hook_events(ingest_result, cal_gateway_events) or []

    return _finish_intercept_chat_request(
        payload=payload,
        person_id=person_id,
        lite=lite,
        vision_prefetch=vision_prefetch,
        web_search_prefetch=web_search_prefetch,
        url_prefetch=url_prefetch,
        calendar_prefetch=calendar_prefetch,
        calendar_write=write_block,
        calendar_confirm=confirm_block,
        extra_gateway_events=cal_gateway_events,
        message=message,
        session_key=session_key,
        dismiss_outcome=dismiss_outcome,
        ol7_result=ol7_result,
        hybrid=hybrid,
    )


def _finish_intercept_chat_request(
    *,
    payload: dict,
    person_id: str,
    lite: bool,
    vision_prefetch: str | None,
    web_search_prefetch: str | None,
    url_prefetch: str | None,
    calendar_prefetch: str | None,
    calendar_write: str | None,
    calendar_confirm: str | None,
    extra_gateway_events: list[dict[str, Any]] | None,
    message: str,
    session_key: str | None,
    dismiss_outcome,
    ol7_result: Ol7IngestResult | None = None,
    hybrid: HybridBodyIntent | None = None,
) -> ChatInterceptResult:
    compose_max_chars = lite_compose_max_chars() if lite else full_compose_max_chars()

    gateway_events: list[dict[str, Any]] = list(extra_gateway_events or [])
    memory_notes: list[str] = []
    archive_closed_loops: list[str] = []
    resolved = hybrid or resolve_hybrid_intent(message)
    user_intent = resolved.user_intent
    remember_intent = None
    remember_saved = False
    if user_intent.wants_remember:
        remember_intent = detect_remember_intent(message) or detect_personal_fact_intent(message)
    if remember_intent:
        outcome = persist_remember_intent(remember_intent)
        if outcome.ok:
            remember_saved = True
            label = "もう覚えてある" if outcome.duplicate else "記憶に保存した"
            gateway_events.append(
                progress_event(phase="remember", label=label)
            )
            archive_closed_loops.extend(
                _close_archive_remember_loops(
                    person_id=person_id,
                    message=message,
                    saved_content=remember_intent.content,
                )
            )
        else:
            gateway_events.append(
                progress_event(phase="remember", label="記憶の保存に失敗")
            )
        memory_notes.append(memory_saved_prompt_note(outcome))
    elif not remember_saved:
        sd_outcome = encode_self_disclosure_if_any(
            person_id=person_id,
            text=message,
            session_id=session_key,
        )
        if sd_outcome.encoded:
            if sd_outcome.ltm_saved:
                label = "もう覚えてある" if sd_outcome.duplicate_ltm else "自己開示を記憶に保存した"
                gateway_events.append(progress_event(phase="remember", label=label))
                archive_closed_loops.extend(
                    _close_archive_remember_loops(
                        person_id=person_id,
                        message=message,
                        saved_content=sd_outcome.gist or message,
                    )
                )
                memory_notes.append(
                    memory_saved_prompt_note(
                        RememberOutcome(
                            ok=True,
                            content=sd_outcome.gist or message,
                            memory_id=sd_outcome.ltm_memory_id,
                            duplicate=sd_outcome.duplicate_ltm,
                        )
                    )
                )
            else:
                gateway_events.append(
                    progress_event(phase="remember", label="自己開示を短期記憶に記録した")
                )

    merged_closed_loops = [*dismiss_outcome.closed_loops, *archive_closed_loops]
    if dismiss_outcome.any or archive_closed_loops:
        memory_notes.append(
            dismiss_note(
                closed_loops=merged_closed_loops,
                cancelled_commitments=dismiss_outcome.cancelled_commitments,
            )
        )
        gateway_events.append(
            progress_event(
                phase="relationship",
                label=dismiss_progress_label(
                    closed_loops=merged_closed_loops,
                    cancelled_commitments=dismiss_outcome.cancelled_commitments,
                ),
            )
        )

    list_request = detect_memory_list_request(message)
    if detect_soul_read_request(message) and not list_request:
        turn_delta = soul_read_prefetch_block()
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
        gateway_events.append(
            progress_event(phase="soul", label="SOUL.md を読み込んだ")
        )
        return ChatInterceptResult(
            forward=True,
            payload=enriched,
            plan_move="answer_directly",
            user_text=message,
            gateway_events=gateway_events,
        )

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
    try:
        from interaction_orchestrator_mcp.topic_retire import (
            TopicRetireStore,
            maybe_record_topic_retire,
            topic_retire_enabled,
        )

        if topic_retire_enabled():
            TopicRetireStore(stores.db).clear_matching_topics(
                person_id=person_id,
                user_text=message,
            )
            if maybe_record_topic_retire(
                stores.db,
                person_id=person_id,
                user_text=message,
            ):
                gateway_events.append(
                    progress_event(phase="memory", label="話題をcomposeから降ろした")
                )
    except Exception:
        pass

    prefetch_fact_check = bool(
        web_search_prefetch and "trigger=ws5" in web_search_prefetch
    )

    ctx = compose_interaction_context(
        ComposeInteractionContextInput(
            person_id=person_id,
            channel="chat",
            user_text=message,
            session_id=session_key,
            claude_session_resume=bool(session_key),
            include_private=not lite,
            max_chars=compose_max_chars,
            prefetch_fact_check=prefetch_fact_check,
        ),
        social_state_store=stores.social_state,
        relationship_store=stores.relationship,
        joint_attention_store=stores.joint_attention,
        boundary_store=stores.boundary,
        self_narrative_store=stores.self_narrative,
        orchestrator_store=stores.orchestrator,
        policy_timezone=stores.policy_timezone,
        social_db=stores.db,
    )
    ctx = enrich_interaction_context(ctx, channel="chat", user_text=message)
    plan = plan_response(
        PlanResponseInput(
            interaction_context=ctx,
            user_text=message,
        )
    )
    plan = _apply_ol7_to_intercept(
        ol7=ol7_result,
        person_id=person_id,
        message=message,
        memory_notes=memory_notes,
        gateway_events=gateway_events,
        plan=plan,
    )
    apply_somatic_plan_side_effects(
        primary_move=plan.primary_move,
        channel="chat",
        quiet_active=quiet_from_context(ctx),
        local_time=ctx.local_time,
        timezone=ctx.timezone,
        user_text=message,
    )

    if plan.primary_move in _SILENT_MOVES:
        apply_pulse_schedule(
            channel="chat",
            plan=plan,
            ctx=ctx,
            action=plan.primary_move,
            reason_suffix="silent",
        )
        return ChatInterceptResult(
            forward=False,
            plan_move=plan.primary_move,
            user_text=message,
            gateway_events=gateway_events,
            plan=plan,
            ctx=ctx,
            session_id=session_key,
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
        apply_pulse_schedule(
            channel="chat",
            plan=plan,
            ctx=ctx,
            action="write_private_reflection",
            reason_suffix="direct",
        )
        return ChatInterceptResult(
            forward=False,
            plan_move=plan.primary_move,
            user_text=message,
            gateway_events=gateway_events,
            direct_action_summary=outcome.summary,
            plan=plan,
            ctx=ctx,
            session_id=session_key,
        )

    turn_delta = build_social_turn_delta(ctx=ctx, plan=plan)
    effective = merge_intent_with_plan(
        intent=user_intent,
        plan=plan,
        vision_prefetch_done=bool(vision_prefetch),
        web_search_prefetch_done=bool(web_search_prefetch),
        url_prefetch_done=bool(url_prefetch),
        calendar_prefetch_done=bool(calendar_prefetch),
        calendar_write_done=bool(calendar_write),
        calendar_confirm_pending=bool(calendar_confirm),
        remember_saved=remember_saved,
    )
    gateway_speak = ibf_gateway_speak_enabled() and effective.gateway_speak_after_reply
    if effective.speak_action_note:
        turn_delta = (
            f"{turn_delta}\n\n{effective.speak_action_note}"
            if turn_delta
            else effective.speak_action_note
        )
    if memory_notes:
        note = "\n\n".join(memory_notes)
        turn_delta = f"{turn_delta}\n\n{note}" if turn_delta else note
    if (
        ws_guard_enabled()
        and looks_like_web_search_request(message)
        and not web_search_prefetch
        and not url_prefetch
    ):
        honesty = web_search_honesty_directive()
        turn_delta = f"{turn_delta}\n\n{honesty}" if turn_delta else honesty
    if (
        calendar_prefetch_enabled()
        and looks_like_calendar_query(message)
        and not calendar_prefetch
        and not calendar_write
    ):
        honesty = calendar_honesty_directive()
        turn_delta = f"{turn_delta}\n\n{honesty}" if turn_delta else honesty
    if (
        calendar_write_enabled()
        and (looks_like_calendar_create(message) or looks_like_calendar_update(message))
        and not calendar_write
    ):
        honesty = calendar_write_honesty_directive()
        turn_delta = f"{turn_delta}\n\n{honesty}" if turn_delta else honesty
    inbound_delta = _inbound_reply_dialogue_delta(payload, user_reply=message)
    if inbound_delta:
        turn_delta = f"{turn_delta}\n\n{inbound_delta}" if turn_delta else inbound_delta
    if lite and turn_delta:
        turn_delta = truncate_lite_turn_delta(turn_delta, lite_append_max_chars())
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
    if web_search_prefetch:
        enriched_message = f"{enriched_message.rstrip()}\n\n{web_search_prefetch.strip()}"
    if url_prefetch:
        enriched_message = f"{enriched_message.rstrip()}\n\n{url_prefetch.strip()}"
    if calendar_prefetch:
        enriched_message = f"{enriched_message.rstrip()}\n\n{calendar_prefetch.strip()}"
    if calendar_write:
        enriched_message = f"{enriched_message.rstrip()}\n\n{calendar_write.strip()}"
    if calendar_confirm:
        enriched_message = f"{enriched_message.rstrip()}\n\n{calendar_confirm.strip()}"
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
        gateway_speak_after_reply=gateway_speak,
        plan=plan,
        ctx=ctx,
        session_id=session_key,
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
