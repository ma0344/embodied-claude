"""Bounded web search for autonomous browse_curiosity."""

from __future__ import annotations

import os
import random

import httpx
from interaction_orchestrator_mcp.schemas import InteractionContext, OpenLoopSummary

_DDG_URL = "https://api.duckduckgo.com/"


def pick_browse_query(ctx: InteractionContext) -> str:
    """Choose a short query for autonomous curiosity browsing."""
    env = os.getenv("PRESENCE_WEB_SEARCH_QUERY", "").strip()
    if env:
        return env[:120]

    loops: list[OpenLoopSummary] = list(ctx.open_loops or [])
    for loop in loops[:2]:
        topic = (loop.topic or "").strip()
        if len(topic) >= 4:
            return topic[:120]

    if ctx.prompt_summary:
        summary = ctx.prompt_summary.strip()
        if len(summary) >= 6:
            return summary[:120]

    raw_defaults = os.getenv(
        "PRESENCE_WEB_SEARCH_DEFAULTS",
        "ローカル LLM,心血管 AI,エージェント記憶",
    )
    choices = [part.strip() for part in raw_defaults.split(",") if part.strip()]
    return random.choice(choices) if choices else "technology news"


async def ddg_instant_answer(
    query: str,
    *,
    timeout_sec: float = 10.0,
) -> tuple[str, str]:
    """Return (answer_text, query_used). Empty answer on failure."""
    q = query.strip()[:120]
    if not q:
        return "", ""

    params = {
        "q": q,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(_DDG_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return "", q

    abstract = str(data.get("AbstractText") or "").strip()
    if abstract:
        return abstract[:900], q

    related = data.get("RelatedTopics") or []
    snippets: list[str] = []
    for item in related:
        if isinstance(item, dict):
            text = str(item.get("Text") or "").strip()
            if text:
                snippets.append(text[:280])
        if len(snippets) >= 2:
            break

    if snippets:
        return "\n".join(snippets)[:900], q

    heading = str(data.get("Heading") or "").strip()
    if heading:
        return heading[:400], q

    return "", q
