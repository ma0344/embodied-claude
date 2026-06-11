"""FastAPI app — Koyori's Room gateway (8090 → Claude Code 8080)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from presence_ui import __version__
from presence_ui.gateway.backend import backend_base_url
from presence_ui.gateway.proxy import proxy_get
from presence_ui.gateway.social_chat import intercept_chat_request, stream_silent_response
from presence_ui.gateway.stream_sanitize import proxy_post_stream_filtered
from presence_ui.schemas import CameraSnapshotResponse, HealthResponse
from presence_ui.services.camera import fetch_camera_snapshot
from presence_ui.services.status import fetch_koyori_status
from presence_ui.utf8 import utf8_json

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PERSON_ID = os.getenv("PRESENCE_PERSON_ID", "ma")


def _load_repo_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    repo_root = Path(__file__).resolve().parents[3]
    load_dotenv(repo_root / "wifi-cam-mcp" / ".env")
    load_dotenv(repo_root / ".env")


def create_app() -> FastAPI:
    _load_repo_env()
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

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            details={
                "person_id": DEFAULT_PERSON_ID,
                "claude_code_backend": backend_base_url(),
                "mode": "gateway",
            },
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

        try:
            result = intercept_chat_request(payload=payload, person_id=DEFAULT_PERSON_ID)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not result.forward:
            return StreamingResponse(
                stream_silent_response(plan_move=result.plan_move or "stay_silent"),
                media_type="application/x-ndjson",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        user_text = result.user_text or str(payload.get("message") or "").strip()
        return await proxy_post_stream_filtered(
            "/api/chat",
            result.payload or payload,
            user_text=user_text,
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

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html; charset=utf-8",
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
