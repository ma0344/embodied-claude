"""DOC-READ D — persist book map gist + first-discussion markers to memory-mcp.

A: after map generation — gist for bridge recall (even before まー discusses the book).
B: on first successful doc_context prefetch — 「まーと話した」experience row.

See docs/tracks/doc-read-discuss.md §4 D.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from presence_ui.gateway.deterministic_memory import (
    RememberIntent,
    RememberOutcome,
    persist_remember_intent,
)
from presence_ui.services import doc_read

logger = logging.getLogger(__name__)

_JST = ZoneInfo("Asia/Tokyo")


def doc_memory_enabled() -> bool:
    return os.getenv("PRESENCE_DOC_MEMORY", "1").strip().lower() not in ("0", "false", "no", "off")


def _gist_max_chars() -> int:
    raw = os.getenv("PRESENCE_DOC_MEMORY_GIST_MAX_CHARS", "3500").strip()
    try:
        return max(800, min(int(raw), 8000))
    except ValueError:
        return 3500


def _jst_now() -> str:
    return datetime.now(tz=_JST).isoformat(timespec="seconds")


def _display_title(doc_id: str) -> str:
    for entry in doc_read.list_registry():
        if entry.doc_id == doc_id and entry.title:
            return entry.title
    meta = doc_read.load_meta(doc_id)
    return meta.title if meta else doc_id


def _aliases(doc_id: str) -> list[str]:
    for entry in doc_read.list_registry():
        if entry.doc_id == doc_id:
            return list(entry.aliases or [])
    return []


def gist_for_memory(map_text: str, *, max_chars: int | None = None) -> str:
    """Trim map.md to an L3-safe gist (from ## 全体 onward)."""
    limit = max_chars if max_chars is not None else _gist_max_chars()
    raw = (map_text or "").strip()
    if not raw:
        return ""
    if "## 全体" in raw:
        raw = raw[raw.index("## 全体"):]
    elif "## 章ごと" in raw:
        raw = raw[raw.index("## 章ごと"):]
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + "…"


def _map_memory_content(doc_id: str, *, map_gist: str) -> str:
    title = _display_title(doc_id)
    aliases = _aliases(doc_id)
    alias_line = ", ".join(aliases) if aliases else "（なし）"
    return (
        "[doc_read — 本の地図 gist]\n"
        f"title: {title}\n"
        f"doc_id: {doc_id}\n"
        f"aliases: {alias_line}\n"
        "source: BOOK map（全文ではない。議論時は doc_context で章を引く）\n"
        "\n"
        f"{map_gist.strip()}"
    )


def _discussed_memory_content(doc_id: str, *, cue: str, discussed_at: str) -> str:
    title = _display_title(doc_id)
    cue_body = (cue or "").strip()
    if len(cue_body) > 240:
        cue_body = cue_body[:240].rstrip() + "…"
    return (
        "[doc_read — まーと議論した本]\n"
        f"title: {title}\n"
        f"doc_id: {doc_id}\n"
        f"discussed_at: {discussed_at}\n"
        f"cue: {cue_body or '（きっかけ不明）'}\n"
        "\n"
        "まーとこの本について会話した。地図 gist は別 memory（同 doc_id）。"
    )


def remember_book_map(doc_id: str) -> RememberOutcome:
    """A — persist map gist after build_map (idempotent via registry)."""
    if not doc_memory_enabled():
        return RememberOutcome(ok=False, content="", error="doc memory disabled")

    entry = doc_read.get_doc_registry_entry(doc_id)
    if entry.get("memory_map_id"):
        return RememberOutcome(
            ok=True,
            content="",
            memory_id=str(entry.get("memory_map_id")),
            duplicate=True,
        )

    map_text = doc_read.load_map(doc_id)
    if not map_text.strip():
        return RememberOutcome(ok=False, content="", error="map missing")

    gist = gist_for_memory(map_text)
    if not gist:
        return RememberOutcome(ok=False, content="", error="empty map gist")

    content = _map_memory_content(doc_id, map_gist=gist)
    outcome = persist_remember_intent(RememberIntent(content=content, category="memory"))
    if outcome.ok:
        doc_read.patch_doc_registry_entry(
            doc_id,
            memory_map_id=outcome.memory_id,
            memory_map_at=_jst_now(),
        )
        logger.info("doc_read memory A ok doc_id=%s id=%s", doc_id, outcome.memory_id)
    else:
        logger.warning("doc_read memory A failed doc_id=%s: %s", doc_id, outcome.error)
    return outcome


def remember_book_discussed(doc_id: str, *, cue: str) -> RememberOutcome:
    """B — first time doc_context is injected for this book."""
    if not doc_memory_enabled():
        return RememberOutcome(ok=False, content="", error="doc memory disabled")

    entry = doc_read.get_doc_registry_entry(doc_id)
    if entry.get("memory_discussed_id"):
        return RememberOutcome(
            ok=True,
            content="",
            memory_id=str(entry.get("memory_discussed_id")),
            duplicate=True,
        )

    discussed_at = _jst_now()
    content = _discussed_memory_content(doc_id, cue=cue, discussed_at=discussed_at)
    outcome = persist_remember_intent(RememberIntent(content=content, category="conversation"))
    if outcome.ok:
        doc_read.patch_doc_registry_entry(
            doc_id,
            memory_discussed_id=outcome.memory_id,
            discussed_at=discussed_at,
        )
        logger.info("doc_read memory B ok doc_id=%s id=%s", doc_id, outcome.memory_id)
    else:
        logger.warning("doc_read memory B failed doc_id=%s: %s", doc_id, outcome.error)
    return outcome


def maybe_remember_discussed(doc_id: str, *, cue: str) -> RememberOutcome | None:
    """Hook from doc_prefetch — no-op when already discussed."""
    entry = doc_read.get_doc_registry_entry(doc_id)
    if entry.get("memory_discussed_id"):
        return None
    return remember_book_discussed(doc_id, cue=cue)
