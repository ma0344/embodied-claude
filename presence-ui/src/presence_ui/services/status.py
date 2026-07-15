"""Aggregate Koyori internal state for the Presence UI."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from interaction_orchestrator_mcp.compose import compose_interaction_context
from interaction_orchestrator_mcp.desire_source import load_desire_snapshot
from interaction_orchestrator_mcp.plan import plan_response
from interaction_orchestrator_mcp.schemas import ComposeInteractionContextInput, PlanResponseInput
from system_temperature_mcp.server import get_all_temperatures

from presence_ui.deps import get_stores
from presence_ui.heartbeat.pulse_state import load_pulse_state
from presence_ui.heartbeat.schedule import policy_timezone, seconds_until_wake
from presence_ui.schemas import (
    ActiveArc,
    AgentPulseView,
    DesireItem,
    KoyoriStatusResponse,
    LiveInnerVoiceView,
    PlanPreviewView,
    RecentExperience,
    ReminderCardItem,
    SocialStateView,
    TemperatureReading,
    TemperatureView,
)
from presence_ui.services.somatic_context import enrich_interaction_context

_CPU_NAME_HINTS = ("cpu", "package", "core", "tctl", "ccd", "processor")
_PLAN_PREVIEW_TTL_SEC = 45.0
_plan_preview_cache: tuple[float, PlanPreviewView | None] | None = None

_STATUS_EXPERIENCE_KINDS = (
    "agent_response",
    "agent_voice_utterance",
    "agent_observation",
    "agent_autonomous_action",
    "agent_private_reflection",
    "body_affliction",
    "open_loop_progress",
    "boundary_respected",
    "desire_satisfied",
)

_LIVE_PHRASE_MAX = 80
_INJECTION_MARKERS = (
    "[gateway_turn_context]",
    "[desires]",
    "[dream_digest]",
    "[overnight_inner_voice]",
    "mcp__",
    "compact_prompt_block",
)

_DESIRE_PHRASES: dict[str, str] = {
    "look_outside": "外の様子が、ちょっと気になる",
    "miss_companion": "まーの様子、ちらっと気になる",
    "observe_room": "部屋の様子を、静かに見ていたい",
    "cognitive_load": "頭の中で、何かを整理している",
    "identity_coherence": "自分が自分でいられるか、確かめたい",
    "browse_curiosity": "気になることが、ちらついている",
    "speak_up": "何か、声に出して伝えたいことがある",
    "reflect": "自分のことを、少し考えたい",
}


def _sanitize_live_phrase(text: str, *, max_len: int = _LIVE_PHRASE_MAX) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    lower = cleaned.lower()
    for marker in _INJECTION_MARKERS:
        idx = lower.find(marker.lower())
        if idx >= 0:
            cleaned = cleaned[:idx].strip(" -—·|")
            lower = cleaned.lower()
    if len(cleaned) > max_len:
        return f"{cleaned[: max_len - 1].rstrip()}…"
    return cleaned


def _desire_live_phrase(desire_id: str | None) -> str | None:
    if not desire_id:
        return None
    return _DESIRE_PHRASES.get(desire_id, f"「{desire_id}」が、心の隅にある")


def _build_live_inner_voice(
    *,
    person_id: str,
    stores,
    dominant_desire: str | None,
    public_experiences: list[RecentExperience],
) -> LiveInnerVoiceView:
    private_rows = stores.orchestrator.recent_agent_experiences(
        person_id=person_id,
        limit=8,
        include_private=True,
    )
    for exp in private_rows:
        if exp.kind != "agent_private_reflection":
            continue
        phrase = _sanitize_live_phrase(exp.summary or "")
        if phrase:
            return LiveInnerVoiceView(
                phrase=phrase,
                source="private_reflection",
                source_label="心の声",
                ts=exp.ts,
            )

    desire_phrase = _desire_live_phrase(dominant_desire)
    if desire_phrase:
        return LiveInnerVoiceView(
            phrase=_sanitize_live_phrase(desire_phrase),
            source="desire",
            source_label="いまの気持ち",
        )

    for exp in public_experiences:
        phrase = _sanitize_live_phrase(exp.summary or "")
        if phrase:
            return LiveInnerVoiceView(
                phrase=phrase,
                source="experience",
                source_label="さっきまで",
                ts=exp.ts,
            )

    return LiveInnerVoiceView(
        phrase="静かに、呼吸を整えている",
        source="idle",
        source_label="心の声",
    )


def _format_desires(snapshot: dict | None) -> tuple[list[DesireItem], str | None]:
    if not snapshot:
        return [], None
    desires_map = snapshot.get("desires") or {}
    discomforts = snapshot.get("discomforts") or {}
    items = [
        DesireItem(
            id=str(name),
            level=float(value),
            discomfort=float(discomforts[name]) if name in discomforts else None,
        )
        for name, value in desires_map.items()
    ]
    items.sort(key=lambda item: item.level, reverse=True)
    dominant = snapshot.get("dominant")
    return items, str(dominant) if dominant else None


def _pick_primary_reading(temps: list[dict]) -> dict | None:
    if not temps:
        return None
    lowered = [(row, str(row.get("name") or "").lower()) for row in temps]
    for hint in _CPU_NAME_HINTS:
        for row, name in lowered:
            if hint in name:
                return row
    return max(temps, key=lambda row: float(row.get("temperature_celsius") or 0))


def _pick_temperature() -> TemperatureView:
    try:
        payload = get_all_temperatures()
    except Exception:
        return TemperatureView(
            celsius=None,
            feeling="温度を感じられへん…（センサー読み取り失敗）",
            source=None,
        )

    temps = payload.get("temperatures") or []
    feeling = str(payload.get("feeling") or "unknown")
    readings = [
        TemperatureReading(
            name=str(row.get("name") or "sensor"),
            celsius=float(row.get("temperature_celsius") or 0),
            source=str(row.get("source") or "") or None,
        )
        for row in temps[:6]
    ]
    if not temps:
        return TemperatureView(
            celsius=None,
            feeling=feeling,
            source=None,
            readings=readings,
        )

    primary = _pick_primary_reading(temps)
    assert primary is not None
    return TemperatureView(
        celsius=float(primary.get("temperature_celsius") or 0),
        feeling=feeling,
        source=str(primary.get("name") or primary.get("source") or ""),
        readings=readings,
    )


def _fetch_agent_pulse() -> AgentPulseView | None:
    pulse = load_pulse_state()
    if pulse is None or not pulse.next_wake_at:
        return None
    return AgentPulseView(
        next_wake_at=pulse.next_wake_at,
        next_wake_in_sec=round(seconds_until_wake(pulse), 1),
        reason=pulse.reason or None,
        last_wake_at=pulse.last_wake_at,
        last_action=pulse.last_action,
        dominant_desire=pulse.dominant_desire,
        channel=pulse.channel,
    )


def _quiet_hours_active(ctx) -> bool:
    social = ctx.social_state or {}
    availability = str(social.get("availability") or "unknown")
    return any(
        "quiet hours are active" in hint for hint in ctx.boundary_hints
    ) or availability == "do_not_interrupt"


def _fetch_autonomous_plan_preview(*, person_id: str) -> PlanPreviewView | None:
    global _plan_preview_cache
    now = time.monotonic()
    if _plan_preview_cache is not None:
        cached_at, cached = _plan_preview_cache
        if now - cached_at < _PLAN_PREVIEW_TTL_SEC:
            return cached

    stores = get_stores()
    try:
        ctx = compose_interaction_context(
            ComposeInteractionContextInput(
                person_id=person_id,
                channel="autonomous",
                user_text=None,
                autonomous_trigger="status_preview",
                include_private=False,
                max_chars=int(os.getenv("PRESENCE_COMPOSE_MAX_CHARS", "6000")),
            ),
            social_state_store=stores.social_state,
            relationship_store=stores.relationship,
            joint_attention_store=stores.joint_attention,
            boundary_store=stores.boundary,
            self_narrative_store=stores.self_narrative,
            orchestrator_store=stores.orchestrator,
            policy_timezone=stores.policy_timezone,
        )
        ctx = enrich_interaction_context(ctx, channel="autonomous", user_text=None)
        plan = plan_response(
            PlanResponseInput(interaction_context=ctx, user_text=None),
        )
    except Exception:
        _plan_preview_cache = (now, None)
        return None

    preview = PlanPreviewView(
        primary_move=plan.primary_move,
        why=plan.why_this_move,
        allowed_actions=list(plan.initiative.allowed_actions or []),
        forbidden_actions=list(plan.initiative.forbidden_actions or []),
        quiet_hours_active=_quiet_hours_active(ctx),
        preview_at=datetime.now(policy_timezone()).isoformat(),
    )
    _plan_preview_cache = (now, preview)
    return preview


def fetch_koyori_status(*, person_id: str = "ma") -> KoyoriStatusResponse:
    stores = get_stores()
    window = int(os.getenv("PRESENCE_SOCIAL_WINDOW_SECONDS", "900"))
    reminders_limit = int(os.getenv("PRESENCE_REMINDERS_CARD_LIMIT", "10"))
    experience_limit = int(os.getenv("PRESENCE_STATUS_EXPERIENCE_LIMIT", "5"))

    desire_items, dominant = _format_desires(load_desire_snapshot())

    arcs = [
        ActiveArc(
            title=arc.title,
            status=arc.status,
            importance=arc.importance,
            summary=arc.summary,
        )
        for arc in stores.self_narrative.list_active_arcs()
    ]

    raw_experiences = stores.orchestrator.recent_agent_experiences(
        person_id=person_id,
        limit=experience_limit * 2,
        include_private=False,
    )
    experiences = [
        RecentExperience(
            experience_id=exp.experience_id,
            ts=exp.ts,
            kind=exp.kind,
            summary=exp.summary,
            importance=exp.importance,
        )
        for exp in raw_experiences
        if exp.kind in _STATUS_EXPERIENCE_KINDS
    ][:experience_limit]

    social_view: SocialStateView | None = None
    try:
        state = stores.social_state.get_social_state(
            window_seconds=window,
            person_id=person_id,
            include_evidence=False,
        )
        social_view = SocialStateView(
            timestamp=state.timestamp,
            presence=state.presence,
            activity=state.activity,
            availability=state.availability,
            interaction_phase=state.interaction_phase,
            energy=state.energy,
            interrupt_cost=state.interrupt_cost,
            affect_label=state.affect_guess.label,
            summary=state.summary_for_prompt,
        )
    except Exception:
        social_view = None

    reminders: list[ReminderCardItem] = []
    try:
        commitments = stores.relationship.list_active_commitments(
            person_id=person_id, limit=reminders_limit
        )
        reminders = [
            ReminderCardItem(
                commitment_id=c.id,
                due_at=c.due_at,
                title=c.text,
                speak_line=(c.metadata or {}).get("speak_line"),
                delivery=(c.metadata or {}).get("delivery") or "say",
            )
            for c in commitments
        ]
    except Exception:
        reminders = []

    include_plan = os.getenv("PRESENCE_STATUS_PLAN_PREVIEW", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    return KoyoriStatusResponse(
        updated_at=datetime.now(timezone.utc).isoformat(),
        desires=desire_items,
        dominant_desire=dominant,
        active_arcs=arcs,
        recent_experiences=experiences,
        live_inner_voice=_build_live_inner_voice(
            person_id=person_id,
            stores=stores,
            dominant_desire=dominant,
            public_experiences=experiences,
        ),
        social_state=social_view,
        temperature=_pick_temperature(),
        reminders=reminders,
        agent_pulse=_fetch_agent_pulse(),
        autonomous_plan=_fetch_autonomous_plan_preview(person_id=person_id)
        if include_plan
        else None,
    )
