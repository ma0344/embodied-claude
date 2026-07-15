"""Near-eye camera — pull JPEG from koyori Phase 1 HTTP (Surface front cam)."""

from __future__ import annotations

import base64
import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from presence_ui.schemas import NearCameraSnapshotResponse

logger = logging.getLogger(__name__)

_MIN_JPEG_BYTES = 500


def near_camera_base_url() -> str:
    return os.getenv("KOYORI_CAM_URL", "http://koyori.local:8765").rstrip("/")


def near_camera_timeout_seconds(*, fresh: bool) -> float:
    env_key = (
        "PRESENCE_NEAR_CAMERA_SEE_TIMEOUT_SECONDS"
        if fresh
        else "PRESENCE_NEAR_CAMERA_TIMEOUT_SECONDS"
    )
    default = 25.0 if fresh else 8.0
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default


def near_camera_default_fresh() -> bool:
    return os.getenv("PRESENCE_NEAR_CAMERA_REFRESH", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def near_camera_default_describe() -> bool:
    return os.getenv("PRESENCE_NEAR_CAMERA_DESCRIBE", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _jpeg_size(image_base64: str) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        raw = base64.standard_b64decode(image_base64)
        img = Image.open(io.BytesIO(raw))
        return img.size
    except Exception:
        return None, None


async def fetch_koyori_near_health() -> dict[str, object]:
    """Proxy koyori /health (Phase 1 liveness)."""
    url = f"{near_camera_base_url()}/health"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(near_camera_timeout_seconds(fresh=False))
        ) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return {
                "ok": False,
                "error": f"koyori health HTTP {resp.status_code}",
                "url": url,
            }
        data = resp.json()
        if isinstance(data, dict):
            data.setdefault("ok", True)
            data["url"] = url
            return data
        return {"ok": True, "url": url, "raw": data}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "url": url}


async def fetch_near_camera_snapshot(
    *,
    fresh: bool | None = None,
    describe: bool | None = None,
) -> NearCameraSnapshotResponse:
    """Fetch near-eye JPEG from koyori; optionally LM Studio caption.

    fresh=False → GET /latest.jpg (timer cache; fast)
    fresh=True  → GET /see (sync capture; slow)
    """
    use_fresh = near_camera_default_fresh() if fresh is None else fresh
    do_describe = near_camera_default_describe() if describe is None else describe
    path = "/see" if use_fresh else "/latest.jpg"
    url = f"{near_camera_base_url()}{path}"
    ts = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(near_camera_timeout_seconds(fresh=use_fresh))
        ) as client:
            resp = await client.get(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("near-camera fetch failed url=%s: %s", url, exc)
        return NearCameraSnapshotResponse(
            timestamp=ts,
            source="koyori",
            path=path,
            error=str(exc),
        )

    content_type = (resp.headers.get("content-type") or "").lower()
    body = resp.content
    if resp.status_code != 200:
        detail = body[:200].decode("utf-8", errors="replace")
        return NearCameraSnapshotResponse(
            timestamp=ts,
            source="koyori",
            path=path,
            error=f"koyori HTTP {resp.status_code}: {detail}",
        )
    if "json" in content_type:
        # /see error payloads are JSON
        detail = body[:300].decode("utf-8", errors="replace")
        return NearCameraSnapshotResponse(
            timestamp=ts,
            source="koyori",
            path=path,
            error=f"koyori returned JSON error: {detail}",
        )
    if len(body) < _MIN_JPEG_BYTES or body[:2] != b"\xff\xd8":
        return NearCameraSnapshotResponse(
            timestamp=ts,
            source="koyori",
            path=path,
            error=f"not a JPEG (bytes={len(body)}, type={content_type!r})",
        )

    image_b64 = base64.standard_b64encode(body).decode("ascii")
    width, height = _jpeg_size(image_b64)
    caption: str | None = None
    if do_describe:
        try:
            from wifi_cam_mcp.vision import describe_image_outcome

            outcome = await describe_image_outcome(image_b64)
            caption = outcome.caption
            if not caption and outcome.error:
                logger.info("near-camera describe failed: %s", outcome.error)
        except Exception as exc:  # noqa: BLE001
            logger.warning("near-camera describe exception: %s", exc)
            caption = None

    return NearCameraSnapshotResponse(
        timestamp=ts,
        image_base64=image_b64,
        width=width,
        height=height,
        source="koyori",
        path=path,
        caption=caption,
        url=url,
    )


def save_near_camera_jpeg(image_base64: str) -> str | None:
    """Persist near-eye JPEG under ~/.claude/captures/near/; return path or None."""
    try:
        raw = base64.standard_b64decode(image_base64)
    except Exception:
        return None
    if len(raw) < _MIN_JPEG_BYTES or raw[:2] != b"\xff\xd8":
        return None
    out_dir = Path.home() / ".claude" / "captures" / "near"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"near_{ts}.jpg"
    path.write_bytes(raw)
    return str(path)


def near_look_fresh_default() -> bool:
    return os.getenv("PRESENCE_NEAR_LOOK_FRESH", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
