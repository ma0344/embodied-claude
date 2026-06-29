"""OL7 gateway ingest — classify, immediate close, or OL6-shaped pending_check."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from presence_ui.gateway.ol7_return_signal import (
    OpenLoopCandidate,
    classify_return_signal,
    ol7_enabled,
)
from presence_ui.gateway.ol_gate import should_run_ol_gate

if TYPE_CHECKING:
    from presence_ui.deps import PresenceStores

logger = logging.getLogger(__name__)

Ol7Route = Literal["no_op", "immediate_close", "pending_confirm"]


@dataclass(frozen=True, slots=True)
class Ol7IngestResult:
    route: Ol7Route
    closed_topics: tuple[str, ...] = ()
    pending_loop_id: str | None = None


def ol7_immediate_confidence() -> float:
    try:
        return float(os.environ.get("PRESENCE_OL7_IMMEDIATE_CONFIDENCE", "0.9"))
    except ValueError:
        return 0.9


def route_ol7_classification(
    *,
    signal: str,
    close_loop_ids: tuple[str, ...],
    confidence: float,
) -> Ol7Route:
    if signal == "none" or not close_loop_ids:
        return "no_op"
    if signal == "return_signal":
        return "pending_confirm"
    if signal == "explicit_completion" and confidence >= ol7_immediate_confidence():
        return "immediate_close"
    return "pending_confirm"


def _open_loop_candidates(stores: PresenceStores, *, person_id: str) -> list[OpenLoopCandidate]:
    loops = stores.relationship.list_open_loops(person_id=person_id, limit=20)
    candidates: list[OpenLoopCandidate] = []
    for loop in loops:
        detail = loop.detail if isinstance(loop.detail, dict) else {}
        pending = detail.get("pending_check")
        if isinstance(pending, dict) and pending.get("asked_at"):
            continue
        departure = str(detail.get("utterance") or detail.get("source_utterance") or loop.topic)
        event = detail.get("event")
        if isinstance(event, dict):
            what = event.get("what")
            if what and str(what).strip():
                departure = str(what).strip()
        candidates.append(
            OpenLoopCandidate(
                loop_id=loop.id,
                topic=loop.topic,
                departure_utterance=departure,
            )
        )
    return candidates


def _awaiting_pending_confirm(stores: PresenceStores, *, person_id: str) -> bool:
    for loop in stores.relationship.list_open_loops(person_id=person_id, limit=20):
        detail = loop.detail if isinstance(loop.detail, dict) else {}
        pending = detail.get("pending_check")
        if isinstance(pending, dict) and pending.get("asked_at"):
            return True
    return False


def apply_ol7_after_ingest(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
) -> Ol7IngestResult:
    """Sync OL7 ingest hook — call after OL-GATE / OL5 on human turns."""
    if not ol7_enabled():
        return Ol7IngestResult(route="no_op")
    stripped = (text or "").strip()
    if not stripped or not should_run_ol_gate(stripped):
        return Ol7IngestResult(route="no_op")
    if _awaiting_pending_confirm(stores, person_id=person_id):
        return Ol7IngestResult(route="no_op")

    candidates = _open_loop_candidates(stores, person_id=person_id)
    if not candidates:
        return Ol7IngestResult(route="no_op")

    classification = classify_return_signal(
        utterance=stripped,
        open_loops=candidates,
        apply_confidence_gate=False,
    )
    if classification is None:
        return Ol7IngestResult(route="no_op")

    route = route_ol7_classification(
        signal=classification.signal,
        close_loop_ids=classification.close_loop_ids,
        confidence=classification.confidence,
    )
    if route == "no_op":
        return Ol7IngestResult(route="no_op")

    loop_id = classification.close_loop_ids[0]
    summary = classification.completion_summary or ""

    if route == "immediate_close":
        closed = stores.relationship.close_open_loops_by_ids(
            person_id=person_id,
            loop_ids=list(classification.close_loop_ids[:1]),
            ts=ts,
            source_event_id=source_event_id,
            source_text=stripped,
            close_kind="ol7_completion",
        )
        return Ol7IngestResult(route="immediate_close", closed_topics=tuple(closed))

    stores.relationship.set_ol7_pending_candidate(
        loop_id=loop_id,
        person_id=person_id,
        ts=ts,
        source_utterance=stripped,
        completion_summary=summary,
    )
    return Ol7IngestResult(route="pending_confirm", pending_loop_id=loop_id)


async def try_ol7_after_ingest(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
) -> Ol7IngestResult:
    return await asyncio.to_thread(
        apply_ol7_after_ingest,
        stores,
        person_id=person_id,
        text=text,
        ts=ts,
        source_event_id=source_event_id,
    )
