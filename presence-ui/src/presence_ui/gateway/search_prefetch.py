"""WS-2a/2b — gateway web search prefetch for conversation."""

from __future__ import annotations

import re
from typing import Any

from presence_ui.gateway.room_events import progress_event
from presence_ui.gateway.web_search import SearchHit, search_with_urls
from presence_ui.gateway.ws5_spontaneous import resolve_ws5_prefetch
from presence_ui.gateway.ws5b_weather import (
    extract_region_label,
    resolve_ws5b_prefetch,
)
from presence_ui.gateway.ws5c_offer import (
    classify_ws5c_reply,
    format_ws5c_decline_block,
    format_ws5c_offer_block,
    should_ws5c_offer,
    ws5c_enabled,
)
from presence_ui.gateway.ws5c_offer import (
    clear_pending as clear_ws5c_pending,
)
from presence_ui.gateway.ws5c_offer import (
    load_pending as load_ws5c_pending,
)
from presence_ui.gateway.ws5c_offer import (
    make_pending as make_ws5c_pending,
)
from presence_ui.gateway.ws5c_offer import (
    save_pending as save_ws5c_pending,
)
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
    if resolve_ws5_prefetch(text) is not None:
        return True
    return resolve_ws5b_prefetch(text) is not None


def resolve_web_search_prefetch(
    text: str,
    *,
    timezone: str = "Asia/Tokyo",
) -> tuple[str, str] | None:
    """Return (source, query) — ws2 → ws5 → ws5b."""
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
    ws5 = resolve_ws5_prefetch(line, timezone=timezone)
    if ws5 is not None:
        return ws5
    return resolve_ws5b_prefetch(line)


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
    if answer.strip():
        lines.append(f"answer={answer.strip()[:900]}")
    if url_hits:
        for index, hit in enumerate(url_hits[:5], 1):
            lines.append(_format_hit_line(index, hit))
    elif not answer.strip():
        snippet = rows[0].snippet if rows else ""
        if snippet:
            lines.append(f"answer={snippet[:900]}")
    lines.append("[/web_search_prefetch]")
    lines.append("")
    if status == "ok" and (url_hits or answer or rows):
        if source == "ws5b":
            directive = (
                "Gateway answered a direct weather/temp ask (WS-5b, no-confirm).\n"
                "Open with the region premise (if present) and the concrete numbers "
                "from answer= above (℃ / weather). Do NOT invent temperatures.\n"
                "Brief chat after the numbers is fine. Do NOT call WebSearch/WebFetch.\n"
                "Do NOT invent Sources or URLs beyond the prefetch."
            )
        elif source == "ws5":
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
        elif source == "ws5c":
            directive = (
                "Gateway ran web search after まー consented to a WS-5c offer.\n"
                "You MUST answer from prefetch: lead with concrete hits "
                "(title/URL/snippet or url_prefetch excerpt).\n"
                "Do NOT tell まー to check the city website or call themselves "
                "instead of using the results you already have.\n"
                "If status was empty/error, say lookup failed honestly.\n"
                "Do NOT call WebSearch/WebFetch. Do NOT invent Sources beyond the prefetch."
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
            "Gateway web search failed.\nTell まー honestly lookup failed; do NOT invent results."
        )
    lines.append("[Gateway directive — not for the user]")
    lines.append(directive)
    return "\n".join(lines)


async def web_search_for_message(
    query: str,
) -> tuple[list[SearchHit], str, str, str]:
    """Return (hits, query_used, status, backend)."""
    return await search_with_urls(query)


async def _prefetch_ws5b_weather(
    message: str,
    query: str,
) -> tuple[list[SearchHit], str, str, str, str]:
    """Prefer JMA forecast API; fall back to tiered_search (SERP/L1)."""
    from presence_ui.gateway.weather_api import (
        JMA_FORECAST_URL,
        fetch_jma_matsumoto_weather,
        format_weather_answer,
    )

    region_label, used_default = extract_region_label(message)
    snap = await fetch_jma_matsumoto_weather(region_label=region_label)
    if snap is not None:
        answer = format_weather_answer(snap, used_default_region=used_default)
        hit = SearchHit(
            url=JMA_FORECAST_URL,
            title="気象庁:予報",
            snippet=answer,
        )
        return [hit], query, "ok", "jma_forecast", answer

    hits, used_query, status, backend = await web_search_for_message(query)
    answer = ""
    if status == "ok" and hits:
        # Surface still gets snippets; premise when region was defaulted.
        if used_default:
            answer = f"{region_label}（前提・地域未指定） " + (hits[0].snippet or "")[:800]
        else:
            answer = (hits[0].snippet or "")[:900]
    return hits, used_query or query, status, backend, answer


async def _run_resolved_prefetch(
    *,
    text: str,
    source: str,
    query: str,
) -> tuple[str | None, list[dict[str, Any]], list[SearchHit], str]:
    answer = ""
    if source == "ws5":
        from presence_ui.gateway.search_tier import ws5_record_fetch, ws5_should_skip_fetch

        if ws5_should_skip_fetch(query):
            return None, [], [], ""
        hits, used_query, status, backend = await web_search_for_message(query)
        ws5_record_fetch()
    elif source == "ws5b":
        from presence_ui.gateway.search_tier import (
            ws5b_record_fetch,
            ws5b_should_skip_fetch,
        )

        if ws5b_should_skip_fetch(query):
            return None, [], [], ""
        hits, used_query, status, backend, answer = await _prefetch_ws5b_weather(text, query)
        ws5b_record_fetch()
    else:
        # ws2 / ws5c — shared tiered_search pipe
        hits, used_query, status, backend = await web_search_for_message(query)

    block = format_web_search_prefetch_block(
        query=used_query or query,
        hits=hits,
        answer=answer,
        status=status,
        backend=backend,
        source=source,
    )
    if status == "ok":
        if source == "ws2":
            label = "ネットを調べた"
        elif source == "ws5c":
            label = "ネットを調べた"
        elif source == "ws5b":
            label = "天気を確認した"
        else:
            label = "話の内容を調べた"
    elif status == "empty":
        label = "検索したが見つからなかった"
    else:
        label = "検索に失敗した"
    return block, [progress_event(phase="web_search", label=label)], hits, used_query or query


def _calendar_awaiting_confirm(person_id: str) -> bool:
    """True when calendar owns affirm for this person (fail-open → False)."""
    try:
        from presence_ui.gateway.calendar_pending import load_pending as load_cal_pending

        record = load_cal_pending(person_id=person_id)
    except Exception:
        return False
    return record is not None and record.status == "awaiting_confirm"


def _ws5c_active() -> bool:
    """5c needs both its own flag and the shared web-search prefetch switch."""
    return ws5c_enabled() and web_search_prefetch_enabled()


async def prefetch_web_search_for_message(
    message: str,
    *,
    timezone: str = "Asia/Tokyo",
    person_id: str = "ma",
) -> tuple[str | None, list[dict[str, Any]], list[SearchHit], str]:
    """Run bounded web search — pending 5c → WS-2 → WS-5 → WS-5b → 5c offer.

    When no 5c pending: WS-2 first (unchanged). When pending exists, classify
    consent before WS-2 so 「調べて」 uses stored suggested_query (trigger=ws5c).
    """
    text = (message or "").strip()
    if not text:
        return None, [], [], ""

    five_c_on = _ws5c_active()
    cal_awaiting = _calendar_awaiting_confirm(person_id)

    # 1) Pending 5c consent/decline first (before WS-2 cue words like 「調べて」).
    if five_c_on:
        pending = load_ws5c_pending(person_id=person_id)
        if pending is not None:
            decision = classify_ws5c_reply(text, pending)
            if decision == "accept" and cal_awaiting:
                # Calendar owns affirm — do not consume as 5c accept.
                pass
            elif decision == "accept":
                query = pending.suggested_query.strip()
                clear_ws5c_pending(person_id=person_id)
                if not query:
                    return None, [], [], ""
                return await _run_resolved_prefetch(text=text, source="ws5c", query=query)
            elif decision == "decline":
                clear_ws5c_pending(person_id=person_id)
                return format_ws5c_decline_block(), [], [], ""
            else:
                # ignore / unclassified: keep pending (TTL) so「うん。お願い」typos can retry
                pass

    # 2) Explicit WS-2 (no pending, or pending just cleared as ignore).
    if looks_like_web_search_request(text):
        if five_c_on:
            clear_ws5c_pending(person_id=person_id)
        resolved = resolve_web_search_prefetch(text, timezone=timezone)
        if not resolved:
            return None, [], [], ""
        source, query = resolved
        return await _run_resolved_prefetch(text=text, source=source, query=query)

    # 3–4) WS-5 v0 → WS-5b (resolve order unchanged)
    resolved = resolve_web_search_prefetch(text, timezone=timezone)
    if resolved:
        source, query = resolved
        return await _run_resolved_prefetch(text=text, source=source, query=query)

    # 5) WS-5c offer only on resolve miss + gate (NO SERP). Skip if calendar confirm.
    if five_c_on and not cal_awaiting and should_ws5c_offer(text):
        record = make_ws5c_pending(person_id=person_id, source_utterance=text)
        if not record.suggested_query.strip():
            return None, [], [], ""
        save_ws5c_pending(record)
        return (
            format_ws5c_offer_block(record),
            [progress_event(phase="web_search", label="調べるか確認する")],
            [],
            "",
        )

    return None, [], [], ""
