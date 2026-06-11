"""Aggregate Koyori internal state for the Presence UI."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from interaction_orchestrator_mcp.desire_source import load_desire_snapshot
from system_temperature_mcp.server import get_all_temperatures

from presence_ui.deps import get_stores
from presence_ui.schemas import (
    ActiveArc,
    DesireItem,
    KoyoriStatusResponse,
    RecentExperience,
    SocialStateView,
    TemperatureView,
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


def _pick_temperature() -> TemperatureView:
    try:
        payload = get_all_temperatures()
    except Exception:
        return TemperatureView(celsius=None, feeling="unknown", source=None)

    temps = payload.get("temperatures") or []
    feeling = str(payload.get("feeling") or "unknown")
    if not temps:
        return TemperatureView(celsius=None, feeling=feeling, source=None)

    primary = max(temps, key=lambda row: float(row.get("temperature_celsius") or 0))
    return TemperatureView(
        celsius=float(primary.get("temperature_celsius") or 0),
        feeling=feeling,
        source=str(primary.get("name") or primary.get("source") or ""),
    )


def fetch_koyori_status(*, person_id: str = "ma") -> KoyoriStatusResponse:
    stores = get_stores()
    window = int(os.getenv("PRESENCE_SOCIAL_WINDOW_SECONDS", "900"))

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

    experiences = [
        RecentExperience(
            experience_id=exp.experience_id,
            ts=exp.ts,
            kind=exp.kind,
            summary=exp.summary,
            importance=exp.importance,
        )
        for exp in stores.orchestrator.recent_agent_experiences(
            person_id=person_id,
            limit=5,
            include_private=False,
        )
    ]

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

    return KoyoriStatusResponse(
        updated_at=datetime.now(timezone.utc).isoformat(),
        desires=desire_items,
        dominant_desire=dominant,
        active_arcs=arcs,
        recent_experiences=experiences,
        social_state=social_view,
        temperature=_pick_temperature(),
    )
