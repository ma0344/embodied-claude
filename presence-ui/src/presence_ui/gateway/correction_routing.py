"""SHIFT-R2 — Stage 2 correction_target classification and Stage 3 store routing."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, replace
from typing import Any

from interaction_orchestrator_mcp.schemas import (
    RecordAgentExperienceInput,
    RecordInterpretationShiftInput,
)

from presence_ui.deps import PresenceStores
from presence_ui.gateway.gw_silent import run_classifier_turn
from presence_ui.gateway.llm_intent import _extract_json_object
from presence_ui.gateway.ol_gate import OlGateParsed
from presence_ui.gateway.ol_gate_prompts import (
    SHIFT_R2_CORRECTION_STAGE2_SYSTEM,
    build_shift_r2_correction_stage2_task,
)

logger = logging.getLogger(__name__)

CORRECTION_KIND = "correction"

CORRECTION_TARGETS = frozenset(
    {
        "world_fact",
        "schedule",
        "dismiss_topic",
        "boundary",
        "agent_behavior",
        "relationship",
        "rule",
        "self_model",
    }
)

_SHIFT_TARGETS = frozenset({"boundary", "agent_behavior", "relationship", "rule", "self_model"})

# Stage 1 LLM が other のまま返したとき correction Stage 2 へ進める最小 cue（destination 決定ではない）
_CORRECTION_KIND_CUE = re.compile(
    r"(?:"
    r"違う|そうじゃない|それは違|間違って|忘れて|やめて|しないで|"
    r"静かに|黙って|うるさい|内緒|プライバシー|見ないで|撮らない"
    r")",
    re.IGNORECASE,
)


def correction_routing_enabled() -> bool:
    flag = os.environ.get("PRESENCE_GW_CORRECTION_ROUTING", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _correction_stage2_max_tokens() -> int:
    return int(os.environ.get("PRESENCE_SHIFT_R2_STAGE2_MAX_TOKENS", "512"))


def _nullable_field(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def _clamp_confidence(value: object, *, default: float = 0.75) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, num))


@dataclass(frozen=True, slots=True)
class CorrectionParsed:
    utterance: str
    correction_target: str
    persists_across_turns: bool
    canonical_topic: str
    old_interpretation: str
    new_interpretation: str
    confidence: float
    dismiss_topic_hint: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectionRouteOutcome:
    correction_target: str
    wrote_shift: bool = False
    shift_id: str | None = None
    wrote_boundary: bool = False
    boundary_id: str | None = None
    wrote_experience: bool = False
    closed_loops: tuple[str, ...] = ()
    detail: dict[str, Any] | None = None


def parse_correction_stage2_response(
    text: str,
    *,
    fallback_utterance: str,
) -> CorrectionParsed | None:
    data = _extract_json_object(text)
    if not data:
        return None
    target = str(data.get("correction_target") or "world_fact").strip()
    if target not in CORRECTION_TARGETS:
        target = "world_fact"
    utterance = str(data.get("utterance") or fallback_utterance).strip()
    utterance = utterance or fallback_utterance.strip()
    if not utterance:
        return None
    canonical = _nullable_field(data.get("canonical_topic")) or utterance[:60]
    default_old = "Assumed default behavior before this turn"
    old = _nullable_field(data.get("old_interpretation")) or default_old
    new = _nullable_field(data.get("new_interpretation")) or utterance[:400]
    persists_raw = data.get("persists_across_turns")
    persists = bool(persists_raw) if persists_raw is not None else target in _SHIFT_TARGETS
    return CorrectionParsed(
        utterance=utterance,
        correction_target=target,
        persists_across_turns=persists,
        canonical_topic=canonical,
        old_interpretation=old,
        new_interpretation=new,
        confidence=_clamp_confidence(data.get("confidence")),
        dismiss_topic_hint=_nullable_field(data.get("dismiss_topic_hint")),
    )


def should_run_correction_stage2(*, utterance_kind: str) -> bool:
    """G1 — only Stage 1 ``correction`` enters correction Stage 2."""
    return utterance_kind == CORRECTION_KIND


def promote_correction_kind_if_cued(stage1: OlGateParsed, *, utterance: str) -> OlGateParsed:
    """When Stage 1 says ``other`` but utterance has correction cue, upgrade to ``correction``."""
    if not correction_routing_enabled():
        return stage1
    if stage1.utterance_kind in {
        CORRECTION_KIND,
        "greeting",
        "future_commitment",
        "past_completion",
        "past_report",
    }:
        return stage1
    if not _CORRECTION_KIND_CUE.search(utterance):
        return stage1
    return replace(stage1, utterance_kind=CORRECTION_KIND)


def run_correction_stage2(*, utterance: str) -> CorrectionParsed | None:
    raw = run_classifier_turn(
        system=SHIFT_R2_CORRECTION_STAGE2_SYSTEM,
        user=build_shift_r2_correction_stage2_task(utterance=utterance),
        max_tokens=_correction_stage2_max_tokens(),
        log_label="SHIFT-R2 correction Stage2",
    )
    if not raw:
        return None
    return parse_correction_stage2_response(raw, fallback_utterance=utterance)


def route_correction(
    stores: PresenceStores,
    *,
    person_id: str,
    text: str,
    ts: str,
    source_event_id: str,
    parsed: CorrectionParsed,
) -> CorrectionRouteOutcome:
    """Stage 3 — route to shift / boundary / dismiss / experience (never blind regex shift)."""
    target = parsed.correction_target
    detail: dict[str, Any] = {
        "kind": "shift_r2",
        "correction_target": target,
        "canonical_topic": parsed.canonical_topic,
        "persists_across_turns": parsed.persists_across_turns,
        "confidence": parsed.confidence,
    }

    if target == "world_fact":
        stores.orchestrator.record_agent_experience(
            RecordAgentExperienceInput(
                ts=ts,
                person_id=person_id,
                kind="user_correction",
                summary=f"Fact correction: {parsed.canonical_topic[:120]}",
                public_summary=parsed.new_interpretation[:180],
                importance=3,
                privacy_level="relationship",
                artifacts=[{"source_text": text[:240], "correction_target": target}],
            )
        )
        return CorrectionRouteOutcome(
            correction_target=target,
            wrote_experience=True,
            detail=detail,
        )

    if target == "schedule":
        logger.info("SHIFT-R2 schedule correction skipped shift (OL/GAPI path): %s", text[:60])
        return CorrectionRouteOutcome(correction_target=target, detail=detail)

    if target == "dismiss_topic":
        outcome = stores.relationship.dismiss_from_utterance(
            person_id=person_id,
            text=text,
            ts=ts,
            source_event_id=source_event_id,
        )
        if not outcome.closed_loops and parsed.dismiss_topic_hint:
            outcome = stores.relationship.close_open_loops_matching_topic(
                person_id=person_id,
                topic_hint=parsed.dismiss_topic_hint,
                ts=ts,
                source_event_id=source_event_id,
                source_text=text,
            )
        detail["closed_loops"] = list(outcome.closed_loops)
        return CorrectionRouteOutcome(
            correction_target=target,
            closed_loops=tuple(outcome.closed_loops),
            detail=detail,
        )

    boundary_id: str | None = None
    if target == "boundary":
        result = stores.relationship.record_boundary(
            person_id=person_id,
            kind="presence",
            rule=parsed.new_interpretation[:240],
            source_text=text,
        )
        boundary_id = result.get("boundary_id")
        detail["boundary_id"] = boundary_id

    shift_id: str | None = None
    if target in _SHIFT_TARGETS and parsed.persists_across_turns:
        stored = stores.orchestrator.record_interpretation_shift(
            RecordInterpretationShiftInput(
                person_id=person_id,
                topic=parsed.canonical_topic,
                old_interpretation=parsed.old_interpretation,
                new_interpretation=parsed.new_interpretation,
                trigger=f"SHIFT-R2 ingest ({target})",
                confidence=parsed.confidence,
                ts=ts,
            )
        )
        shift_id = stored.experience_id
        detail["shift_id"] = shift_id

    return CorrectionRouteOutcome(
        correction_target=target,
        wrote_shift=shift_id is not None,
        shift_id=shift_id,
        wrote_boundary=boundary_id is not None,
        boundary_id=boundary_id,
        detail=detail,
    )
