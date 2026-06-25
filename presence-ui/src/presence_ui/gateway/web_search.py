"""Bounded web search for autonomous browse_curiosity and WS-2b conversation prefetch."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import httpx
from interaction_orchestrator_mcp.schemas import InteractionContext, OpenLoopSummary

_DDG_URL = "https://api.duckduckgo.com/"
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass(frozen=True, slots=True)
class SearchHit:
    url: str
    title: str
    snippet: str


def web_search_backend() -> str:
    raw = os.getenv("PRESENCE_WEB_SEARCH_BACKEND", "auto").strip().lower()
    if raw in {"auto", "brave", "ddg", "instant"}:
        return raw
    return "auto"


def _brave_api_key() -> str:
    from presence_ui.repo_env import load_repo_env

    load_repo_env(force=True)
    return (
        os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        or os.getenv("BRAVE_API_KEY", "").strip()
    )


def _web_search_max_results() -> int:
    raw = os.getenv("PRESENCE_WEB_SEARCH_MAX_RESULTS", "3").strip()
    try:
        return max(1, min(int(raw), 5))
    except ValueError:
        return 3


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


async def brave_web_search(
    query: str,
    *,
    count: int | None = None,
    timeout_sec: float = 12.0,
) -> list[SearchHit]:
    """Brave Search API — returns URL + title + snippet hits."""
    key = _brave_api_key()
    q = query.strip()[:120]
    if not key or not q:
        return []

    limit = count if count is not None else _web_search_max_results()
    params: dict[str, str | int] = {
        "q": q,
        "count": limit,
        "country": os.getenv("PRESENCE_WEB_SEARCH_COUNTRY", "JP"),
        "search_lang": os.getenv("PRESENCE_WEB_SEARCH_LANG", "jp"),
    }
    headers = {
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "X-Subscription-Token": key,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(_BRAVE_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return []

    raw_results = data.get("web", {}).get("results") if isinstance(data, dict) else None
    if not isinstance(raw_results, list):
        return []

    hits: list[SearchHit] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("description") or item.get("snippet") or "").strip()
        hits.append(
            SearchHit(
                url=url,
                title=title[:200],
                snippet=snippet[:280],
            )
        )
        if len(hits) >= limit:
            break
    return hits


async def search_with_urls(
    query: str,
) -> tuple[list[SearchHit], str, str, str]:
    """Return (hits, query_used, status, backend) where status is ok|empty|failed."""
    q = query.strip()[:120]
    if not q:
        return [], "", "empty", "none"

    backend = web_search_backend()
    try:
        if backend in {"auto", "brave"} and (backend == "brave" or _brave_api_key()):
            hits = await brave_web_search(q)
            if hits:
                return hits, q, "ok", "brave"
            if backend == "brave":
                return [], q, "empty", "brave"

        if backend in {"auto", "ddg", "instant"}:
            answer, used = await ddg_instant_answer(q)
            if answer.strip():
                return (
                    [SearchHit(url="", title="", snippet=answer.strip()[:900])],
                    used or q,
                    "ok",
                    "ddg_instant",
                )
    except Exception:
        return [], q, "failed", backend

    return [], q, "empty", backend
