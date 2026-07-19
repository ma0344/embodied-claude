"""MEM-8b — conditional compose stage-2 recall (gateway prefetch, not LM tool loop)."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, Literal

from interaction_orchestrator_mcp.compose_salience import (
    apply_compose_memory_salience,
    health_safety_active_from_somatic,
    select_surface_memories,
)
from interaction_orchestrator_mcp.memory_adapter import _hits_from_http_items
from interaction_orchestrator_mcp.recall_query import (
    build_recall_queries,
    extract_schedule_facts,
    is_temporal_question,
)
from interaction_orchestrator_mcp.schemas import InteractionContext, RelevantMemoryRef

if TYPE_CHECKING:
    from social_core import SocialDB

Stage2Trigger = Literal[
    "recall_utterance",
    "temporal_thin",
    "temporal_empty",
    "thin_mentionable",
    "history_question",
]

_HISTORY_Q = re.compile(r"思い出|以前|前に|昔|あの時|あの頃|覚えて|覚えと|記憶")


def compose_recall_stage2_enabled() -> bool:
    raw = os.getenv("PRESENCE_COMPOSE_RECALL_STAGE2", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def compose_recall_stage2_divergent_enabled() -> bool:
    raw = os.getenv("PRESENCE_COMPOSE_RECALL_STAGE2_DIVERGENT", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def count_mentionable(memories: list[RelevantMemoryRef]) -> int:
    mentionable, _ = select_surface_memories(memories)
    return len(mentionable)


def should_run_compose_recall_stage2(
    *,
    user_text: str | None,
    relevant_memories: list[RelevantMemoryRef],
    is_recall_utterance: bool = False,
) -> tuple[bool, Stage2Trigger | None]:
    """Return (run, trigger_reason)."""
    if not compose_recall_stage2_enabled():
        return False, None
    text = (user_text or "").strip()
    if len(text) < 2:
        return False, None

    from interaction_orchestrator_mcp.memory_retrieve_route import (
        allows_compose_recall_stage2,
        classify_memory_retrieve_route,
        memory_retrieve_route_enabled,
    )
    from interaction_orchestrator_mcp.recall_query import should_skip_compose_recall

    if memory_retrieve_route_enabled():
        route = classify_memory_retrieve_route(
            text,
            is_recall_utterance=is_recall_utterance,
        )
        if not allows_compose_recall_stage2(route):
            return False, None

    if should_skip_compose_recall(text) and not is_recall_utterance:
        return False, None

    mentionable_n = count_mentionable(relevant_memories)
    temporal = is_temporal_question(text)

    if is_recall_utterance:
        return True, "recall_utterance"

    if temporal:
        sources = [m.content for m in relevant_memories]
        facts = extract_schedule_facts(text, sources)
        if not facts:
            return True, "temporal_empty" if not relevant_memories else "temporal_thin"
        if mentionable_n == 0:
            return True, "temporal_thin"

    if mentionable_n == 0 and relevant_memories and len(text) >= 6:
        return True, "thin_mentionable"

    if mentionable_n == 0 and not relevant_memories and len(text) >= 8:
        if _HISTORY_Q.search(text):
            return True, "history_question"
        if temporal:
            return True, "temporal_empty"

    return False, None


def build_stage2_recall_queries(
    *,
    user_text: str,
    profile_gists: list[str] | None,
    trigger: Stage2Trigger,
) -> list[str]:
    """Extra HTTP /recall queries beyond compose stage-1 (0–4)."""
    from interaction_orchestrator_mcp.recall_query import (
        _entities_in_text,
        _keyword_query,
        _normalize_queries,
    )

    text = user_text.strip()
    gists = [g.strip() for g in (profile_gists or []) if g and g.strip()]
    queries: list[str] = []

    stage1 = build_recall_queries(purpose="compose", user_text=text, profile_gists=gists)
    entities = _entities_in_text(text)

    if trigger in {"temporal_thin", "temporal_empty"}:
        entity_part = " ".join(entities) if entities else _keyword_query(text, max_keywords=4)
        queries.extend(
            [
                f"{entity_part} 水曜 午前 スケジュール まー",
                f"{entity_part} 予定 曜日 時間",
                f"{entity_part} 仕事 定例",
            ]
        )

    if trigger == "recall_utterance":
        queries.append(_keyword_query(text, max_keywords=8))
        queries.append(f"まー {_keyword_query(text, max_keywords=5)}")

    if trigger in {"thin_mentionable", "history_question"}:
        queries.append(_keyword_query(text, max_keywords=8))
        if entities:
            queries.append(" ".join([*entities, "まー"]))

    if trigger == "history_question":
        queries.append(f"まー {_keyword_query(text, max_keywords=6)} 会話")

    # Follow-up keyword path when stage-1 queries were empty (deixis-only etc.)
    if not stage1 and not queries:
        queries.append(_keyword_query(text))

    # Avoid repeating stage-1 query strings verbatim.
    seen = set(stage1)
    out: list[str] = []
    for q in _normalize_queries(queries):
        if q in seen:
            continue
        seen.add(q)
        out.append(q)
    return out[:4]


def http_items_to_memory_refs(
    items: list[dict[str, Any]],
    *,
    temporal: bool,
    include_private: bool = True,
    max_results: int = 6,
) -> list[RelevantMemoryRef]:
    hits = _hits_from_http_items(
        items,
        max_results=max(max_results, 8),
        include_private=include_private,
        purpose="compose",
        temporal=temporal,
    )
    refs: list[RelevantMemoryRef] = []
    for hit in hits:
        refs.append(
            RelevantMemoryRef(
                memory_id=hit.memory_id or None,
                content=hit.content,
                relevance=hit.relevance,
                use_policy=hit.use_policy,
                reason=(hit.reason or "") + "; stage2_recall",
            )
        )
    return refs


def merge_memory_refs(
    existing: list[RelevantMemoryRef],
    extra: list[RelevantMemoryRef],
    *,
    max_total: int = 10,
) -> list[RelevantMemoryRef]:
    seen: set[str] = set()
    merged: list[RelevantMemoryRef] = []
    for mem in [*existing, *extra]:
        key = mem.content.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(mem)
    merged.sort(key=lambda m: m.relevance, reverse=True)
    return merged[:max_total]


def refresh_interaction_context_memories(
    ctx: InteractionContext,
    *,
    relevant_memories: list[RelevantMemoryRef],
    user_text: str | None,
    max_chars: int,
    prefetch_fact_check: bool = False,
    social_db: SocialDB | None = None,
    health_safety_active: bool | None = None,
) -> InteractionContext:
    """Re-run salience + rebuild compact block after stage-2 merge."""
    from interaction_orchestrator_mcp.compose import _build_prompt_summary, _compact_block

    if health_safety_active is None:
        health_safety_active = health_safety_active_from_somatic(ctx.somatic_state)

    memories = apply_compose_memory_salience(
        relevant_memories,
        user_text=user_text,
        person_id=ctx.person_id,
        db=social_db,
        prefetch_fact_check=prefetch_fact_check,
        health_safety_active=health_safety_active,
    )
    profile_gists = list((ctx.person_model or {}).get("profile_gists") or [])
    person_name = ctx.person_name
    if not person_name and ctx.person_model:
        person_name = str(ctx.person_model.get("canonical_name") or "") or None

    quiet_active = bool(
        ctx.boundary_hints and any("quiet" in h.lower() for h in ctx.boundary_hints)
    )
    desires = dict(ctx.agent_state.desires or {})
    dominant_desire = ctx.agent_state.dominant_desire

    from social_core.date_resolution import calendar_anchor_line

    calendar_anchor = calendar_anchor_line(ts=ctx.ts, tz_name=ctx.timezone)

    prompt_summary = _build_prompt_summary(
        local_time=ctx.local_time,
        calendar_anchor=calendar_anchor,
        person_id=ctx.person_id,
        person_name=person_name,
        social_state=ctx.social_state,
        agent_state=ctx.agent_state,
        quiet_active=quiet_active,
        dominant_desire=dominant_desire,
        desires=desires,
        open_loops=ctx.open_loops,
        relevant_memories=memories,
    )
    compact_prompt_block = _compact_block(
        prompt_summary=prompt_summary,
        response_contract=ctx.response_contract,
        relevant_memories=memories,
        user_text=user_text,
        session_context_block=ctx.session_context_block,
        dominant_desire=dominant_desire,
        desires=desires,
        discomforts=dict(ctx.agent_state.discomforts or {}),
        open_loops=ctx.open_loops,
        loops_due_for_check=ctx.loops_due_for_check,
        commitments_due=ctx.commitments_due,
        recent_shifts=ctx.agent_state.recent_interpretation_shifts,
        recent_experiences=ctx.recent_experiences,
        profile_gists=profile_gists,
        max_chars=max_chars,
        prefetch_fact_check=prefetch_fact_check,
    )
    return ctx.model_copy(
        update={
            "relevant_memories": memories,
            "prompt_summary": prompt_summary,
            "compact_prompt_block": compact_prompt_block,
        }
    )


def stage2_use_divergent(trigger: Stage2Trigger) -> bool:
    if not compose_recall_stage2_divergent_enabled():
        return False
    return trigger in {"recall_utterance", "thin_mentionable", "history_question"}


def stage2_divergent_context(
    *,
    user_text: str,
    profile_gists: list[str] | None,
    trigger: Stage2Trigger,
) -> str:
    gists = [g.strip() for g in (profile_gists or []) if g and g.strip()]
    parts = [user_text.strip()]
    if gists:
        parts.extend(gists[:3])
    if trigger == "recall_utterance":
        parts.append("まー 覚えてる 記憶")
    return " ".join(parts)[:480]
