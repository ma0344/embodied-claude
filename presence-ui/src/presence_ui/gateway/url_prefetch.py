"""WS-2c — fetch URL excerpts for conversation (query-aware, bounded loop)."""

from __future__ import annotations

import os
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx

from presence_ui.gateway.room_events import progress_event
from presence_ui.gateway.search_prefetch import extract_search_query
from presence_ui.gateway.web_search import SearchHit

_URL_RE = re.compile(r"https?://[^\s<>\"')\]}]+", re.IGNORECASE)
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_MAIN_RE = re.compile(
    r"<(?:main|article)[^>]*>(.*)</(?:main|article)>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def url_prefetch_enabled() -> bool:
    raw = os.getenv("PRESENCE_URL_PREFETCH", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _max_excerpt_chars() -> int:
    raw = os.getenv("PRESENCE_URL_PREFETCH_MAX_CHARS", "6000").strip()
    try:
        return max(500, min(int(raw), 8000))
    except ValueError:
        return 6000


def _max_message_urls() -> int:
    raw = os.getenv("PRESENCE_URL_PREFETCH_MAX_URLS", "2").strip()
    try:
        return max(1, min(int(raw), 3))
    except ValueError:
        return 2


def _search_max_attempts() -> int:
    raw = os.getenv("PRESENCE_URL_PREFETCH_SEARCH_MAX_ATTEMPTS", "3").strip()
    try:
        return max(1, min(int(raw), 5))
    except ValueError:
        return 3


def _fetch_timeout_sec() -> float:
    raw = os.getenv("PRESENCE_URL_PREFETCH_TIMEOUT_SEC", "12").strip()
    try:
        return max(3.0, min(float(raw), 30.0))
    except ValueError:
        return 12.0


def _max_response_bytes() -> int:
    raw = os.getenv("PRESENCE_URL_PREFETCH_MAX_BYTES", "1048576").strip()
    try:
        return max(50_000, min(int(raw), 5_000_000))
    except ValueError:
        return 1_048_576


def extract_urls_from_message(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;:)」』、。")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def query_terms(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    terms: list[str] = []
    for match in re.finditer(r"[\u3040-\u9fff]{2,}", q):
        term = match.group()
        if term not in terms:
            terms.append(term)
    for match in re.finditer(r"[A-Za-z]{3,}", q):
        term = match.group().lower()
        if term not in terms:
            terms.append(term)
    return terms[:16]


def html_to_text(html: str) -> str:
    body = html or ""
    body = _SCRIPT_STYLE_RE.sub(" ", body)
    main = _MAIN_RE.search(body)
    if main and len(main.group(1)) > 200:
        body = main.group(1)
    body = _BR_RE.sub("\n", body)
    body = _TAG_RE.sub(" ", body)
    body = unescape(body)
    body = re.sub(r"[ \t\f\v]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def _excerpt_score(text: str, terms: list[str]) -> int:
    if not text:
        return 0
    lower = text.lower()
    score = 0
    for term in terms:
        if term in text or term.lower() in lower:
            score += max(2, len(term))
    return score


def _term_hits(text: str, terms: list[str]) -> int:
    if not text:
        return 0
    lower = text.lower()
    return sum(1 for term in terms if term in text or term.lower() in lower)


def is_excerpt_satisfactory(excerpt: str, terms: list[str]) -> bool:
    body = (excerpt or "").strip()
    if len(body) < 80:
        return False
    if not terms:
        return len(body) >= 200
    long_terms = [term for term in terms if len(term) >= 4]
    if long_terms and not any(term in body for term in long_terms):
        return False
    return _excerpt_score(body, terms) >= 8


def select_excerpt(text: str, terms: list[str], *, max_chars: int) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars:
        return raw

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return raw[:max_chars]

    anchor = 0
    best_score = -1
    for index, line in enumerate(lines):
        score = _term_hits(line, terms)
        if score > best_score:
            best_score = score
            anchor = index

    if best_score > 0:
        start = max(0, anchor - 4)
        end = min(len(lines), anchor + 28)
        chunk = "\n".join(lines[start:end])
        if len(chunk) > max_chars:
            return chunk[:max_chars]
        return chunk

    return raw[:max_chars]


def _looks_like_pdf(url: str, content_type: str) -> bool:
    if url.lower().split("?", 1)[0].endswith(".pdf"):
        return True
    return "application/pdf" in (content_type or "").lower()


async def fetch_url_excerpt(
    url: str,
    *,
    query_terms_list: list[str] | None = None,
) -> tuple[str, str]:
    """Return (excerpt, status) where status is ok|empty|failed|pdf_unsupported|blocked."""
    target = (url or "").strip()
    if not target:
        return "", "failed"

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        return "", "failed"

    headers = {
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "User-Agent": os.getenv(
            "PRESENCE_URL_PREFETCH_USER_AGENT",
            "KoyoriPresence/1.0 (+https://github.com/ma/embodied-claude)",
        ),
    }
    try:
        async with httpx.AsyncClient(
            timeout=_fetch_timeout_sec(),
            follow_redirects=True,
        ) as client:
            response = await client.get(target, headers=headers)
            if response.status_code in {401, 403}:
                return "", "blocked"
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if _looks_like_pdf(target, content_type):
                return "", "pdf_unsupported"
            raw = response.content[: _max_response_bytes()]
            html = raw.decode(response.encoding or "utf-8", errors="replace")
    except (httpx.HTTPError, UnicodeError, ValueError):
        return "", "failed"

    text = html_to_text(html)
    if not text:
        return "", "empty"
    excerpt = select_excerpt(text, query_terms_list or [], max_chars=_max_excerpt_chars())
    if not excerpt.strip():
        return "", "empty"
    return excerpt.strip(), "ok"


def format_url_prefetch_block(
    *,
    url: str,
    excerpt: str,
    status: str,
    source: str,
    attempt: int = 0,
    also_tried: list[str] | None = None,
    search_rank: int = 0,
) -> str:
    lines = [
        "[url_prefetch]",
        f"source={source}",
        f"url={url.strip()}",
        f"status={status}",
    ]
    if attempt:
        lines.append(f"attempt={attempt}")
    if search_rank:
        lines.append(f"search_rank={search_rank}")
    if also_tried:
        lines.append(f"also_tried={', '.join(also_tried[:5])}")
    if excerpt.strip():
        lines.append(f"excerpt={excerpt.strip()[: _max_excerpt_chars()]}")
    lines.append("[/url_prefetch]")
    lines.append("")
    if status == "ok" and excerpt.strip():
        directive = (
            "Gateway fetched this page excerpt. Describe page contents ONLY from excerpt above.\n"
            "Do NOT infer details from search snippets or training data.\n"
            "If excerpt lacks the answer, say so honestly and point to other numbered search URLs."
        )
    elif status == "pdf_unsupported":
        directive = (
            "This URL is a PDF (not fetched). Do NOT claim you read the file.\n"
            "Tell まー to open the PDF locally or paste a HTML page URL."
        )
    elif status == "blocked":
        directive = "Gateway could not access this URL (blocked). Do NOT invent page contents."
    else:
        directive = (
            "Gateway could not extract useful page text. Do NOT invent page contents.\n"
            "Use search URL list only for links; be honest about unread pages."
        )
    lines.append("[Gateway directive — not for the user]")
    lines.append(directive)
    return "\n".join(lines)


def _combine_blocks(blocks: list[str]) -> str | None:
    cleaned = [block.strip() for block in blocks if block.strip()]
    if not cleaned:
        return None
    return "\n\n".join(cleaned)


async def _fetch_search_hit_with_loop(
    hits: list[SearchHit],
    *,
    search_query: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    terms = query_terms(search_query)
    candidates = [hit for hit in hits if hit.url][: _search_max_attempts()]
    if not candidates:
        return None, []

    events = [progress_event(phase="url_fetch", label="ページを読んでる…")]
    tried: list[str] = []
    best: tuple[str, str, str, int] | None = None

    for index, hit in enumerate(candidates, 1):
        tried.append(hit.url)
        excerpt, status = await fetch_url_excerpt(hit.url, query_terms_list=terms)
        if status == "ok" and excerpt:
            score = _excerpt_score(excerpt, terms)
            if best is None or score >= _excerpt_score(best[1], terms):
                best = (hit.url, excerpt, status, index)
            if is_excerpt_satisfactory(excerpt, terms):
                block = format_url_prefetch_block(
                    url=hit.url,
                    excerpt=excerpt,
                    status=status,
                    source="search_loop",
                    attempt=index,
                    also_tried=tried[:-1],
                    search_rank=index,
                )
                return block, events

    if best:
        url, excerpt, status, attempt = best
        block = format_url_prefetch_block(
            url=url,
            excerpt=excerpt,
            status=status,
            source="search_loop",
            attempt=attempt,
            also_tried=[u for u in tried if u != url],
            search_rank=attempt,
        )
        return block, events

    if tried:
        block = format_url_prefetch_block(
            url=tried[-1],
            excerpt="",
            status="empty",
            source="search_loop",
            attempt=len(tried),
            also_tried=tried[:-1],
            search_rank=len(tried),
        )
        return block, events

    return None, events


async def prefetch_urls_for_turn(
    message: str,
    *,
    search_hits: list[SearchHit] | None = None,
    search_query: str = "",
) -> tuple[str | None, list[dict[str, Any]]]:
    """Fetch URL excerpts from pasted links or search-hit loop."""
    if not url_prefetch_enabled():
        return None, []

    text = (message or "").strip()
    pasted = extract_urls_from_message(text)[: _max_message_urls()]
    if pasted:
        blocks: list[str] = []
        events = [progress_event(phase="url_fetch", label="ページを読んでる…")]
        terms = query_terms(search_query or extract_search_query(text))
        for url in pasted:
            excerpt, status = await fetch_url_excerpt(url, query_terms_list=terms)
            blocks.append(
                format_url_prefetch_block(
                    url=url,
                    excerpt=excerpt,
                    status=status,
                    source="pasted",
                )
            )
        return _combine_blocks(blocks), events

    if search_hits:
        query = search_query or extract_search_query(text)
        return await _fetch_search_hit_with_loop(search_hits, search_query=query)

    return None, []
