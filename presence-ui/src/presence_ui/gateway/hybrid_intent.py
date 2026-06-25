"""C12 — rules-first intent with optional LM Studio fallback."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

from presence_ui.gateway.intent_labels import BODY_LABELS, normalize_intent_labels
from presence_ui.gateway.llm_intent import classify_with_llm, lm_studio_available
from presence_ui.gateway.see_intent import PtzIntent, SeeIntent
from presence_ui.gateway.user_intent import UserIntent, resolve_user_intent

logger = logging.getLogger(__name__)

_AMBIGUOUS_CUE = re.compile(
    r"(デスク|desk|ダイニング|dining|左|右|上|下|向|見|look|see|窓|外|部屋|どう|様子)",
    re.IGNORECASE,
)
_PURE_CHAT = re.compile(
    r"^(?:おはよう|こんにちは|こんばんは|ありがとう|うん|ok|はい|ねえ)[。!！]?$",
    re.IGNORECASE,
)

IntentSource = Literal["rules", "llm"]


@dataclass(frozen=True, slots=True)
class HybridBodyIntent:
    user_intent: UserIntent
    see_intent: SeeIntent | None = None
    ptz_intent: PtzIntent | None = None
    source: IntentSource = "rules"
    llm_labels: tuple[str, ...] = ()
    llm_confidence: float | None = None


def llm_intent_fallback_enabled() -> bool:
    return os.getenv("PRESENCE_LLM_INTENT_FALLBACK", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def _rules_body_active(intent: UserIntent) -> bool:
    return (
        intent.wants_speech
        or intent.wants_observe
        or intent.wants_remember
        or intent.wants_web_search
    )


def should_try_llm_fallback(text: str, rules: UserIntent) -> bool:
    """Call LLM only when rules found no body intent but utterance looks ambiguous."""
    if not llm_intent_fallback_enabled() or _rules_body_active(rules):
        return False
    line = (text or "").strip()
    if len(line) < 2 or len(line) > 60:
        return False
    if _PURE_CHAT.match(line):
        return False
    return bool(_AMBIGUOUS_CUE.search(line))


def _see_intent_from_labels(labels: list[str]) -> SeeIntent | None:
    for label in labels:
        if not label.startswith("observe_"):
            continue
        mode = label.removeprefix("observe_")
        if mode in {"current", "window", "desk", "dining", "look_around"}:
            return SeeIntent(mode=mode, reason="llm intent router")  # type: ignore[arg-type]
    return None


def _ptz_intent_from_labels(labels: list[str]) -> PtzIntent | None:
    degrees = {"up": 20, "down": 20, "left": 30, "right": 30}
    for label in labels:
        if not label.startswith("ptz_"):
            continue
        direction = label.removeprefix("ptz_")
        if direction in degrees:
            return PtzIntent(
                direction=direction,  # type: ignore[arg-type]
                degrees=degrees[direction],
                reason="llm intent router",
            )
    return None


def _user_intent_from_labels(labels: list[str]) -> UserIntent:
    body = [label for label in labels if label in BODY_LABELS]
    wants_observe = any(
        label.startswith("observe_") or label.startswith("ptz_") for label in body
    )
    return UserIntent(
        wants_speech="speech" in body,
        explicit_say=False,
        wants_observe=wants_observe,
        wants_remember="remember" in body,
        wants_web_search=False,
    )


def _hybrid_from_labels(labels: list[str], *, confidence: float | None) -> HybridBodyIntent:
    normalized = normalize_intent_labels(labels)
    return HybridBodyIntent(
        user_intent=_user_intent_from_labels(normalized),
        see_intent=_see_intent_from_labels(normalized),
        ptz_intent=_ptz_intent_from_labels(normalized),
        source="llm",
        llm_labels=tuple(normalized),
        llm_confidence=confidence,
    )


def resolve_hybrid_intent(text: str) -> HybridBodyIntent:
    """Rules first; optional LM Studio when rules yield chat-only on ambiguous cues."""
    rules = resolve_user_intent(text)
    if _rules_body_active(rules):
        return HybridBodyIntent(user_intent=rules, source="rules")

    if not should_try_llm_fallback(text, rules):
        return HybridBodyIntent(user_intent=rules, source="rules")

    if not lm_studio_available():
        logger.debug("C12 llm intent fallback skipped: LM Studio unreachable")
        return HybridBodyIntent(user_intent=rules, source="rules")

    min_conf = float(os.getenv("PRESENCE_LLM_INTENT_MIN_CONF", "0.55"))
    labels, confidence, detail = classify_with_llm(text)
    if not labels or labels == ["chat"]:
        logger.debug("C12 llm intent: no body labels (%s)", detail[:80])
        return HybridBodyIntent(user_intent=rules, source="rules")

    if confidence is not None and confidence < min_conf:
        logger.info(
            "C12 llm intent below confidence %.2f < %.2f for %r",
            confidence,
            min_conf,
            text[:40],
        )
        return HybridBodyIntent(user_intent=rules, source="rules")

    hybrid = _hybrid_from_labels(labels, confidence=confidence)
    logger.info(
        "C12 llm intent labels=%s conf=%s text=%r",
        hybrid.llm_labels,
        confidence,
        text[:60],
    )
    return hybrid
