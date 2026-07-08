"""Native chat routes — SSE chat with gateway enrich and list direct-reply."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from claude_code_server import AgentConfig
from claude_code_server.agent import ClaudeAgent
from claude_code_server.models import LoginRequest
from fastapi import APIRouter, Depends, HTTPException, Request
from social_core import utc_now
from starlette.responses import StreamingResponse

from presence_ui.gateway.calendar_prefetch import prefetch_calendar_for_message
from presence_ui.gateway.ccs_integration import (
    agent_config_from_intercept,
    default_agent_config,
)
from presence_ui.gateway.claude_session_mode import ClaudeSessionRegistry
from presence_ui.gateway.deterministic_memory import (
    MemoryListRequest,
    detect_memory_list_request,
    fetch_memory_list,
    format_memory_list_reply,
)
from presence_ui.gateway.gateway_turn_cache import gateway_turn_cache_scope
from presence_ui.gateway.hybrid_intent import resolve_hybrid_intent
from presence_ui.gateway.native_chat_models import NativeChatRequest
from presence_ui.gateway.search_prefetch import prefetch_web_search_for_message
from presence_ui.gateway.see_prefetch import prefetch_camera_for_message
from presence_ui.gateway.social_chat import ChatInterceptResult, intercept_chat_request_async
from presence_ui.gateway.surface_direct import use_surface_direct_path
from presence_ui.gateway.surface_session import append_surface_turn
from presence_ui.gateway.doc_prefetch import prefetch_doc_context_for_turn
from presence_ui.gateway.url_prefetch import prefetch_urls_for_turn
from presence_ui.services.chat_image import (
    prepare_chat_image_data_url,
    prepare_enriched_for_camera_see,
    prepare_enriched_for_user_image,
    user_log_text_with_image,
)
from presence_ui.services.llm import generate_surface_reply

logger = logging.getLogger(__name__)

_TOKENS: set[str] = set()
# Session lifecycle for Claude CLI (--session-id vs --resume).
_CLAUDE_SESSIONS = ClaudeSessionRegistry()
_SESSION_CHAT_LOCKS: dict[str, asyncio.Lock] = {}


def _require_auth(request: Request) -> None:
    if native_bearer_authorized(request):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def native_bearer_authorized(request: Request) -> bool:
    """True when request carries a valid native-chat login token."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[7:] in _TOKENS:
        return True
    token = request.query_params.get("token", "")
    return bool(token and token in _TOKENS)


def can_edit_claude_permissions(request: Request) -> bool:
    """Localhost or native login — settings.local.json lives on ma-home."""
    client = request.client
    if client and client.host in {"127.0.0.1", "::1", "testclient"}:
        return True
    return native_bearer_authorized(request)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_memory_list(
    *,
    rows: list[dict[str, str]],
    list_request: MemoryListRequest,
    session_id: str | None,
) -> AsyncIterator[str]:
    del session_id  # direct path — never mint a Claude-resumable session id
    body = format_memory_list_reply(
        rows,
        limit=list_request.limit,
        oldest_first=list_request.oldest_first,
    )
    yield _sse("text", {"content": body})
    yield _sse("done", {"cost": 0.0, "duration_ms": 0, "direct": True, "claude_session": False})


def _session_chat_lock(session_id: str) -> asyncio.Lock:
    lock = _SESSION_CHAT_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _SESSION_CHAT_LOCKS[session_id] = lock
    return lock


async def _emit_post_reply_side_effects(
    *,
    person_id: str,
    session_id: str,
    user_text: str,
    reply: str,
    intercept: ChatInterceptResult,
) -> AsyncIterator[str]:
    if intercept.plan and intercept.ctx:
        from presence_ui.heartbeat.record import finalize_chat_turn

        await asyncio.to_thread(
            finalize_chat_turn,
            person_id=person_id,
            session_id=session_id,
            user_text=user_text,
            reply_text=reply,
            plan=intercept.plan,
            ctx=intercept.ctx,
        )

    if intercept.gateway_speak_after_reply and reply:
        from presence_ui.gateway.gateway_speak import deliver_gateway_speak_after_reply

        ok, detail = await deliver_gateway_speak_after_reply(
            text=reply,
            person_id=person_id,
        )
        yield _sse(
            "room_activity",
            {
                "kind": "say",
                "label": "Surface で話した" if ok else "声を届けられなかった",
                "detail": detail[:120],
                "ok": ok,
            },
        )


def _resolve_surface_session_id(
    *,
    req: NativeChatRequest,
    intercept: ChatInterceptResult,
) -> str:
    for candidate in (intercept.session_id, req.session_id):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return str(uuid.uuid4())


async def _stream_surface_chat(
    *,
    req: NativeChatRequest,
    intercept: ChatInterceptResult,
    person_id: str,
    image_data_url: str | None = None,
    camera_see: bool = False,
    camera_see_mode: str = "current",
) -> AsyncIterator[str]:
    """Direct LM Studio surface path — no Claude Code subprocess."""
    enriched = intercept.payload or {}
    enriched_user = str(enriched.get("message") or req.prompt).strip()
    raw_user = str(req.prompt).strip()
    user_attached_image = bool(req.image_base64 and str(req.image_base64).strip())
    has_image = bool(image_data_url)
    image_source = "user" if user_attached_image else ("camera" if camera_see else "user")
    if has_image and user_attached_image:
        enriched_user = prepare_enriched_for_user_image(enriched_user)
        logger.info("native chat user image attached (utterance=%r)", raw_user[:80])
    elif has_image and camera_see:
        enriched_user = prepare_enriched_for_camera_see(enriched_user, see_mode=camera_see_mode)
        logger.info(
            "native chat camera see via surface 12b (mode=%s utterance=%r)",
            camera_see_mode,
            raw_user[:80],
        )
    sid = _resolve_surface_session_id(req=req, intercept=intercept)
    yield _sse("session", {"session_id": sid, "claude_session": False})
    user_context = {"enriched": enriched_user, "raw": raw_user}
    if has_image:
        user_context["image_attached"] = True
        user_context["image_source"] = image_source
    if enriched_user and enriched_user != raw_user:
        yield _sse("user_context", user_context)
    elif has_image:
        yield _sse("user_context", user_context)

    reply = ""
    async with _session_chat_lock(sid):
        try:
            if intercept.ctx is None:
                raise RuntimeError("surface direct requires intercept.ctx from compose/plan")
            reply = await generate_surface_reply(
                enriched_user=enriched_user,
                raw_user=raw_user,
                ctx=intercept.ctx,
                image_data_url=image_data_url,
                image_source="camera" if camera_see else "user",
            )
            if camera_see and image_data_url and reply:
                from presence_ui.services.somatic import note_eyes_multimodal_see_ok

                note_eyes_multimodal_see_ok(see_mode=camera_see_mode)
        except Exception as exc:
            logger.exception("surface direct reply failed")
            yield _sse("error", {"message": str(exc)})
            return

        if reply:
            yield _sse("text", {"content": reply})
        yield _sse(
            "done",
            {"cost": 0.0, "duration_ms": 0, "direct": True, "claude_session": False},
        )

        if reply or has_image:
            ts = utc_now()
            log_user = user_log_text_with_image(
                raw_user=raw_user,
                image_attached=has_image and not camera_see,
                camera_see=camera_see and has_image,
            )
            append_surface_turn(
                session_id=sid,
                role="user",
                text=log_user,
                timestamp=ts,
                enriched=enriched_user if enriched_user != log_user else None,
            )
            if reply:
                append_surface_turn(
                    session_id=sid,
                    role="assistant",
                    text=reply,
                    timestamp=ts,
                )

    async for event in _emit_post_reply_side_effects(
        person_id=person_id,
        session_id=sid,
        user_text=raw_user,
        reply=reply,
        intercept=intercept,
    ):
        yield event


async def _stream_agent_chat(
    *,
    req: NativeChatRequest,
    intercept: ChatInterceptResult,
    base_config: AgentConfig,
    person_id: str,
) -> AsyncIterator[str]:
    cfg = agent_config_from_intercept(intercept, base_config)
    enriched = intercept.payload or {}
    prompt = str(enriched.get("message") or req.prompt).strip()
    sid, is_new = _CLAUDE_SESSIONS.resolve(req.session_id)
    if is_new:
        _CLAUDE_SESSIONS.mark_in_flight(sid)
    reply_parts: list[str] = []
    # Tell the browser the session id immediately (CLI init can arrive much later).
    yield _sse("session", {"session_id": sid, "claude_session": True})
    agent = ClaudeAgent()
    reply = ""
    async with _session_chat_lock(sid):
        try:
            async for event in agent.chat(
                prompt=prompt,
                session_id=sid,
                config=cfg,
                is_new=is_new,
            ):
                evt_type = event["event"]
                evt_data = event["data"]
                if evt_type == "session":
                    registered = evt_data.get("session_id")
                    if isinstance(registered, str) and registered:
                        _CLAUDE_SESSIONS.mark_created(registered)
                if evt_type == "text":
                    content = evt_data.get("content")
                    if content:
                        reply_parts.append(str(content))
                yield _sse(evt_type, evt_data)
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
        finally:
            _CLAUDE_SESSIONS.clear_in_flight(sid)
            await agent.cancel()

        if reply_parts:
            _CLAUDE_SESSIONS.mark_created(sid)

        reply = "".join(reply_parts).strip()
        # PAUSE（青空の咀嚼）は inward 自律 tick で実行。会話直後の post-chat internal は
        # ma のターンに食い込むため native chat からは呼ばない（gw_resume は smoke 用に残す）。

    async for event in _emit_post_reply_side_effects(
        person_id=person_id,
        session_id=sid,
        user_text=req.prompt,
        reply=reply,
        intercept=intercept,
    ):
        yield event


def create_native_chat_router(*, person_id: str) -> APIRouter:
    """FastAPI router: login + SSE chat (list direct-reply bypasses Claude CLI)."""
    router = APIRouter()
    base = default_agent_config()

    @router.post("/login")
    async def login(req: LoginRequest) -> dict[str, str]:
        if req.password != base.password:
            raise HTTPException(status_code=401, detail="Wrong password")
        token = uuid.uuid4().hex
        _TOKENS.add(token)
        return {"token": token}

    @router.get("/auth/check")
    async def auth_check(_: None = Depends(_require_auth)) -> dict[str, bool]:
        return {"ok": True}

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "native-chat-poc"}

    @router.post("/chat")
    async def chat(
        req: NativeChatRequest,
        _: None = Depends(_require_auth),
    ) -> StreamingResponse:
        with gateway_turn_cache_scope():
            return await _handle_native_chat(req, person_id=person_id, base_config=base)

    async def _handle_native_chat(
        req: NativeChatRequest,
        *,
        person_id: str,
        base_config: AgentConfig,
    ) -> StreamingResponse:
        image_data_url: str | None = None
        if req.image_base64 and str(req.image_base64).strip():
            try:
                image_data_url = prepare_chat_image_data_url(
                    image_base64=req.image_base64,
                    image_mime=req.image_mime,
                )
                logger.info(
                    "native chat received image attachment (b64=%d, mime=%s)",
                    len(str(req.image_base64).strip()),
                    req.image_mime or "image/jpeg",
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        prompt_text = str(req.prompt or "").strip()
        if not prompt_text and not image_data_url:
            raise HTTPException(status_code=400, detail="prompt or image required")

        list_request = detect_memory_list_request(prompt_text)
        if list_request:
            # Ingest utterance + progress via intercept side effects without Claude.
            await intercept_chat_request_async(
                payload={"message": req.prompt, "sessionId": req.session_id},
                person_id=person_id,
                lite=True,
            )
            rows = fetch_memory_list(
                limit=list_request.limit,
                oldest_first=list_request.oldest_first,
            )
            stream = _stream_memory_list(
                rows=rows,
                list_request=list_request,
                session_id=req.session_id,
            )
            return StreamingResponse(stream, media_type="text/event-stream")

        hybrid = resolve_hybrid_intent(prompt_text)
        vision_note: str | None = None
        camera_see_mode = hybrid.see_intent.mode if hybrid.see_intent else "current"
        web_search_note: str | None = None
        url_note: str | None = None
        calendar_note: str | None = None
        calendar_write_note: str | None = None
        search_hits = []
        search_query = ""
        try:
            calendar_note, _cal_events = await prefetch_calendar_for_message(prompt_text)
            if calendar_note:
                logger.info("native chat calendar prefetch ok (%d chars)", len(calendar_note))
        except Exception as exc:
            logger.warning("native chat calendar prefetch failed: %s", exc)
            calendar_note = None
        try:
            web_search_note, _web_events, search_hits, search_query = (
                await prefetch_web_search_for_message(prompt_text)
            )
            if web_search_note:
                logger.info("native chat web search prefetch ok (%d chars)", len(web_search_note))
        except Exception as exc:
            logger.warning("native chat web search prefetch failed: %s", exc)
            web_search_note = None
        try:
            url_note, _url_events = await prefetch_urls_for_turn(
                req.prompt,
                search_hits=search_hits,
                search_query=search_query,
            )
            if url_note:
                logger.info("native chat url prefetch ok (%d chars)", len(url_note))
        except Exception as exc:
            logger.warning("native chat url prefetch failed: %s", exc)
            url_note = None
        doc_note: str | None = None
        try:
            doc_note, _doc_events = await prefetch_doc_context_for_turn(
                req.prompt,
                session_id=req.session_id,
            )
            if doc_note:
                logger.info("native chat doc prefetch ok (%d chars)", len(doc_note))
        except Exception as exc:
            logger.warning("native chat doc prefetch failed: %s", exc)
            doc_note = None
        camera_image_from_prefetch = False
        try:
            from presence_ui.deps import get_stores

            if not image_data_url:
                use_camera_surface = use_surface_direct_path()
                vision_note, _prefetch_events, camera_image_url = await prefetch_camera_for_message(
                    req.prompt,
                    see_intent=hybrid.see_intent,
                    ptz_intent=hybrid.ptz_intent,
                    stores=get_stores(),
                    person_id=person_id,
                    surface_multimodal=use_camera_surface,
                )
                if camera_image_url:
                    image_data_url = camera_image_url
                    vision_note = None
                    camera_image_from_prefetch = True
                    logger.info(
                        "native chat camera surface multimodal ok (mode=%s)",
                        camera_see_mode,
                    )
                elif vision_note:
                    logger.info("native chat camera prefetch ok (%d chars)", len(vision_note))
        except Exception as exc:
            logger.warning("native chat camera prefetch failed: %s", exc)
            vision_note = None

        intercept_payload: dict[str, object] = {
            "message": req.prompt,
            "sessionId": req.session_id,
        }
        inbound_nudge = getattr(req, "inbound_nudge", None)
        inbound_nudge_id = getattr(req, "inbound_nudge_id", None)
        if inbound_nudge and str(inbound_nudge).strip():
            intercept_payload["inboundNudge"] = str(inbound_nudge).strip()
            if inbound_nudge_id:
                intercept_payload["inboundNudgeId"] = inbound_nudge_id

        intercept = await intercept_chat_request_async(
            payload=intercept_payload,
            person_id=person_id,
            lite=True,
            vision_prefetch=vision_note,
            web_search_prefetch=web_search_note,
            url_prefetch=url_note,
            doc_prefetch=doc_note,
            calendar_prefetch=calendar_note,
            calendar_write=calendar_write_note,
            hybrid=hybrid,
        )
        if not intercept.forward:
            async def silent_stream() -> AsyncIterator[str]:
                yield _sse("text", {"content": ""})
                yield _sse("done", {"cost": 0.0, "duration_ms": 0, "silent": True})

            return StreamingResponse(silent_stream(), media_type="text/event-stream")

        if use_surface_direct_path():
            stream = _stream_surface_chat(
                req=req,
                intercept=intercept,
                person_id=person_id,
                image_data_url=image_data_url,
                camera_see=camera_image_from_prefetch,
                camera_see_mode=camera_see_mode,
            )
        else:
            stream = _stream_agent_chat(
                req=req, intercept=intercept, base_config=base_config, person_id=person_id
            )
        return StreamingResponse(stream, media_type="text/event-stream")

    return router
