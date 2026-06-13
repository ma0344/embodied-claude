"""Gateway-wrapped chat NDJSON stream (progress + tool activity)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from presence_ui.gateway.room_events import encode_event, progress_event
from presence_ui.gateway.social_chat import (
    ChatInterceptResult,
    intercept_chat_request,
    stream_silent_response,
)
from presence_ui.gateway.stream_sanitize import stream_passthrough_chat


async def stream_gateway_chat(
    *,
    payload: dict[str, Any],
    person_id: str = "ma",
) -> AsyncIterator[bytes]:
    """Run social intercept, then proxy Claude Code with room UI side-channels."""

    yield encode_event(progress_event(phase="composing", label="文脈を集めてる…"))

    try:
        result: ChatInterceptResult = await asyncio.to_thread(
            intercept_chat_request,
            payload=payload,
            person_id=person_id,
        )
    except ValueError as exc:
        err = {"type": "error", "error": str(exc)}
        yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")
        return

    for event in result.gateway_events:
        yield encode_event(event)

    if not result.forward:
        async for chunk in stream_silent_response(plan_move=result.plan_move or "stay_silent"):
            yield chunk
        return

    yield encode_event(progress_event(phase="replying", label="こよりが考えてる…"))

    user_text = result.user_text or str(payload.get("message") or "").strip()
    async for chunk in stream_passthrough_chat(
        path="/api/chat",
        payload=result.payload or payload,
        user_text=user_text,
        emit_tool_activity=True,
    ):
        yield chunk
