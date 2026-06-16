"""FastAPI app — Koyori's Room gateway (8090 → Claude Code 8080)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from presence_ui import __version__
from presence_ui.gateway.backend import backend_base_url
from presence_ui.gateway.chat_stream import stream_gateway_chat
from presence_ui.gateway.proxy import proxy_get
from presence_ui.schemas import (
    CameraSnapshotResponse,
    CancelReminderRequest,
    CancelReminderResponse,
    ClaudePermissionsResponse,
    ClaudePermissionsSaveRequest,
    ClaudePermissionsSaveResponse,
    HealthResponse,
    NativeHiddenSessionsRequest,
    NativeHideSessionResponse,
    NativeSessionListResponse,
    NativeSessionMessagesResponse,
    OutboundAckRequest,
    OutboundAckResponse,
    OutboundPendingResponse,
    PatchReminderSpeakLineRequest,
    PatchReminderSpeakLineResponse,
    RoomSayAckRequest,
    RoomSayAckResponse,
    RoomSayPendingItem,
    RoomSayPendingResponse,
    RoomSayResponse,
    TtsSurfaceRequest,
    TtsSurfaceResponse,
)
from presence_ui.services.camera import fetch_camera_snapshot
from presence_ui.services.display_time import display_timezone
from presence_ui.services.status import fetch_koyori_status
from presence_ui.utf8 import utf8_json

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PERSON_ID = os.getenv("PRESENCE_PERSON_ID", "ma")


def _native_chat_enabled() -> bool:
    return os.getenv("PRESENCE_NATIVE_CHAT", "").lower() in {"1", "true", "yes"}


def _load_repo_env() -> None:
    from presence_ui.repo_env import load_repo_env

    load_repo_env()


def create_app() -> FastAPI:
    _load_repo_env()
    native_chat = _native_chat_enabled()
    app = FastAPI(
        title="Koyori's Room",
        description="Gateway UI for Claude Code Web UI + sociality filter",
        version=__version__,
    )

    @app.on_event("startup")
    async def _prune_wifi_cam_capture_cache() -> None:
        import asyncio
        import logging

        from presence_ui.services.capture_cache import prune_startup

        try:
            removed = await asyncio.to_thread(prune_startup)
            if removed:
                logging.getLogger(__name__).info(
                    "Pruned %d stale wifi-cam capture file(s)", removed
                )
        except Exception as exc:
            logging.getLogger(__name__).debug("capture cache prune skipped: %s", exc)

        from presence_ui.gateway.reminder_watchdog import start_reminder_watchdog
        from presence_ui.gateway.tts_health_watchdog import start_tts_health_watchdog

        start_reminder_watchdog()
        start_tts_health_watchdog()

    @app.on_event("shutdown")
    async def _stop_background_tasks() -> None:
        from presence_ui.gateway.reminder_watchdog import stop_reminder_watchdog
        from presence_ui.gateway.tts_health_watchdog import stop_tts_health_watchdog

        stop_reminder_watchdog()
        stop_tts_health_watchdog()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("PRESENCE_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def no_cache_ui_assets(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Kiosk/PC must not keep stale app.js (crypto.randomUUID fix, send timeout)."""
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        from presence_ui.services.tts_surface import (
            surface_tts_enabled,
            surface_tts_ready,
            surface_tts_status,
        )

        tts_ready = surface_tts_ready() if surface_tts_enabled() else True
        status = "ok" if tts_ready else "degraded"
        return HealthResponse(
            status=status,
            version=__version__,
            details={
                "person_id": DEFAULT_PERSON_ID,
                "claude_code_backend": backend_base_url(),
                "mode": "gateway+native" if native_chat else "gateway",
                "native_chat": native_chat,
                "native_chat_prefix": "/api/native" if native_chat else None,
                "surface_tts_ready": tts_ready,
                "surface_tts_status": surface_tts_status(),
            },
        )

    @app.get("/api/v1/ui-config")
    def ui_config() -> JSONResponse:
        """Frontend routing: native SSE vs legacy 8080 proxy chat."""
        from presence_ui.services.outbound import outbound_web_speech_suppress_on_localhost
        from presence_ui.services.outbound_kiosk import kiosk_primary_active, kiosk_primary_enabled
        from presence_ui.services.outbound_sse import sse_enabled
        from presence_ui.services.tts_surface import (
            surface_tts_enabled,
            surface_tts_ready,
            surface_tts_status,
        )

        return utf8_json(
            {
                "chat_backend": "native" if native_chat else "proxy8080",
                "native_chat": native_chat,
                "native_login_path": "/api/native/login" if native_chat else None,
                "native_chat_path": "/api/native/chat" if native_chat else None,
                "native_sessions_path": "/api/v1/native/sessions" if native_chat else None,
                "display_timezone": display_timezone(),
                "legacy_chat_path": "/api/chat",
                "outbound_pending_path": "/api/v1/outbound/pending",
                "outbound_ack_path": "/api/v1/outbound/ack",
                "outbound_stream_path": "/api/v1/outbound/stream",
                "outbound_sse_enabled": sse_enabled(),
                "outbound_surface_tts_enabled": surface_tts_enabled(),
                "surface_tts_ready": surface_tts_ready(),
                "surface_tts_status": surface_tts_status(),
                "surface_tts_synthesize_path": "/api/v1/tts/surface",
                "kiosk_primary_enabled": kiosk_primary_enabled(),
                "kiosk_primary_active": kiosk_primary_active(),
                "outbound_poll_ms": int(os.getenv("PRESENCE_OUTBOUND_POLL_MS", "3000")),
                "outbound_poll_fallback_ms": int(
                    os.getenv("PRESENCE_OUTBOUND_POLL_FALLBACK_MS", "60000")
                ),
                "room_say_pending_path": "/api/v1/tts/room-say/pending",
                "room_say_ack_path": "/api/v1/tts/room-say/ack",
                "room_say_poll_ms": int(os.getenv("PRESENCE_ROOM_SAY_POLL_MS", "3000")),
                "reminder_watchdog_sec": int(os.getenv("PRESENCE_REMINDER_POLL_SEC", "60")),
                "outbound_web_speech_suppress_on_localhost": (
                    outbound_web_speech_suppress_on_localhost()
                ),
            },
        )

    @app.post("/api/v1/reminders/cancel", response_model=CancelReminderResponse)
    def post_reminders_cancel(body: CancelReminderRequest) -> CancelReminderResponse:
        """Cancel active reminder (A: hide/cancel)."""
        from presence_ui.deps import get_stores

        stores = get_stores()
        try:
            stores.relationship.cancel_commitment(
                body.commitment_id,
                source_text=body.source_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return CancelReminderResponse(ok=True, commitment_id=body.commitment_id)

    @app.post(
        "/api/v1/reminders/speak-line", response_model=PatchReminderSpeakLineResponse
    )
    def post_reminders_patch_speak_line(
        body: PatchReminderSpeakLineRequest,
    ) -> PatchReminderSpeakLineResponse:
        """Patch speak_line for active reminder (B: edit spoken phrase)."""
        from presence_ui.deps import get_stores

        stores = get_stores()
        try:
            stores.relationship.patch_commitment_speak_line(
                body.commitment_id, speak_line=body.speak_line
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return PatchReminderSpeakLineResponse(
            ok=True,
            commitment_id=body.commitment_id,
            speak_line=body.speak_line,
        )

    @app.get("/api/v1/claude/permissions", response_model=ClaudePermissionsResponse)
    def get_claude_permissions(request: Request) -> ClaudePermissionsResponse:
        """Claude Code permissions.allow presets (no secrets from settings.local.json)."""
        from presence_ui.gateway.native_chat_router import can_edit_claude_permissions
        from presence_ui.services.claude_permissions import (
            list_permission_state,
            settings_local_path,
        )

        presets, preserved = list_permission_state()
        return ClaudePermissionsResponse(
            presets=[
                {
                    "id": p.id,
                    "rule": p.rule,
                    "label": p.label,
                    "enabled": p.enabled,
                }
                for p in presets
            ],
            preserved_rules=preserved,
            settings_path=str(settings_local_path()),
            editable=can_edit_claude_permissions(request),
        )

    @app.post("/api/v1/claude/permissions", response_model=ClaudePermissionsSaveResponse)
    def post_claude_permissions(
        body: ClaudePermissionsSaveRequest,
        request: Request,
    ) -> ClaudePermissionsSaveResponse:
        """Update permissions.allow presets in settings.local.json."""
        from presence_ui.gateway.native_chat_router import can_edit_claude_permissions
        from presence_ui.services.claude_permissions import (
            list_permission_state,
            save_enabled_preset_ids,
        )

        if not can_edit_claude_permissions(request):
            raise HTTPException(status_code=403, detail="permissions edit denied")
        try:
            save_enabled_preset_ids(body.enabled_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        presets, preserved = list_permission_state()
        return ClaudePermissionsSaveResponse(
            presets=[
                {
                    "id": p.id,
                    "rule": p.rule,
                    "label": p.label,
                    "enabled": p.enabled,
                }
                for p in presets
            ],
            preserved_rules=preserved,
        )

    @app.get("/api/v1/outbound/pending", response_model=OutboundPendingResponse)
    def get_outbound_pending(
        person_id: str = DEFAULT_PERSON_ID,
        client_id: str = "",
        since: str | None = None,
        limit: int = 20,
    ) -> OutboundPendingResponse:
        from social_core import utc_now

        from presence_ui.deps import get_stores
        from presence_ui.services.outbound import list_pending_outbound
        from presence_ui.services.outbound_kiosk import (
            is_kiosk_client,
            note_kiosk_seen,
            should_deliver_to_client,
        )

        if not client_id.strip():
            raise HTTPException(status_code=400, detail="client_id is required")
        client = client_id.strip()
        if is_kiosk_client(client):
            note_kiosk_seen()
        if not should_deliver_to_client(client):
            from social_core import utc_now

            return OutboundPendingResponse(items=[], server_ts=utc_now())

        stores = get_stores()
        items = list_pending_outbound(
            stores,
            person_id=person_id,
            client_id=client,
            since=since,
            limit=limit,
        )
        return OutboundPendingResponse(
            items=[
                {
                    "nudge_id": item.nudge_id,
                    "ts": item.ts,
                    "text": item.text,
                    "speak": item.speak,
                    "channels": item.channels,
                    "desire": item.desire,
                }
                for item in items
            ],
            server_ts=utc_now(),
        )

    @app.post("/api/v1/outbound/ack", response_model=OutboundAckResponse)
    async def post_outbound_ack(body: OutboundAckRequest) -> OutboundAckResponse:
        from presence_ui.deps import get_stores
        from presence_ui.services.outbound import ack_outbound_delivery

        stores = get_stores()
        ok = ack_outbound_delivery(
            stores,
            nudge_id=body.nudge_id,
            client_id=body.client_id,
            channels=body.channels,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="nudge not found")
        return OutboundAckResponse(ok=True, nudge_id=body.nudge_id)

    @app.get("/api/v1/outbound/stream")
    async def get_outbound_stream(
        person_id: str = DEFAULT_PERSON_ID,
        client_id: str = "",
        since: str | None = None,
        limit: int = 20,
    ) -> StreamingResponse:
        from presence_ui.deps import get_stores
        from presence_ui.services.outbound import list_pending_outbound
        from presence_ui.services.outbound_kiosk import (
            is_kiosk_client,
            note_kiosk_seen,
            should_deliver_to_client,
        )
        from presence_ui.services.outbound_sse import (
            pending_item_payload,
            sse_enabled,
            stream_room_inbound,
        )

        if not sse_enabled():
            raise HTTPException(status_code=404, detail="outbound SSE disabled")
        if not client_id.strip():
            raise HTTPException(status_code=400, detail="client_id is required")

        client = client_id.strip()
        if is_kiosk_client(client):
            note_kiosk_seen()

        stores = get_stores()
        pending: list = []
        if should_deliver_to_client(client):
            pending = list_pending_outbound(
                stores,
                person_id=person_id,
                client_id=client,
                since=since,
                limit=limit,
            )
        catch_up = [pending_item_payload(item) for item in pending]

        return StreamingResponse(
            stream_room_inbound(catch_up=catch_up, client_id=client),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/v1/tts/surface", response_model=TtsSurfaceResponse)
    async def post_tts_surface(body: TtsSurfaceRequest) -> TtsSurfaceResponse:
        from presence_ui.services.tts_surface import (
            surface_tts_enabled,
            synthesize_surface_audio_async,
        )

        if not surface_tts_enabled():
            raise HTTPException(status_code=503, detail="surface TTS not configured")
        try:
            token, _fmt, content_type = await synthesize_surface_audio_async(body.text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc
        return TtsSurfaceResponse(
            token=token,
            audio_url=f"/api/v1/tts/surface/{token}",
            content_type=content_type,
        )

    @app.get("/api/v1/tts/surface/{token}")
    def get_tts_surface(token: str) -> FileResponse:
        from presence_ui.services.tts_surface import surface_audio_path, surface_media_type

        path = surface_audio_path(token)
        if path is None:
            raise HTTPException(status_code=404, detail="audio not found")
        return FileResponse(
            path,
            media_type=surface_media_type(path),
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.post("/api/v1/tts/room-say", response_model=RoomSayResponse)
    async def post_room_say(body: TtsSurfaceRequest) -> RoomSayResponse:
        from presence_ui.services.kiosk_say import deliver_speak_to_kiosk
        from presence_ui.services.outbound_kiosk import kiosk_primary_active, note_kiosk_seen

        if not kiosk_primary_active():
            raise HTTPException(
                status_code=409,
                detail="kiosk not primary — play on local speaker",
            )
        line = body.text.strip()
        if not line:
            raise HTTPException(status_code=400, detail="empty text")
        note_kiosk_seen()
        delivered, say_id, audio_url = deliver_speak_to_kiosk(line, source="say")
        detail = (
            f"routed to kiosk (listeners={delivered}, say_id={say_id}, audio="
            f"{'yes' if audio_url else 'no'})"
            if delivered
            else (
                f"queued for kiosk poll (no SSE listeners, say_id={say_id}, audio="
                f"{'yes' if audio_url else 'no'})"
            )
        )
        return RoomSayResponse(
            ok=True,
            detail=detail,
            say_id=say_id,
            sse_listeners=delivered,
            queued=True,
        )

    @app.get("/api/v1/tts/room-say/pending", response_model=RoomSayPendingResponse)
    def get_room_say_pending(
        client_id: str = "",
        since: str | None = None,
        limit: int = 10,
    ) -> RoomSayPendingResponse:
        from social_core import utc_now

        from presence_ui.services.outbound_kiosk import is_kiosk_client, note_kiosk_seen
        from presence_ui.services.room_say_pending import list_pending_room_say, room_say_payload

        if not client_id.strip():
            raise HTTPException(status_code=400, detail="client_id is required")
        client = client_id.strip()
        if is_kiosk_client(client):
            note_kiosk_seen()
        items = list_pending_room_say(
            client_id=client,
            since=since,
            limit=min(max(limit, 1), 20),
        )
        return RoomSayPendingResponse(
            items=[RoomSayPendingItem(**room_say_payload(item)) for item in items],
            server_ts=utc_now(),
        )

    @app.post("/api/v1/tts/room-say/ack", response_model=RoomSayAckResponse)
    def post_room_say_ack(body: RoomSayAckRequest) -> RoomSayAckResponse:
        from presence_ui.services.room_say_pending import ack_room_say

        ok = ack_room_say(say_id=body.say_id, client_id=body.client_id)
        if not ok:
            raise HTTPException(status_code=404, detail="unknown say_id")
        return RoomSayAckResponse(ok=True, say_id=body.say_id)

    @app.get("/api/v1/native/sessions", response_model=NativeSessionListResponse)
    def get_native_sessions(limit: int = 40) -> NativeSessionListResponse:
        """List chat sessions from Claude Code JSONL (shared across all browsers on ma-home)."""
        from presence_ui.services.native_history import list_native_sessions

        return list_native_sessions(limit=min(max(limit, 1), 100))

    @app.post("/api/v1/native/sessions/{session_id}/hide", response_model=NativeHideSessionResponse)
    def hide_native_session(session_id: str) -> NativeHideSessionResponse:
        from presence_ui.services.native_session_prefs import hide_session

        try:
            hidden = hide_session(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return NativeHideSessionResponse(
            session_id=session_id,
            hidden_count=len(hidden),
        )

    @app.post("/api/v1/native/hidden", response_model=NativeHideSessionResponse)
    def merge_native_hidden(body: NativeHiddenSessionsRequest) -> NativeHideSessionResponse:
        """Merge session ids into the shared hidden set (legacy localStorage migration)."""
        from presence_ui.services.native_session_prefs import hide_session_ids

        if not body.session_ids:
            from presence_ui.services.native_session_prefs import load_hidden_session_ids

            hidden = load_hidden_session_ids()
            return NativeHideSessionResponse(session_id="", hidden_count=len(hidden))
        try:
            hidden = hide_session_ids(body.session_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return NativeHideSessionResponse(
            session_id=body.session_ids[-1],
            hidden_count=len(hidden),
        )

    @app.get(
        "/api/v1/native/sessions/{session_id}/messages",
        response_model=NativeSessionMessagesResponse,
    )
    def get_native_session_messages(session_id: str) -> NativeSessionMessagesResponse:
        from presence_ui.services.native_history import fetch_native_session_messages

        result = fetch_native_session_messages(session_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result

    if native_chat:
        from presence_ui.gateway.ccs_integration import mount_claude_code_server_router

        mount_claude_code_server_router(app, person_id=DEFAULT_PERSON_ID)

        @app.get("/poc/native")
        async def poc_native_page() -> FileResponse:
            return FileResponse(
                STATIC_DIR / "poc-native.html",
                media_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store, must-revalidate"},
            )

    # --- Claude Code mirror: transparent GET proxy (8090 → 8080) ---

    @app.get("/api/projects")
    async def get_projects() -> Response:
        return await proxy_get("/api/projects")

    @app.get("/api/projects/{encoded_project}/histories")
    async def get_project_histories(encoded_project: str) -> Response:
        return await proxy_get(f"/api/projects/{encoded_project}/histories")

    @app.get("/api/projects/{encoded_project}/histories/{session_id}")
    async def get_conversation_history(encoded_project: str, session_id: str) -> Response:
        return await proxy_get(
            f"/api/projects/{encoded_project}/histories/{session_id}",
        )

    # --- Claude Code mirror: POST with sociality filter ---

    @app.post("/api/chat")
    async def post_chat(request: Request) -> StreamingResponse:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="body must be a JSON object")

        if not str(payload.get("message") or "").strip():
            raise HTTPException(status_code=400, detail="message must not be empty")

        return StreamingResponse(
            stream_gateway_chat(payload=payload, person_id=DEFAULT_PERSON_ID),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @app.post("/api/abort/{request_id}")
    async def post_abort(request_id: str, request: Request) -> Response:
        body = await request.body()
        path = f"/api/abort/{request_id}"
        url = f"{backend_base_url()}{path}"
        import httpx

        content_type = request.headers.get("content-type", "application/json")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                upstream = await client.post(
                    url,
                    content=body,
                    headers={"Content-Type": content_type},
                )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
        )

    # --- Koyori presence extras (not Claude Code session API) ---

    @app.get("/api/v1/koyori/status")
    def get_koyori_status(person_id: str = DEFAULT_PERSON_ID) -> JSONResponse:
        return utf8_json(fetch_koyori_status(person_id=person_id))

    @app.get("/api/v1/camera/snapshot", response_model=CameraSnapshotResponse)
    async def get_camera_snapshot() -> CameraSnapshotResponse:
        return await fetch_camera_snapshot()

    @app.post("/api/v1/autonomous-tick")
    async def post_autonomous_tick(request: Request) -> JSONResponse:
        """Run one bounded autonomous action (compose/plan/execute, no MCP body tools)."""
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be a JSON object")

        person_id = str(body.get("person_id") or DEFAULT_PERSON_ID)
        trigger = body.get("trigger")
        speech_text = body.get("speech_text")
        smoke_action = body.get("smoke_action")

        from presence_ui.gateway.autonomous_tick import run_autonomous_tick

        try:
            result = await run_autonomous_tick(
                person_id=person_id,
                trigger=str(trigger) if trigger else None,
                speech_text=str(speech_text) if speech_text else None,
                smoke_action=str(smoke_action) if smoke_action else None,
            )
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("autonomous-tick failed")
            payload = {
                "ok": False,
                "primary_move": "error",
                "action": smoke_action or "none",
                "summary": str(exc) or type(exc).__name__,
                "detail": type(exc).__name__,
                "events": [],
            }
            return utf8_json(payload)
        payload = {
            "ok": result.ok,
            "primary_move": result.primary_move,
            "action": result.action,
            "summary": result.summary,
            "detail": result.detail,
            "events": result.events,
        }
        return utf8_json(payload)

    @app.get("/projects")
    @app.get("/projects/{_rest:path}")
    async def legacy_webui_project_path() -> RedirectResponse:
        """8080 SPA paths bookmarked on kiosk — presence-ui lives at /."""
        return RedirectResponse(url="/", status_code=302)

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store, must-revalidate"},
        )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    host = os.getenv("PRESENCE_UI_HOST", "0.0.0.0")
    port = int(os.getenv("PRESENCE_UI_PORT", "8090"))
    uvicorn.run(
        "presence_ui.main:app",
        host=host,
        port=port,
        reload=os.getenv("PRESENCE_UI_RELOAD", "").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    run()
