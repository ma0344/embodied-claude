"""GAPI-7b / GAPI-2w — calendar confirm flow orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from social_core import utc_now

from presence_ui.gapi.auth import GoogleAuthError, get_calendar_service
from presence_ui.gapi.policy import load_google_policy
from presence_ui.gateway.calendar_pending import (
    CalendarPendingRecord,
    calendar_confirm_enabled,
    clear_pending,
    format_calendar_cancel_block,
    format_calendar_confirm_block,
    format_calendar_ingest_failed_block,
    is_calendar_affirmation,
    is_calendar_denial,
    load_pending,
    pending_from_clarification,
    pending_from_resolved,
    pending_matches_utterance,
    save_pending,
)
from presence_ui.gateway.calendar_prefetch import looks_like_calendar_query
from presence_ui.gateway.calendar_stage import (
    calendar_staged_enabled,
    compute_missing_fields,
    resolve_create_draft,
    resolve_update_draft,
    run_calendar_stage2_extract,
)
from presence_ui.gateway.calendar_write import (
    calendar_write_enabled,
    execute_pending_calendar_sync,
)
from presence_ui.gateway.room_events import progress_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CalendarTurnOutcome:
    write_block: str | None = None
    confirm_block: str | None = None
    progress_events: tuple[dict[str, Any], ...] = ()


def calendar_write_staged_enabled() -> bool:
    """Stage1 calendar_write gate for chat/ingest (GAPI-2w)."""
    if not calendar_write_enabled() or not calendar_confirm_enabled():
        return False
    raw = os.getenv("PRESENCE_GAPI_CALENDAR_WRITE_STAGED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def classify_calendar_write_stage1(*, utterance: str) -> str | None:
    from presence_ui.gateway.calendar_read_flow import classify_calendar_read_stage1

    return classify_calendar_read_stage1(utterance=utterance)


def should_run_calendar_write(text: str, *, person_id: str = "ma") -> bool:
    """True when gateway should run 7b confirm flow for this utterance."""
    line = (text or "").strip()
    if not line:
        return False
    if is_calendar_affirmation(line) or is_calendar_denial(line):
        return load_pending(person_id=person_id) is not None
    if not calendar_write_staged_enabled():
        return False
    if not looks_like_calendar_query(line):
        return False
    kind = classify_calendar_write_stage1(utterance=line)
    if kind is None:
        logger.warning(
            "GAPI-2w: Stage1 unavailable for calendar cue %r — skipping write",
            line[:80],
        )
        return False
    from presence_ui.gateway.stage1_calendar import normalized_calendar_kind

    return normalized_calendar_kind(kind=kind, utterance=line) == "calendar_write"


def should_skip_ol_for_calendar(text: str, *, person_id: str = "ma") -> bool:
    return should_run_calendar_write(text, person_id=person_id)


def _progress_for_status(*, action: str, status: str) -> str:
    if status == "ok":
        return "カレンダーに入れた" if action == "create" else "予定を変更した"
    if status == "error":
        return "カレンダー操作に失敗"
    return "カレンダーを確認中"


def _clear_superseded_pending(
    *,
    person_id: str,
    utterance: str,
) -> None:
    existing = load_pending(person_id=person_id)
    if existing is None:
        return
    if not pending_matches_utterance(existing, utterance):
        clear_pending(person_id=person_id)


def process_calendar_staged_ingest(
    *,
    person_id: str,
    utterance: str,
    ts: str | None = None,
) -> CalendarPendingRecord | None:
    """Run Stage2 extract on ingest; save pending for confirm/clarify."""
    if not calendar_staged_enabled() or not calendar_confirm_enabled():
        return None
    when = ts or utc_now()
    extract = run_calendar_stage2_extract(utterance=utterance)
    if extract is None:
        _clear_superseded_pending(person_id=person_id, utterance=utterance)
        return None
    missing = list(compute_missing_fields(extract))
    policy = load_google_policy()
    if missing:
        record = pending_from_clarification(
            person_id=person_id,
            source_utterance=utterance,
            extract=extract,
            missing_fields=missing,
            created_at=when,
        )
        save_pending(record)
        return record
    try:
        service = get_calendar_service()
    except GoogleAuthError:
        _clear_superseded_pending(person_id=person_id, utterance=utterance)
        return None
    draft = None
    if extract.action == "create":
        draft = resolve_create_draft(extract, anchor_iso=when, tz_name=policy.timezone)
    else:
        draft = resolve_update_draft(
            extract,
            anchor_iso=when,
            tz_name=policy.timezone,
            service=service,
            policy=policy,
        )
    if draft is None:
        record = pending_from_clarification(
            person_id=person_id,
            source_utterance=utterance,
            extract=extract,
            missing_fields=missing or ["start_phrase", "end_phrase", "topic"],
            created_at=when,
        )
        save_pending(record)
        return record
    record = pending_from_resolved(
        person_id=person_id,
        source_utterance=utterance,
        draft=draft,
        created_at=when,
    )
    save_pending(record)
    return record


def _ingest_failed_outcome(
    *,
    utterance: str,
    events: list[dict[str, Any]],
) -> CalendarTurnOutcome:
    events.append(progress_event(phase="calendar", label="予定を読み取れなかった"))
    return CalendarTurnOutcome(
        confirm_block=format_calendar_ingest_failed_block(utterance=utterance),
        progress_events=tuple(events),
    )


def process_calendar_turn_sync(
    *,
    person_id: str,
    message: str,
) -> CalendarTurnOutcome:
    if not calendar_confirm_enabled():
        return CalendarTurnOutcome()

    text = (message or "").strip()
    if not text:
        return CalendarTurnOutcome()

    pending = load_pending(person_id=person_id)
    events: list[dict[str, Any]] = []

    if pending and is_calendar_denial(text):
        clear_pending(person_id=person_id)
        events.append(progress_event(phase="calendar", label="カレンダー操作をキャンセル"))
        return CalendarTurnOutcome(
            confirm_block=format_calendar_cancel_block(),
            progress_events=tuple(events),
        )

    if pending and pending.status == "awaiting_confirm" and is_calendar_affirmation(text):
        if not pending.start_iso or not pending.end_iso:
            clear_pending(person_id=person_id)
            events.append(progress_event(phase="calendar", label="カレンダー操作に失敗"))
            return _ingest_failed_outcome(utterance=pending.source_utterance, events=events)
        block, status = execute_pending_calendar_sync(pending)
        clear_pending(person_id=person_id)
        label = _progress_for_status(action=pending.action, status=status)
        events.append(progress_event(phase="calendar", label=label))
        return CalendarTurnOutcome(write_block=block, progress_events=tuple(events))

    pending = load_pending(person_id=person_id)
    is_calendar_op = should_run_calendar_write(text, person_id=person_id)
    if pending and pending.status in {"awaiting_confirm", "needs_clarification"}:
        if is_calendar_op:
            when = utc_now()
            new_record = process_calendar_staged_ingest(
                person_id=person_id, utterance=text, ts=when
            )
            if new_record:
                events.append(progress_event(phase="calendar", label="予定を読み直した"))
                return CalendarTurnOutcome(
                    confirm_block=format_calendar_confirm_block(new_record),
                    progress_events=tuple(events),
                )
            if not pending_matches_utterance(pending, text):
                clear_pending(person_id=person_id)
                return _ingest_failed_outcome(utterance=text, events=events)
        if pending.status == "awaiting_confirm" and pending_matches_utterance(pending, text):
            events.append(progress_event(phase="calendar", label="カレンダー入れの確認"))
            return CalendarTurnOutcome(
                confirm_block=format_calendar_confirm_block(pending),
                progress_events=tuple(events),
            )
        if pending.status == "awaiting_confirm":
            events.append(progress_event(phase="calendar", label="確認待ち"))
            return CalendarTurnOutcome(
                confirm_block=format_calendar_confirm_block(pending),
                progress_events=tuple(events),
            )

    if is_calendar_op:
        pending = load_pending(person_id=person_id)
        if pending and pending.source_utterance.strip() == text:
            label = (
                "足りない情報を確認"
                if pending.status == "needs_clarification"
                else "カレンダー入れの確認"
            )
            events.append(progress_event(phase="calendar", label=label))
            return CalendarTurnOutcome(
                confirm_block=format_calendar_confirm_block(pending),
                progress_events=tuple(events),
            )
        when = utc_now()
        record = process_calendar_staged_ingest(
            person_id=person_id,
            utterance=text,
            ts=when,
        )
        if record:
            label = (
                "足りない情報を確認"
                if record.status == "needs_clarification"
                else "カレンダー入れの確認"
            )
            events.append(progress_event(phase="calendar", label=label))
            return CalendarTurnOutcome(
                confirm_block=format_calendar_confirm_block(record),
                progress_events=tuple(events),
            )
        return _ingest_failed_outcome(utterance=text, events=events)

    return CalendarTurnOutcome()


async def process_calendar_turn(
    *,
    person_id: str,
    message: str,
) -> CalendarTurnOutcome:
    return await asyncio.to_thread(
        process_calendar_turn_sync,
        person_id=person_id,
        message=message,
    )
