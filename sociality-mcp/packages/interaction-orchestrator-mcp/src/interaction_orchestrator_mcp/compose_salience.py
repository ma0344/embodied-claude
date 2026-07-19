"""MEM-8g — filter compose memories for surface injection (no regex topic filters)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from interaction_orchestrator_mcp.memory_adapter import _extract_keywords
from interaction_orchestrator_mcp.recall_query import (
    is_desire_satisfaction_telemetry,
    is_episodic_blob,
    is_legacy_food_talk_fact,
    is_literary_agent_passage,
    is_meal_record_fact,
    is_somatic_escalation_push_passage,
    is_vision_bridge_noise,
    literary_user_cue,
)
from interaction_orchestrator_mcp.schemas import RelevantMemoryRef
from interaction_orchestrator_mcp.topic_retire import (
    TopicRetireStore,
    memory_matches_retired_topics,
    topic_retire_enabled,
)

if TYPE_CHECKING:
    from social_core import SocialDB


def compose_salience_enabled() -> bool:
    import os

    raw = os.getenv("PRESENCE_COMPOSE_SALIENCE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def health_safety_active_from_somatic(somatic_state: dict | None) -> bool:
    """True when escalation is elevated/critical (plan health_safety equivalent)."""
    if not somatic_state:
        return False
    escalation = somatic_state.get("escalation") or {}
    return str(escalation.get("level") or "none") in {"elevated", "critical"}


def _keyword_overlap(user_text: str, memory_content: str) -> bool:
    user_kw = set(_extract_keywords(user_text or "", max_keywords=8))
    if not user_kw:
        return False
    mem_kw = set(_extract_keywords(memory_content or "", max_keywords=12))
    return bool(user_kw & mem_kw)


def apply_compose_memory_salience(
    memories: list[RelevantMemoryRef],
    *,
    user_text: str | None,
    person_id: str | None,
    db: SocialDB | None = None,
    prefetch_fact_check: bool = False,
    health_safety_active: bool = False,
) -> list[RelevantMemoryRef]:
    """Demote episodic / retired / off-topic hits — never promote episodic to mentionable."""
    if not compose_salience_enabled():
        return memories

    retired: list[str] = []
    if topic_retire_enabled() and db is not None and person_id:
        retired = TopicRetireStore(db).active_retired_topics(person_id=person_id)

    utterance = user_text or ""
    reading_cue = literary_user_cue(utterance)
    has_ua_meal = any(m.reason == "user_action_meal" for m in memories)
    adjusted: list[RelevantMemoryRef] = []
    for mem in memories:
        policy = mem.use_policy
        reason = mem.reason
        episodic = is_episodic_blob(mem.content)
        literary = is_literary_agent_passage(mem.content)
        somatic_push = is_somatic_escalation_push_passage(mem.content)
        vision_noise = is_vision_bridge_noise(mem.content)
        desire_telemetry = is_desire_satisfaction_telemetry(mem.content)

        if episodic or "会話の区切り" in mem.content or "会話の一区切り" in mem.content:
            policy = "background_only"
            reason = "episodic_not_for_surface"
        if desire_telemetry:
            # Agent satisfaction encode lines — not speakable cross-session gists.
            # Writing stop / purge is out of scope; compose demote only.
            policy = "do_not_surface"
            reason = "desire_satisfaction_telemetry"
        if literary and not reading_cue:
            # LW-READ dumps are agent-internal; do not let them ride mentionable
            # on unrelated turns (羅生門 × 大丈夫). Wins over desire reason when
            # the line is `[desire:literary_…] 青空…`.
            policy = "do_not_surface"
            reason = "literary_passage_off_topic"
        if vision_noise:
            # Past VISION / Center View dumps — live see uses [vision_prefetch].
            # Always demote; no undemote gate (unlike somatic).
            policy = "do_not_surface"
            reason = "vision_caption_off_topic"
        if somatic_push and not health_safety_active:
            # BIO-8d push template — keep off dinner/chitchat surfaces unless
            # escalation is currently elevated/critical.
            policy = "do_not_surface"
            reason = "somatic_escalation_push_off_topic"
        elif (
            somatic_push
            and health_safety_active
            and (
                mem.reason == "somatic_escalation_push_off_topic"
                or reason == "somatic_escalation_push_off_topic"
            )
        ):
            # Re-gate after enrich attaches somatic_state (compose ran with False).
            policy = "mentionable"
            reason = "somatic_escalation_push_in_scope"
        if is_legacy_food_talk_fact(mem.content):
            # Prefer dated 「食べた記録」 cards over 「話をした（食事の話題）」.
            policy = "do_not_surface"
            reason = "legacy_food_talk_not_meal_record"
        if (
            has_ua_meal
            and mem.reason != "user_action_meal"
            and is_meal_record_fact(mem.content)
        ):
            policy = "do_not_surface"
            reason = "legacy_meal_record_demoted_for_ua"
        if retired and memory_matches_retired_topics(mem.content, retired):
            policy = "background_only"
            reason = "topic_retired"
        elif episodic and utterance and not _keyword_overlap(utterance, mem.content):
            policy = "background_only"
            reason = "episodic_off_topic"
        if prefetch_fact_check and episodic:
            policy = "do_not_surface"
            reason = "prefetch_fact_check_episodic_omitted"
        if prefetch_fact_check and literary and not reading_cue:
            policy = "do_not_surface"
            reason = "prefetch_fact_check_literary_omitted"

        if policy == mem.use_policy and reason == mem.reason:
            adjusted.append(mem)
        else:
            adjusted.append(
                RelevantMemoryRef(
                    memory_id=mem.memory_id,
                    content=mem.content,
                    relevance=mem.relevance,
                    use_policy=policy,
                    reason=reason,
                )
            )
    return adjusted


def select_surface_memories(
    memories: list[RelevantMemoryRef],
    *,
    prefetch_fact_check: bool = False,
) -> tuple[list[RelevantMemoryRef], list[RelevantMemoryRef]]:
    """Return (mentionable_for_surface, background_for_surface)."""
    mentionable = [
        m
        for m in memories
        if m.use_policy == "mentionable" and not is_episodic_blob(m.content)
    ]
    background = [
        m
        for m in memories
        if m.use_policy == "background_only" and not is_episodic_blob(m.content)
    ]
    if prefetch_fact_check:
        background = []
    return mentionable[:3], background[:2]
