"""Post-reply interpretation shift detection — gateway records growth moments."""

from __future__ import annotations

import logging
import re
from typing import Literal

from interaction_orchestrator_mcp.schemas import (
    InteractionContext,
    RecordInterpretationShiftInput,
    ResponsePlan,
)

logger = logging.getLogger(__name__)

ShiftKind = Literal["user_correction", "boundary", "relationship", "policy"]

_CORRECTION_CUE = re.compile(
    r"(?:"
    r"違う|そうじゃない|それは違|間違って|忘れて|やめて|しないで|"
    r"静かに|黙って|うるさい|内緒|プライバシー|見ないで|撮らない|"
    r"that's wrong|that is wrong|not right|stop doing|don't do"
    r")",
    re.IGNORECASE,
)

_TOPIC_RULES: list[tuple[ShiftKind, re.Pattern[str], str]] = [
    (
        "boundary",
        re.compile(r"静かに|黙って|うるさい|夜|深夜|寝|眠|quiet|sleep", re.IGNORECASE),
        "quiet hours and presence",
    ),
    (
        "boundary",
        re.compile(r"プライバシー|内緒|見ないで|撮らない|privacy", re.IGNORECASE),
        "privacy and camera",
    ),
    (
        "relationship",
        re.compile(r"距離|しつこ|うざ|勘弁|leave me|back off", re.IGNORECASE),
        "interaction pace with ma",
    ),
    (
        "policy",
        re.compile(r"ルール|方針|ポリシー|schedule|設定", re.IGNORECASE),
        "house rules and policy purpose",
    ),
]


def _topic_for(user_text: str) -> tuple[ShiftKind, str]:
    for kind, pattern, label in _TOPIC_RULES:
        if pattern.search(user_text):
            return kind, label
    return "user_correction", user_text.strip()[:80] or "ma's correction"


def _old_interpretation(
    *,
    topic: str,
    ctx: InteractionContext | None,
) -> str:
    if ctx and ctx.agent_state.recent_interpretation_shifts:
        for shift in ctx.agent_state.recent_interpretation_shifts:
            if shift.topic == topic or topic in shift.topic:
                return shift.new_interpretation
    return "Assumed default behavior before this turn"


def infer_interpretation_shifts(
    *,
    person_id: str,
    user_text: str,
    reply_text: str,
    ctx: InteractionContext | None,
    plan: ResponsePlan | None,
) -> list[RecordInterpretationShiftInput]:
    """Heuristic v1 — user correction cues and boundary hints."""
    user = (user_text or "").strip()
    if not user:
        return []

    has_cue = bool(_CORRECTION_CUE.search(user))
    # Compose policy hints (e.g. maybe_interruptible) are NOT user corrections.
    if not has_cue:
        return []

    boundary_hints = list(ctx.boundary_hints) if ctx else []
    kind, topic = _topic_for(user)

    new_text = user[:400]
    if reply_text.strip():
        reply = reply_text.strip()
        if any(marker in reply for marker in ("わかった", "了解", "覚え", "守る", "気をつけ")):
            new_text = f"{user[:200]} → acknowledged: {reply[:180]}"

    confidence = 0.72
    if has_cue:
        confidence = 0.82
    if boundary_hints:
        confidence = max(confidence, 0.78)
    if plan and plan.boundary and plan.boundary.privacy_sensitive:
        confidence = max(confidence, 0.85)

    implications: list[str] = []
    if kind == "boundary":
        implications.append("Respect ma's boundary on future turns (plan must_include).")
    if kind == "policy":
        implications.append("Honor policy purpose over literal wording.")

    return [
        RecordInterpretationShiftInput(
            person_id=person_id,
            topic=topic,
            old_interpretation=_old_interpretation(topic=topic, ctx=ctx),
            new_interpretation=new_text,
            trigger=f"gateway post-reply hook ({kind})",
            confidence=confidence,
            implications=implications,
        )
    ]


def record_interpretation_shifts(
    *,
    person_id: str,
    user_text: str,
    reply_text: str,
    ctx: InteractionContext | None,
    plan: ResponsePlan | None,
) -> list[str]:
    """Persist inferred shifts; return shift_ids."""
    from presence_ui.deps import get_stores

    payloads = infer_interpretation_shifts(
        person_id=person_id,
        user_text=user_text,
        reply_text=reply_text,
        ctx=ctx,
        plan=plan,
    )
    if not payloads:
        return []

    stores = get_stores()
    shift_ids: list[str] = []
    for payload in payloads:
        try:
            recent = stores.orchestrator.recent_interpretation_shifts(
                person_id=person_id,
                limit=3,
            )
            if recent:
                latest = recent[0]
                if (
                    latest.topic == payload.topic
                    and latest.new_interpretation.strip() == payload.new_interpretation.strip()
                ):
                    continue
            stored = stores.orchestrator.record_interpretation_shift(payload)
            shift_ids.append(stored.experience_id)
            logger.info(
                "BIO interpretation_shift topic=%s id=%s",
                payload.topic[:40],
                stored.experience_id,
            )
        except Exception as exc:
            logger.warning("interpretation_shift record failed: %s", exc)
    return shift_ids
