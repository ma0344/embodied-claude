"""MEM-8g — filter compose memories for surface injection (no regex topic filters)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from interaction_orchestrator_mcp.memory_adapter import _extract_keywords
from interaction_orchestrator_mcp.recall_query import is_episodic_blob
from interaction_orchestrator_mcp.schemas import RelevantMemoryRef
from interaction_orchestrator_mcp.topic_retire import (
    TopicRetireStore,
    memory_matches_retired_topics,
    topic_retire_enabled,
)

if TYPE_CHECKING:
    from social_core import SocialDB


def compose_salience_enabled() -> bool:
    import os

    raw = os.getenv("PRESENCE_COMPOSE_SALIENCE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _keyword_overlap(user_text: str, memory_content: str) -> bool:
    user_kw = set(_extract_keywords(user_text or "", max_keywords=8))
    if not user_kw:
        return False
    mem_kw = set(_extract_keywords(memory_content or "", max_keywords=12))
    return bool(user_kw & mem_kw)


def apply_compose_memory_salience(
    memories: list[RelevantMemoryRef],
    *,
    user_text: str | None,
    person_id: str | None,
    db: SocialDB | None = None,
    prefetch_fact_check: bool = False,
) -> list[RelevantMemoryRef]:
    """Demote episodic / retired / off-topic hits — never promote episodic to mentionable."""
    if not compose_salience_enabled():
        return memories

    retired: list[str] = []
    if topic_retire_enabled() and db is not None and person_id:
        retired = TopicRetireStore(db).active_retired_topics(person_id=person_id)

    utterance = user_text or ""
    adjusted: list[RelevantMemoryRef] = []
    for mem in memories:
        policy = mem.use_policy
        reason = mem.reason
        episodic = is_episodic_blob(mem.content)

        if episodic or "会話の区切り" in mem.content or "会話の一区切り" in mem.content:
            policy = "background_only"
            reason = "episodic_not_for_surface"
        if retired and memory_matches_retired_topics(mem.content, retired):
            policy = "background_only"
            reason = "topic_retired"
        elif episodic and utterance and not _keyword_overlap(utterance, mem.content):
            policy = "background_only"
            reason = "episodic_off_topic"
        if prefetch_fact_check and episodic:
            policy = "do_not_surface"
            reason = "prefetch_fact_check_episodic_omitted"

        if policy == mem.use_policy and reason == mem.reason:
            adjusted.append(mem)
        else:
            adjusted.append(
                RelevantMemoryRef(
                    memory_id=mem.memory_id,
                    content=mem.content,
                    relevance=mem.relevance,
                    use_policy=policy,
                    reason=reason,
                )
            )
    return adjusted


def select_surface_memories(
    memories: list[RelevantMemoryRef],
    *,
    prefetch_fact_check: bool = False,
) -> tuple[list[RelevantMemoryRef], list[RelevantMemoryRef]]:
    """Return (mentionable_for_surface, background_for_surface)."""
    mentionable = [
        m
        for m in memories
        if m.use_policy == "mentionable" and not is_episodic_blob(m.content)
    ]
    background = [
        m
        for m in memories
        if m.use_policy == "background_only" and not is_episodic_blob(m.content)
    ]
    if prefetch_fact_check:
        background = []
    return mentionable[:3], background[:2]
