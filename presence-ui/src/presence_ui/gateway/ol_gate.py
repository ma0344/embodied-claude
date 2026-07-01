"""GW-S2 / OL-GATE — ingest utterance extraction and gateway merge."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Sequence

from relationship_mcp.date_resolution import DEFAULT_TIMEZONE, anchor_temporal_in_text, as_of_date
from relationship_mcp.inference import (
    is_archive_remember_utterance,
    is_dismiss_utterance,
    is_recall_utterance,
)
from social_core.ol_stale import infer_stale_policy_for_loop

from presence_ui.deps import PresenceStores
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object
from presence_ui.gateway.ol_gate_prompts import (
    OL_GATE_CLASSIFIER_STABLE,
    build_ol_gate_extract_task,
)
from presence_ui.gateway.stage1_context import Stage1DepartureHint
from presence_ui.gateway.stage1_kinds import CLOSE_SHAPES, STAGE1_KINDS

logger = logging.getLogger(__name__)

_PAST_TEMPORAL_MARKERS = ("昨日", "一昨日", "先週", "先月", "yesterday", "last week")
_OBJECT_PARTICLE_RE = re.compile(r"[をがはにでと]$")
_FUTURE_DEPARTURE_CUE = re.compile(r"これから")
_DEPARTURE_ACTION_RE = re.compile(r"行って(?:き|く)る|行く|出かけ")
# Finite wake/return greetings for Q3a safety net (not OL verb lists).
_CONTEXTUAL_WAKE_GREETING_RE = re.compile(
    r"^(?:おはよう|おはー|起きた|おきた)(?:[!.！?？～〜*\s]*)$",
    re.I,
)


@dataclass(frozen=True, slots=True)
class OlGateParsed:
    utterance: str
    utterance_kind: str
    temporal_phrase: str | None
    inferred_temporal_phrase: str | None
    temporal_source: str | None
    object_phrase: str | None
    action_phrase: str | None
    action_terms: tuple[str, ...]
    completion_verbs: tuple[str, ...]
    ineligibility_reason: str | None
    close_shape: str | None = None


@dataclass(frozen=True, slots=True)
class OlGateGatewayDecision:
    utterance: str
    utterance_kind: str
    create_open_loop: bool
    try_ol5_close: bool
    loop_topic: str
    action_terms: tuple[str, ...]
    completion_verbs: tuple[str, ...]
    resolved_date: str | None
    needs_date_confirmation: bool
    ambiguous_phrases: tuple[str, ...]
    original_topic: str | None
    detail: dict[str, Any] = field(default_factory=dict)


def gw_s2_enabled() -> bool:
    flag = os.environ.get("PRESENCE_GW_S2_ENABLED", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def gw_s2_fallback_rules() -> bool:
    flag = os.environ.get("PRESENCE_GW_S2_FALLBACK_RULES", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _nullable_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def _str_list(value: object, *, limit: int = 5) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return tuple(out)


def normalize_close_shape(
    *,
    utterance_kind: str,
    raw: object,
    object_phrase: str | None,
    action_phrase: str | None,
) -> str | None:
    """Infer close_shape from Stage1 when the model omits it."""
    if utterance_kind != "past_completion":
        return None
    shape = _nullable_str(raw)
    if shape in CLOSE_SHAPES:
        return shape
    if (object_phrase or "").strip():
        return "activity_named"
    if (action_phrase or "").strip():
        return "action_only"
    return None


def parse_ol_gate_response(text: str, *, fallback_utterance: str = "") -> OlGateParsed | None:
    data = _extract_json_object(text)
    if not data:
        return None
    kind = str(data.get("utterance_kind") or "other").strip()
    if kind not in STAGE1_KINDS:
        kind = "other"
    utterance = str(data.get("utterance") or fallback_utterance).strip()
    utterance = utterance or fallback_utterance.strip()
    if not utterance:
        return None
    object_phrase = _nullable_str(data.get("object_phrase"))
    action_phrase = _nullable_str(data.get("action_phrase"))
    return OlGateParsed(
        utterance=utterance,
        utterance_kind=kind,
        temporal_phrase=_nullable_str(data.get("temporal_phrase")),
        inferred_temporal_phrase=_nullable_str(data.get("inferred_temporal_phrase")),
        temporal_source=_nullable_str(data.get("temporal_source")),
        object_phrase=object_phrase,
        action_phrase=action_phrase,
        action_terms=_str_list(data.get("action_terms")),
        completion_verbs=_str_list(data.get("completion_verbs")),
        ineligibility_reason=_nullable_str(data.get("ineligibility_reason")),
        close_shape=normalize_close_shape(
            utterance_kind=kind,
            raw=data.get("close_shape"),
            object_phrase=object_phrase,
            action_phrase=action_phrase,
        ),
    )


def _normalize_action_terms(
    parsed: OlGateParsed,
) -> tuple[str, ...]:
    if parsed.utterance_kind == "other":
        return ()
    if parsed.action_terms:
        cleaned = []
        for term in parsed.action_terms:
            noun = _OBJECT_PARTICLE_RE.sub("", term).strip()
            if noun and noun not in cleaned:
                cleaned.append(noun)
        return tuple(cleaned[:5])
    if parsed.object_phrase:
        noun = _OBJECT_PARTICLE_RE.sub("", parsed.object_phrase).strip()
        if noun:
            return (noun,)
    return ()


def seed_completion_verbs(
    action_phrase: str | None,
    *,
    llm_verbs: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """OL5-a: hint verbs at loop create; close still re-parses ingest utterances."""
    out: list[str] = [v for v in llm_verbs if v]
    phrase = (action_phrase or "").strip()
    if phrase:
        stem_rules: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("作", ("作った", "できた", "完成した")),
            ("行", ("行ってきた", "行った", "出かけてきた")),
            ("してくる", ("してきた",)),
            ("食べ", ("食べた", "食べ終わった")),
            ("飲", ("飲んだ", "飲み終わった")),
            ("散歩", ("散歩してきた", "散歩終わった")),
            ("終", ("終わった", "終えた")),
            ("済", ("済んだ", "済ませた")),
        )
        for key, verbs in stem_rules:
            if key in phrase:
                for verb in verbs:
                    if verb not in out:
                        out.append(verb)
        if not out and phrase.endswith("る") and len(phrase) > 1:
            out.append(f"{phrase[:-1]}た")
    return tuple(out[:5])


def _effective_temporal(parsed: OlGateParsed) -> str | None:
    return parsed.temporal_phrase or parsed.inferred_temporal_phrase


def promote_future_departure_if_cued(stage1: OlGateParsed, *, utterance: str) -> OlGateParsed:
    """Safety net when Stage1 mis-tags これから+出発 as past_* (prefer Stage1 Q5)."""
    line = (utterance or "").strip()
    if stage1.utterance_kind == "future_commitment":
        return stage1
    if stage1.utterance_kind in (
        "greeting",
        "correction",
        "calendar_read",
        "calendar_write",
    ):
        return stage1
    if not _FUTURE_DEPARTURE_CUE.search(line):
        return stage1
    if not _DEPARTURE_ACTION_RE.search(line):
        return stage1
    logger.info(
        "GW-S2: promote %s -> future_commitment (これから + departure) utterance=%r",
        stage1.utterance_kind,
        line[:80],
    )
    return replace(stage1, utterance_kind="future_commitment", close_shape=None)


def _contextual_wake_action_phrase(utterance: str) -> str:
    line = (utterance or "").strip()
    for prefix in ("おはよう", "おはー", "起きた", "おきた"):
        if line.lower().startswith(prefix.lower()):
            return prefix
    return line[:20] or "起きた"


def promote_contextual_wake_greeting_if_cued(
    stage1: OlGateParsed,
    *,
    utterance: str,
    open_departure_loops: tuple[Stage1DepartureHint, ...] | Sequence[Stage1DepartureHint] = (),
) -> OlGateParsed:
    """Safety net when Stage1 tags Q3a wake greeting as plain greeting (prefer prompt Q3a)."""
    if stage1.utterance_kind != "greeting":
        return stage1
    if len(open_departure_loops) != 1:
        return stage1
    line = (utterance or "").strip()
    if not _CONTEXTUAL_WAKE_GREETING_RE.match(line):
        return stage1
    action = _contextual_wake_action_phrase(line)
    logger.info(
        "GW-S2: promote greeting -> past_completion (contextual wake, departure=%s) utterance=%r",
        open_departure_loops[0].loop_id,
        line[:80],
    )
    return replace(
        stage1,
        utterance_kind="past_completion",
        close_shape="action_only",
        object_phrase=None,
        action_phrase=action,
        completion_verbs=(action,),
    )


def _is_future_commitment(
    parsed: OlGateParsed,
    *,
    resolved_date: date | None,
    as_of_day: date,
) -> bool:
    if parsed.utterance_kind != "future_commitment":
        return False
    temporal = _effective_temporal(parsed)
    if temporal and any(marker in temporal for marker in _PAST_TEMPORAL_MARKERS):
        return False
    if resolved_date is not None and resolved_date < as_of_day:
        return False
    return bool(parsed.object_phrase or parsed.action_phrase or parsed.action_terms)


def merge_ol_gate_gateway(
    parsed: OlGateParsed,
    *,
    ts: str,
    timezone: str = DEFAULT_TIMEZONE,
) -> OlGateGatewayDecision:
    """Apply gateway rules — do not trust LLM slots when kind=other."""
    as_of_day = as_of_date(as_of_ts=ts, tz_name=timezone)
    base_detail: dict[str, Any] = {
        "kind": "ol_gate",
        "utterance_kind": parsed.utterance_kind,
        "close_shape": parsed.close_shape,
        "temporal_phrase": parsed.temporal_phrase,
        "inferred_temporal_phrase": parsed.inferred_temporal_phrase,
        "temporal_source": parsed.temporal_source,
        "object_phrase": parsed.object_phrase if parsed.utterance_kind != "other" else None,
        "action_phrase": parsed.action_phrase if parsed.utterance_kind != "other" else None,
        "ineligibility_reason": parsed.ineligibility_reason,
    }

    if parsed.utterance_kind in ("other", "greeting"):
        return OlGateGatewayDecision(
            utterance=parsed.utterance,
            utterance_kind=parsed.utterance_kind,
            create_open_loop=False,
            try_ol5_close=False,
            loop_topic="",
            action_terms=(),
            completion_verbs=(),
            resolved_date=None,
            needs_date_confirmation=False,
            ambiguous_phrases=(),
            original_topic=None,
            detail={**base_detail, "create_open_loop": False},
        )

    action_terms = _normalize_action_terms(parsed)
    if parsed.utterance_kind == "past_completion":
        completion_verbs = seed_completion_verbs(
            parsed.action_phrase,
            llm_verbs=parsed.completion_verbs,
        )
        if parsed.action_phrase and parsed.action_phrase not in completion_verbs:
            completion_verbs = (*completion_verbs, parsed.action_phrase)
        return OlGateGatewayDecision(
            utterance=parsed.utterance,
            utterance_kind=parsed.utterance_kind,
            create_open_loop=False,
            try_ol5_close=True,
            loop_topic="",
            action_terms=action_terms,
            completion_verbs=completion_verbs,
            resolved_date=None,
            needs_date_confirmation=False,
            ambiguous_phrases=(),
            original_topic=None,
            detail={
                **base_detail,
                "action_terms": list(action_terms),
                "completion_verbs": list(completion_verbs),
                "create_open_loop": False,
            },
        )

    if parsed.utterance_kind == "past_report":
        return OlGateGatewayDecision(
            utterance=parsed.utterance,
            utterance_kind=parsed.utterance_kind,
            create_open_loop=False,
            try_ol5_close=False,
            loop_topic="",
            action_terms=action_terms,
            completion_verbs=(),
            resolved_date=None,
            needs_date_confirmation=False,
            ambiguous_phrases=(),
            original_topic=None,
            detail={**base_detail, "create_open_loop": False},
        )

    loop_topic = parsed.utterance.strip()
    temporal = _effective_temporal(parsed)
    if temporal and temporal not in loop_topic:
        loop_topic = f"{temporal} {loop_topic}".strip()
    anchored_result = anchor_temporal_in_text(loop_topic, updated_at=ts, tz_name=timezone)
    resolved = anchored_result.resolved_date
    create = _is_future_commitment(parsed, resolved_date=resolved, as_of_day=as_of_day)
    create = create and not anchored_result.needs_date_confirmation

    completion_verbs = seed_completion_verbs(
        parsed.action_phrase,
        llm_verbs=parsed.completion_verbs,
    )

    detail = {
        **base_detail,
        "action_terms": list(action_terms),
        "completion_verbs": list(completion_verbs),
        "create_open_loop": create,
        "is_future_commitment": _is_future_commitment(
            parsed, resolved_date=resolved, as_of_day=as_of_day
        ),
    }
    if anchored_result.needs_date_confirmation:
        detail["needs_date_confirmation"] = True
        detail["ambiguous_phrases"] = list(anchored_result.ambiguous_phrases)
    elif resolved is not None:
        detail["resolved_date"] = resolved.isoformat()
    if anchored_result.text != loop_topic:
        detail["original_topic"] = loop_topic[:200]

    if create:
        policy, stale_after = infer_stale_policy_for_loop(
            utterance=parsed.utterance,
            loop_topic=anchored_result.text,
            resolved_date=resolved,
            needs_date_confirmation=anchored_result.needs_date_confirmation,
            temporal_phrase=temporal,
        )
        detail["stale_policy"] = policy
        if stale_after:
            detail["stale_after"] = stale_after

    return OlGateGatewayDecision(
        utterance=parsed.utterance,
        utterance_kind=parsed.utterance_kind,
        create_open_loop=create,
        try_ol5_close=False,
        loop_topic=anchored_result.text if create else "",
        action_terms=action_terms,
        completion_verbs=completion_verbs,
        resolved_date=None if resolved is None else resolved.isoformat(),
        needs_date_confirmation=anchored_result.needs_date_confirmation,
        ambiguous_phrases=tuple(anchored_result.ambiguous_phrases),
        original_topic=loop_topic if anchored_result.text != loop_topic else None,
        detail=detail,
    )


def run_ol_gate_extract(
    *,
    utterance: str,
    open_departure_loops: Sequence[Stage1DepartureHint] = (),
) -> OlGateParsed | None:
    raw = run_classifier_turn(
        system=OL_GATE_CLASSIFIER_STABLE,
        user=build_ol_gate_extract_task(
            utterance=utterance,
            open_departure_loops=open_departure_loops,
        ),
        log_label="GW-S2 OL-GATE",
    )
    if not raw:
        return None
    parsed = parse_ol_gate_response(raw, fallback_utterance=utterance)
    if parsed is None:
        return None
    from presence_ui.gateway.stage1_calendar import normalize_calendar_stage1

    parsed = normalize_calendar_stage1(parsed, utterance=utterance)
    return promote_contextual_wake_greeting_if_cued(
        parsed,
        utterance=utterance,
        open_departure_loops=tuple(open_departure_loops),
    )


def should_run_ol_gate(text: str) -> bool:
    stripped = (text or "").strip()
    if len(stripped) < 2:
        return False
    if is_dismiss_utterance(stripped):
        return False
    if is_recall_utterance(stripped):
        return False
    if is_archive_remember_utterance(stripped):
        return False
    return True


async def try_ol_gate_after_ingest(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
    timezone: str | None = None,
) -> OlGateGatewayDecision | None:
    """Run GW-S2 classifier after human ingest and apply gateway decision."""
    if not gw_s2_enabled() or not should_run_ol_gate(text):
        return None
    tz = timezone or stores.policy_timezone

    from presence_ui.gateway.stage1_context import fetch_stage1_departure_hints
    from presence_ui.gateway.temp_c_staged import (
        apply_staged_decisions,
        gw_s2_staged_enabled,
        run_staged_classify,
    )

    # SQLite: ``stores`` is bound to the ingest asyncio thread — do not pass it to
    # ``asyncio.to_thread`` (see ``try_ol7_after_ingest`` / ``presence_ui.deps``).
    departure_hints = fetch_stage1_departure_hints(stores, person_id=person_id)

    if gw_s2_staged_enabled():
        result = await asyncio.to_thread(
            run_staged_classify,
            utterance=text,
            open_departure_loops=departure_hints,
        )
        if result is None:
            if gw_s2_fallback_rules():
                stores.relationship.note_human_utterance_for_loops(
                    person_id=person_id,
                    text=text,
                    ts=ts,
                    source_event_id=source_event_id,
                    rule_open_loops=True,
                )
            return None
        decisions = apply_staged_decisions(
            stores,
            person_id=person_id,
            text=text,
            ts=ts,
            source_event_id=source_event_id,
            result=result,
            timezone=tz,
        )
        return decisions[-1] if decisions else None

    parsed = await asyncio.to_thread(
        run_ol_gate_extract,
        utterance=text,
        open_departure_loops=departure_hints,
    )
    if parsed is None:
        if gw_s2_fallback_rules():
            stores.relationship.note_human_utterance_for_loops(
                person_id=person_id,
                text=text,
                ts=ts,
                source_event_id=source_event_id,
                rule_open_loops=True,
            )
        return None
    decision = merge_ol_gate_gateway(parsed, ts=ts, timezone=tz)
    from presence_ui.gateway.ol5_completion_verbs import enrich_decision_completion_verbs

    decision = enrich_decision_completion_verbs(decision)
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
        timezone=tz,
    )
    return decision
