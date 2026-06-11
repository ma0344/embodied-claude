"""Transparent GET proxy to Claude Code backend."""

from __future__ import annotations

import httpx
from fastapi import HTTPException
from fastapi.responses import Response
from starlette.responses import StreamingResponse

from presence_ui.gateway.backend import backend_base_url


async def proxy_get(path: str) -> Response:
    """Forward GET request unchanged to Claude Code backend."""
    url = f"{backend_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream = await client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Claude Code backend unreachable at {backend_base_url()}: {exc}",
        ) from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


async def proxy_post_stream(path: str, payload: dict) -> StreamingResponse:
    """Forward POST body unchanged; stream NDJSON response back."""
    url = f"{backend_base_url()}{path}"

    async def stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload) as upstream:
                    upstream.raise_for_status()
                    async for chunk in upstream.aiter_bytes():
                        yield chunk
        except httpx.HTTPStatusError as exc:
            err = {"type": "error", "error": str(exc.response.text)}
            import json

            yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")
        except httpx.RequestError as exc:
            err = {"type": "error", "error": f"backend unreachable: {exc}"}
            yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
