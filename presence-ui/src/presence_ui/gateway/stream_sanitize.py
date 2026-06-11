"""Filter Claude Code NDJSON stream to UI-safe SDK messages (structural, not string)."""

from __future__ import annotations

import copy
import json
import logging
from typing import Any, AsyncIterator

import httpx
from starlette.responses import StreamingResponse

from presence_ui.gateway.backend import backend_base_url
from presence_ui.gateway.sdk_content import (
    build_text_only_content,
    extract_text_blocks,
    join_text_blocks,
    resolve_user_utterance,
)
from presence_ui.gateway.user_prompt import strip_enriched_user_prompt

logger = logging.getLogger(__name__)


def extract_assistant_speech(sdk_message: dict[str, Any]) -> str:
    if not sdk_message or sdk_message.get("type") != "assistant":
        return ""
    inner = sdk_message.get("message") or sdk_message
    return join_text_blocks(inner.get("content"))


def extract_user_speech(sdk_message: dict[str, Any], *, user_text: str = "") -> str:
    if not sdk_message or sdk_message.get("type") != "user":
        return ""
    inner = sdk_message.get("message") or sdk_message
    content = inner.get("content")
    utterance = resolve_user_utterance(content=content, user_text=user_text)
    if user_text:
        return utterance
    return strip_enriched_user_prompt(utterance)


def _set_message_content(message: dict[str, Any], text_blocks: list[str]) -> None:
    message["content"] = build_text_only_content(text_blocks)


def sanitize_claude_json_data(data: dict[str, Any], *, user_text: str) -> dict[str, Any] | None:
    """Keep only UI-facing SDK fields; speech comes from content[type=text]."""
    if not data:
        return None

    msg_type = data.get("type")

    if msg_type == "system":
        if data.get("subtype") == "init":
            return copy.deepcopy(data)
        logger.debug("skipped system sdk message subtype=%s", data.get("subtype"))
        return None

    if msg_type == "result":
        logger.debug("skipped result sdk message subtype=%s", data.get("subtype"))
        return None

    if msg_type == "user":
        speech = extract_user_speech(data, user_text=user_text)
        if not speech:
            return None
        out = copy.deepcopy(data)
        inner_out = out.get("message") or out
        _set_message_content(inner_out, [speech])
        if "message" in out:
            out["message"] = inner_out
        return out

    if msg_type == "assistant":
        inner = data.get("message") or data
        text_blocks = extract_text_blocks(inner.get("content"))
        if not text_blocks:
            return None
        out = copy.deepcopy(data)
        inner_out = out.get("message") or out
        _set_message_content(inner_out, text_blocks)
        if "message" in out:
            out["message"] = inner_out
        return out

    logger.debug("skipped sdk message type=%s", msg_type)
    return None


def sanitize_stream_line(line_obj: dict[str, Any], *, user_text: str) -> dict[str, Any] | None:
    """Filter one NDJSON object for the room UI."""
    line_type = line_obj.get("type")

    if line_type in {"error", "done", "social_silent"}:
        return line_obj

    if line_type == "claude_json":
        data = line_obj.get("data")
        if not isinstance(data, dict):
            return None
        cleaned = sanitize_claude_json_data(data, user_text=user_text)
        if cleaned is None:
            return None
        return {"type": "claude_json", "data": cleaned}

    return None


async def stream_filtered_chat(*, path: str, payload: dict, user_text: str) -> AsyncIterator[bytes]:
    """POST to Claude Code backend and yield structurally filtered NDJSON."""
    url = f"{backend_base_url()}{path}"
    buffer = ""

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
                        out = sanitize_stream_line(obj, user_text=user_text)
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
                out = sanitize_stream_line(obj, user_text=user_text)
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
        stream_filtered_chat(path=path, payload=payload, user_text=user_text),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
