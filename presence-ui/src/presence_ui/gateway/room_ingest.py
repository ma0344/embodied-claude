"""Persist room utterances to social.db (+ open loops for human turns)."""

from __future__ import annotations

import asyncio
import logging

from relationship_mcp.schemas import DismissOutcome
from social_core import utc_now

from presence_ui.deps import get_stores
from presence_ui.services.room_events import ROOM_WRITE_SOURCE

logger = logging.getLogger(__name__)


def ingest_human_turn(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
) -> tuple[str, DismissOutcome]:
    """Record human speech (sync — rule-based reminders only)."""
    return asyncio.run(
        _ingest_human_core_async(
            person_id=person_id,
            session_id=session_id,
            text=text,
            ts=ts,
            run_llm=False,
        )
    )


async def ingest_human_turn_async(
    *,
    person_id: str,
    session_id: str | None,
    text: str,
    ts: str | None = None,
) -> tuple[str, DismissOutcome]:
    """Record human speech; Phase B LLM reminder when rule parser misses."""
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
) -> tuple[str, DismissOutcome]:
    stores = get_stores()
    when = ts or utc_now()
    result = stores.social_state.ingest_social_event(
        {
            "ts": when,
            "source": ROOM_WRITE_SOURCE,
            "kind": "human_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        }
    )
    event_id = str(result.get("event_id") or "")
    outcome = DismissOutcome()
    try:
        from presence_ui.gateway.ol_gate import gw_s2_enabled

        outcome = stores.relationship.note_human_utterance_for_loops(
            person_id=person_id,
            text=text,
            ts=when,
            source_event_id=event_id,
            rule_open_loops=not gw_s2_enabled(),
        )
    except Exception:
        logger.exception("note_human_utterance_for_loops failed")
    if run_llm:
        try:
            from presence_ui.gateway.ol_gate import gw_s2_enabled, try_ol_gate_after_ingest

            if gw_s2_enabled():
                await try_ol_gate_after_ingest(
                    stores,
                    person_id=person_id,
                    text=text,
                    ts=when,
                    source_event_id=event_id,
                )
        except Exception:
            logger.exception("GW-S2 OL-GATE failed")
        try:
            from presence_ui.gateway.reminder_spec import try_create_llm_reminder_commitment

            await try_create_llm_reminder_commitment(
                stores,
                person_id=person_id,
                text=text,
                ts=when,
            )
        except Exception:
            logger.exception("LLM reminder spec failed")
    return event_id, outcome


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
    result = stores.social_state.ingest_social_event(
        {
            "ts": when,
            "source": ROOM_WRITE_SOURCE,
            "kind": "agent_utterance",
            "person_id": person_id,
            "session_id": session_id,
            "confidence": 1.0,
            "payload": {"text": text, "channel": "chat"},
        }
    )
    return str(result.get("event_id") or "")
