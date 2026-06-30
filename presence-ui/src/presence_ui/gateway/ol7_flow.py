"""OL7 gateway ingest — classify, immediate close, or OL6-shaped pending_check."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from social_core.activity_frame import (
    activity_gloss,
    build_activity_frame_from_detail,
    build_completion_frame,
    frames_match_completion,
    is_action_only_close,
)

from presence_ui.gateway.ol7_return_signal import (
    OpenLoopCandidate,
    activity_label_for_loop,
    classify_return_signal,
    ol7_enabled,
    resolve_ol7_loop_ids,
    should_run_ol7_classifier,
)
from presence_ui.gateway.ol_gate import gw_s2_enabled, should_run_ol_gate

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
        activity = activity_label_for_loop(
            topic=loop.topic,
            departure=departure,
            detail=detail if isinstance(detail, dict) else None,
        )
        frame = build_activity_frame_from_detail(detail if isinstance(detail, dict) else {})
        gloss = activity_gloss(frame) if frame else activity
        candidates.append(
            OpenLoopCandidate(
                loop_id=loop.id,
                topic=loop.topic,
                departure_utterance=departure,
                activity_label=activity,
                activity_frame=frame,
                frame_gloss=gloss,
            )
        )
    return candidates


def _frame_matched_candidates(
    *,
    candidates: list[OpenLoopCandidate],
    utterance: str,
    object_phrase: str | None,
    action_phrase: str | None,
) -> list[OpenLoopCandidate]:
    close_frame = build_completion_frame(
        object_phrase=object_phrase,
        action_phrase=action_phrase,
        utterance=utterance,
    )
    matched: list[OpenLoopCandidate] = []
    for cand in candidates:
        if cand.activity_frame is None:
            continue
        if frames_match_completion(
            cand.activity_frame,
            close_frame,
            utterance=utterance,
            close_action_phrase=action_phrase,
        ):
            matched.append(cand)
    return matched


def _departure_candidates(candidates: list[OpenLoopCandidate]) -> list[OpenLoopCandidate]:
    return [
        cand
        for cand in candidates
        if cand.activity_frame is not None and cand.activity_frame.mode == "departure"
    ]


def _unscoped_departure_candidates(
    *,
    candidates: list[OpenLoopCandidate],
    utterance_kind: str | None,
    close_shape: str | None,
    object_phrase: str | None,
    action_phrase: str | None,
) -> list[OpenLoopCandidate]:
    if not is_action_only_close(
        utterance_kind=utterance_kind,
        close_shape=close_shape,
        object_phrase=object_phrase,
        action_phrase=action_phrase,
    ):
        return []
    return _departure_candidates(candidates)


def _pick_unscoped_departure_close(
    unscoped: list[OpenLoopCandidate],
) -> OpenLoopCandidate | None:
    """Unscoped past_completion closes only when exactly one departure loop is open."""
    if len(unscoped) == 1:
        return unscoped[0]
    return None


def _immediate_close_loop(
    stores: PresenceStores,
    *,
    person_id: str,
    loop_id: str,
    ts: str,
    source_event_id: str,
    source_text: str,
) -> Ol7IngestResult:
    closed = stores.relationship.close_open_loops_by_ids(
        person_id=person_id,
        loop_ids=[loop_id],
        ts=ts,
        source_event_id=source_event_id,
        source_text=source_text,
        close_kind="ol7_completion",
    )
    return Ol7IngestResult(route="immediate_close", closed_topics=tuple(closed))


def apply_ol7_after_ingest(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
    utterance_kind: str | None = None,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
    close_shape: str | None = None,
) -> Ol7IngestResult:
    """Sync OL7 ingest hook — call after OL-GATE / OL5 on human turns."""
    if not ol7_enabled():
        logger.info("OL7 skip: PRESENCE_OL7_ENABLED is off (process env=%r)", os.environ.get("PRESENCE_OL7_ENABLED"))
        return Ol7IngestResult(route="no_op")
    stripped = (text or "").strip()
    if not stripped or not should_run_ol_gate(stripped):
        logger.info("OL7 skip: gate filter utterance=%r", stripped[:60])
        return Ol7IngestResult(route="no_op")

    gw_s2_active = gw_s2_enabled()
    if not should_run_ol7_classifier(
        utterance_kind=utterance_kind,
        gw_s2_active=gw_s2_active,
    ):
        logger.info(
            "OL7 skip: Stage1 kind=%s not eligible (gw_s2=%s) utterance=%r",
            utterance_kind,
            gw_s2_active,
            stripped[:60],
        )
        return Ol7IngestResult(route="no_op")

    candidates = _open_loop_candidates(stores, person_id=person_id)
    if not candidates:
        logger.info(
            "OL7 skip: no open loop candidates person=%s (open loops may all have asked_at)",
            person_id,
        )
        return Ol7IngestResult(route="no_op")

    if utterance_kind == "past_completion":
        frame_hits = _frame_matched_candidates(
            candidates=candidates,
            utterance=stripped,
            object_phrase=object_phrase,
            action_phrase=action_phrase,
        )
        if len(frame_hits) == 1:
            return _immediate_close_loop(
                stores,
                person_id=person_id,
                loop_id=frame_hits[0].loop_id,
                ts=ts,
                source_event_id=source_event_id,
                source_text=stripped,
            )
        if len(frame_hits) > 1:
            logger.info(
                "OL7 frame match: ambiguous hits=%s — defer to classifier/pending",
                [c.loop_id for c in frame_hits],
            )
        else:
            unscoped = _unscoped_departure_candidates(
                candidates=candidates,
                utterance_kind=utterance_kind,
                close_shape=close_shape,
                object_phrase=object_phrase,
                action_phrase=action_phrase,
            )
            picked = _pick_unscoped_departure_close(unscoped)
            if picked is not None:
                loop_id = picked.loop_id
                logger.info(
                    "OL7 unscoped past_completion + departure loop_id=%s "
                    "action=%r utterance=%r hits=%s",
                    loop_id,
                    action_phrase,
                    stripped[:60],
                    [c.loop_id for c in unscoped],
                )
                return _immediate_close_loop(
                    stores,
                    person_id=person_id,
                    loop_id=loop_id,
                    ts=ts,
                    source_event_id=source_event_id,
                    source_text=stripped,
                )
            if len(unscoped) > 1:
                logger.info(
                    "OL7 unscoped past_completion: ambiguous departure hits=%s",
                    [c.loop_id for c in unscoped],
                )

    logger.info(
        "OL7 classify start: utterance=%r candidate_loops=%s",
        stripped[:80],
        [c.loop_id for c in candidates],
    )

    classification = classify_return_signal(
        utterance=stripped,
        open_loops=candidates,
        utterance_kind=utterance_kind,
        object_phrase=object_phrase,
        action_phrase=action_phrase,
        close_shape=close_shape,
        apply_confidence_gate=False,
    )
    if classification is None:
        logger.warning(
            "OL7 classifier returned None (e4b down or parse fail) utterance=%r",
            stripped[:80],
        )
        return Ol7IngestResult(route="no_op")

    classification = resolve_ol7_loop_ids(
        classification,
        utterance=stripped,
        open_loops=candidates,
        utterance_kind=utterance_kind,
        object_phrase=object_phrase,
        action_phrase=action_phrase,
        close_shape=close_shape,
    )

    route = route_ol7_classification(
        signal=classification.signal,
        close_loop_ids=classification.close_loop_ids,
        confidence=classification.confidence,
    )
    logger.info(
        "OL7 classify: signal=%s route=%s loop_ids=%s confidence=%.2f reason=%s utterance=%r",
        classification.signal,
        route,
        list(classification.close_loop_ids),
        classification.confidence,
        classification.reason[:80],
        stripped[:80],
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
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
    utterance_kind: str | None = None,
    object_phrase: str | None = None,
    action_phrase: str | None = None,
    close_shape: str | None = None,
) -> Ol7IngestResult:
    """Run OL7 ingest hook off the event loop (LLM + DB).

    Must call ``get_stores()`` inside the worker thread — ``SocialDB`` is not
    portable across threads (see ``presence_ui.deps``).
    """

    def _run() -> Ol7IngestResult:
        from presence_ui.deps import get_stores

        return apply_ol7_after_ingest(
            get_stores(),
            person_id=person_id,
            text=text,
            ts=ts,
            source_event_id=source_event_id,
            utterance_kind=utterance_kind,
            object_phrase=object_phrase,
            action_phrase=action_phrase,
            close_shape=close_shape,
        )

    return await asyncio.to_thread(_run)
