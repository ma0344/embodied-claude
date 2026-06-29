"""GAPI-7b — e4b calendar Stage2 extract + resolve."""

from __future__ import annotations

import os
from dataclasses import dataclass

from presence_ui.gateway.calendar_resolve import (
    ResolvedRange,
    resolve_start_end_phrases,
)
from presence_ui.gateway.calendar_stage_prompts import (
    CALENDAR_STAGE2_SYSTEM,
    build_calendar_stage2_task,
)
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object


@dataclass(frozen=True, slots=True)
class CalendarStageExtract:
    action: str
    calendar_id: str
    topic: str | None
    start_phrase: str | None
    end_phrase: str | None
    match_start_phrase: str | None
    match_topic: str | None
    missing_fields: tuple[str, ...]
    confidence: float | None


@dataclass(frozen=True, slots=True)
class CalendarResolvedDraft:
    action: str
    calendar_id: str
    topic: str | None
    range: ResolvedRange
    match_label: str = ""
    event_id: str | None = None
    event_calendar_id: str | None = None
    event_summary: str | None = None
    old_start: str | None = None
    old_end: str | None = None


def calendar_staged_enabled() -> bool:
    from presence_ui.gateway.calendar_write import calendar_write_enabled

    if not calendar_write_enabled():
        return False
    raw = os.getenv("PRESENCE_GAPI_CALENDAR_STAGED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _nullable(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def _missing_list(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def parse_calendar_stage2_response(text: str) -> CalendarStageExtract | None:
    data = _extract_json_object(text)
    if not data:
        return None
    action = str(data.get("action") or "").strip().lower()
    if action not in {"create", "update"}:
        return None
    calendar_id = _nullable(data.get("calendar_id")) or "primary"
    conf_raw = data.get("confidence")
    confidence: float | None
    try:
        confidence = float(conf_raw) if conf_raw is not None else None
    except (TypeError, ValueError):
        confidence = None
    return CalendarStageExtract(
        action=action,
        calendar_id=calendar_id,
        topic=_nullable(data.get("topic")),
        start_phrase=_nullable(data.get("start_phrase")),
        end_phrase=_nullable(data.get("end_phrase")),
        match_start_phrase=_nullable(data.get("match_start_phrase")),
        match_topic=_nullable(data.get("match_topic")),
        missing_fields=_missing_list(data.get("missing_fields")),
        confidence=confidence,
    )


def run_calendar_stage2_extract(*, utterance: str) -> CalendarStageExtract | None:
    raw = run_classifier_turn(
        system=CALENDAR_STAGE2_SYSTEM,
        user=build_calendar_stage2_task(utterance=utterance),
        max_tokens=int(os.getenv("PRESENCE_GAPI_CALENDAR_STAGE2_MAX_TOKENS", "512")),
        log_label="GAPI-7b calendar Stage2",
    )
    if not raw:
        return None
    return parse_calendar_stage2_response(raw)


def compute_missing_fields(extract: CalendarStageExtract) -> tuple[str, ...]:
    missing = list(extract.missing_fields)
    if extract.action == "create":
        if not extract.topic and "topic" not in missing:
            missing.append("topic")
        if not extract.start_phrase and "start_phrase" not in missing:
            missing.append("start_phrase")
    elif extract.action == "update":
        if not extract.match_start_phrase and "match_start_phrase" not in missing:
            missing.append("match_start_phrase")
        if not extract.start_phrase and "start_phrase" not in missing:
            missing.append("start_phrase")
    return tuple(dict.fromkeys(missing))


def resolve_create_draft(
    extract: CalendarStageExtract,
    *,
    anchor_iso: str,
    tz_name: str,
) -> CalendarResolvedDraft | None:
    missing = compute_missing_fields(extract)
    if missing:
        return None
    resolved = resolve_start_end_phrases(
        start_phrase=extract.start_phrase,
        end_phrase=extract.end_phrase,
        anchor_iso=anchor_iso,
        tz_name=tz_name,
    )
    if resolved is None:
        return None
    return CalendarResolvedDraft(
        action="create",
        calendar_id=extract.calendar_id,
        topic=extract.topic,
        range=resolved,
    )


def resolve_update_draft(
    extract: CalendarStageExtract,
    *,
    anchor_iso: str,
    tz_name: str,
    service: object,
    policy: object,
) -> CalendarResolvedDraft | None:
    from presence_ui.gapi.calendar_client import (
        list_events_for_day,
        match_event_by_local_start,
    )
    from presence_ui.gapi.policy import GooglePolicy

    missing = compute_missing_fields(extract)
    if missing:
        return None
    assert isinstance(policy, GooglePolicy)
    match_day = resolve_start_end_phrases(
        start_phrase=extract.match_start_phrase,
        end_phrase=None,
        anchor_iso=anchor_iso,
        tz_name=tz_name,
    )
    if match_day is None:
        return None
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(tz_name)
    events = list_events_for_day(service, policy, day=match_day.day)
    matched = match_event_by_local_start(
        events,
        target_day=match_day.day,
        hour=match_day.start.hour,
        minute=match_day.start.minute,
        tz=zone,
    )
    if matched is None and extract.match_topic:
        for event in events:
            if extract.match_topic in (event.summary or ""):
                matched = event
                break
    if matched is None:
        return None
    new_range = resolve_start_end_phrases(
        start_phrase=extract.start_phrase,
        end_phrase=extract.end_phrase,
        anchor_iso=anchor_iso,
        tz_name=tz_name,
    )
    if new_range is None:
        return None
    match_label = matched.summary or extract.match_topic or extract.match_start_phrase or ""
    return CalendarResolvedDraft(
        action="update",
        calendar_id=extract.calendar_id,
        topic=matched.summary,
        range=new_range,
        match_label=match_label,
        event_id=matched.event_id,
        event_calendar_id=matched.calendar_id,
        event_summary=matched.summary,
        old_start=matched.start,
        old_end=matched.end,
    )
