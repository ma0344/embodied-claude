"""Gateway direct execution — compose/plan decisions without LLM MCP tools."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from interaction_orchestrator_mcp.plan import inward_autonomous_window
from interaction_orchestrator_mcp.schemas import (
    AppendPrivateReflectionInput,
    InteractionContext,
    RecordAgentExperienceInput,
    ResponsePlan,
)
from social_core import utc_now

from presence_ui.deps import PresenceStores
from presence_ui.gateway.aozora import (
    aozora_passage_max_chars,
    complete_reading_pause,
    finish_close_book,
    last_passage_index,
    load_reading_state,
    passage_needs_reflect,
    passage_reflect_stuck,
    pick_passage,
)
from presence_ui.gateway.gw_silent import (
    gw_s1_enabled,
    parse_pause_response,
    run_silent_internal_turn,
)
from presence_ui.gateway.lw7 import (
    clear_pending_followup,
    pending_followup_query,
    should_run_lw7_web_search,
)
from presence_ui.gateway.memory_http import http_recall, http_recall_divergent, http_remember
from presence_ui.gateway.reading_prompts import (
    build_close_book_reflection,
    build_gw_s1_pause_task,
    build_pause_reflection_from_gw_s1,
    build_pause_reflection_v0,
)
from presence_ui.gateway.room_events import activity_event, progress_event
from presence_ui.gateway.web_search import ddg_instant_answer, pick_browse_query
from presence_ui.services.camera_locations import CAMERA_LOCATIONS, PresetLocation
from presence_ui.services.outbound import (
    default_surface_channels,
    enqueue_outbound_nudge,
    outbound_delivery_artifacts,
    voice_local_enabled,
)
from presence_ui.services.somatic_context import quiet_from_context

logger = logging.getLogger(__name__)


def outbound_nudge_speak_enabled(*, want_speak: bool) -> bool:
    """When kiosk is primary, TTS goes via room_say only (avoid double playback)."""
    if not want_speak:
        return False
    try:
        from presence_ui.services.outbound_kiosk import kiosk_primary_active

        if kiosk_primary_active():
            return False
    except Exception:
        pass
    return True


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HOOKS = _REPO_ROOT / ".claude" / "hooks"
if _HOOKS.is_dir() and str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))


@dataclass(slots=True)
class DirectActionOutcome:
    ok: bool
    action: str
    summary: str
    detail: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    desire_satisfied: str | None = None


def direct_actions_enabled() -> bool:
    return os.getenv("PRESENCE_GATEWAY_DIRECT_ACTIONS", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def boundary_allows(
    stores: PresenceStores,
    *,
    action_type: str,
    person_id: str | None,
    urgency: str = "low",
) -> tuple[bool, list[str]]:
    result = stores.boundary.evaluate_action(
        action_type=action_type,
        channel="autonomous",
        person_id=person_id,
        urgency=urgency,
    )
    allowed = result.decision in {"allow", "allow_with_override"}
    return allowed, list(result.reasons)


def _reflection_context_hints(ctx: InteractionContext) -> list[str]:
    """Short cues for gateway private notes — not injection blocks (MEM-5f-a)."""
    hints: list[str] = []
    agent = ctx.agent_state
    if agent and agent.dominant_desire:
        hints.append(f"いまの欲求: {agent.dominant_desire}")
    if ctx.open_loops:
        loop = ctx.open_loops[0]
        if isinstance(loop, dict):
            topic = str(loop.get("topic") or loop.get("loop_id") or "").strip()
        else:
            topic = (loop.topic or loop.loop_id or "").strip()
        if topic:
            hints.append(f"続きの話: {topic[:100]}")
    elif agent and agent.recent_experiences:
        exp = agent.recent_experiences[0]
        summary = (exp.summary or "").strip()
        if summary:
            hints.append(f"さっき: {summary[:100]}")
    somatic = ctx.somatic_state or {}
    pending = somatic.get("pending_unreported") or []
    if pending:
        summary = str(pending[0].get("summary") or "").strip()
        if summary:
            hints.append(f"からだ: {summary[:80]}")
    return hints


def _reflection_body(ctx: InteractionContext, plan: ResponsePlan) -> str:
    """Inner-voice scaffold for gateway direct reflection (MEM-5f-a)."""
    parts: list[str] = []
    why = plan.why_this_move.strip()
    if why:
        parts.append(why)
    hints = _reflection_context_hints(ctx)
    if hints:
        parts.append("いま心に残ってること:\n" + "\n".join(f"- {hint}" for hint in hints))
    body = "\n\n".join(parts)
    return body[:4000] if body else "静かな夜。うちだけのメモ。"


def write_private_reflection_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    body: str | None = None,
) -> DirectActionOutcome:
    """Persist a private reflection without mcp__sociality__append_private_reflection."""
    note = (body or _reflection_body(ctx, plan)).strip()
    title = f"Private note {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    stored = stores.orchestrator.append_private_reflection(
        AppendPrivateReflectionInput(
            person_id=person_id,
            title=title,
            body=note,
            tags=["gateway", "private"],
            importance=3,
            may_surface_later=True,
        )
    )
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_private_reflection",
            summary=note[:240],
            private_summary=note,
            public_summary="",
            importance=3,
            privacy_level="private",
            related_event_ids=[],
        )
    )
    events = [
        progress_event(phase="reflect", label="ひそかにメモした"),
        activity_event(kind="reflect", label="private reflection", detail=note[:120], ok=True),
    ]
    return DirectActionOutcome(
        ok=True,
        action="write_private_reflection",
        summary="Private reflection saved.",
        detail=stored.experience_id,
        events=events,
    )


async def read_aozora_passage_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> DirectActionOutcome:
    """READ phase: one Aozora chunk → remember; reflection is PAUSE (LW-READ)."""
    state = load_reading_state()
    if state.phase == "pause":
        if passage_reflect_stuck(state):
            complete_reading_pause(
                next_move="advance",
                reflected_passage_index=last_passage_index(state),
            )
        elif passage_needs_reflect(state):
            return DirectActionOutcome(
                ok=False,
                action="read_aozora_passage",
                summary="Reading phase is pause — chew before next passage.",
                detail="wrong_phase",
            )
        else:
            return DirectActionOutcome(
                ok=False,
                action="read_aozora_passage",
                summary="Reading pause with no passage to chew.",
                detail="empty_pause",
            )

    picked = await asyncio.to_thread(pick_passage)
    if picked is None:
        return DirectActionOutcome(
            ok=False,
            action="read_aozora_passage",
            summary="Could not fetch an Aozora passage.",
            detail="fetch_failed",
            events=[
                activity_event(
                    kind="read",
                    label="青空文庫",
                    detail="fetch failed",
                    ok=False,
                )
            ],
        )

    work = picked.work
    passage = picked.text[: aozora_passage_max_chars()]
    title = work.title
    author = work.author
    memory_line = (
        f"青空文庫で読んだ『{title}』（{author}）— {passage[:400]}"
    )
    remember_result = await asyncio.to_thread(
        http_remember,
        content=memory_line,
        category="feeling",
        emotion="moved",
        importance=4,
    )
    remember_ok = bool(remember_result.get("ok"))

    summary = f"青空『{title}』— {passage[:220]}"
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_autonomous_action",
            summary=summary,
            private_summary=passage[:400],
            public_summary="",
            importance=4,
            privacy_level="private",
            related_event_ids=[],
            artifacts=[
                {
                    "source_url": picked.source_url,
                    "work_id": work.work_id,
                    "passage_index": picked.passage_index,
                    "remember_ok": remember_ok,
                    "lw_read_phase": "read",
                }
            ],
        )
    )
    return DirectActionOutcome(
        ok=True,
        action="read_aozora_passage",
        summary=summary,
        detail=picked.source_url,
        desire_satisfied="literary_wander",
        events=[
            progress_event(phase="read", label="青空を読んだ"),
            activity_event(
                kind="read",
                label="青空文庫",
                detail=f"{title}: {summary[:80]}",
                ok=True,
            ),
        ],
    )


def close_aozora_reading_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> DirectActionOutcome:
    """CLOSE phase: summarize one finished book and open the next."""
    state = load_reading_state()
    last = state.last_passage or {}
    title = str(last.get("title") or "（作品）")
    author = str(last.get("author") or "")
    sections = state.sections_this_session
    body = build_close_book_reflection(
        title=title,
        author=author,
        sections_read=sections,
        last_hook=state.last_hook,
    )
    outcome = write_private_reflection_direct(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        body=body,
    )
    if not outcome.ok:
        return DirectActionOutcome(
            ok=False,
            action="close_aozora_reading",
            summary="Could not save book-close note.",
            detail=outcome.detail,
            events=outcome.events,
        )

    finish_close_book()
    summary = f"青空『{title}』を閉じた（{sections} 節）"
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_autonomous_action",
            summary=summary,
            private_summary=body[:400],
            public_summary="",
            importance=4,
            privacy_level="private",
            related_event_ids=[],
            artifacts=[{"lw_read_phase": "close", "title": title}],
        )
    )
    return DirectActionOutcome(
        ok=True,
        action="close_aozora_reading",
        summary=summary,
        detail=title,
        events=[
            progress_event(phase="read", label="一冊読み終えた"),
            activity_event(
                kind="read",
                label="青空文庫",
                detail=summary[:120],
                ok=True,
            ),
        ],
    )


def _pause_tick_summary(*, title: str, passage: str, hook: str = "") -> str:
    source = hook.strip() or passage.strip()
    excerpt = source.replace("\n", " ")[:48]
    if len(source) > 48:
        excerpt += "…"
    if excerpt:
        return f"青空『{title}』— {excerpt}"
    return f"青空『{title}』— 一節を噛んだ"


def reflect_on_aozora_passage_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> DirectActionOutcome:
    """PAUSE phase: chew the last passage (v1 = GW-S1; v0 template fallback)."""
    state = load_reading_state()
    if state.phase == "close":
        return close_aozora_reading_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    if state.phase != "pause":
        return DirectActionOutcome(
            ok=False,
            action="reflect_on_aozora_passage",
            summary="No passage waiting to reflect on.",
            detail=f"phase={state.phase}",
        )

    last = state.last_passage or {}
    title = str(last.get("title") or "（作品）")
    author = str(last.get("author") or "")
    passage = str(last.get("text") or "")
    passage_idx = int(last.get("passage_index") or 0)
    if not passage.strip():
        complete_reading_pause(next_move="advance")
        return DirectActionOutcome(
            ok=False,
            action="reflect_on_aozora_passage",
            summary="Last passage empty; advanced.",
            detail="empty_last_passage",
        )

    if passage_reflect_stuck(state):
        after = complete_reading_pause(
            next_move="advance",
            reflected_passage_index=passage_idx,
        )
        summary = _pause_tick_summary(title=title, passage=passage)
        return DirectActionOutcome(
            ok=True,
            action="reflect_on_aozora_passage",
            summary=summary,
            detail="already_reflected_heal",
            desire_satisfied="cognitive_load",
            events=[
                progress_event(phase="reflect", label="青空を噛んでる"),
                activity_event(
                    kind="reflect",
                    label="青空の咀嚼",
                    detail="phase heal → read",
                    ok=True,
                ),
            ],
        )

    total_passages = int(last.get("total_passages") or 1)
    prior_hooks = [state.last_hook] if state.last_hook.strip() else None
    parsed = None
    pause_detail = "v0"
    next_move = "advance"
    hook = ""
    followup_query = ""
    interest_tags: list[str] = []

    if gw_s1_enabled():
        task = build_gw_s1_pause_task(
            title=title,
            author=author,
            passage=passage,
            passage_index=passage_idx,
            total_passages=total_passages,
            sections_this_session=state.sections_this_session,
            prior_hooks=prior_hooks,
        )
        raw = run_silent_internal_turn(task=task, session_id=ctx.session_id or None)
        if raw:
            parsed = parse_pause_response(raw)
        pause_detail = "gw_s1" if parsed else "gw_s1_fallback_v0"

    if parsed:
        hook = parsed.hook
        followup_query = parsed.followup_query
        next_move = parsed.next_move
        interest_tags = list(parsed.interest_tags)
        body = build_pause_reflection_from_gw_s1(
            title=title,
            author=author,
            passage=passage,
            passage_index=passage_idx,
            total_passages=total_passages,
            sections_this_session=state.sections_this_session,
            hook=hook,
            felt=parsed.felt,
            next_move=next_move,
            interest_tags=interest_tags,
            followup_query=followup_query,
        )
    else:
        body = build_pause_reflection_v0(
            title=title,
            author=author,
            passage=passage,
            passage_index=passage_idx,
            total_passages=total_passages,
            sections_this_session=state.sections_this_session,
        )

    outcome = write_private_reflection_direct(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        body=body,
    )
    if not outcome.ok:
        return DirectActionOutcome(
            ok=False,
            action="reflect_on_aozora_passage",
            summary="Pause reflection failed.",
            detail=outcome.detail,
            events=outcome.events,
        )

    after = complete_reading_pause(
        next_move=next_move,
        hook=hook,
        followup_query=followup_query,
        reflected_passage_index=passage_idx,
    )
    summary = _pause_tick_summary(title=title, passage=passage, hook=hook)
    artifacts: dict[str, Any] = {
        "lw_read_phase": "pause",
        "title": title,
        "pause_engine": pause_detail,
        "next_move": next_move,
    }
    if hook:
        artifacts["hook"] = hook[:200]
    if followup_query:
        artifacts["followup_query"] = followup_query[:200]
    if interest_tags:
        artifacts["interest_tags"] = interest_tags[:8]
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_private_reflection",
            summary=summary,
            private_summary=body[:400],
            public_summary="",
            importance=3,
            privacy_level="private",
            related_event_ids=[],
            artifacts=[artifacts],
        )
    )

    if after.phase == "close":
        closed = close_aozora_reading_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
        return DirectActionOutcome(
            ok=closed.ok,
            action="reflect_on_aozora_passage",
            summary=f"{summary} → {closed.summary}",
            detail=closed.detail,
            desire_satisfied="cognitive_load",
            events=outcome.events + closed.events,
        )

    return DirectActionOutcome(
        ok=True,
        action="reflect_on_aozora_passage",
        summary=summary,
        detail=title,
        desire_satisfied="cognitive_load",
        events=[
            progress_event(phase="reflect", label="青空を噛んでる"),
            activity_event(
                kind="reflect",
                label="青空の咀嚼",
                detail=f"{title}: {(hook or body)[:80]}",
                ok=True,
            ),
        ],
    )


async def web_search_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    query: str | None = None,
    source: str = "browse_curiosity",
) -> DirectActionOutcome:
    """Bounded DuckDuckGo instant answer for browse_curiosity or LW-7 followup."""
    used_query = (query or "").strip()[:120] or pick_browse_query(ctx)
    answer, resolved_query = await ddg_instant_answer(used_query)
    used_query = resolved_query or used_query
    if not answer:
        return DirectActionOutcome(
            ok=False,
            action="web_search",
            summary=f"No web result for: {used_query or query}",
            detail="ddg_empty",
            events=[
                activity_event(
                    kind="search",
                    label="Web検索",
                    detail=(used_query or query or "")[:120],
                    ok=False,
                )
            ],
        )

    prefix = "LW-7 WebSearch" if source == "lw7" else "WebSearchで調べた"
    memory_line = f"{prefix}: 「{used_query}」 — {answer[:400]}"
    remember_result = await asyncio.to_thread(
        http_remember,
        content=memory_line,
        category="observation",
        emotion="curious",
        importance=3,
    )
    remember_ok = bool(remember_result.get("ok"))
    summary = answer[:240]
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_autonomous_action",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=[{"query": used_query, "remember_ok": remember_ok, "source": source}],
        )
    )
    return DirectActionOutcome(
        ok=True,
        action="web_search",
        summary=summary,
        detail=used_query,
        desire_satisfied="browse_curiosity",
        events=[
            progress_event(phase="search", label="Webで調べた"),
            activity_event(
                kind="search",
                label="Web検索",
                detail=f"{used_query}: {summary[:80]}",
                ok=True,
            ),
        ],
    )


def think_or_discuss_topic_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> DirectActionOutcome:
    """Light cognitive note for cognitive_load (private reflection style)."""
    parts: list[str] = ["（自律の思考メモ）", plan.why_this_move.strip()]
    if ctx.open_loops:
        topics = ", ".join(loop.topic for loop in ctx.open_loops[:3] if loop.topic)
        if topics:
            parts.append(f"Open loops: {topics}")
    if ctx.compact_prompt_block:
        parts.append(ctx.compact_prompt_block.strip())
    elif ctx.prompt_summary:
        parts.append(ctx.prompt_summary.strip())
    body = "\n\n".join(part for part in parts if part)[:2000]

    outcome = write_private_reflection_direct(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        body=body,
    )
    return DirectActionOutcome(
        ok=outcome.ok,
        action="think_or_discuss_topic",
        summary=outcome.summary,
        detail=outcome.detail,
        events=outcome.events,
        desire_satisfied="cognitive_load",
    )


def recall_memories_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> DirectActionOutcome:
    """Recall via :18900 and persist a private identity note."""
    query = os.getenv("PRESENCE_RECALL_QUERY", "").strip()
    if not query:
        query = ctx.prompt_summary.strip() if ctx.prompt_summary else ""
    if not query:
        query = "こより 自分 アイデンティティ 関係"

    use_divergent = os.getenv("PRESENCE_PULSE_USE_DIVERGENT", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    if use_divergent:
        items = http_recall_divergent(context=query, n_results=4)
    else:
        items = http_recall(query=query, n=4)
    if items:
        lines = []
        for item in items[:4]:
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"- {content[:180]}")
        body = "（自律の記憶なぞり）\n" + "\n".join(lines)
        summary = f"Recalled {len(lines)} memories."
    else:
        body = "（記憶なぞり — 関連する記憶が見つからなかった）"
        summary = "No relevant memories recalled."

    outcome = write_private_reflection_direct(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        body=body[:2000],
    )
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_autonomous_action",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="private",
            related_event_ids=[],
            artifacts=[{"query": query, "hits": len(items)}],
        )
    )
    return DirectActionOutcome(
        ok=outcome.ok,
        action="recall_memories",
        summary=summary,
        detail=query[:120],
        events=[
            progress_event(phase="recall", label="記憶をなぞった"),
            activity_event(
                kind="recall",
                label="記憶なぞり",
                detail=summary[:120],
                ok=outcome.ok,
            ),
        ],
        desire_satisfied="identity_coherence",
    )


async def observe_room_direct(
    stores: PresenceStores,
    *,
    person_id: str,
) -> DirectActionOutcome:
    """Look around via TapoCamera, vision-describe center, store observation memory."""
    from presence_ui.services.camera import camera_failure_hint, camera_look_around
    from presence_ui.services.vision_capture import (
        describe_existing_capture,
        observation_summary_from_vision,
        remember_vision_capture,
    )

    captures = await camera_look_around()
    if not captures:
        hint = camera_failure_hint() or "no captures"
        from presence_ui.services.somatic import maybe_record_eye_affliction

        maybe_record_eye_affliction(
            stores,
            person_id=person_id,
            action="camera_look_around",
            error=hint,
            capture_failed=True,
        )
        return DirectActionOutcome(
            ok=False,
            action="camera_look_around",
            summary=f"Camera look-around failed: {hint}",
            detail=hint,
            events=[
                activity_event(
                    kind="see",
                    label="部屋を見た",
                    detail=hint[:200],
                    ok=False,
                )
            ],
        )

    paths = [c.file_path for c in captures if getattr(c, "file_path", None)]
    vision = await describe_existing_capture(
        captures[0],
        mode="look_around",
        label="--- Center View (room scan) ---",
        extra_line=f"Room scan: {len(captures)} angles captured.",
    )
    if not vision.ok:
        hint = vision.error or "vision describe failed"
        from presence_ui.services.somatic import maybe_record_eye_affliction

        maybe_record_eye_affliction(
            stores,
            person_id=person_id,
            action="camera_look_around",
            error=hint,
            vision=vision,
        )
        return DirectActionOutcome(
            ok=False,
            action="camera_look_around",
            summary=f"Camera look-around vision failed: {hint}",
            detail=hint,
            events=[
                activity_event(
                    kind="see",
                    label="部屋を見た",
                    detail=hint[:200],
                    ok=False,
                )
            ],
        )

    remember_ok = remember_vision_capture(vision)
    summary = observation_summary_from_vision(vision)
    if not vision.caption and len(captures) > 0:
        summary = f"{summary}（{len(captures)} angles）"
    from presence_ui.services.somatic import maybe_record_eye_affliction, maybe_record_eye_ok

    remedy = "vision_reload" if vision.vision_reloaded else None
    affliction = maybe_record_eye_affliction(
        stores,
        person_id=person_id,
        action="camera_look_around",
        vision=vision,
        remedy=remedy,
    )
    if not affliction:
        maybe_record_eye_ok(vision=vision, note=summary[:120])
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_observation",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=[{"capture_count": len(captures), "paths": paths[:4]}],
        )
    )
    stores.social_state.ingest_social_event(
        {
            "ts": utc_now(),
            "source": "gateway_direct",
            "kind": "scene_parse",
            "person_id": person_id,
            "confidence": 0.7,
            "payload": {
                "scene_summary": summary,
                "capture_count": len(captures),
            },
        }
    )
    events = [
        progress_event(phase="see", label="部屋を見渡した"),
        activity_event(
            kind="see",
            label="部屋を見た",
            detail=f"{len(captures)} captures, remember={'ok' if remember_ok else 'fail'}",
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="camera_look_around",
        summary=summary,
        detail=vision.file_path or "",
        events=events,
        desire_satisfied="observe_room" if remember_ok else None,
    )


async def talk_to_companion_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    text: str | None = None,
    skip_cooldown: bool = False,
) -> DirectActionOutcome:
    """Speak to まー when boundary allows (miss_companion)."""
    allowed, reasons = boundary_allows(
        stores, action_type="say", person_id=person_id, urgency="low"
    )
    if not allowed:
        return DirectActionOutcome(
            ok=False,
            action="talk_to_companion",
            summary="Boundary denied say.",
            detail="; ".join(reasons),
            events=[
                activity_event(
                    kind="say",
                    label="声をかけられなかった",
                    detail="; ".join(reasons)[:200],
                    ok=False,
                )
            ],
        )

    line = (text or "").strip()
    if not line:
        from presence_ui.services.llm import generate_koyori_reply

        line = await generate_koyori_reply(
            user_text="（まーに短く一声。居るかどうかわからん。1〜2文。関西弁。）",
            ctx=ctx,
            plan=plan,
            max_tokens=120,
        )

    channels = default_surface_channels()
    enqueue = enqueue_outbound_nudge(
        stores,
        person_id=person_id,
        text=line,
        speak=outbound_nudge_speak_enabled(want_speak=True),
        channels=channels,
        desire="miss_companion",
        skip_cooldown=skip_cooldown,
    )
    if not enqueue.ok:
        return DirectActionOutcome(
            ok=False,
            action="talk_to_companion",
            summary=enqueue.reason or "Outbound enqueue failed.",
            detail=enqueue.reason,
            events=[
                activity_event(
                    kind="say",
                    label="声をかけられなかった",
                    detail=(enqueue.reason or "cooldown")[:200],
                    ok=False,
                )
            ],
        )

    from presence_ui.services.outbound_kiosk import should_deliver_pc_local
    from presence_ui.services.tts import speak_text

    spoke_local = False
    speak_detail = ""
    if voice_local_enabled() and should_deliver_pc_local():
        spoke_local, speak_detail = await speak_text(line, speaker="local")

    try:
        from presence_ui.services.kiosk_say import deliver_speak_to_kiosk
        from presence_ui.services.outbound_kiosk import kiosk_primary_active

        if kiosk_primary_active():
            deliver_speak_to_kiosk(line, source="talk")
    except Exception as exc:
        logger.warning("kiosk talk say failed: %s", exc)

    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_voice_utterance",
            summary=line[:240],
            public_summary=line[:240],
            importance=3,
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
                "via": "presence_outbound",
                "nudge_id": enqueue.nudge_id,
                "channels": list(enqueue.channels),
            },
        }
    )
    events = [
        progress_event(phase="say", label="声をかけた"),
        activity_event(
            kind="say",
            label="声を出した",
            detail=line[:120],
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="talk_to_companion",
        summary=line,
        detail=speak_detail or enqueue.nudge_id or "",
        events=events,
        desire_satisfied="miss_companion",
    )


def _is_junk_reminder_title(label: str) -> bool:
    cleaned = label.strip()
    if len(cleaned) < 4:
        return True
    if cleaned.startswith(("の", "に", "を", "が", "は", "、")):
        return True
    if "にして" in cleaned and "打合せ" not in cleaned and "会議" not in cleaned:
        return True
    return False


def _reminder_spoken_line(*, commitment, text: str) -> str:
    line = (text or "").strip()
    if line:
        return line
    speak_line = (commitment.speak_line or "").strip()
    if speak_line:
        return speak_line
    label = commitment.text.strip()
    if label and not _is_junk_reminder_title(label):
        return f"まー、{label} の時間やで"
    return "まー、リマインドの時間やで"


async def remind_commitment_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    text: str | None = None,
) -> DirectActionOutcome:
    """Deliver a due commitment reminder to まー (OL2)."""
    if not ctx.commitments_due:
        return DirectActionOutcome(
            ok=False,
            action="remind_commitment",
            summary="No due commitment in context.",
        )

    commitment = ctx.commitments_due[0]
    allowed, reasons = boundary_allows(
        stores, action_type="say", person_id=person_id, urgency="moderate"
    )
    if not allowed:
        return DirectActionOutcome(
            ok=False,
            action="remind_commitment",
            summary="Boundary denied say.",
            detail="; ".join(reasons),
            events=[
                activity_event(
                    kind="say",
                    label="リマインドできなかった",
                    detail="; ".join(reasons)[:200],
                    ok=False,
                )
            ],
        )

    line = _reminder_spoken_line(commitment=commitment, text=text or "")

    use_say = commitment.delivery != "nudge_only"
    channels = default_surface_channels()
    enqueue = enqueue_outbound_nudge(
        stores,
        person_id=person_id,
        text=line,
        speak=outbound_nudge_speak_enabled(want_speak=use_say),
        channels=channels,
        desire="reminder",
        skip_cooldown=True,
    )
    if not enqueue.ok:
        return DirectActionOutcome(
            ok=False,
            action="remind_commitment",
            summary=enqueue.reason or "Outbound enqueue failed.",
            detail=enqueue.reason,
            events=[
                activity_event(
                    kind="say",
                    label="リマインドできなかった",
                    detail=(enqueue.reason or "enqueue failed")[:200],
                    ok=False,
                )
            ],
        )

    from presence_ui.services.outbound_kiosk import should_deliver_pc_local
    from presence_ui.services.tts import speak_text

    spoke_local = False
    speak_detail = ""
    if use_say and voice_local_enabled() and should_deliver_pc_local():
        spoke_local, speak_detail = await speak_text(line, speaker="local")

    if use_say:
        try:
            from presence_ui.services.kiosk_say import deliver_speak_to_kiosk
            from presence_ui.services.outbound_kiosk import kiosk_primary_active

            if kiosk_primary_active():
                deliver_speak_to_kiosk(line, source="reminder")
        except Exception as exc:
            logger.warning("kiosk reminder say failed: %s", exc)

    commitment_id = commitment.commitment_id
    if commitment_id:
        try:
            stores.relationship.complete_commitment(commitment_id)
        except Exception as exc:
            logger.warning("complete_commitment failed for %s: %s", commitment_id, exc)

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
                speak=use_say,
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
                "via": "remind_commitment",
                "commitment_id": commitment_id,
                "nudge_id": enqueue.nudge_id,
                "channels": list(enqueue.channels),
            },
        }
    )
    events = [
        progress_event(phase="say", label="リマインドした"),
        activity_event(
            kind="say",
            label="リマインドを伝えた",
            detail=line[:120],
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="remind_commitment",
        summary=line,
        detail=speak_detail or enqueue.nudge_id or "",
        events=events,
    )


def satisfy_desire_direct(
    *,
    desire_name: str,
    action_summary: str,
    person_id: str | None = None,
) -> tuple[bool, str]:
    """Recompute desires.json after a bounded gateway action (desire-system logic)."""
    desire_dir = _REPO_ROOT / "desire-system"
    if not desire_dir.is_dir():
        return False, "desire-system not found"

    if str(desire_dir) not in sys.path:
        sys.path.insert(0, str(desire_dir))

    try:
        from backend import make_default_adapter  # type: ignore[import-not-found]
        from desire_updater import (  # type: ignore[import-not-found]
            DESIRE_CONFIGS,
            DESIRES_PATH,
            compute_desires,
            save_desires,
        )
    except ImportError as exc:
        return False, f"desire-system import failed: {exc}"

    if desire_name not in DESIRE_CONFIGS:
        return False, f"unknown desire: {desire_name}"

    try:
        adapter = make_default_adapter()
        cfg = DESIRE_CONFIGS[desire_name]
        marker = cfg.keywords[0]
        summary_text = action_summary or marker
        adapter.record_satisfaction(
            desire_name=desire_name,
            summary=f"{marker}。{summary_text}",
            ts=datetime.now(timezone.utc),
            metadata={"outcome": "satisfied", "person_id": person_id, "via": "gateway"},
        )
        state = compute_desires(adapter)
        save_desires(state, DESIRES_PATH)
        return True, desire_name
    except Exception as exc:  # noqa: BLE001
        logger.warning("satisfy_desire_direct failed: %s", exc)
        return False, str(exc)


SMOKE_ACTIONS = frozenset(
    {
        "observe_room",
        "look_outside",
        "look_desk",
        "look_dining",
        "miss_companion",
        "write_private_reflection",
        "web_search",
        "read_aozora",
        "think_or_discuss",
        "recall_memories",
    }
)

_PRESET_SMOKE: dict[str, PresetLocation] = {
    "look_outside": "window",
    "look_desk": "desk",
    "look_dining": "dining",
}


async def look_preset_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    location: PresetLocation,
) -> DirectActionOutcome:
    from presence_ui.services.vision_capture import (
        capture_and_describe,
        observation_summary_from_vision,
        remember_vision_capture,
    )

    spec = CAMERA_LOCATIONS[location]
    action = f"camera_look_{location}" if location != "window" else "camera_look_outside"
    activity_label = spec.label_ja

    vision = await capture_and_describe(mode=location, label=spec.capture_label)
    if not vision.ok:
        from presence_ui.services.somatic import maybe_record_eye_affliction

        maybe_record_eye_affliction(
            stores,
            person_id=person_id,
            action=action,
            error=vision.error or "capture failed",
            vision=vision,
            capture_failed=True,
        )
        return DirectActionOutcome(
            ok=False,
            action=action,
            summary=vision.error or "capture failed",
            detail=vision.error or "",
            events=[
                activity_event(
                    kind="see",
                    label=activity_label,
                    detail=(vision.error or "failed")[:200],
                    ok=False,
                )
            ],
        )

    remember_ok = remember_vision_capture(vision)
    summary = observation_summary_from_vision(vision)
    from presence_ui.services.somatic import maybe_record_eye_affliction, maybe_record_eye_ok

    remedy = "vision_reload" if vision.vision_reloaded else None
    affliction = maybe_record_eye_affliction(
        stores,
        person_id=person_id,
        action=action,
        vision=vision,
        remedy=remedy,
    )
    if not affliction:
        maybe_record_eye_ok(vision=vision, note=summary[:120])
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_observation",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=[{"file_path": vision.file_path, "mode": location}],
        )
    )
    return DirectActionOutcome(
        ok=True,
        action=action,
        summary=summary,
        detail=vision.file_path or "",
        desire_satisfied=location if remember_ok and location != "window" else (
            "look_outside" if remember_ok and location == "window" else None
        ),
        events=[
            progress_event(phase="see", label=activity_label),
            activity_event(
                kind="see",
                label=activity_label,
                detail=summary[:120],
                ok=True,
            ),
        ],
    )


async def look_outside_direct(
    stores: PresenceStores,
    *,
    person_id: str,
) -> DirectActionOutcome:
    return await look_preset_direct(stores, person_id=person_id, location="window")


async def execute_smoke_action(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    smoke_action: str,
    speech_text: str | None = None,
) -> DirectActionOutcome:
    """Run one gateway action explicitly (smoke / manual verification)."""
    key = smoke_action.strip()
    if key not in SMOKE_ACTIONS:
        return DirectActionOutcome(
            ok=False,
            action=key,
            summary=f"Unknown smoke_action. Valid: {sorted(SMOKE_ACTIONS)}",
        )

    if key == "observe_room":
        outcome = await observe_room_direct(stores, person_id=person_id)
        if outcome.ok and not outcome.desire_satisfied:
            outcome.desire_satisfied = "observe_room"
    elif key == "look_outside":
        outcome = await look_outside_direct(stores, person_id=person_id)
    elif key in _PRESET_SMOKE:
        outcome = await look_preset_direct(
            stores,
            person_id=person_id,
            location=_PRESET_SMOKE[key],
        )
    elif key == "miss_companion":
        outcome = await talk_to_companion_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            text=speech_text,
            skip_cooldown=True,
        )
    elif key == "web_search":
        outcome = await web_search_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif key == "read_aozora":
        outcome = await read_aozora_passage_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif key == "think_or_discuss":
        outcome = think_or_discuss_topic_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif key == "recall_memories":
        outcome = recall_memories_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    else:
        outcome = write_private_reflection_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )

    return await _finalize_autonomous_outcome(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        outcome=outcome,
        record_experience=True,
    )


async def _finalize_autonomous_outcome(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    outcome: DirectActionOutcome,
    record_experience: bool,
) -> DirectActionOutcome:
    if outcome.desire_satisfied:
        ok, detail = await asyncio.to_thread(
            satisfy_desire_direct,
            desire_name=outcome.desire_satisfied,
            action_summary=outcome.summary,
            person_id=person_id,
        )
        if ok:
            outcome.events.append(
                activity_event(
                    kind="desire",
                    label="欲求を満たした",
                    detail=outcome.desire_satisfied or "",
                    ok=True,
                )
            )
        else:
            logger.info("desire satisfy skipped: %s", detail)

    followup = plan.followup_action or {}
    dominant = ctx.agent_state.dominant_desire
    if followup.get("kind") == "satisfy_desire" and not outcome.desire_satisfied:
        name = str(followup.get("desire_name") or dominant or "")
        if name:
            await asyncio.to_thread(
                satisfy_desire_direct,
                desire_name=name,
                action_summary=outcome.summary,
                person_id=person_id,
            )

    if (
        record_experience
        and outcome.ok
        and outcome.action
        not in {
            "stay_silent",
            "defer",
            "quietly_prepare",
            "web_search",
            "read_aozora_passage",
            "reflect_on_aozora_passage",
            "close_aozora_reading",
            "think_or_discuss_topic",
            "recall_memories",
        }
    ):
        stores.orchestrator.record_agent_experience(
            RecordAgentExperienceInput(
                ts=utc_now(),
                person_id=person_id,
                kind="agent_autonomous_action",
                summary=outcome.summary[:240],
                public_summary=outcome.summary[:240],
                importance=3,
                privacy_level="relationship",
                related_event_ids=[],
            )
        )
    return outcome


async def execute_autonomous_plan(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    speech_text: str | None = None,
) -> DirectActionOutcome:
    """Run one bounded action from an autonomous compose/plan result."""
    move = plan.primary_move

    if move == "write_private_reflection":
        return write_private_reflection_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )

    if move in {"stay_silent", "defer", "quietly_prepare"}:
        return DirectActionOutcome(
            ok=True,
            action=move,
            summary=f"No action ({move}).",
            events=[progress_event(phase="silent", label="静かに過ごす")],
        )

    if move != "act_autonomously":
        return DirectActionOutcome(
            ok=False,
            action=move,
            summary=f"Unsupported autonomous move: {move}",
        )

    allowed = list(plan.initiative.allowed_actions or [])
    dominant = ctx.agent_state.dominant_desire
    quiet_active = quiet_from_context(ctx)
    inward = inward_autonomous_window(ctx=ctx, quiet_active=quiet_active)

    if "remind_commitment" in allowed and ctx.commitments_due:
        outcome = await remind_commitment_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            text=speech_text,
        )
    elif inward:
        reading = load_reading_state()
        if should_run_lw7_web_search(reading):
            outcome = await web_search_direct(
                stores,
                person_id=person_id,
                ctx=ctx,
                plan=plan,
                query=pending_followup_query(reading),
                source="lw7",
            )
            if outcome.ok:
                clear_pending_followup()
        elif reading.phase == "close" and (
            "reflect_on_aozora_passage" in allowed
            or "read_aozora_passage" in allowed
            or "close_aozora_reading" in allowed
        ):
            outcome = close_aozora_reading_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        elif (
            passage_needs_reflect(reading) or passage_reflect_stuck(reading)
        ) and (
            "reflect_on_aozora_passage" in allowed
            or "read_aozora_passage" in allowed
        ):
            outcome = reflect_on_aozora_passage_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        elif reading.phase == "read" and "read_aozora_passage" in allowed:
            outcome = await read_aozora_passage_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        elif "think_or_discuss_topic" in allowed:
            outcome = think_or_discuss_topic_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        elif "write_private_reflection" in allowed:
            outcome = write_private_reflection_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        elif "recall_memories" in allowed:
            outcome = recall_memories_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        elif "web_search" in allowed:
            outcome = await web_search_direct(
                stores, person_id=person_id, ctx=ctx, plan=plan
            )
        else:
            outcome = DirectActionOutcome(
                ok=True,
                action="act_autonomously",
                summary="No executable allowed_action; skipped.",
            )
    elif "web_search" in allowed or (
        not inward and dominant == "browse_curiosity"
    ):
        outcome = await web_search_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif "read_aozora_passage" in allowed:
        outcome = await read_aozora_passage_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif "think_or_discuss_topic" in allowed or (
        not inward and dominant == "cognitive_load"
    ):
        outcome = think_or_discuss_topic_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif "recall_memories" in allowed or dominant == "identity_coherence":
        outcome = recall_memories_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif "camera_look_around" in allowed or (
        not inward and dominant == "observe_room"
    ):
        outcome = await observe_room_direct(stores, person_id=person_id)
    elif "camera_look_outside" in allowed or (
        not inward and dominant == "look_outside"
    ):
        outcome = await look_outside_direct(stores, person_id=person_id)
    elif "talk_to_companion" in allowed or (
        not inward and dominant == "miss_companion"
    ):
        outcome = await talk_to_companion_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            text=speech_text,
        )
    elif "write_private_reflection" in allowed:
        outcome = write_private_reflection_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    else:
        outcome = DirectActionOutcome(
            ok=True,
            action="act_autonomously",
            summary="No executable allowed_action; skipped.",
        )

    return await _finalize_autonomous_outcome(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        outcome=outcome,
        record_experience=(move == "act_autonomously"),
    )
