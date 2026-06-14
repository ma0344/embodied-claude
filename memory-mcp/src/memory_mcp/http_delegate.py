"""Delegate stdio MCP tool calls to the HTTP daemon when it is healthy.

Avoids a second E5 load and SQLite/Chroma contention when Claude Code spawns
memory-mcp while memory-mcp-http-daemon already owns :18900.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from memory_mcp.http_sidecar import probe_health


def _http_port() -> int:
    raw = os.environ.get("MEMORY_HTTP_PORT", "18900")
    try:
        return int(raw)
    except ValueError:
        return 18900


def stdio_delegate_enabled() -> bool:
    raw = os.environ.get("MEMORY_STDIO_DELEGATE_HTTP", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def daemon_healthy(*, port: int | None = None, timeout_sec: float = 1.5) -> bool:
    return probe_health(port or _http_port(), timeout_sec=timeout_sec)


def http_recall(*, query: str, n: int, timeout_sec: float = 12.0) -> list[dict[str, Any]]:
    port = _http_port()
    q = urllib.parse.quote(query)
    url = f"http://127.0.0.1:{port}/recall?q={q}&n={max(1, n)}"
    with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return items
    return []


def http_remember(
    *,
    content: str,
    category: str = "daily",
    emotion: str = "neutral",
    importance: int = 3,
    timeout_sec: float = 25.0,
) -> dict[str, Any]:
    port = _http_port()
    payload = json.dumps(
        {
            "content": content,
            "category": category,
            "emotion": emotion,
            "importance": importance,
            "auto_link": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/remember",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    return data if isinstance(data, dict) else {"ok": False, "error": "invalid JSON"}


def format_recall_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No relevant memories found."
    lines = [f"Recalled {len(items)} relevant memories (via HTTP daemon):\n"]
    for i, item in enumerate(items, 1):
        content = str(item.get("content") or "")[:200]
        emotion = str(item.get("emotion") or "")
        score = item.get("score", "")
        lines.append(f"--- Memory {i} ---")
        if emotion:
            lines.append(f"[{emotion}] (score: {score})")
        lines.append(content)
        lines.append("")
    return "\n".join(lines).strip()


def format_remember_result(data: dict[str, Any], *, content: str) -> str:
    if not data.get("ok"):
        err = str(data.get("error") or "remember failed")
        return f"Error: {err}"
    mid = str(data.get("id") or "unknown")
    dup = " (duplicate)" if data.get("duplicate") else ""
    return (
        f"Memory saved via HTTP daemon{dup}!\n"
        f"ID: {mid}\n"
        f"Content: {content}"
    )
