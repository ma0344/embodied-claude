"""Native chat routes — SSE chat with gateway enrich and list direct-reply."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from claude_code_server import AgentConfig, ChatRequest
from claude_code_server.agent import ClaudeAgent
from claude_code_server.models import LoginRequest
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from presence_ui.gateway.calendar_prefetch import prefetch_calendar_for_message
from presence_ui.gateway.calendar_write import execute_calendar_write_for_message
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
from presence_ui.gateway.hybrid_intent import resolve_hybrid_intent
from presence_ui.gateway.search_prefetch import prefetch_web_search_for_message
from presence_ui.gateway.see_prefetch import prefetch_camera_for_message
from presence_ui.gateway.social_chat import ChatInterceptResult, intercept_chat_request_async
from presence_ui.gateway.url_prefetch import prefetch_urls_for_turn

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


async def _stream_agent_chat(
    *,
    req: ChatRequest,
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
        if reply and intercept.plan and intercept.ctx:
            from presence_ui.gateway.gw_resume import run_post_chat_internal_turn

            await run_post_chat_internal_turn(
                session_id=sid,
                person_id=person_id,
                ctx=intercept.ctx,
                plan=intercept.plan,
                reply_text=reply,
            )

    if intercept.plan and intercept.ctx:
        from presence_ui.heartbeat.record import finalize_chat_turn

        await asyncio.to_thread(
            finalize_chat_turn,
            person_id=person_id,
            session_id=sid,
            user_text=req.prompt,
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
        req: ChatRequest,
        _: None = Depends(_require_auth),
    ) -> StreamingResponse:
        list_request = detect_memory_list_request(req.prompt)
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

        hybrid = resolve_hybrid_intent(req.prompt)
        vision_note: str | None = None
        web_search_note: str | None = None
        url_note: str | None = None
        calendar_note: str | None = None
        calendar_write_note: str | None = None
        search_hits = []
        search_query = ""
        try:
            calendar_write_note, _write_events = await execute_calendar_write_for_message(
                req.prompt
            )
            if calendar_write_note:
                logger.info(
                    "native chat calendar write ok (%d chars)", len(calendar_write_note)
                )
        except Exception as exc:
            logger.warning("native chat calendar write failed: %s", exc)
            calendar_write_note = None
        try:
            calendar_note, _cal_events = await prefetch_calendar_for_message(req.prompt)
            if calendar_note:
                logger.info("native chat calendar prefetch ok (%d chars)", len(calendar_note))
        except Exception as exc:
            logger.warning("native chat calendar prefetch failed: %s", exc)
            calendar_note = None
        try:
            web_search_note, _web_events, search_hits, search_query = (
                await prefetch_web_search_for_message(req.prompt)
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
        try:
            from presence_ui.deps import get_stores

            vision_note, _prefetch_events = await prefetch_camera_for_message(
                req.prompt,
                see_intent=hybrid.see_intent,
                ptz_intent=hybrid.ptz_intent,
                stores=get_stores(),
                person_id=person_id,
            )
            if vision_note:
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
            calendar_prefetch=calendar_note,
            calendar_write=calendar_write_note,
            hybrid=hybrid,
        )
        if not intercept.forward:
            async def silent_stream() -> AsyncIterator[str]:
                yield _sse("text", {"content": ""})
                yield _sse("done", {"cost": 0.0, "duration_ms": 0, "silent": True})

            return StreamingResponse(silent_stream(), media_type="text/event-stream")

        stream = _stream_agent_chat(
            req=req, intercept=intercept, base_config=base, person_id=person_id
        )
        return StreamingResponse(stream, media_type="text/event-stream")

    return router
