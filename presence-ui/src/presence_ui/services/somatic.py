"""Somatic awareness — record organ afflictions (BIO-8a)."""

from __future__ import annotations

from typing import Any, Literal

from interaction_orchestrator_mcp.schemas import RecordAgentExperienceInput
from social_core import utc_now

from presence_ui.deps import PresenceStores
from presence_ui.services.body_state import (
    load_body_state,
    note_organ_affliction,
    note_organ_ok,
    save_body_state,
)
from presence_ui.services.vision_capture import VisionCaptureResult

BodyOrgan = Literal["eyes", "ears", "voice", "mind"]

_ORGAN_JA = {
    "eyes": "目",
    "ears": "耳",
    "voice": "声",
    "mind": "考え",
}


def eye_affliction_summary(
    *,
    action: str,
    error: str | None = None,
    vision: VisionCaptureResult | None = None,
    capture_failed: bool = False,
) -> str | None:
    """Japanese first-person summary when eyes are not healthy; None if OK."""
    if capture_failed or (vision is not None and not vision.ok):
        detail = (error or (vision.error if vision else None) or "カメラに繋がれへん").strip()
        return f"目が開かへんかった（{action}）。{detail[:160]}"
    if vision is None:
        return None
    if vision.caption and vision.caption.strip():
        return None
    if vision.vision_corrupt:
        return "目が曇ってた。画像の説明が ? だらけで取れへんかった"
    return "目は開いたけど、何が見えてるか説明できへんかった"


def record_body_affliction(
    stores: PresenceStores,
    *,
    person_id: str,
    organ: BodyOrgan,
    summary: str,
    action: str,
    detail: str = "",
    remedy: str | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> None:
    """Persist somatic discomfort as agent experience (status + compose surface)."""
    organ_ja = _ORGAN_JA.get(organ, organ)
    payload_artifacts: list[dict[str, Any]] = [
        {"organ": organ, "action": action, "organ_ja": organ_ja},
    ]
    if remedy:
        payload_artifacts.append({"remedy_attempted": remedy})
    if artifacts:
        payload_artifacts.extend(artifacts)
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="body_affliction",
            summary=summary,
            public_summary=summary,
            why=f"{organ_ja}の不調",
            felt_state={"organ": organ, "action": action},
            importance=4,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=payload_artifacts,
        )
    )
    state = load_body_state()
    note_organ_affliction(
        state,
        organ=organ,
        summary=summary,
        action=action,
        remedy=remedy,
        status="failed" if organ == "eyes" else "degraded",
    )
    save_body_state(state)
    maybe_escalate_after_affliction(stores, person_id=person_id)


def maybe_escalate_after_affliction(
    stores: PresenceStores,
    *,
    person_id: str,
) -> None:
    from presence_ui.services.somatic_escalation import maybe_escalate_somatic

    maybe_escalate_somatic(stores, person_id=person_id)


def record_eye_affliction(
    stores: PresenceStores,
    *,
    person_id: str,
    action: str,
    summary: str,
    detail: str = "",
    remedy: str | None = None,
    vision: VisionCaptureResult | None = None,
) -> None:
    artifacts: list[dict[str, Any]] = []
    if detail:
        artifacts.append({"detail": detail[:240]})
    if vision and vision.file_path:
        artifacts.append({"file_path": vision.file_path})
    record_body_affliction(
        stores,
        person_id=person_id,
        organ="eyes",
        summary=summary,
        action=action,
        detail=detail,
        remedy=remedy,
        artifacts=artifacts or None,
    )


def maybe_record_eye_affliction(
    stores: PresenceStores,
    *,
    person_id: str,
    action: str,
    error: str | None = None,
    vision: VisionCaptureResult | None = None,
    capture_failed: bool = False,
    remedy: str | None = None,
) -> str | None:
    """Record body_affliction when eyes are unhealthy; return summary if recorded."""
    summary = eye_affliction_summary(
        action=action,
        error=error,
        vision=vision,
        capture_failed=capture_failed,
    )
    if not summary:
        return None
    detail = error or (vision.error if vision else "") or ""
    record_eye_affliction(
        stores,
        person_id=person_id,
        action=action,
        summary=summary,
        detail=detail,
        remedy=remedy,
        vision=vision,
    )
    return summary


def maybe_record_eye_ok(
    *,
    vision: VisionCaptureResult | None = None,
    note: str | None = None,
) -> bool:
    """Mark eyes healthy in body_state when vision succeeded with a caption."""
    if vision is None or not vision.ok:
        return False
    caption = (vision.caption or "").strip()
    if not caption:
        return False
    state = load_body_state()
    note_organ_ok(state, organ="eyes", note=(note or caption)[:120])
    save_body_state(state)
    return True
