"""Periodic TTS engine health — log when Aivis/VOICEVOX goes down or recovers."""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_watchdog_task: asyncio.Task[None] | None = None
_last_ready: bool | None = None


def tts_health_watchdog_enabled() -> bool:
    return os.getenv("PRESENCE_TTS_HEALTH_WATCHDOG", "1").lower() not in {"0", "false", "no"}


def tts_health_poll_sec() -> int:
    return max(30, int(os.getenv("PRESENCE_TTS_HEALTH_POLL_SEC", "60")))


async def check_tts_health_once() -> bool:
    from presence_ui.services.tts_surface import surface_tts_enabled, surface_tts_ready, surface_tts_status

    if not surface_tts_enabled():
        return True
    return surface_tts_ready()


async def _tts_health_watchdog_loop() -> None:
    global _last_ready
    interval = tts_health_poll_sec()
    logger.info("TTS health watchdog started (every %ds)", interval)
    while True:
        try:
            from presence_ui.services.tts_surface import surface_tts_status

            ready = await check_tts_health_once()
            if _last_ready is None:
                _last_ready = ready
                if not ready:
                    logger.warning("TTS not ready at startup: %s", surface_tts_status())
            elif ready != _last_ready:
                if ready:
                    logger.warning("TTS recovered: %s", surface_tts_status())
                else:
                    logger.warning("TTS became unavailable: %s", surface_tts_status())
                _last_ready = ready
        except Exception:
            logger.exception("TTS health watchdog tick failed")
        await asyncio.sleep(interval)


def start_tts_health_watchdog() -> None:
    global _watchdog_task
    if not tts_health_watchdog_enabled():
        return
    if _watchdog_task is not None and not _watchdog_task.done():
        return
    _watchdog_task = asyncio.create_task(_tts_health_watchdog_loop(), name="tts_health_watchdog")


def stop_tts_health_watchdog() -> None:
    global _watchdog_task
    if _watchdog_task is None:
        return
    _watchdog_task.cancel()
    _watchdog_task = None
