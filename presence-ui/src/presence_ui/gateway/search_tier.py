"""L0–L2 tiered web search — session cache, authority URLs, then API backends (L3)."""

from __future__ import annotations

import os
import re
import time
from typing import TYPE_CHECKING

from presence_ui.gateway.web_search import SearchHit

if TYPE_CHECKING:
    pass

_CACHE: dict[str, tuple[float, list[SearchHit], str, str, str]] = {}
_ws5_last_fetch_at: float = 0.0
_ws5b_last_fetch_at: float = 0.0

_JMA_TSUYU = "https://www.data.jma.go.jp/cpd/bosai/season/tsuyu_index.html"
_JMA_QUAKE = "https://www.data.jma.go.jp/multi/quake/index.html"
_JMA_TYPHOON = "https://www.data.jma.go.jp/multi/cyclone/index.html"


def normalize_query_key(query: str) -> str:
    q = re.sub(r"\s+", " ", (query or "").strip().lower())
    return q[:120]


def cache_ttl_sec() -> int:
    raw = os.getenv("PRESENCE_WEB_SEARCH_CACHE_TTL_SEC", "900").strip()
    try:
        return max(60, min(int(raw), 3600))
    except ValueError:
        return 900


def ws5_cooldown_sec() -> int:
    raw = os.getenv("PRESENCE_WS5_COOLDOWN_SEC", "90").strip()
    try:
        return max(0, min(int(raw), 600))
    except ValueError:
        return 90


def ws5b_cooldown_sec() -> int:
    """Separate from WS-5 so weather spam does not starve disaster prefetch."""
    raw = os.getenv("PRESENCE_WS5B_COOLDOWN_SEC", "60").strip()
    try:
        return max(0, min(int(raw), 600))
    except ValueError:
        return 60


def get_cached(query: str) -> tuple[list[SearchHit], str, str, str] | None:
    key = normalize_query_key(query)
    row = _CACHE.get(key)
    if not row:
        return None
    expires_at, hits, used, status, backend = row
    if expires_at <= time.monotonic():
        _CACHE.pop(key, None)
        return None
    return hits, used, status, backend


def store_cache(
    query: str,
    hits: list[SearchHit],
    used: str,
    status: str,
    backend: str,
) -> None:
    key = normalize_query_key(query)
    _CACHE[key] = (
        time.monotonic() + cache_ttl_sec(),
        hits,
        used,
        status,
        backend,
    )


def clear_search_cache() -> None:
    """Test helper — drop all cached search rows."""
    _CACHE.clear()


def ws5_should_skip_fetch(query: str) -> bool:
    """Throttle WS-5 spontaneous fetches (same query may still hit L0 cache)."""
    if get_cached(query):
        return False
    cooldown = ws5_cooldown_sec()
    if cooldown <= 0:
        return False
    return (time.monotonic() - _ws5_last_fetch_at) < cooldown


def ws5_record_fetch() -> None:
    global _ws5_last_fetch_at
    _ws5_last_fetch_at = time.monotonic()


def reset_ws5_cooldown() -> None:
    """Test helper — allow immediate WS-5 fetch."""
    global _ws5_last_fetch_at
    _ws5_last_fetch_at = 0.0


def ws5b_should_skip_fetch(query: str) -> bool:
    """Throttle WS-5b weather fetches (independent of WS-5 disaster cooldown)."""
    if get_cached(query):
        return False
    cooldown = ws5b_cooldown_sec()
    if cooldown <= 0:
        return False
    return (time.monotonic() - _ws5b_last_fetch_at) < cooldown


def ws5b_record_fetch() -> None:
    global _ws5b_last_fetch_at
    _ws5b_last_fetch_at = time.monotonic()


def reset_ws5b_cooldown() -> None:
    """Test helper — allow immediate WS-5b fetch."""
    global _ws5b_last_fetch_at
    _ws5b_last_fetch_at = 0.0


def direct_url_candidates(query: str) -> list[str]:
    """L2 — known authority pages before paid SERP APIs."""
    q = (query or "").strip()
    if not q:
        return []
    urls: list[str] = []
    if re.search(r"梅雨|入梅|明け|季節", q):
        urls.append(_JMA_TSUYU)
    if re.search(r"地震|震度|余震", q):
        urls.append(_JMA_QUAKE)
    if re.search(r"台風|暴風|接近", q):
        urls.append(_JMA_TYPHOON)
    return urls


async def fetch_direct_url_hits(query: str) -> list[SearchHit]:
    from presence_ui.gateway.url_prefetch import (
        fetch_url_excerpt,
        is_excerpt_satisfactory,
        query_terms,
        select_excerpt,
    )

    terms = query_terms(query)
    hits: list[SearchHit] = []
    for url in direct_url_candidates(query)[:2]:
        excerpt, status = await fetch_url_excerpt(url, query_terms_list=terms)
        if status != "ok" or not excerpt.strip():
            continue
        if not is_excerpt_satisfactory(excerpt, terms) and len(excerpt.strip()) < 120:
            continue
        label = urlparse_last_segment(url)
        snippet = select_excerpt(excerpt, terms, max_chars=900)
        hits.append(
            SearchHit(
                url=url,
                title=f"気象庁:{label}",
                snippet=snippet,
            )
        )
        break
    return hits


def urlparse_last_segment(url: str) -> str:
    segment = url.rstrip("/").rsplit("/", 1)[-1]
    return segment or "page"


async def tiered_search(query: str) -> tuple[list[SearchHit], str, str, str]:
    """L0 cache → L2 direct URL → L1 DDG instant → L3 Brave."""
    from presence_ui.gateway.web_search import search_api_backends

    q = query.strip()[:120]
    if not q:
        return [], "", "empty", "none"

    cached = get_cached(q)
    if cached:
        hits, used, status, backend = cached
        return hits, used, status, f"cache:{backend}"

    direct_hits = await fetch_direct_url_hits(q)
    if direct_hits:
        store_cache(q, direct_hits, q, "ok", "direct_url")
        return direct_hits, q, "ok", "direct_url"

    hits, used, status, backend = await search_api_backends(q)
    if status == "ok" and hits:
        store_cache(q, hits, used or q, status, backend)
    return hits, used or q, status, backend
