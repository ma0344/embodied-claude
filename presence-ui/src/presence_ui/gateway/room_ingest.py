"""Persist room utterances to social.db (+ open loops for human turns)."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass

from relationship_mcp.schemas import DismissOutcome
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.gateway.ingest_hooks import IngestHookFailure, record_ingest_hook_failure
from presence_ui.gateway.ol7_flow import Ol7IngestResult
from presence_ui.services.room_events import ROOM_WRITE_SOURCE

logger = logging.getLogger(__name__)

_INGEST_LOCK_RETRIES = 5


@dataclass(frozen=True, slots=True)
class HumanIngestResult:
    event_id: str
    dismiss_outcome: DismissOutcome
    ol7: Ol7IngestResult
    hook_failures: tuple[IngestHookFailure, ...] = ()


def _ingest_social_event_with_retry(stores, event: dict) -> dict:
    """Retry transient SQLITE_BUSY while kiosk/chat contend on social.db."""
    last_exc: sqlite3.OperationalError | None = None
    for attempt in range(_INGEST_LOCK_RETRIES):
        try:
            return stores.social_state.ingest_social_event(event)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            if attempt + 1 >= _INGEST_LOCK_RETRIES:
                break
            time.sleep(0.05 * (2**attempt))
    assert last_exc is not None
    raise last_exc


def ingest_human_turn(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
    run_llm: bool = False,
) -> HumanIngestResult:
    """Record human speech. Set ``run_llm=True`` for GW-S2 / OL7 ingest hooks."""
    return asyncio.run(
        _ingest_human_core_async(
            person_id=person_id,
            session_id=session_id,
            text=text,
            ts=ts,
            run_llm=run_llm,
        )
    )


async def ingest_human_turn_async(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
) -> HumanIngestResult:
    """Record human speech; GW-S2 / OL7 when enabled."""
    return await _ingest_human_core_async(
        person_id=person_id,
        session_id=session_id,
        text=text,
        ts=ts,
        run_llm=True,
    )


async def _ingest_human_core_async(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None,
    run_llm: bool,
) -> HumanIngestResult:
    stores = get_stores()
    when = ts or utc_now()
    result = _ingest_social_event_with_retry(
        stores,
        {
            "ts": when,
            "source": ROOM_WRITE_SOURCE,
            "kind": "human_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        },
    )
    event_id = str(result.get("event_id") or "")
    outcome = DismissOutcome()
    ol7_result = Ol7IngestResult(route="no_op")
    hook_failures: list[IngestHookFailure] = []
    utterance_kind: str | None = None
    object_phrase: str | None = None
    action_phrase: str | None = None
    close_shape: str | None = None
    try:
        from presence_ui.gateway.ol_gate import gw_s2_enabled

        outcome = stores.relationship.note_human_utterance_for_loops(
            person_id=person_id,
            text=text,
            ts=when,
            source_event_id=event_id,
            rule_open_loops=not gw_s2_enabled(),
        )
    except Exception as exc:
        hook_failures.append(record_ingest_hook_failure("note_human_utterance_for_loops", exc))
    if run_llm:
        try:
            from presence_ui.gateway.ol_gate import gw_s2_enabled, try_ol_gate_after_ingest

            if gw_s2_enabled():
                gate_decision = await try_ol_gate_after_ingest(
                    stores,
                    person_id=person_id,
                    text=text,
                    ts=when,
                    source_event_id=event_id,
                )
                if gate_decision is not None:
                    utterance_kind = gate_decision.utterance_kind
                    detail = gate_decision.detail if isinstance(gate_decision.detail, dict) else {}
                    object_phrase = str(detail.get("object_phrase") or "").strip() or None
                    action_phrase = str(detail.get("action_phrase") or "").strip() or None
                    close_shape = str(detail.get("close_shape") or "").strip() or None
        except Exception as exc:
            hook_failures.append(record_ingest_hook_failure("gw_s2_ol_gate", exc))
        try:
            from presence_ui.gateway.ol7_flow import ol7_enabled, try_ol7_after_ingest

            if ol7_enabled():
                ol7_result = await try_ol7_after_ingest(
                    person_id=person_id,
                    text=text,
                    ts=when,
                    source_event_id=event_id,
                    utterance_kind=utterance_kind,
                    object_phrase=object_phrase,
                    action_phrase=action_phrase,
                    close_shape=close_shape,
                )
                if ol7_result.closed_topics:
                    outcome = outcome.model_copy(
                        update={
                            "closed_loops": [
                                *outcome.closed_loops,
                                *ol7_result.closed_topics,
                            ]
                        }
                    )
                logger.info(
                    "OL7 ingest: route=%s closed=%s pending_loop=%s utterance=%r",
                    ol7_result.route,
                    list(ol7_result.closed_topics),
                    ol7_result.pending_loop_id,
                    text[:80],
                )
            else:
                logger.info(
                    "OL7 ingest: skipped (PRESENCE_OL7_ENABLED=%r)",
                    os.environ.get("PRESENCE_OL7_ENABLED"),
                )
        except Exception as exc:
            hook_failures.append(record_ingest_hook_failure("ol7_return_signal", exc))
        try:
            from presence_ui.gateway.reminder_spec import try_create_llm_reminder_commitment

            await try_create_llm_reminder_commitment(
                stores,
                person_id=person_id,
                text=text,
                ts=when,
            )
        except Exception as exc:
            hook_failures.append(record_ingest_hook_failure("llm_reminder_spec", exc))
    try:
        from presence_ui.gateway.user_action_meal import (
            try_encode_user_action_meal,
            user_actions_meal_enabled,
        )

        if user_actions_meal_enabled() and person_id.strip().lower() == "ma":
            meal = try_encode_user_action_meal(
                stores.relationship,
                person_id=person_id,
                text=text,
                ts=when,
                source_event_id=event_id,
            )
            if meal.route != "none":
                logger.info(
                    "UserAction meal: route=%s object=%s action_id=%s utterance=%r",
                    meal.route,
                    meal.object,
                    meal.action_id,
                    text[:80],
                )
    except Exception as exc:
        hook_failures.append(record_ingest_hook_failure("user_action_meal", exc))
    return HumanIngestResult(
        event_id=event_id,
        dismiss_outcome=outcome,
        ol7=ol7_result,
        hook_failures=tuple(hook_failures),
    )


def ingest_agent_turn(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
) -> str:
    """Record Koyori's spoken reply (no open-loop inference on agent text)."""

    stores = get_stores()
    when = ts or utc_now()
    result = _ingest_social_event_with_retry(
        stores,
        {
            "ts": when,
            "source": ROOM_WRITE_SOURCE,
            "kind": "agent_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        },
    )
    return str(result.get("event_id") or "")
