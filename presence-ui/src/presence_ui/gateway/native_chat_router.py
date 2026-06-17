"""Native chat routes — SSE chat with gateway enrich and list direct-reply."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from claude_code_server import AgentConfig, ChatRequest
from claude_code_server.agent import ClaudeAgent
from claude_code_server.models import LoginRequest
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import StreamingResponse

from presence_ui.gateway.ccs_integration import (
    agent_config_from_intercept,
    default_agent_config,
)
from presence_ui.gateway.deterministic_memory import (
    MemoryListRequest,
    detect_memory_list_request,
    fetch_memory_list,
    format_memory_list_reply,
)
from presence_ui.gateway.hybrid_intent import resolve_hybrid_intent
from presence_ui.gateway.see_prefetch import prefetch_camera_for_message
from presence_ui.gateway.social_chat import ChatInterceptResult, intercept_chat_request_async

logger = logging.getLogger(__name__)

_TOKENS: set[str] = set()
# Session IDs that Claude CLI actually created (direct-reply paths must not register here).
_CLAUDE_SESSION_IDS: set[str] = set()


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
    sid = req.session_id or str(uuid.uuid4())
    is_new = req.session_id is None or req.session_id not in _CLAUDE_SESSION_IDS
    reply_parts: list[str] = []
    # Tell the browser the session id immediately (CLI init can arrive much later).
    yield _sse("session", {"session_id": sid, "claude_session": True})
    agent = ClaudeAgent()
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
                    _CLAUDE_SESSION_IDS.add(registered)
            if evt_type == "text":
                content = evt_data.get("content")
                if content:
                    reply_parts.append(str(content))
            yield _sse(evt_type, evt_data)
    except Exception as exc:
        yield _sse("error", {"message": str(exc)})
    finally:
        await agent.cancel()

    reply = "".join(reply_parts).strip()
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
        try:
            vision_note, _prefetch_events = await prefetch_camera_for_message(
                req.prompt,
                see_intent=hybrid.see_intent,
                ptz_intent=hybrid.ptz_intent,
            )
            if vision_note:
                logger.info("native chat camera prefetch ok (%d chars)", len(vision_note))
        except Exception as exc:
            logger.warning("native chat camera prefetch failed: %s", exc)
            vision_note = None

        intercept = await intercept_chat_request_async(
            payload={"message": req.prompt, "sessionId": req.session_id},
            person_id=person_id,
            lite=True,
            vision_prefetch=vision_note,
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
