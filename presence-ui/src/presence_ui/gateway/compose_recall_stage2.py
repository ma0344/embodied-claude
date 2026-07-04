"""Gateway hook — conditional compose stage-2 memory prefetch (MEM-8b)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from interaction_orchestrator_mcp.schemas import InteractionContext
from interaction_orchestrator_mcp.stage2_recall import (
    Stage2Trigger,
    build_stage2_recall_queries,
    count_mentionable,
    http_items_to_memory_refs,
    merge_memory_refs,
    refresh_interaction_context_memories,
    should_run_compose_recall_stage2,
    stage2_divergent_context,
    stage2_use_divergent,
)
from relationship_mcp.inference import is_recall_utterance

from presence_ui.gateway.memory_http import http_recall, http_recall_divergent

if TYPE_CHECKING:
    from social_core import SocialDB


def _stage2_recall_n() -> int:
    raw = os.environ.get("PRESENCE_COMPOSE_RECALL_STAGE2_N", "6")
    try:
        return max(2, min(10, int(raw)))
    except ValueError:
        return 6


def _fetch_stage2_hits(
    *,
    user_text: str,
    profile_gists: list[str],
    trigger: Stage2Trigger,
    temporal: bool,
    include_private: bool,
) -> list[dict]:
    items: list[dict] = []
    seen_content: set[str] = set()

    def _add(raw_items: list[dict]) -> None:
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content or content in seen_content:
                continue
            seen_content.add(content)
            items.append(item)

    for query in build_stage2_recall_queries(
        user_text=user_text,
        profile_gists=profile_gists,
        trigger=trigger,
    ):
        _add(http_recall(query=query, n=_stage2_recall_n()))

    if stage2_use_divergent(trigger):
        context = stage2_divergent_context(
            user_text=user_text,
            profile_gists=profile_gists,
            trigger=trigger,
        )
        _add(
            http_recall_divergent(
                context=context,
                n_results=_stage2_recall_n(),
                max_branches=3,
                max_depth=2,
            )
        )

    return items


def maybe_enrich_compose_recall_stage2(
    ctx: InteractionContext,
    *,
    user_text: str,
    max_chars: int,
    include_private: bool = True,
    prefetch_fact_check: bool = False,
    social_db: SocialDB | None = None,
) -> tuple[InteractionContext, str | None]:
    """Run stage-2 recall when stage-1 compose memories are thin. Returns (ctx, label)."""
    from interaction_orchestrator_mcp.recall_query import is_temporal_question

    recall = is_recall_utterance(user_text)
    run, trigger = should_run_compose_recall_stage2(
        user_text=user_text,
        relevant_memories=list(ctx.relevant_memories),
        is_recall_utterance=recall,
    )
    if not run or trigger is None:
        return ctx, None

    before = count_mentionable(ctx.relevant_memories)
    profile_gists = list((ctx.person_model or {}).get("profile_gists") or [])
    temporal = is_temporal_question(user_text)
    raw_items = _fetch_stage2_hits(
        user_text=user_text,
        profile_gists=profile_gists,
        trigger=trigger,
        temporal=temporal,
        include_private=include_private,
    )
    if not raw_items:
        return ctx, None

    extra = http_items_to_memory_refs(
        raw_items,
        temporal=temporal,
        include_private=include_private,
        max_results=_stage2_recall_n(),
    )
    if not extra:
        return ctx, None

    merged = merge_memory_refs(list(ctx.relevant_memories), extra)
    updated = refresh_interaction_context_memories(
        ctx,
        relevant_memories=merged,
        user_text=user_text,
        max_chars=max_chars,
        prefetch_fact_check=prefetch_fact_check,
        social_db=social_db,
    )
    after = count_mentionable(updated.relevant_memories)
    if after <= before and trigger not in {"recall_utterance", "temporal_thin", "temporal_empty"}:
        return ctx, None

    label = f"記憶を深掘り ({trigger}, mentionable {before}→{after})"
    return updated, label
