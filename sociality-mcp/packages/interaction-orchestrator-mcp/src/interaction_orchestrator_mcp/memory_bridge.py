"""MEM-8h-C — cue-driven memory bridge (kw → dated gist for compose pin)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.recall_query import compose_hit_rank, is_episodic_blob
from interaction_orchestrator_mcp.schemas import InteractionContext

if TYPE_CHECKING:
    from social_core import SocialDB


@dataclass(frozen=True, slots=True)
class MemoryBridgeHit:
    keyword: str
    content: str
    timestamp: str | None
    score: float


def memory_bridge_enabled() -> bool:
    raw = os.getenv("PRESENCE_MEM8H_BRIDGE", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def bridge_max_keywords() -> int:
    raw = os.getenv("PRESENCE_MEM8H_BRIDGE_KEYWORDS", "3")
    try:
        return max(1, min(5, int(raw)))
    except ValueError:
        return 3


def bridge_recall_n() -> int:
    raw = os.getenv("PRESENCE_MEM8H_BRIDGE_N", "2")
    try:
        return max(1, min(5, int(raw)))
    except ValueError:
        return 2


def bridge_max_lines() -> int:
    raw = os.getenv("PRESENCE_MEM8H_BRIDGE_MAX_LINES", "3")
    try:
        return max(1, min(6, int(raw)))
    except ValueError:
        return 3


def extract_bridge_keywords(user_text: str) -> list[str]:
    from interaction_orchestrator_mcp.memory_retrieve_route import bridge_topic_keywords

    return bridge_topic_keywords(user_text)[: bridge_max_keywords()]


def _format_bridge_date(timestamp: str | None, *, tz_name: str) -> str:
    if not timestamp:
        return "日付不明"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo(tz_name)).date().isoformat()
    except (ValueError, KeyError):
        return timestamp[:10] if len(timestamp) >= 10 else "日付不明"


def _snippet(content: str, *, episodic: bool) -> str:
    text = " ".join(content.split()).strip()
    limit = 100 if episodic else 140
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def hits_from_http_items(
    items: list[dict[str, Any]],
    *,
    keyword: str,
) -> list[MemoryBridgeHit]:
    hits: list[MemoryBridgeHit] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content or is_episodic_blob(content):
            continue
        score = float(item.get("score") or 0.0)
        ts = item.get("timestamp")
        timestamp = str(ts).strip() if ts else None
        hits.append(
            MemoryBridgeHit(
                keyword=keyword,
                content=content,
                timestamp=timestamp,
                score=compose_hit_rank(content, base_relevance=score, temporal=False),
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def merge_bridge_hits(
    batches: list[list[MemoryBridgeHit]],
    *,
    existing_contents: set[str],
    max_lines: int,
) -> list[MemoryBridgeHit]:
    seen: set[str] = set(existing_contents)
    merged: list[MemoryBridgeHit] = []
    for batch in batches:
        for hit in batch:
            key = hit.content.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    merged.sort(key=lambda h: h.score, reverse=True)
    return merged[:max_lines]


def format_bridge_lines(
    hits: list[MemoryBridgeHit],
    *,
    tz_name: str,
) -> list[str]:
    lines: list[str] = []
    for hit in hits:
        day = _format_bridge_date(hit.timestamp, tz_name=tz_name)
        snippet = _snippet(hit.content, episodic=is_episodic_blob(hit.content))
        lines.append(f"- {day}: {snippet}")
    return lines


def apply_memory_bridge_to_context(
    ctx: InteractionContext,
    *,
    bridge_lines: list[str],
    user_text: str | None,
    max_chars: int,
    prefetch_fact_check: bool = False,
    social_db: SocialDB | None = None,
) -> InteractionContext:
    """Rebuild compact block with tier-1 [memory_bridge] pin."""
    from interaction_orchestrator_mcp.compose import _build_prompt_summary, _compact_block

    memories = list(ctx.relevant_memories)
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
        memory_bridge_lines=bridge_lines,
    )
    return ctx.model_copy(
        update={
            "prompt_summary": prompt_summary,
            "compact_prompt_block": compact_prompt_block,
        }
    )
