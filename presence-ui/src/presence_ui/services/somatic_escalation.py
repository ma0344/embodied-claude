"""BIO-8d — cross-organ escalation (push / health_safety)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import RecordAgentExperienceInput

from presence_ui.deps import PresenceStores
from presence_ui.services.body_state import (
    BodyState,
    compute_escalation,
    load_body_state,
    mark_escalation_push,
    save_body_state,
)

logger = logging.getLogger(__name__)

_ORGAN_JA = {
    "eyes": "目",
    "ears": "耳",
    "voice": "声",
    "mind": "考え",
}


def somatic_escalation_enabled() -> bool:
    return os.getenv("PRESENCE_SOMATIC_ESCALATION", "1").lower() not in {"0", "false", "no"}


def escalation_push_cooldown_sec() -> int:
    raw = os.getenv("PRESENCE_SOMATIC_ESCALATION_PUSH_COOLDOWN_SEC", "1800")
    try:
        return max(60, int(raw))
    except ValueError:
        return 1800


def _within_push_cooldown(state: BodyState) -> bool:
    pushed_at = state.last_escalation_push_at
    if not pushed_at:
        return False
    try:
        ts = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(ts.tzinfo or ZoneInfo("UTC")) - ts < timedelta(
        seconds=escalation_push_cooldown_sec()
    )


def _escalation_push_text(escalation: dict[str, Any]) -> str:
    organs = escalation.get("organs_affected") or []
    labels = [
        str(item.get("organ_ja") or _ORGAN_JA.get(str(item.get("organ")), "体"))
        for item in organs[:3]
    ]
    if labels:
        joined = "と".join(labels)
        return f"体の調子がおかしいで。{joined}が同時にダメかも。見てもらえる？"
    return "体の調子がおかしいで。複数の感覚が同時にダメかも。見てもらえる？"


def _boundary_allows_health_push(
    stores: PresenceStores,
    *,
    person_id: str,
    local_time: str,
) -> bool:
    result = stores.boundary.evaluate_action(
        action_type="nudge_human",
        channel="autonomous",
        person_id=person_id,
        urgency="critical",
        context={"health_safety": True, "time_local": local_time},
    )
    return result.decision in {"allow", "allow_with_override"}


def maybe_escalate_somatic(
    stores: PresenceStores,
    *,
    person_id: str = "ma",
    local_time: str | None = None,
    timezone: str = "Asia/Tokyo",
) -> dict[str, Any]:
    """Evaluate escalation; on critical, best-effort push to まー (respects cooldown)."""
    if not somatic_escalation_enabled():
        return {"level": "none", "push": "disabled"}

    state = load_body_state()
    escalation = compute_escalation(state)
    level = str(escalation.get("level") or "none")
    if level == "none":
        return escalation

    state.last_escalation_level = level
    save_body_state(state)

    if level != "critical":
        return escalation

    if _within_push_cooldown(state):
        escalation["push"] = "cooldown"
        return escalation

    ts = local_time or state.updated_at
    if not _boundary_allows_health_push(stores, person_id=person_id, local_time=ts):
        escalation["push"] = "boundary_denied"
        return escalation

    from presence_ui.services.outbound_push import send_outbound_push

    text = _escalation_push_text(escalation)
    ok, detail = send_outbound_push(text=text, title="こより — 体の不調")
    mark_escalation_push(state, level=level)
    save_body_state(state)
    escalation["push"] = "ok" if ok else detail
    if ok:
        stores.orchestrator.record_agent_experience(
            RecordAgentExperienceInput(
                ts=state.last_escalation_push_at or state.updated_at,
                person_id=person_id,
                kind="body_affliction",
                summary=text[:240],
                public_summary=text[:240],
                why="somatic escalation push",
                felt_state={"escalation_level": level, "escalation_push": True},
                importance=5,
                privacy_level="relationship",
                related_event_ids=[],
                artifacts=[
                    {
                        "escalation": escalation,
                        "push_detail": detail,
                        "escalation_push": True,
                    }
                ],
            )
        )
        logger.info("Somatic escalation push ok: %s", detail)
    else:
        logger.warning("Somatic escalation push failed: %s", detail)
    return escalation
