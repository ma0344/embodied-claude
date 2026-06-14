"""Gateway-wrapped chat NDJSON stream (progress + tool activity)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from presence_ui.gateway.room_events import activity_event, encode_event, progress_event
from presence_ui.gateway.room_ingest import ingest_agent_turn
from presence_ui.gateway.see_intent import (
    SEE_ACTIVITY_LABELS,
    SEE_PROGRESS_LABELS,
    detect_see_intent,
)
from presence_ui.gateway.social_chat import (
    ChatInterceptResult,
    intercept_chat_request,
    stream_direct_action_response,
    stream_silent_response,
)
from presence_ui.gateway.stream_sanitize import extract_assistant_speech, stream_passthrough_chat
from presence_ui.services.vision_capture import prefetch_vision_for_chat, vision_prefetch_enabled


async def stream_gateway_chat(
    *,
    payload: dict[str, Any],
    person_id: str = "ma",
) -> AsyncIterator[bytes]:
    """Run social intercept, then proxy Claude Code with room UI side-channels."""

    message = str(payload.get("message") or "").strip()
    vision_note: str | None = None
    gateway_events: list[dict[str, Any]] = []

    see_intent = detect_see_intent(message) if message else None
    if see_intent and vision_prefetch_enabled():
        progress_label = SEE_PROGRESS_LABELS.get(see_intent.mode, "見てる…")
        yield encode_event(progress_event(phase="see", label=progress_label))
        try:
            _result, vision_note = await prefetch_vision_for_chat(
                intent=see_intent,
                user_text=message,
                remember=True,
            )
            detail = _result.caption or _result.error or _result.label
            activity_label = SEE_ACTIVITY_LABELS.get(see_intent.mode, "見た")
            if not _result.ok:
                activity_label = "見られなかった"
            gateway_events.append(
                activity_event(
                    kind="see",
                    label=activity_label,
                    detail=(detail or "")[:200],
                    ok=_result.ok,
                )
            )
        except Exception as exc:  # noqa: BLE001
            vision_note = (
                "[vision_prefetch]\n"
                f"error={exc}\n\n"
                "[Gateway directive — not for the user]\n"
                "Camera/vision prefetch failed. Do NOT guess; say capture failed."
            )
            gateway_events.append(
                activity_event(kind="see", label="見られなかった", detail=str(exc)[:120], ok=False)
            )

    yield encode_event(progress_event(phase="composing", label="文脈を集めてる…"))

    try:
        result: ChatInterceptResult = await asyncio.to_thread(
            intercept_chat_request,
            payload=payload,
            person_id=person_id,
            vision_prefetch=vision_note,
        )
    except ValueError as exc:
        err = {"type": "error", "error": str(exc)}
        yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")
        return

    for event in gateway_events:
        yield encode_event(event)

    for event in result.gateway_events:
        yield encode_event(event)

    if not result.forward:
        if result.direct_action_summary:
            async for chunk in stream_direct_action_response(
                plan_move=result.plan_move or "direct",
                summary=result.direct_action_summary,
            ):
                yield chunk
        else:
            async for chunk in stream_silent_response(plan_move=result.plan_move or "stay_silent"):
                yield chunk
        return

    yield encode_event(progress_event(phase="replying", label="こよりが考えてる…"))

    user_text = result.user_text or str(payload.get("message") or "").strip()
    session_key = str(payload.get("sessionId")) if payload.get("sessionId") else None
    assistant_parts: list[str] = []

    async for chunk in stream_passthrough_chat(
        path="/api/chat",
        payload=result.payload or payload,
        user_text=user_text,
        emit_tool_activity=True,
    ):
        line = chunk.decode("utf-8", errors="replace").strip()
        if line:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("type") == "claude_json":
                    data = obj.get("data")
                    if isinstance(data, dict):
                        speech = extract_assistant_speech(data)
                        if speech:
                            assistant_parts.append(speech)
            except json.JSONDecodeError:
                pass
        yield chunk

    reply = assistant_parts[-1].strip() if assistant_parts else ""
    if reply:
        await asyncio.to_thread(
            ingest_agent_turn,
            person_id=person_id,
            session_id=session_key,
            text=reply,
        )
