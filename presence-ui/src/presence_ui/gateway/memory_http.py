"""HTTP helpers for memory-mcp sidecar (:18900)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def memory_http_port() -> int:
    raw = os.environ.get("MEMORY_HTTP_PORT", "18900")
    try:
        return int(raw)
    except ValueError:
        return 18900


def http_recall(
    *,
    query: str,
    n: int = 4,
    timeout_sec: float = 12.0,
) -> list[dict[str, Any]]:
    port = memory_http_port()
    q = urllib.parse.quote(query)
    url = f"http://127.0.0.1:{port}/recall?q={q}&n={max(1, n)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
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
    category: str = "observation",
    emotion: str = "curious",
    importance: int = 3,
    timeout_sec: float = 25.0,
) -> dict[str, Any]:
    port = memory_http_port()
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
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid JSON"}
    return data if isinstance(data, dict) else {"ok": False, "error": "invalid response"}


def http_recall_divergent(
    *,
    context: str,
    n_results: int = 5,
    max_branches: int = 3,
    max_depth: int = 3,
    temperature: float = 0.7,
    include_diagnostics: bool = False,
    timeout_sec: float = 35.0,
) -> list[dict[str, Any]]:
    port = memory_http_port()
    payload = json.dumps(
        {
            "context": context,
            "n_results": max(1, n_results),
            "max_branches": max_branches,
            "max_depth": max_depth,
            "temperature": temperature,
            "include_diagnostics": include_diagnostics,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/recall/divergent",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return items
    return []


def http_consolidate(
    *,
    window_hours: int = 24,
    max_replay_events: int = 200,
    link_update_strength: float = 0.2,
    timeout_sec: float = 130.0,
) -> dict[str, Any]:
    port = memory_http_port()
    payload = json.dumps(
        {
            "window_hours": window_hours,
            "max_replay_events": max_replay_events,
            "link_update_strength": link_update_strength,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/consolidate",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid JSON"}
    return data if isinstance(data, dict) else {"ok": False, "error": "invalid response"}
