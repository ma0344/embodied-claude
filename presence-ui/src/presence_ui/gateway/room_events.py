"""Gateway → room UI NDJSON events (progress + compact tool activity)."""

from __future__ import annotations

import json
from typing import Any


def progress_event(*, phase: str, label: str) -> dict[str, str]:
    return {"type": "room_progress", "phase": phase, "label": label}


def activity_event(
    *,
    kind: str,
    label: str,
    detail: str = "",
    ok: bool = True,
) -> dict[str, Any]:
    return {
        "type": "room_activity",
        "kind": kind,
        "label": label,
        "detail": detail[:240],
        "ok": ok,
    }


def encode_event(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


_TOOL_LABELS: dict[str, tuple[str, str]] = {
    "mcp__memory__remember": ("remember", "記憶に保存"),
    "mcp__memory__recall": ("recall", "思い出し"),
    "mcp__memory__search_memories": ("recall", "記憶を検索"),
    "mcp__memory__list_recent_memories": ("recall", "最近の記憶"),
    "mcp__memory__get_memory_stats": ("recall", "記憶統計"),
    "mcp__wifi-cam__see": ("see", "見てる"),
    "mcp__wifi-cam__see_right": ("see", "右目で見てる"),
    "mcp__wifi-cam__see_both": ("see", "両目で見てる"),
    "mcp__wifi-cam__listen": ("listen", "聞いてる"),
    "mcp__tts__say": ("say", "声を出してる"),
    "mcp__sociality__append_private_reflection": ("reflect", "ひそかにメモ"),
}


def _is_mcp_tool(tool_name: str) -> bool:
    return tool_name.startswith("mcp__")


# Pill UI: embodied “senses + memory” only (hide sociality orchestrator noise).
_MCP_UI_SERVERS = frozenset({"memory", "tts", "wifi-cam", "usb-webcam"})


def _show_in_mcp_ui(tool_name: str) -> bool:
    parts = tool_name.split("__")
    return len(parts) >= 3 and parts[1] in _MCP_UI_SERVERS


def _label_for_mcp_tool(tool_name: str) -> tuple[str, str]:
    if tool_name in _TOOL_LABELS:
        return _TOOL_LABELS[tool_name]
    parts = tool_name.split("__")
    if len(parts) >= 3:
        return ("mcp", f"{parts[1]} · {parts[2].replace('_', ' ')}")
    return ("mcp", tool_name.removeprefix("mcp__"))


def mcp_activity_event(
    *,
    kind: str,
    label: str,
    detail: str = "",
    ok: bool = True,
) -> dict[str, Any]:
    return {
        "type": "mcp_activity",
        "kind": kind,
        "label": label,
        "detail": detail[:240],
        "ok": ok,
    }


def activity_for_tool_use(
    tool_name: str,
    tool_input: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not _is_mcp_tool(tool_name) or not _show_in_mcp_ui(tool_name):
        return None
    kind, label = _label_for_mcp_tool(tool_name)
    detail = ""
    if tool_input:
        if tool_name.endswith("__remember"):
            detail = str(tool_input.get("content") or "")[:120]
        elif tool_name.endswith("__say"):
            detail = str(tool_input.get("text") or "")[:80]
        elif "query" in tool_input:
            detail = str(tool_input.get("query") or "")[:80]
        elif "context" in tool_input:
            detail = str(tool_input.get("context") or "")[:80]
    return mcp_activity_event(kind=kind, label=label, detail=detail, ok=True)


def activity_for_tool_result(
    tool_name: str,
    content: str,
    *,
    is_error: bool,
) -> dict[str, Any] | None:
    if not _is_mcp_tool(tool_name) or not _show_in_mcp_ui(tool_name):
        return None
    if not is_error:
        return None
    kind, label = _label_for_mcp_tool(tool_name)
    return mcp_activity_event(
        kind=kind,
        label=f"{label} · 失敗",
        detail=content[:160],
        ok=False,
    )


def register_tool_uses(
    data: dict[str, Any],
    tool_names: dict[str, str],
) -> None:
    """Map tool_use_id → tool name from an assistant SDK message."""

    if not data or data.get("type") != "assistant":
        return
    inner = data.get("message") or data
    content = inner.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        tool_id = str(block.get("id") or "")
        name = str(block.get("name") or "")
        if tool_id and name:
            tool_names[tool_id] = name


def activities_from_sdk_message(
    data: dict[str, Any],
    *,
    tool_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Extract compact activity events from one Claude SDK message."""

    if not data:
        return []
    msg_type = data.get("type")
    inner = data.get("message") or data
    content = inner.get("content")
    if not isinstance(content, list):
        return []

    events: list[dict[str, Any]] = []
    if msg_type == "assistant":
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            evt = activity_for_tool_use(
                str(block.get("name") or ""),
                block.get("input") if isinstance(block.get("input"), dict) else None,
            )
            if evt:
                events.append(evt)
    elif msg_type == "user":
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            raw = block.get("content")
            text = raw if isinstance(raw, str) else str(raw or "")
            is_error = bool(block.get("is_error"))
            tool_id = str(block.get("tool_use_id") or "")
            tool_name = (tool_names or {}).get(tool_id, "")
            if not tool_name:
                continue
            evt = activity_for_tool_result(tool_name, text, is_error=is_error)
            if evt:
                events.append(evt)
    return events
