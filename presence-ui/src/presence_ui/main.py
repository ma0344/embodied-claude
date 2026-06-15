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
    HealthResponse,
    NativeSessionListResponse,
    NativeSessionMessagesResponse,
)
from presence_ui.services.camera import fetch_camera_snapshot
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
        return HealthResponse(
            status="ok",
            version=__version__,
            details={
                "person_id": DEFAULT_PERSON_ID,
                "claude_code_backend": backend_base_url(),
                "mode": "gateway+native" if native_chat else "gateway",
                "native_chat": native_chat,
                "native_chat_prefix": "/api/native" if native_chat else None,
            },
        )

    @app.get("/api/v1/ui-config")
    def ui_config() -> JSONResponse:
        """Frontend routing: native SSE vs legacy 8080 proxy chat."""
        return utf8_json(
            {
                "chat_backend": "native" if native_chat else "proxy8080",
                "native_chat": native_chat,
                "native_login_path": "/api/native/login" if native_chat else None,
                "native_chat_path": "/api/native/chat" if native_chat else None,
                "native_sessions_path": "/api/v1/native/sessions" if native_chat else None,
                "legacy_chat_path": "/api/chat",
            },
        )

    @app.get("/api/v1/native/sessions", response_model=NativeSessionListResponse)
    def get_native_sessions(limit: int = 40) -> NativeSessionListResponse:
        """List chat sessions from Claude Code JSONL (shared across all browsers on ma-home)."""
        from presence_ui.services.native_history import list_native_sessions

        return list_native_sessions(limit=min(max(limit, 1), 100))

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
