"""Tests for koyori near-eye Phase 2 pull."""

from __future__ import annotations

import base64
import io

import httpx
import pytest
from PIL import Image

from presence_ui.services import near_camera


def _jpeg_bytes(*, size: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=(40, 80, 120)).save(buf, format="JPEG", quality=85)
    data = buf.getvalue()
    assert len(data) >= 500
    assert data[:2] == b"\xff\xd8"
    return data


@pytest.fixture(autouse=True)
def _near_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOYORI_CAM_URL", "http://koyori.test:8765")
    monkeypatch.setenv("PRESENCE_NEAR_CAMERA_REFRESH", "0")
    monkeypatch.setenv("PRESENCE_NEAR_CAMERA_DESCRIBE", "0")
    monkeypatch.setenv("PRESENCE_NEAR_CAMERA_TIMEOUT_SECONDS", "2")


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    real_client = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs = dict(kwargs)
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(near_camera.httpx, "AsyncClient", client_factory)


@pytest.mark.asyncio
async def test_fetch_near_camera_latest_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    jpeg = _jpeg_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/latest.jpg"
        return httpx.Response(200, content=jpeg, headers={"content-type": "image/jpeg"})

    _patch_client(monkeypatch, handler)

    snap = await near_camera.fetch_near_camera_snapshot(fresh=False, describe=False)
    assert snap.error is None
    assert snap.path == "/latest.jpg"
    assert snap.source == "koyori"
    assert snap.image_base64
    assert base64.standard_b64decode(snap.image_base64)[:2] == b"\xff\xd8"
    assert snap.width == 64
    assert snap.height == 64


@pytest.mark.asyncio
async def test_fetch_near_camera_fresh_uses_see(monkeypatch: pytest.MonkeyPatch) -> None:
    jpeg = _jpeg_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/see"
        return httpx.Response(200, content=jpeg, headers={"content-type": "image/jpeg"})

    _patch_client(monkeypatch, handler)

    snap = await near_camera.fetch_near_camera_snapshot(fresh=True, describe=False)
    assert snap.error is None
    assert snap.path == "/see"


@pytest.mark.asyncio
async def test_fetch_near_camera_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"ok": False, "error": "busy"})

    _patch_client(monkeypatch, handler)

    snap = await near_camera.fetch_near_camera_snapshot(fresh=False, describe=False)
    assert snap.image_base64 is None
    assert snap.error
    assert "503" in snap.error


@pytest.mark.asyncio
async def test_fetch_koyori_near_health(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"ok": True, "exists": True, "bytes": 12000})

    _patch_client(monkeypatch, handler)

    health = await near_camera.fetch_koyori_near_health()
    assert health.get("ok") is True
    assert health.get("exists") is True
