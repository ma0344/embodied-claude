"""Pass-through NDJSON stream from Claude Code backend to the room UI.

The gateway must not rewrite SDK message content. Display filtering belongs in
the frontend (cc-messages.js), not in the proxy.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, AsyncIterator

import httpx
from starlette.responses import StreamingResponse

from presence_ui.gateway.backend import backend_base_url
from presence_ui.gateway.room_events import (
    activities_from_sdk_message,
    encode_event,
    register_tool_uses,
)
from presence_ui.gateway.sdk_content import (
    join_text_blocks,
    resolve_user_utterance,
)
from presence_ui.gateway.user_prompt import strip_enriched_user_prompt

logger = logging.getLogger(__name__)

_PASSTHROUGH_LINE_TYPES = frozenset({"error", "done", "aborted", "social_silent"})


def extract_assistant_speech(sdk_message: dict[str, Any]) -> str:
    """Legacy helper: text blocks only (used by tests / diagnostics)."""
    if not sdk_message or sdk_message.get("type") != "assistant":
        return ""
    inner = sdk_message.get("message") or sdk_message
    return join_text_blocks(inner.get("content"))


def extract_user_speech(sdk_message: dict[str, Any], *, user_text: str = "") -> str:
    """Legacy helper: user utterance extraction (optional strip for history fallback)."""
    if not sdk_message or sdk_message.get("type") != "user":
        return ""
    inner = sdk_message.get("message") or sdk_message
    content = inner.get("content")
    utterance = resolve_user_utterance(content=content, user_text=user_text)
    if user_text:
        return utterance
    return strip_enriched_user_prompt(utterance)


def passthrough_claude_json_data(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return SDK payload unchanged (deep copy)."""
    if not data:
        return None
    return copy.deepcopy(data)


def passthrough_stream_line(
    line_obj: dict[str, Any],
    *,
    user_text: str = "",
) -> dict[str, Any] | None:
    """Forward one NDJSON object without rewriting message content."""
    del user_text  # kept for call-site compatibility; stream no longer strips user text

    if not isinstance(line_obj, dict):
        return None

    line_type = line_obj.get("type")
    if line_type in _PASSTHROUGH_LINE_TYPES:
        return line_obj

    if line_type == "claude_json":
        data = line_obj.get("data")
        if not isinstance(data, dict):
            return None
        passed = passthrough_claude_json_data(data)
        if passed is None:
            return None
        return {"type": "claude_json", "data": passed}

    logger.debug("skipped unknown stream line type=%s", line_type)
    return None


# Backward-compatible alias
sanitize_stream_line = passthrough_stream_line


async def stream_passthrough_chat(
    *,
    path: str,
    payload: dict,
    user_text: str,
    emit_tool_activity: bool = False,
) -> AsyncIterator[bytes]:
    """POST to Claude Code backend and yield NDJSON lines unchanged."""
    url = f"{backend_base_url()}{path}"
    buffer = ""
    tool_names: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as upstream:
                upstream.raise_for_status()
                async for chunk in upstream.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(obj, dict):
                            continue
                        if emit_tool_activity and obj.get("type") == "claude_json":
                            data = obj.get("data")
                            if isinstance(data, dict):
                                register_tool_uses(data, tool_names)
                                for event in activities_from_sdk_message(
                                    data, tool_names=tool_names
                                ):
                                    yield encode_event(event)
                        out = passthrough_stream_line(obj, user_text=user_text)
                        if out is not None:
                            yield (json.dumps(out, ensure_ascii=False) + "\n").encode("utf-8")
    except httpx.HTTPStatusError as exc:
        err = {"type": "error", "error": str(exc.response.text)}
        yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")
    except httpx.RequestError as exc:
        err = {"type": "error", "error": f"backend unreachable: {exc}"}
        yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")

    trailing = buffer.strip()
    if trailing:
        try:
            obj = json.loads(trailing)
            if isinstance(obj, dict):
                if emit_tool_activity and obj.get("type") == "claude_json":
                    data = obj.get("data")
                    if isinstance(data, dict):
                        register_tool_uses(data, tool_names)
                        for event in activities_from_sdk_message(data, tool_names=tool_names):
                            yield encode_event(event)
                out = passthrough_stream_line(obj, user_text=user_text)
                if out is not None:
                    yield (json.dumps(out, ensure_ascii=False) + "\n").encode("utf-8")
        except json.JSONDecodeError:
            pass


async def proxy_post_stream_filtered(
    path: str,
    payload: dict,
    *,
    user_text: str,
) -> StreamingResponse:
    return StreamingResponse(
        stream_passthrough_chat(path=path, payload=payload, user_text=user_text),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
