"""GW-S2 / OL-GATE — ingest utterance extraction and gateway merge."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

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

logger = logging.getLogger(__name__)

VALID_UTTERANCE_KINDS = frozenset(
    {"future_commitment", "past_completion", "past_report", "greeting", "correction", "other"}
)
_PAST_TEMPORAL_MARKERS = ("昨日", "一昨日", "先週", "先月", "yesterday", "last week")
_OBJECT_PARTICLE_RE = re.compile(r"[をがはにでと]$")


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


def parse_ol_gate_response(text: str, *, fallback_utterance: str = "") -> OlGateParsed | None:
    data = _extract_json_object(text)
    if not data:
        return None
    kind = str(data.get("utterance_kind") or "other").strip()
    if kind not in VALID_UTTERANCE_KINDS:
        kind = "other"
    utterance = str(data.get("utterance") or fallback_utterance).strip()
    utterance = utterance or fallback_utterance.strip()
    if not utterance:
        return None
    return OlGateParsed(
        utterance=utterance,
        utterance_kind=kind,
        temporal_phrase=_nullable_str(data.get("temporal_phrase")),
        inferred_temporal_phrase=_nullable_str(data.get("inferred_temporal_phrase")),
        temporal_source=_nullable_str(data.get("temporal_source")),
        object_phrase=_nullable_str(data.get("object_phrase")),
        action_phrase=_nullable_str(data.get("action_phrase")),
        action_terms=_str_list(data.get("action_terms")),
        completion_verbs=_str_list(data.get("completion_verbs")),
        ineligibility_reason=_nullable_str(data.get("ineligibility_reason")),
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
    completion_verbs = parsed.completion_verbs if parsed.utterance_kind == "past_completion" else ()

    if parsed.utterance_kind == "past_completion":
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


def run_ol_gate_extract(*, utterance: str) -> OlGateParsed | None:
    raw = run_classifier_turn(
        system=OL_GATE_CLASSIFIER_STABLE,
        user=build_ol_gate_extract_task(utterance=utterance),
        log_label="GW-S2 OL-GATE",
    )
    if not raw:
        return None
    return parse_ol_gate_response(raw, fallback_utterance=utterance)


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

    from presence_ui.gateway.temp_c_staged import (
        apply_staged_decisions,
        gw_s2_staged_enabled,
        run_staged_classify,
    )

    if gw_s2_staged_enabled():
        result = await asyncio.to_thread(run_staged_classify, utterance=text)
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

    parsed = await asyncio.to_thread(run_ol_gate_extract, utterance=text)
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
