"""UserAction meal v0 — deterministic encode + dinner retrieve (MEM-8h).

Stage LLM is deferred; fail-closed allowlist + finite markers only.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

from social_core import ensure_iso8601, parse_timestamp

from presence_ui.gateway.food_topic_encode import (
    foods_mentioned_in_text,
    format_cook_topic_fact,
    format_food_topic_fact,
)

if TYPE_CHECKING:
    from interaction_orchestrator_mcp.schemas import InteractionContext
    from relationship_mcp.store import RelationshipStore

logger = logging.getLogger(__name__)

KIND_MEAL = "meal"

# Finite markers — gate only (not open-ended natural language).
_ATE_MARKERS: tuple[str, ...] = ("食べちゃった", "食べたよ", "食べた")
_ATE_EXCLUSIONS: tuple[str, ...] = (
    "食べたい",
    "食べよう",
    "食べた気",
    "食べたこと",
    "食べた覚え",
    "食べた話",
)
# Plan needs a dinner-ish cue (not bare 「にする」 alone).
_PLAN_COMMIT: tuple[str, ...] = ("にする", "にしよう", "にするわ", "でいく")
_CONFIRM_ATE: tuple[str, ...] = ("済ませた", "食べたよ", "食べた", "もう食べ")
_CONFIRM_AFFIRM_EXACT: frozenset[str] = frozenset(
    {"うん", "うん。", "うん!", "うん！", "うんうん", "ええよ", "そう"}
)
_CONFIRM_DENY: tuple[str, ...] = ("ううん", "いや", "まだ", "違う", "ちゃう")
_DINNER_CUES: tuple[str, ...] = ("晩御飯", "晩ご飯", "夕飯", "夕食", "今晚")


def user_actions_meal_enabled() -> bool:
    raw = os.getenv("PRESENCE_USER_ACTIONS_MEAL", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def action_date_from_ts(ts: str | None, *, tz_name: str = "Asia/Tokyo") -> str:
    when = ensure_iso8601(ts or "2026-01-01T12:00:00+00:00")
    local = parse_timestamp(when).astimezone(ZoneInfo(tz_name))
    return local.date().isoformat()


def looks_like_dinner_cue(text: str) -> bool:
    return any(cue in (text or "") for cue in _DINNER_CUES)


def _looks_like_question(text: str) -> bool:
    line = (text or "").strip()
    return any(mark in line for mark in ("？", "?"))


def _has_ate_claim(text: str) -> bool:
    line = text or ""
    if any(ex in line for ex in _ATE_EXCLUSIONS):
        return False
    if _looks_like_question(line):
        return False
    return any(marker in line for marker in _ATE_MARKERS)


def _has_plan_marker(text: str) -> bool:
    """Dinner plan only — not 「夜はカレーの動画にする」 etc."""
    line = text or ""
    if any(noise in line for noise in ("動画", "配信", "見る", "観る", "番組", "話")):
        return False
    if any(d in line for d in ("晩御飯", "晩ご飯", "夕飯", "夕食")):
        return True
    if "夜は" in line and any(commit in line for commit in _PLAN_COMMIT):
        return True
    return False


def _has_confirm_marker(text: str) -> bool:
    line = (text or "").strip()
    if not line:
        return False
    if any(deny in line for deny in _CONFIRM_DENY):
        return False
    if _looks_like_question(line):
        return False
    if any(ex in line for ex in _ATE_EXCLUSIONS):
        return False
    if line in _CONFIRM_AFFIRM_EXACT:
        return True
    return any(marker in line for marker in _CONFIRM_ATE)


@dataclass(frozen=True, slots=True)
class MealEncodeResult:
    route: Literal["none", "self_report", "plan", "confirm"]
    action_id: str | None = None
    object: str | None = None


def try_encode_user_action_meal(
    store: RelationshipStore,
    *,
    person_id: str,
    text: str,
    ts: str | None = None,
    source_event_id: str | None = None,
    tz_name: str = "Asia/Tokyo",
) -> MealEncodeResult:
    """Deterministic meal encode for ma chat turns. Fail-closed; no invented objects."""
    if not user_actions_meal_enabled():
        return MealEncodeResult(route="none")
    if (person_id or "").strip().lower() != "ma":
        return MealEncodeResult(route="none")

    line = (text or "").strip()
    if not line:
        return MealEncodeResult(route="none")

    foods = foods_mentioned_in_text(line)
    day = action_date_from_ts(ts, tz_name=tz_name)
    when = ensure_iso8601(ts) if ts else None

    # 1) Self-report / confirm-with-food: allowlist food + clear ate claim
    if foods and _has_ate_claim(line):
        food = foods[0]
        intended = store.list_active_intended(person_id=person_id, kind=KIND_MEAL, now=when)
        match = next((row for row in intended if row.object == food), None)
        if match is not None:
            confirmed = store.confirm(
                action_id=match.action_id,
                action_date=day,
                source_event_id=source_event_id,
                ts=when,
            )
            return MealEncodeResult(
                route="confirm",
                action_id=confirmed.action_id if confirmed else match.action_id,
                object=food,
            )
        record = store.insert_confirmed(
            person_id=person_id,
            kind=KIND_MEAL,
            object=food,
            action_date=day,
            source_event_id=source_event_id,
            detail={"route": "self_report", "utterance": line[:120]},
            ts=when,
        )
        return MealEncodeResult(route="self_report", action_id=record.action_id, object=food)

    # 2) Plan: allowlist food + plan-style markers (do not confirm)
    if foods and _has_plan_marker(line) and not _has_ate_claim(line):
        food = foods[0]
        record = store.upsert_intended(
            person_id=person_id,
            kind=KIND_MEAL,
            object=food,
            source_event_id=source_event_id,
            detail={"route": "plan", "utterance": line[:120]},
            ts=when,
        )
        return MealEncodeResult(route="plan", action_id=record.action_id, object=food)

    # 3) Confirm: active intended + affirmation (うん / 食べた / 済ませた)
    # Bare 「うん」 only when exactly one intended; food mismatch → none (fail-closed).
    if _has_confirm_marker(line):
        intended = store.list_active_intended(person_id=person_id, kind=KIND_MEAL, now=when)
        if not intended:
            return MealEncodeResult(route="none")
        target = None
        if foods:
            target = next((row for row in intended if row.object == foods[0]), None)
            if target is None:
                return MealEncodeResult(route="none")
        elif len(intended) == 1:
            target = intended[0]
        else:
            return MealEncodeResult(route="none")
        confirmed = store.confirm(
            action_id=target.action_id,
            action_date=day,
            source_event_id=source_event_id,
            ts=when,
        )
        return MealEncodeResult(
            route="confirm",
            action_id=confirmed.action_id if confirmed else target.action_id,
            object=target.object,
        )

    # Mention-only / uncertain → never write
    return MealEncodeResult(route="none")


def _loop_looks_like_cook(topic: str) -> bool:
    """Prefer completed-cook wording; require allowlist food in topic."""
    text = topic or ""
    if "作った" not in text and "作り終" not in text:
        return False
    return bool(foods_mentioned_in_text(text))


def _food_from_cook_topic(topic: str) -> str | None:
    foods = foods_mentioned_in_text(topic or "")
    return foods[0] if foods else None


def collect_meal_mentionable_cards(
    store: RelationshipStore,
    *,
    person_id: str = "ma",
    limit: int = 3,
    tz_name: str = "Asia/Tokyo",
) -> list[tuple[str, str]]:
    """Return (card_text, reason) for dinner retrieve.

    confirmed → meal record; OL close cook-only → cook record (no ate claim).
    intended is never included.
    """
    cards: list[tuple[str, str]] = []
    seen: set[str] = set()

    for row in store.list_confirmed(person_id=person_id, kind=KIND_MEAL, limit=limit):
        card = format_food_topic_fact(row.object, on_date=row.action_date, tz_name=tz_name)
        if card in seen:
            continue
        seen.add(card)
        cards.append((card, "user_action_meal"))
        if len(cards) >= limit:
            return cards

    for loop in store.list_recent_closed_loops(person_id=person_id, limit=20):
        if not _loop_looks_like_cook(loop.topic):
            continue
        food = _food_from_cook_topic(loop.topic)
        if food is None:
            continue
        day = None
        if loop.detail.get("resolved_date"):
            day = str(loop.detail["resolved_date"])
        elif loop.detail.get("_list_updated_at"):
            day = action_date_from_ts(str(loop.detail["_list_updated_at"]), tz_name=tz_name)
        card = format_cook_topic_fact(food, on_date=day, tz_name=tz_name)
        if card in seen:
            continue
        seen.add(card)
        cards.append((card, "user_action_cook_ol"))
        if len(cards) >= limit:
            break
    return cards


def demote_legacy_meal_records(
    memories: list[Any],
    *,
    has_ua_meal: bool,
) -> list[Any]:
    """R1 — prefer UA meal cards over legacy LTM 「食べた記録」."""
    if not has_ua_meal:
        return memories
    from interaction_orchestrator_mcp.recall_query import is_meal_record_fact
    from interaction_orchestrator_mcp.schemas import RelevantMemoryRef

    out: list[Any] = []
    for mem in memories:
        reason = getattr(mem, "reason", "") or ""
        content = getattr(mem, "content", "") or ""
        if reason == "user_action_meal":
            out.append(mem)
            continue
        if is_meal_record_fact(content):
            out.append(
                RelevantMemoryRef(
                    memory_id=getattr(mem, "memory_id", None),
                    content=content,
                    relevance=float(getattr(mem, "relevance", 0.0) or 0.0),
                    use_policy="do_not_surface",
                    reason="legacy_meal_record_demoted_for_ua",
                )
            )
            continue
        out.append(mem)
    return out


def maybe_enrich_user_action_meals(
    ctx: InteractionContext,
    *,
    user_text: str,
    max_chars: int,
    relationship: RelationshipStore | None,
    prefetch_fact_check: bool = False,
) -> tuple[InteractionContext, str | None]:
    """Inject UA confirmed (+ cook OL) cards on dinner / food cues."""
    if not user_actions_meal_enabled() or relationship is None:
        return ctx, None
    person_id = (ctx.person_id or "ma").strip().lower()
    if person_id != "ma":
        return ctx, None

    text = user_text or ""
    foods = foods_mentioned_in_text(text)
    dinner = looks_like_dinner_cue(text)
    if not dinner and not foods:
        return ctx, None

    cards = collect_meal_mentionable_cards(
        relationship,
        person_id=person_id,
        limit=3,
        tz_name=ctx.timezone or "Asia/Tokyo",
    )
    # Food-only cue (no dinner): UA ate cards only — not cook OL (avoid loose inject).
    if not dinner:
        cards = [(c, r) for c, r in cards if r == "user_action_meal"]
    if not cards:
        return ctx, None

    from interaction_orchestrator_mcp.memory_bridge import apply_memory_bridge_to_context
    from interaction_orchestrator_mcp.schemas import RelevantMemoryRef

    bridge_lines = list(ctx.memory_bridge_lines or [])
    memories = list(ctx.relevant_memories)
    existing = {m.content.strip() for m in memories if m.content.strip()}
    existing_lines = {line.strip() for line in bridge_lines}
    ua_added = 0
    has_ua_meal = any(getattr(m, "reason", "") == "user_action_meal" for m in memories)

    for card, reason in cards:
        if card in existing:
            if reason == "user_action_meal":
                has_ua_meal = True
            continue
        memories.insert(
            0,
            RelevantMemoryRef(
                memory_id=None,
                content=card,
                relevance=0.95,
                use_policy="mentionable",
                reason=reason,
            ),
        )
        existing.add(card)
        line = f"- {card}"
        if line not in existing_lines and card not in existing_lines:
            bridge_lines.insert(0, line)
            existing_lines.add(line)
        ua_added += 1
        if reason == "user_action_meal":
            has_ua_meal = True

    memories = demote_legacy_meal_records(memories, has_ua_meal=has_ua_meal)
    if ua_added == 0 and not has_ua_meal:
        return ctx, None

    keywords = list(ctx.memory_bridge_keywords or [])
    for food in foods:
        if food not in keywords:
            keywords.append(food)
    if looks_like_dinner_cue(text) and "晩御飯" not in keywords:
        keywords.append("晩御飯")

    updated = apply_memory_bridge_to_context(
        ctx.model_copy(update={"relevant_memories": memories}),
        bridge_lines=bridge_lines,
        bridge_keywords=keywords[:5] or ["晩御飯"],
        bridge_hits=[],
        user_text=user_text,
        max_chars=max_chars,
        prefetch_fact_check=prefetch_fact_check,
    )
    if ua_added == 0:
        return updated, None
    return updated, f"食事カード ({ua_added} 件)"
