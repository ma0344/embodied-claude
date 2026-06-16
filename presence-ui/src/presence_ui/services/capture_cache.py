"""Startup / manual pruning for wifi-cam capture dir (ma-home Temp accumulation)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def prune_startup() -> int:
    """Prune stale capture JPEGs and old surface TTS files. Safe if camera unused."""
    try:
        from wifi_cam_mcp.capture_cache import (
            prune_capture_dir,
            prune_tts_surface_dir,
            resolve_capture_dir,
        )
    except ImportError:
        return 0

    root = resolve_capture_dir()
    removed = prune_capture_dir(root)
    removed += prune_tts_surface_dir(root)
    return removed


async def prune_startup_async() -> int:
    import asyncio

    return await asyncio.to_thread(prune_startup)
