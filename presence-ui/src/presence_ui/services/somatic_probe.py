"""Lightweight somatic probes on pulse wake (BIO-8b)."""

from __future__ import annotations

import logging
import os

from presence_ui.services.body_state import (
    BodyState,
    load_body_state,
    note_organ_probe,
    save_body_state,
)

logger = logging.getLogger(__name__)


def somatic_probe_enabled() -> bool:
    return os.getenv("PRESENCE_SOMATIC_PROBE", "1").lower() not in {"0", "false", "no"}


def somatic_probe_eyes_capture() -> bool:
    return os.getenv("PRESENCE_SOMATIC_PROBE_EYES_CAPTURE", "0").lower() in {
        "1",
        "true",
        "yes",
    }


async def probe_eyes() -> tuple[str, str | None]:
    from presence_ui.services.camera import camera_failure_hint, capture_for_mode

    hint = camera_failure_hint()
    if hint:
        return "failed", hint
    if not somatic_probe_eyes_capture():
        return "ok", None
    try:
        outcome = await capture_for_mode("current", save_to_file=False)
        if outcome.ok and outcome.capture:
            return "ok", None
        return "failed", (outcome.error or "capture failed")[:200]
    except Exception as exc:
        return "failed", str(exc)[:200]


async def probe_voice() -> tuple[str, str | None]:
    from presence_ui.gateway.tts_health_watchdog import check_tts_health_once
    from presence_ui.services.tts_surface import surface_tts_enabled, surface_tts_status

    if not surface_tts_enabled():
        return "ok", None
    try:
        ready = await check_tts_health_once()
        if ready:
            return "ok", None
        return "degraded", surface_tts_status()[:200]
    except Exception as exc:
        return "degraded", str(exc)[:200]


def probe_mind_sync() -> tuple[str, str | None]:
    from presence_ui.gateway.memory_http import http_memory_health

    result = http_memory_health(timeout_sec=2.0)
    if result.get("ok"):
        return "ok", None
    return "failed", str(result.get("error") or "memory health failed")[:200]


async def run_somatic_probes() -> BodyState:
    """Update body_state from lightweight organ probes."""
    import asyncio

    state = load_body_state()
    eyes_status, eyes_summary = await probe_eyes()
    note_organ_probe(state, organ="eyes", status=eyes_status, summary=eyes_summary)  # type: ignore[arg-type]
    voice_status, voice_summary = await probe_voice()
    note_organ_probe(state, organ="voice", status=voice_status, summary=voice_summary)  # type: ignore[arg-type]
    mind_status, mind_summary = await asyncio.to_thread(probe_mind_sync)
    note_organ_probe(state, organ="mind", status=mind_status, summary=mind_summary)  # type: ignore[arg-type]
    for organ, status, summary in (
        ("eyes", eyes_status, eyes_summary),
        ("voice", voice_status, voice_summary),
        ("mind", mind_status, mind_summary),
    ):
        if summary and status != "ok":
            logger.info("Somatic probe %s: %s — %s", organ, status, summary[:80])
    save_body_state(state)
    from presence_ui.deps import get_stores
    from presence_ui.services.somatic_escalation import maybe_escalate_somatic

    maybe_escalate_somatic(get_stores())
    return state
