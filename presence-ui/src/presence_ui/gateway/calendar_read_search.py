"""GAPI-2s — calendar read keyword filter (e4b primary, quoted fallback only).

Regex here is intentionally minimal: one well-formed 「…」 or 『…』 pair when e4b
did not return ``search_query``. Nested/mixed quotes are skipped (e4b handles those).
"""

from __future__ import annotations

import re

from presence_ui.gapi.calendar_client import CalendarEvent

_QUOTE_PAIRS = (("「", "」"), ("『", "』"))

_TEMPORAL_ONLY = frozenset(
    {
        "今日",
        "明日",
        "あした",
        "昨日",
        "きのう",
        "来週",
        "今週",
        "来月",
        "今月",
        "今年",
        "来年",
        "今日以降",
        "今後",
        "これから",
        "これより先",
    }
)


def sanitize_calendar_search_query(query: str | None) -> str | None:
    """Drop temporal noise e4b sometimes copies into search_query."""
    text = (query or "").strip()
    if not text:
        return None
    for term in sorted(_TEMPORAL_ONLY, key=len, reverse=True):
        text = re.sub(re.escape(term) + r"(?:の)?", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" の")
    return text[:80] if text else None


def extract_quoted_search_fallback(utterance: str) -> str | None:
    """First complete quote pair with no nested quote chars inside (e4b miss only)."""
    text = (utterance or "").strip()
    if not text:
        return None
    opener_count = sum(text.count(open_ch) for open_ch, _ in _QUOTE_PAIRS)
    if opener_count != 1:
        return None
    for open_ch, close_ch in _QUOTE_PAIRS:
        start = text.find(open_ch)
        if start < 0:
            continue
        end = text.find(close_ch, start + len(open_ch))
        if end < 0:
            continue
        inner = text[start + len(open_ch) : end].strip()
        if not inner or inner in _TEMPORAL_ONLY:
            continue
        if any(marker in inner for marker in "「」『』"):
            continue
        return inner[:80]
    return None


def resolve_calendar_search_query(
    utterance: str,
    *,
    e4b_search: str | None = None,
) -> str | None:
    """e4b window → e4b search-only → quoted fallback."""
    query = sanitize_calendar_search_query(e4b_search)
    if query:
        return query
    from presence_ui.gateway.calendar_read_stage import run_calendar_read_search_extract

    search_extract = run_calendar_read_search_extract(utterance=utterance)
    if search_extract and search_extract.search_query:
        return sanitize_calendar_search_query(search_extract.search_query)
    return extract_quoted_search_fallback(utterance)


def event_matches_search_query(event: CalendarEvent, query: str) -> bool:
    needle = (query or "").strip().casefold()
    if not needle:
        return True
    for field in (event.summary, event.location):
        if needle in (field or "").casefold():
            return True
    return False


def filter_events_by_search_query(
    events: list[CalendarEvent],
    query: str | None,
) -> list[CalendarEvent]:
    q = (query or "").strip()
    if not q:
        return events
    return [event for event in events if event_matches_search_query(event, q)]
