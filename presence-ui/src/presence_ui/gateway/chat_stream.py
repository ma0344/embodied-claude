"""Gateway-wrapped chat NDJSON stream (progress + tool activity)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from presence_ui.gateway.calendar_prefetch import (
    calendar_prefetch_enabled,
    calendar_read_cue,
    prefetch_calendar_for_message,
)
from presence_ui.gateway.hybrid_intent import resolve_hybrid_intent
from presence_ui.gateway.room_events import activity_event, encode_event, progress_event
from presence_ui.gateway.room_ingest import ingest_agent_turn
from presence_ui.gateway.search_prefetch import (
    detect_web_search_intent,
    prefetch_web_search_for_message,
)
from presence_ui.gateway.see_intent import SEE_PROGRESS_LABELS, detect_see_intent
from presence_ui.gateway.see_prefetch import prefetch_camera_for_message
from presence_ui.gateway.social_chat import (
    ChatInterceptResult,
    intercept_chat_request_async,
    stream_direct_action_response,
    stream_silent_response,
    stream_surface_reply_ndjson,
)
from presence_ui.gateway.surface_direct import use_surface_direct_path
from presence_ui.gateway.gateway_turn_cache import gateway_turn_cache_scope
from presence_ui.gateway.stream_sanitize import extract_assistant_speech, stream_passthrough_chat
from presence_ui.gateway.doc_prefetch import prefetch_doc_context_for_turn
from presence_ui.gateway.url_prefetch import prefetch_urls_for_turn
from presence_ui.services.vision_capture import vision_prefetch_enabled


async def stream_gateway_chat(
    *,
    payload: dict[str, Any],
    person_id: str = "ma",
) -> AsyncIterator[bytes]:
    """Run social intercept, then proxy Claude Code with room UI side-channels."""
    with gateway_turn_cache_scope():
        async for chunk in _stream_gateway_chat_impl(
            payload=payload,
            person_id=person_id,
        ):
            yield chunk


async def _stream_gateway_chat_impl(
    *,
    payload: dict[str, Any],
    person_id: str = "ma",
) -> AsyncIterator[bytes]:
    message = str(payload.get("message") or "").strip()
    vision_note: str | None = None
    web_search_note: str | None = None
    url_note: str | None = None
    calendar_note: str | None = None
    calendar_write_note: str | None = None
    search_hits = []
    search_query = ""
    gateway_events: list[dict[str, Any]] = []
    hybrid = resolve_hybrid_intent(message) if message else None

    if message:
        if calendar_prefetch_enabled() and calendar_read_cue(message):
            yield encode_event(progress_event(phase="calendar", label="カレンダーを見てる…"))
        try:
            calendar_note, cal_events = await prefetch_calendar_for_message(message)
            gateway_events.extend(cal_events)
        except Exception as exc:  # noqa: BLE001
            calendar_note = None
            gateway_events.append(
                activity_event(
                    kind="calendar",
                    label="カレンダー取得に失敗",
                    detail=str(exc)[:120],
                    ok=False,
                )
            )

    if message:
        if detect_web_search_intent(message):
            yield encode_event(progress_event(phase="web_search", label="ネットを調べてる…"))
        try:
            web_search_note, web_events, search_hits, search_query = (
                await prefetch_web_search_for_message(
                    message,
                    person_id=person_id,
                )
            )
            gateway_events.extend(web_events)
        except Exception as exc:  # noqa: BLE001
            web_search_note = None
            gateway_events.append(
                activity_event(
                    kind="web_search",
                    label="検索に失敗した",
                    detail=str(exc)[:120],
                    ok=False,
                )
            )

    if message:
        try:
            url_note, url_events = await prefetch_urls_for_turn(
                message,
                search_hits=search_hits,
                search_query=search_query,
            )
            gateway_events.extend(url_events)
        except Exception as exc:  # noqa: BLE001
            url_note = None
            gateway_events.append(
                activity_event(
                    kind="url_fetch",
                    label="ページを読めなかった",
                    detail=str(exc)[:120],
                    ok=False,
                )
            )

    doc_note: str | None = None
    if message:
        try:
            doc_note, doc_events = await prefetch_doc_context_for_turn(
                message,
                session_id=payload.get("sessionId"),
            )
            gateway_events.extend(doc_events)
        except Exception as exc:  # noqa: BLE001
            doc_note = None
            gateway_events.append(
                activity_event(
                    kind="doc_read",
                    label="本を読み返せなかった",
                    detail=str(exc)[:120],
                    ok=False,
                )
            )

    camera_image_url: str | None = None
    if message and vision_prefetch_enabled():
        see_intent = (hybrid.see_intent if hybrid else None) or detect_see_intent(message)
        if see_intent:
            progress_label = SEE_PROGRESS_LABELS.get(see_intent.mode, "見てる…")
            yield encode_event(progress_event(phase="see", label=progress_label))
        try:
            vision_note, prefetch_events, camera_image_url = await prefetch_camera_for_message(
                message,
                see_intent=hybrid.see_intent if hybrid else None,
                ptz_intent=hybrid.ptz_intent if hybrid else None,
                surface_multimodal=use_surface_direct_path(),
            )
            if camera_image_url:
                vision_note = None
            gateway_events.extend(prefetch_events)
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
        result: ChatInterceptResult = await intercept_chat_request_async(
            payload=payload,
            person_id=person_id,
            vision_prefetch=vision_note,
            web_search_prefetch=web_search_note,
            url_prefetch=url_note,
            doc_prefetch=doc_note,
            calendar_prefetch=calendar_note,
            calendar_write=calendar_write_note,
            hybrid=hybrid,
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
    see_mode = hybrid.see_intent.mode if hybrid and hybrid.see_intent else "current"
    enriched_message = str((result.payload or {}).get("message") or message).strip()

    if (
        use_surface_direct_path()
        and camera_image_url
        and result.ctx is not None
    ):
        async for chunk in stream_surface_reply_ndjson(
            enriched_user=enriched_message,
            raw_user=user_text,
            ctx=result.ctx,
            image_data_url=camera_image_url,
            camera_see=True,
            camera_see_mode=see_mode,
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
    else:
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
    if result.gateway_speak_after_reply and reply:
        from presence_ui.gateway.gateway_speak import deliver_gateway_speak_after_reply

        ok, detail = await deliver_gateway_speak_after_reply(
            text=reply,
            person_id=person_id,
        )
        if ok:
            yield encode_event(
                activity_event(
                    kind="say",
                    label="Surface で話した",
                    detail=detail[:120],
                    ok=True,
                )
            )
        else:
            yield encode_event(
                activity_event(
                    kind="say",
                    label="声を届けられなかった",
                    detail=detail[:120],
                    ok=False,
                )
            )
