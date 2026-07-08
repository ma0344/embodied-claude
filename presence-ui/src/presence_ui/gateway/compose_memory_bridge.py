"""MEM-8h-C hook — cue-driven memory bridge (cross-session dated gist)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from interaction_orchestrator_mcp.memory_bridge import (
    apply_memory_bridge_to_context,
    bridge_max_lines,
    bridge_recall_n,
    extract_bridge_keywords,
    filter_bridge_hits_by_retired_topics,
    format_bridge_lines,
    hits_from_http_items,
    memory_bridge_enabled,
    merge_bridge_hits,
)
from interaction_orchestrator_mcp.memory_retrieve_route import (
    MemoryRetrieveRoute,
    allows_memory_bridge,
    classify_memory_retrieve_route,
    memory_retrieve_route_enabled,
)
from interaction_orchestrator_mcp.schemas import InteractionContext
from relationship_mcp.inference import is_recall_utterance

from presence_ui.gateway.memory_http import http_recall

if TYPE_CHECKING:
    from social_core import SocialDB


def resolve_memory_retrieve_route(user_text: str) -> MemoryRetrieveRoute:
    if not memory_retrieve_route_enabled():
        return "compose_default"
    return classify_memory_retrieve_route(
        user_text,
        is_recall_utterance=is_recall_utterance(user_text),
    )


def maybe_enrich_memory_bridge(
    ctx: InteractionContext,
    *,
    user_text: str,
    max_chars: int,
    route: MemoryRetrieveRoute | None = None,
    prefetch_fact_check: bool = False,
    social_db: SocialDB | None = None,
) -> tuple[InteractionContext, str | None]:
    """Run kw → :18900 recall → [memory_bridge] tier-1 pin when route allows."""
    resolved = route or resolve_memory_retrieve_route(user_text)
    if not allows_memory_bridge(resolved):
        return ctx, None
    if not memory_bridge_enabled():
        return ctx, None

    keywords = extract_bridge_keywords(user_text)
    if not keywords:
        return ctx, None

    retired_topics: list[str] = []
    if social_db is not None and ctx.person_id:
        from interaction_orchestrator_mcp.topic_retire import (
            TopicRetireStore,
            topic_retire_enabled,
        )

        if topic_retire_enabled():
            retired_topics = TopicRetireStore(social_db).active_retired_topics(
                person_id=ctx.person_id
            )

    existing = {m.content.strip() for m in ctx.relevant_memories if m.content.strip()}
    batches: list = []
    for keyword in keywords:
        items = http_recall(query=keyword, n=bridge_recall_n())
        batch = hits_from_http_items(items, keyword=keyword)
        if batch:
            batches.append(
                filter_bridge_hits_by_retired_topics(
                    batch,
                    retired_topics=retired_topics,
                )
            )

    hits = merge_bridge_hits(
        batches,
        existing_contents=existing,
        max_lines=bridge_max_lines(),
    )
    if not hits:
        return ctx, None

    bridge_lines = format_bridge_lines(hits, tz_name=ctx.timezone)
    updated = apply_memory_bridge_to_context(
        ctx,
        bridge_lines=bridge_lines,
        bridge_keywords=keywords,
        bridge_hits=hits,
        user_text=user_text,
        max_chars=max_chars,
        prefetch_fact_check=prefetch_fact_check,
        social_db=social_db,
    )
    label = f"記憶ブリッジ ({len(hits)} 件 · {', '.join(keywords[:3])})"
    return updated, label
