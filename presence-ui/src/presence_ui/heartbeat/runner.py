"""Background pulse — sleep until next_wake_at, then autonomous tick."""

from __future__ import annotations

import asyncio
import logging

from presence_ui.gateway.autonomous_tick import run_autonomous_tick
from presence_ui.heartbeat.pulse_state import load_pulse_state
from presence_ui.heartbeat.schedule import (
    mark_consolidated,
    mark_dreamed,
    pulse_runner_enabled,
    seconds_until_wake,
    should_run_consolidate_now,
    should_run_dream_now,
)

logger = logging.getLogger(__name__)

_pulse_task: asyncio.Task[None] | None = None


async def _maybe_consolidate() -> None:
    if not should_run_consolidate_now():
        return
    from presence_ui.gateway.memory_http import http_consolidate

    result = await asyncio.to_thread(http_consolidate)
    if result.get("ok"):
        mark_consolidated()
        logger.info("BIO consolidate ok: %s", result.get("stats"))
    else:
        logger.warning("BIO consolidate failed: %s", result.get("error"))


async def _maybe_dream(*, person_id: str) -> bool:
    if not should_run_dream_now():
        return False
    from presence_ui.services.stm_episode import close_open_native_episodes_before_dream

    try:
        closed = await close_open_native_episodes_before_dream(person_id=person_id)
        if closed:
            logger.info("MEM-2b pre-dream episode close: %d session(s)", len(closed))
    except Exception as exc:
        logger.warning("MEM-2b pre-dream episode close failed: %s", exc)
    from presence_ui.services.dreaming import run_dreaming_job

    result = await asyncio.to_thread(run_dreaming_job, person_id=person_id)
    if result.skipped:
        logger.info("MEM dreaming skipped: %s", result.reason)
        return False
    if result.ok:
        mark_dreamed(summary=result.digest_summary)
        if result.consolidate_ok:
            mark_consolidated()
        logger.info(
            "MEM dreaming ok remembered=%s stm_marked=%s daybook=%s",
            result.remembered_count,
            result.stm_marked,
            result.daybook_day,
        )
        return True
    return False


async def _pulse_cycle(*, person_id: str) -> None:
    from presence_ui.services.somatic_probe import run_somatic_probes, somatic_probe_enabled

    if somatic_probe_enabled():
        try:
            await run_somatic_probes()
        except Exception as exc:
            logger.warning("Somatic probe failed: %s", exc)
    dreamed = await _maybe_dream(person_id=person_id)
    if not dreamed:
        await _maybe_consolidate()
    result = await run_autonomous_tick(person_id=person_id, trigger="pulse_wake")
    logger.info(
        "BIO pulse tick ok=%s action=%s next=%s summary=%s",
        result.ok,
        result.action,
        result.next_wake_at,
        (result.summary or "")[:80],
    )


async def _pulse_loop(*, person_id: str) -> None:
    while True:
        try:
            delay = seconds_until_wake(load_pulse_state())
            if delay > 0:
                await asyncio.sleep(delay)
            await _pulse_cycle(person_id=person_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("BIO pulse loop error: %s", exc)
            await asyncio.sleep(60)


def start_pulse_runner(*, person_id: str = "ma") -> None:
    global _pulse_task
    if not pulse_runner_enabled():
        logger.info("BIO PulseRunner disabled (PRESENCE_PULSE_RUNNER=0)")
        return
    if _pulse_task is not None and not _pulse_task.done():
        return
    _pulse_task = asyncio.create_task(_pulse_loop(person_id=person_id), name="agent-pulse")
    logger.info("BIO PulseRunner started")


def stop_pulse_runner() -> None:
    global _pulse_task
    if _pulse_task is None:
        return
    _pulse_task.cancel()
    _pulse_task = None
