"""DOC-READ C — inject 「本の地図」+ relevant chapters into a conversation turn.

Two-layer continuity (docs/tracks/doc-read-discuss.md §C):
- **within session**: a sticky TTL keeps 本モード alive for a few turns even when the
  user pauses the topic — and lets it decay naturally (the "終わり方").
- **across sessions**: resolve a book by its registered title/alias appearing in the
  utterance (「この間の〇〇の本の続き」). The registry is persistent and doc_id is a
  content hash, so we always return to the same book.

Contract mirrors WS-2d: describe only from injected map/chunks, never invent.
"""

from __future__ import annotations

import json
import os
from typing import Any

from presence_ui.gateway.room_events import progress_event
from presence_ui.services import doc_memory, doc_read

# Bounded cue vocabulary to (re)open 本モード with the active/sticky book when the
# title is not spoken. Deterministic gate only (regex 方針: ゲートまで).
_CUE_WORDS = ("本", "著作", "続き", "章", "エピローグ", "プロローグ", "この前の話")


def doc_context_enabled() -> bool:
    return os.getenv("PRESENCE_DOC_CONTEXT", "1").strip().lower() not in ("0", "false", "no", "off")


def _sticky_turns() -> int:
    raw = os.getenv("PRESENCE_DOC_STICKY_TURNS", "3").strip()
    try:
        return max(0, min(int(raw), 20))
    except ValueError:
        return 3


def _max_chunks() -> int:
    raw = os.getenv("PRESENCE_DOC_RETRIEVE_MAX_CHUNKS", "2").strip()
    try:
        return max(1, min(int(raw), 5))
    except ValueError:
        return 2


def _map_max_chars() -> int:
    raw = os.getenv("PRESENCE_DOC_MAP_MAX_CHARS", "4000").strip()
    try:
        return max(500, min(int(raw), 12000))
    except ValueError:
        return 4000


def _chunk_max_chars() -> int:
    raw = os.getenv("PRESENCE_DOC_CHUNK_MAX_CHARS", "3000").strip()
    try:
        return max(500, min(int(raw), 12000))
    except ValueError:
        return 3000


def _sessions_path():
    return doc_read.doc_store_dir() / "sessions.json"


def _load_sessions() -> dict[str, Any]:
    path = _sessions_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_sessions(data: dict[str, Any]) -> None:
    path = _sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_sticky(session_id: str | None) -> tuple[str | None, int]:
    if not session_id:
        return None, 0
    entry = _load_sessions().get(session_id) or {}
    return entry.get("doc_id"), int(entry.get("remaining") or 0)


def _set_sticky(session_id: str | None, doc_id: str | None, remaining: int) -> None:
    if not session_id:
        return
    data = _load_sessions()
    if doc_id and remaining > 0:
        data[session_id] = {"doc_id": doc_id, "remaining": remaining}
    else:
        data.pop(session_id, None)
    _save_sessions(data)


def _has_cue(text: str) -> bool:
    return any(word in text for word in _CUE_WORDS)


def resolve_doc_for_turn(message: str, session_id: str | None) -> tuple[str | None, str]:
    """Return (doc_id, reason). reason ∈ title|cue|sticky|none — for logging/tests."""
    text = (message or "").strip()
    if not text:
        return None, "none"

    # 1) explicit book by title/alias (works across sessions)
    by_title = doc_read.resolve_doc_by_text(text)
    if by_title:
        _set_sticky(session_id, by_title, _sticky_turns())
        return by_title, "title"

    sticky_doc, remaining = _get_sticky(session_id)

    # 2) cue word reopens the sticky/active book
    if _has_cue(text):
        doc_id = sticky_doc or doc_read.active_doc_id()
        if doc_id:
            _set_sticky(session_id, doc_id, _sticky_turns())
            return doc_id, "cue"

    # 3) sticky continuation (中断しながら継続 → decay)
    if sticky_doc and remaining > 0:
        _set_sticky(session_id, sticky_doc, remaining - 1)
        return sticky_doc, "sticky"

    return None, "none"


def _trim(text: str, limit: int) -> str:
    body = (text or "").strip()
    return body if len(body) <= limit else body[:limit].rstrip() + "…"


def build_doc_context_block(doc_id: str, message: str) -> str | None:
    meta = doc_read.load_meta(doc_id)
    if meta is None:
        return None
    book_map = doc_read.load_map(doc_id)
    chunks = doc_read.select_chunks(doc_id, message, max_chunks=_max_chunks())
    if not book_map and not chunks:
        return None

    entry_title = next(
        (e.title for e in doc_read.list_registry() if e.doc_id == doc_id and e.title),
        meta.title,
    )
    lines = ["[doc_context]", f"book={entry_title}", f"doc_id={doc_id}"]
    if book_map:
        lines.append("[map]")
        lines.append(_trim(book_map, _map_max_chars()))
    for chunk in chunks:
        label = chunk.heading if chunk.part == 0 else f"{chunk.heading}（{chunk.part}）"
        lines.append(f"[chapter {label} · p{chunk.page_start + 1}-{chunk.page_end + 1}]")
        lines.append(_trim(chunk.text, _chunk_max_chars()))
    lines.append("[/doc_context]")
    lines.append("")
    lines.append("[Gateway directive — not for the user]")
    lines.append(
        "まーの本の地図と該当章を渡した。この本について語るときは上の map/chapter だけを"
        "根拠にする。書いていないことは推測で足さない。地図に無い細部を聞かれたら正直に"
        "「その章はまだ手元にない」と言う。地図棒読みではなく、まーとの対話として自然に。"
    )
    return "\n".join(lines)


async def prefetch_doc_context_for_turn(
    message: str,
    *,
    session_id: str | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Resolve the active book for this turn and build a [doc_context] note."""
    if not doc_context_enabled():
        return None, []
    doc_id, reason = resolve_doc_for_turn(message, session_id)
    if not doc_id:
        return None, []
    block = build_doc_context_block(doc_id, message)
    if not block:
        return None, []
    doc_memory.maybe_remember_discussed(doc_id, cue=message)
    events = [progress_event(phase="doc_read", label="本を読み返してる…")]
    return block, events
