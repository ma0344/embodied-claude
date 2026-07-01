"""WS-2a/2b — gateway web search prefetch for conversation."""

from __future__ import annotations

import re
from typing import Any

from presence_ui.gateway.room_events import progress_event
from presence_ui.gateway.web_search import SearchHit, search_with_urls
from presence_ui.gateway.ws5_spontaneous import resolve_ws5_prefetch
from presence_ui.gateway.ws_guard import looks_like_web_search_request

_SEARCH_STRIP_RES = (
    re.compile(r"^(?:まー[:、]?\s*)", re.I),
    re.compile(
        r"(?:調べて(?:くれる|もらえる|ください)?|検索して(?:くれる|もらえる)?|"
        r"ネットで(?:調べ|探して)|オンラインで(?:調べ|探して)|"
        r"ググって(?:くれる)?|見つけて(?:くれる|もらえる)?|"
        r"探して(?:くれる|もらえる)?)(?:て|で)?",
        re.I,
    ),
    re.compile(r"(?:って|とこ|の)(?:あるか|ある\??|どこ|知りたい)[？?]?$", re.I),
    re.compile(r"[？?！!。．、,]+$"),
)


def web_search_prefetch_enabled() -> bool:
    import os

    raw = os.getenv("PRESENCE_WEB_SEARCH_PREFETCH", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def detect_web_search_intent(text: str) -> bool:
    if not web_search_prefetch_enabled():
        return False
    if looks_like_web_search_request(text):
        return True
    return resolve_ws5_prefetch(text) is not None


def resolve_web_search_prefetch(
    text: str,
    *,
    timezone: str = "Asia/Tokyo",
) -> tuple[str, str] | None:
    """Return (source, query) — ``ws2`` explicit or ``ws5`` spontaneous."""
    if not web_search_prefetch_enabled():
        return None
    line = (text or "").strip()
    if not line:
        return None
    if looks_like_web_search_request(line):
        query = extract_search_query(line)
        if query:
            return ("ws2", query)
        return None
    return resolve_ws5_prefetch(line, timezone=timezone)


def extract_search_query(text: str) -> str:
    """Rule-based query from まー utterance (max 120 chars)."""
    q = (text or "").strip()
    if not q:
        return ""
    for pattern in _SEARCH_STRIP_RES:
        q = pattern.sub("", q).strip()
    q = re.sub(r"\s+", " ", q).strip()
    if len(q) < 3:
        q = (text or "").strip()[:120]
    return q[:120]


def _format_hit_line(index: int, hit: SearchHit) -> str:
    label = hit.title or hit.url
    line = f"{index}. {hit.url} — {label}"
    if hit.snippet:
        line += f"… {hit.snippet[:220]}"
    return line[:500]


def format_web_search_prefetch_block(
    *,
    query: str,
    hits: list[SearchHit] | None = None,
    answer: str = "",
    status: str,
    backend: str = "",
    source: str = "",
) -> str:
    rows = list(hits or [])
    url_hits = [hit for hit in rows if hit.url]
    lines = [
        "[web_search_prefetch]",
        f"query={query.strip()[:120]}",
        f"status={status}",
    ]
    if source:
        lines.append(f"trigger={source}")
    if backend:
        lines.append(f"backend={backend}")
    if url_hits:
        for index, hit in enumerate(url_hits[:5], 1):
            lines.append(_format_hit_line(index, hit))
    else:
        snippet = answer.strip() or (rows[0].snippet if rows else "")
        if snippet:
            lines.append(f"answer={snippet[:900]}")
    lines.append("[/web_search_prefetch]")
    lines.append("")
    if status == "ok" and (url_hits or answer or rows):
        if source == "ws5":
            directive = (
                "Gateway already looked up まー's report (WS-5 spontaneous fact-check).\n"
                "Open your reply with at least one concrete fact from [url_prefetch] excerpt "
                "or [web_search_prefetch] answer/snippets (date, place, official status).\n"
                "Brief empathy or chat is fine AFTER grounding — "
                "do NOT reply as if you never looked.\n"
                "Page body details must come from [url_prefetch] when present; "
                "do NOT infer page contents from snippets alone.\n"
                "Do NOT call WebSearch/WebFetch. Do NOT invent Sources or URLs beyond the prefetch."
            )
        else:
            directive = (
                "Gateway ran web search. URL list/snippets above are for discovery only.\n"
                "Page body details must come from [url_prefetch] excerpt if present — "
                "do NOT infer page contents from snippets alone.\n"
                "Do NOT call WebSearch/WebFetch. Do NOT invent Sources or URLs beyond the prefetch."
            )
    elif status == "empty":
        directive = (
            "Gateway web search returned no useful results.\n"
            "Tell まー honestly you could not find it online yet.\n"
            "Do NOT invent URLs, Sources, or page contents. Ask for a direct URL if helpful."
        )
    else:
        directive = (
            "Gateway web search failed.\n"
            "Tell まー honestly lookup failed; do NOT invent results."
        )
    lines.append("[Gateway directive — not for the user]")
    lines.append(directive)
    return "\n".join(lines)


async def web_search_for_message(
    query: str,
) -> tuple[list[SearchHit], str, str, str]:
    """Return (hits, query_used, status, backend)."""
    return await search_with_urls(query)


async def prefetch_web_search_for_message(
    message: str,
    *,
    timezone: str = "Asia/Tokyo",
) -> tuple[str | None, list[dict[str, Any]], list[SearchHit], str]:
    """Run bounded web search — WS-2 explicit or WS-5 spontaneous fact-check."""
    text = (message or "").strip()
    resolved = resolve_web_search_prefetch(text, timezone=timezone)
    if not resolved:
        return None, [], [], ""

    source, query = resolved
    if source == "ws5":
        from presence_ui.gateway.search_tier import ws5_record_fetch, ws5_should_skip_fetch

        if ws5_should_skip_fetch(query):
            return None, [], [], ""
        hits, used_query, status, backend = await web_search_for_message(query)
        ws5_record_fetch()
    else:
        hits, used_query, status, backend = await web_search_for_message(query)
    block = format_web_search_prefetch_block(
        query=used_query or query,
        hits=hits,
        status=status,
        backend=backend,
        source=source,
    )
    if status == "ok":
        label = "ネットを調べた" if source == "ws2" else "話の内容を調べた"
    elif status == "empty":
        label = "検索したが見つからなかった"
    else:
        label = "検索に失敗した"
    return block, [progress_event(phase="web_search", label=label)], hits, used_query or query
