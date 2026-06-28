"""TEMP-C3 — staged utterance classification (Stage 1 kind gate → Stage 2 events[])."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace

from presence_ui.deps import PresenceStores
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object
from presence_ui.gateway.ol_gate import (
    OlGateGatewayDecision,
    OlGateParsed,
    merge_ol_gate_gateway,
)
from presence_ui.gateway.ol_gate_prompts import (
    TEMP_C_STAGE1_SYSTEM,
    TEMP_C_STAGE2_SYSTEM,
    build_temp_c_stage1_task,
    build_temp_c_stage2_task,
)

logger = logging.getLogger(__name__)

STAGE1_KINDS = frozenset(
    {"future_commitment", "past_completion", "past_report", "greeting", "other"}
)
STAGE2_KINDS = frozenset({"future_commitment", "past_completion", "past_report"})
MAX_EVENTS = 4


def gw_s2_staged_enabled() -> bool:
    flag = os.environ.get("PRESENCE_GW_S2_STAGED", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _stage1_max_tokens() -> int:
    return int(os.environ.get("PRESENCE_TEMP_C_STAGE1_MAX_TOKENS", "420"))


def _stage2_max_tokens() -> int:
    return int(os.environ.get("PRESENCE_TEMP_C_STAGE2_MAX_TOKENS", "768"))


def _nullable_field(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


@dataclass(frozen=True, slots=True)
class StagedEvent:
    index: int
    what: str
    when_phrase: str | None = None
    until_phrase: str | None = None
    after_phrase: str | None = None
    lag_phrase: str | None = None
    action_phrase: str | None = None
    certainty: str | None = None
    depends_on: int | None = None
    effective_when_phrase: str | None = None


@dataclass(frozen=True, slots=True)
class StagedClassifyResult:
    utterance: str
    stage1: OlGateParsed
    commitment_strength: str | None
    events: tuple[StagedEvent, ...]


def parse_stage1_response(text: str, *, fallback_utterance: str = "") -> OlGateParsed | None:
    data = _extract_json_object(text)
    if not data:
        return None
    kind = str(data.get("utterance_kind") or "other").strip()
    if kind not in STAGE1_KINDS:
        kind = "other"
    raw_utterance = str(data.get("utterance") or fallback_utterance).strip()
    utterance = raw_utterance or fallback_utterance.strip()
    if not utterance:
        return None
    temporal = _nullable_field(data.get("temporal_phrase"))
    inferred = _nullable_field(data.get("inferred_temporal_phrase"))
    action_terms: tuple[str, ...] = ()
    raw_terms = data.get("action_terms")
    if isinstance(raw_terms, list):
        action_terms = tuple(str(t).strip() for t in raw_terms if str(t).strip())[:5]
    completion_verbs: tuple[str, ...] = ()
    raw_verbs = data.get("completion_verbs")
    if isinstance(raw_verbs, list):
        completion_verbs = tuple(str(v).strip() for v in raw_verbs if str(v).strip())[:5]
    return OlGateParsed(
        utterance=utterance,
        utterance_kind=kind,
        temporal_phrase=temporal,
        inferred_temporal_phrase=inferred,
        temporal_source=_nullable_field(data.get("temporal_source")),
        object_phrase=_nullable_field(data.get("object_phrase")),
        action_phrase=_nullable_field(data.get("action_phrase")),
        action_terms=action_terms,
        completion_verbs=completion_verbs,
        ineligibility_reason=_nullable_field(data.get("ineligibility_reason")),
    )


def _parse_event(raw: object, *, fallback_index: int) -> StagedEvent | None:
    if not isinstance(raw, dict):
        return None
    what = str(raw.get("what") or "").strip()
    if not what:
        return None
    index_raw = raw.get("index", fallback_index)
    try:
        index = int(index_raw)
    except (TypeError, ValueError):
        index = fallback_index
    depends_raw = raw.get("depends_on")
    depends_on: int | None
    if depends_raw is None or str(depends_raw).strip().lower() == "null":
        depends_on = None
    else:
        try:
            depends_on = int(depends_raw)
        except (TypeError, ValueError):
            depends_on = None
    return StagedEvent(
        index=index,
        what=what,
        when_phrase=_nullable_field(raw.get("when_phrase")),
        until_phrase=_nullable_field(raw.get("until_phrase")),
        after_phrase=_nullable_field(raw.get("after_phrase")),
        lag_phrase=_nullable_field(raw.get("lag_phrase")),
        action_phrase=_nullable_field(raw.get("action_phrase")),
        certainty=_nullable_field(raw.get("certainty")),
        depends_on=depends_on,
    )


def parse_stage2_response(
    text: str,
    *,
    fallback_utterance: str,
    utterance_kind: str,
) -> tuple[str | None, tuple[StagedEvent, ...]]:
    data = _extract_json_object(text)
    if not data:
        return None, ()
    strength = _nullable_field(data.get("commitment_strength"))
    events_raw = data.get("events")
    if not isinstance(events_raw, list):
        return strength, ()
    events: list[StagedEvent] = []
    for idx, item in enumerate(events_raw[:MAX_EVENTS]):
        event = _parse_event(item, fallback_index=idx)
        if event is not None:
            events.append(event)
    return strength, tuple(inherit_when_phrases(events))


def inherit_when_phrases(events: list[StagedEvent]) -> list[StagedEvent]:
    """G6 — child event inherits when_phrase from depends_on parent."""
    by_index = {event.index: event for event in events}
    out: list[StagedEvent] = []
    for event in events:
        effective = event.when_phrase
        if effective is None and event.depends_on is not None:
            parent = by_index.get(event.depends_on)
            if parent is not None:
                effective = parent.when_phrase or parent.effective_when_phrase
        out.append(replace(event, effective_when_phrase=effective))
    return out


def should_run_stage2(stage1: OlGateParsed) -> bool:
    """G1 — greeting / other must not call Stage 2."""
    return stage1.utterance_kind in STAGE2_KINDS


def event_to_topic(event: StagedEvent) -> str:
    """Build loop / anchor topic from one event."""
    parts: list[str] = []
    when = event.effective_when_phrase or event.when_phrase
    if when:
        parts.append(when)
    parts.append(event.what)
    if event.until_phrase:
        parts.append(event.until_phrase)
    if event.after_phrase:
        parts.append(event.after_phrase)
    if event.lag_phrase:
        parts.append(event.lag_phrase)
    if event.action_phrase:
        parts.append(event.action_phrase)
    return " ".join(parts).strip() or event.what


def event_to_parsed(
    *,
    utterance: str,
    utterance_kind: str,
    event: StagedEvent,
) -> OlGateParsed:
    temporal = event.effective_when_phrase or event.when_phrase
    temporal_source = "explicit" if temporal else None
    action = event.action_phrase
    completion_verbs: tuple[str, ...] = ()
    if utterance_kind == "past_completion" and action:
        completion_verbs = (action,)
    action_terms = (event.what,) if event.what else ()
    return OlGateParsed(
        utterance=event_to_topic(event) or utterance,
        utterance_kind=utterance_kind,
        temporal_phrase=temporal,
        inferred_temporal_phrase=None,
        temporal_source=temporal_source,
        object_phrase=event.what,
        action_phrase=action,
        action_terms=action_terms,
        completion_verbs=completion_verbs,
        ineligibility_reason=None,
    )


def should_create_loop_for_event(
    *,
    utterance_kind: str,
    event: StagedEvent,
) -> bool:
    """POC policy — OL for actionable future events (e.g. 角煮), skip duration-only blocks."""
    if utterance_kind != "future_commitment":
        return False
    return bool(event.action_phrase)


def run_staged_classify(*, utterance: str) -> StagedClassifyResult | None:
    """Stage 1 → optional Stage 2 with guards (G1–G4)."""
    raw1 = run_classifier_turn(
        system=TEMP_C_STAGE1_SYSTEM,
        user=build_temp_c_stage1_task(utterance=utterance),
        max_tokens=_stage1_max_tokens(),
        log_label="TEMP-C Stage1",
    )
    stage1 = parse_stage1_response(raw1 or "", fallback_utterance=utterance)
    if stage1 is None:
        return None

    if not should_run_stage2(stage1):
        return StagedClassifyResult(
            utterance=utterance,
            stage1=stage1,
            commitment_strength=None,
            events=(),
        )

    raw2 = run_classifier_turn(
        system=TEMP_C_STAGE2_SYSTEM,
        user=build_temp_c_stage2_task(utterance=utterance, utterance_kind=stage1.utterance_kind),
        max_tokens=_stage2_max_tokens(),
        log_label="TEMP-C Stage2",
    )
    strength, events = parse_stage2_response(
        raw2 or "",
        fallback_utterance=utterance,
        utterance_kind=stage1.utterance_kind,
    )
    if not events:
        return StagedClassifyResult(
            utterance=utterance,
            stage1=stage1,
            commitment_strength=strength,
            events=(),
        )
    return StagedClassifyResult(
        utterance=utterance,
        stage1=stage1,
        commitment_strength=strength,
        events=events,
    )


def staged_to_gateway_decisions(
    result: StagedClassifyResult,
    *,
    ts: str,
    timezone: str,
) -> list[OlGateGatewayDecision]:
    kind = result.stage1.utterance_kind
    if kind in {"greeting", "other"}:
        return [merge_ol_gate_gateway(result.stage1, ts=ts, timezone=timezone)]

    if not result.events:
        return [merge_ol_gate_gateway(result.stage1, ts=ts, timezone=timezone)]

    decisions: list[OlGateGatewayDecision] = []
    for event in result.events:
        parsed = event_to_parsed(
            utterance=result.utterance,
            utterance_kind=kind,
            event=event,
        )
        decision = merge_ol_gate_gateway(parsed, ts=ts, timezone=timezone)
        if kind == "future_commitment" and not should_create_loop_for_event(
            utterance_kind=kind, event=event
        ):
            decision = replace(
                decision,
                create_open_loop=False,
                loop_topic="",
            )
        detail = dict(decision.detail)
        detail["temp_c"] = True
        detail["commitment_strength"] = result.commitment_strength
        detail["event_index"] = event.index
        detail["event"] = {
            "what": event.what,
            "when_phrase": event.when_phrase,
            "effective_when_phrase": event.effective_when_phrase,
            "until_phrase": event.until_phrase,
            "after_phrase": event.after_phrase,
            "lag_phrase": event.lag_phrase,
            "action_phrase": event.action_phrase,
            "certainty": event.certainty,
            "depends_on": event.depends_on,
        }
        decisions.append(replace(decision, detail=detail))
    return decisions


def apply_staged_decisions(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
    result: StagedClassifyResult,
    timezone: str,
) -> list[OlGateGatewayDecision]:
    decisions = staged_to_gateway_decisions(result, ts=ts, timezone=timezone)
    for decision in decisions:
        stores.relationship.apply_ol_gate_decision(
            person_id=person_id,
            ts=ts,
            source_event_id=source_event_id,
            source_text=text,
            create_open_loop=decision.create_open_loop,
            try_ol5_close=decision.try_ol5_close,
            loop_topic=decision.loop_topic,
            action_terms=list(decision.action_terms),
            completion_verbs=list(decision.completion_verbs),
            detail=decision.detail,
            timezone=timezone,
        )
    return decisions
