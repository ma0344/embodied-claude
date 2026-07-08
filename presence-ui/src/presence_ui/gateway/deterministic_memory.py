"""Deterministic long-term memory for presence-ui Gateway (list + auto-save).

Auto-save logic lives in ``.claude/hooks/memory_auto_save.py`` (shared with CLI hook).
"""

from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

_HOOKS = Path(__file__).resolve().parents[4] / ".claude" / "hooks"
if _HOOKS.is_dir() and str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

import memory_auto_save as _mas  # noqa: E402

RememberIntent: TypeAlias = _mas.RememberIntent
RememberOutcome: TypeAlias = _mas.RememberOutcome
detect_personal_fact_intent = _mas.detect_personal_fact_intent
detect_remember_intent = _mas.detect_remember_intent
detect_self_disclosure = _mas.detect_self_disclosure
memory_saved_prompt_note = _mas.memory_saved_prompt_note
persist_remember_intent = _mas.persist_remember_intent

_LIST_HINT = re.compile(
    r"(記憶|メモリ|memory).*(?:リスト|一覧|完全|出して|見せ|教え)|"
    r"(?:リスト|一覧).*(?:記憶|メモリ)|"
    r"(?:list|show).*(?:memor|memories)|"
    r"(?:直近|最近).*(?:記憶|メモリ)|"
    r"\d+\s*(?:個|件).*(?:記憶|メモリ)|"
    r"(?:記憶|メモリ).*\d+\s*(?:個|件)",
    re.IGNORECASE,
)

_MEMORIES_COMMAND = re.compile(
    r"^/?(?:memories|memory)(?:\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class MemoryListRequest:
    limit: int
    oldest_first: bool


def _parse_list_limit(text: str, *, default: int = 10) -> int:
    match = re.search(r"(\d+)\s*(?:個|件)", text)
    if match:
        return min(int(match.group(1)), 30)
    return default


def detect_memory_list_request(user_text: str) -> MemoryListRequest | None:
    """User wants a concrete memory list (not social state / not Skill)."""
    text = (user_text or "").strip()
    if not text:
        return None

    cmd = _MEMORIES_COMMAND.match(text)
    if cmd:
        raw_limit = cmd.group("limit")
        limit = min(int(raw_limit), 30) if raw_limit else 10
        return MemoryListRequest(limit=limit, oldest_first=False)

    if len(text) < 4 or not _LIST_HINT.search(text):
        return None
    limit = _parse_list_limit(text)
    oldest_first = bool(re.search(r"最初|古い順|早い順|古い方", text))
    return MemoryListRequest(limit=limit, oldest_first=oldest_first)


def fetch_memory_list(*, limit: int, oldest_first: bool) -> list[dict[str, str]]:
    """Read memories from memory.db (no embedding required)."""
    db_path = _mas.memory_db_path()
    if not db_path.is_file():
        return []
    order = "ASC" if oldest_first else "DESC"
    query = (
        "SELECT id, content, timestamp, category, emotion "
        f"FROM memories ORDER BY timestamp {order} LIMIT ?"
    )
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(query, (limit,)).fetchall()
    except sqlite3.Error:
        return []
    return [
        {
            "id": str(row[0]),
            "content": str(row[1]),
            "timestamp": str(row[2]),
            "category": str(row[3] or ""),
            "emotion": str(row[4] or ""),
        }
        for row in rows
    ]


def memory_list_prefetch_note(
    rows: list[dict[str, str]],
    *,
    limit: int,
    oldest_first: bool,
) -> str:
    if not rows:
        return (
            "[memory_list_prefetch]\n"
            "FACT: No memories in memory.db (store is empty).\n"
            "Reply in Japanese: まだ記憶がない、と伝える。\n"
            "Do NOT call mcp__memory__*, mcp__sociality__*, Skill, or /memories.\n"
            "Do NOT say a tool error occurred — there is nothing to read."
        )
    order_label = "oldest-first" if oldest_first else "newest-first"
    lines = [
        "[memory_list_prefetch]",
        f"FACT: Gateway loaded {len(rows)} memories ({order_label}, limit={limit}).",
        "Reply NOW by copying this numbered list into your answer (Japanese).",
        "Do NOT call mcp__memory__*, mcp__sociality__*, Skill, or /memories.",
        "Do NOT mention Cursor, 作戦, or that you cannot run commands.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. [{row['timestamp']}] ({row['category']}) {row['content'][:300]}"
        )
    return "\n".join(lines)


def format_memory_list_reply(
    rows: list[dict[str, str]],
    *,
    limit: int,
    oldest_first: bool,
) -> str:
    """User-visible numbered list (Gateway direct reply, no LLM)."""
    if not rows:
        return "記憶ストアは空っぽや。まだ何も覚えてへん。"
    order_label = "古い順" if oldest_first else "新しい順"
    lines = [f"直近の記憶 {len(rows)} 件（{order_label}、上限 {limit}）:", ""]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. [{row['timestamp']}] ({row['category']}) {row['content'][:300]}"
        )
    return "\n".join(lines)
