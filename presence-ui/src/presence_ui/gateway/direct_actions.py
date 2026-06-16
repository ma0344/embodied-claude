"""Gateway direct execution — compose/plan decisions without LLM MCP tools."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from interaction_orchestrator_mcp.schemas import (
    AppendPrivateReflectionInput,
    InteractionContext,
    RecordAgentExperienceInput,
    ResponsePlan,
)
from social_core import utc_now

from presence_ui.deps import PresenceStores
from presence_ui.gateway.room_events import activity_event, progress_event
from presence_ui.services.camera_locations import CAMERA_LOCATIONS, PresetLocation
from presence_ui.services.outbound import (
    default_surface_channels,
    enqueue_outbound_nudge,
    outbound_delivery_artifacts,
    voice_local_enabled,
)

logger = logging.getLogger(__name__)


def outbound_nudge_speak_enabled(*, want_speak: bool) -> bool:
    """When kiosk is primary, TTS goes via room_say only (avoid double playback)."""
    if not want_speak:
        return False
    try:
        from presence_ui.services.outbound_kiosk import kiosk_primary_active

        if kiosk_primary_active():
            return False
    except Exception:
        pass
    return True


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HOOKS = _REPO_ROOT / ".claude" / "hooks"
if _HOOKS.is_dir() and str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))


@dataclass(slots=True)
class DirectActionOutcome:
    ok: bool
    action: str
    summary: str
    detail: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    desire_satisfied: str | None = None


def direct_actions_enabled() -> bool:
    return os.getenv("PRESENCE_GATEWAY_DIRECT_ACTIONS", "1").lower() not in {
        "0",
        "false",
        "no",
    }


def boundary_allows(
    stores: PresenceStores,
    *,
    action_type: str,
    person_id: str | None,
    urgency: str = "low",
) -> tuple[bool, list[str]]:
    result = stores.boundary.evaluate_action(
        action_type=action_type,
        channel="autonomous",
        person_id=person_id,
        urgency=urgency,
    )
    allowed = result.decision in {"allow", "allow_with_override"}
    return allowed, list(result.reasons)


def _reflection_body(ctx: InteractionContext, plan: ResponsePlan) -> str:
    parts: list[str] = [plan.why_this_move.strip()]
    if ctx.compact_prompt_block:
        parts.append(ctx.compact_prompt_block.strip())
    elif ctx.prompt_summary:
        parts.append(ctx.prompt_summary.strip())
    body = "\n\n".join(part for part in parts if part)
    return body[:4000] if body else "Quiet private note."


def write_private_reflection_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    body: str | None = None,
) -> DirectActionOutcome:
    """Persist a private reflection without mcp__sociality__append_private_reflection."""
    note = (body or _reflection_body(ctx, plan)).strip()
    title = f"Private note {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    stored = stores.orchestrator.append_private_reflection(
        AppendPrivateReflectionInput(
            person_id=person_id,
            title=title,
            body=note,
            tags=["gateway", "private"],
            importance=3,
            may_surface_later=True,
        )
    )
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_private_reflection",
            summary=note[:240],
            private_summary=note,
            public_summary="",
            importance=3,
            privacy_level="private",
            related_event_ids=[],
        )
    )
    events = [
        progress_event(phase="reflect", label="ひそかにメモした"),
        activity_event(kind="reflect", label="private reflection", detail=note[:120], ok=True),
    ]
    return DirectActionOutcome(
        ok=True,
        action="write_private_reflection",
        summary="Private reflection saved.",
        detail=stored.experience_id,
        events=events,
    )


async def observe_room_direct(
    stores: PresenceStores,
    *,
    person_id: str,
) -> DirectActionOutcome:
    """Look around via TapoCamera, vision-describe center, store observation memory."""
    from presence_ui.services.camera import camera_failure_hint, camera_look_around
    from presence_ui.services.vision_capture import (
        describe_existing_capture,
        remember_vision_capture,
    )

    captures = await camera_look_around()
    if not captures:
        hint = camera_failure_hint() or "no captures"
        return DirectActionOutcome(
            ok=False,
            action="camera_look_around",
            summary=f"Camera look-around failed: {hint}",
            detail=hint,
            events=[
                activity_event(
                    kind="see",
                    label="部屋を見た",
                    detail=hint[:200],
                    ok=False,
                )
            ],
        )

    paths = [c.file_path for c in captures if getattr(c, "file_path", None)]
    vision = await describe_existing_capture(
        captures[0],
        mode="look_around",
        label="--- Center View (room scan) ---",
        extra_line=f"Room scan: {len(captures)} angles captured.",
    )
    if not vision.ok:
        hint = vision.error or "vision describe failed"
        return DirectActionOutcome(
            ok=False,
            action="camera_look_around",
            summary=f"Camera look-around vision failed: {hint}",
            detail=hint,
            events=[
                activity_event(
                    kind="see",
                    label="部屋を見た",
                    detail=hint[:200],
                    ok=False,
                )
            ],
        )

    remember_ok = remember_vision_capture(vision)
    summary = vision.caption or vision.mcp_text[:240] or (
        f"Gateway observe_room: {len(captures)} angles"
    )
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_observation",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=[{"capture_count": len(captures), "paths": paths[:4]}],
        )
    )
    stores.social_state.ingest_social_event(
        {
            "ts": utc_now(),
            "source": "gateway_direct",
            "kind": "scene_parse",
            "person_id": person_id,
            "confidence": 0.7,
            "payload": {
                "scene_summary": summary,
                "capture_count": len(captures),
            },
        }
    )
    events = [
        progress_event(phase="see", label="部屋を見渡した"),
        activity_event(
            kind="see",
            label="部屋を見た",
            detail=f"{len(captures)} captures, remember={'ok' if remember_ok else 'fail'}",
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="camera_look_around",
        summary=summary,
        detail=vision.file_path or "",
        events=events,
        desire_satisfied="observe_room" if remember_ok else None,
    )


async def talk_to_companion_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    text: str | None = None,
    skip_cooldown: bool = False,
) -> DirectActionOutcome:
    """Speak to まー when boundary allows (miss_companion)."""
    allowed, reasons = boundary_allows(
        stores, action_type="say", person_id=person_id, urgency="low"
    )
    if not allowed:
        return DirectActionOutcome(
            ok=False,
            action="talk_to_companion",
            summary="Boundary denied say.",
            detail="; ".join(reasons),
            events=[
                activity_event(
                    kind="say",
                    label="声をかけられなかった",
                    detail="; ".join(reasons)[:200],
                    ok=False,
                )
            ],
        )

    line = (text or "").strip()
    if not line:
        from presence_ui.services.llm import generate_koyori_reply

        line = await generate_koyori_reply(
            user_text="（まーに短く一声。居るかどうかわからん。1〜2文。関西弁。）",
            ctx=ctx,
            plan=plan,
            max_tokens=120,
        )

    channels = default_surface_channels()
    enqueue = enqueue_outbound_nudge(
        stores,
        person_id=person_id,
        text=line,
        speak=outbound_nudge_speak_enabled(want_speak=True),
        channels=channels,
        desire="miss_companion",
        skip_cooldown=skip_cooldown,
    )
    if not enqueue.ok:
        return DirectActionOutcome(
            ok=False,
            action="talk_to_companion",
            summary=enqueue.reason or "Outbound enqueue failed.",
            detail=enqueue.reason,
            events=[
                activity_event(
                    kind="say",
                    label="声をかけられなかった",
                    detail=(enqueue.reason or "cooldown")[:200],
                    ok=False,
                )
            ],
        )

    from presence_ui.services.outbound_kiosk import should_deliver_pc_local
    from presence_ui.services.tts import speak_text

    spoke_local = False
    speak_detail = ""
    if voice_local_enabled() and should_deliver_pc_local():
        spoke_local, speak_detail = await speak_text(line, speaker="local")

    try:
        from presence_ui.services.kiosk_say import deliver_speak_to_kiosk
        from presence_ui.services.outbound_kiosk import kiosk_primary_active

        if kiosk_primary_active():
            deliver_speak_to_kiosk(line, source="talk")
    except Exception as exc:
        logger.warning("kiosk talk say failed: %s", exc)

    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_voice_utterance",
            summary=line[:240],
            public_summary=line[:240],
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=outbound_delivery_artifacts(
                nudge_id=enqueue.nudge_id or "",
                channels=list(enqueue.channels),
                speak=True,
                delivered_local=spoke_local,
            ),
        )
    )
    stores.social_state.ingest_social_event(
        {
            "ts": utc_now(),
            "source": "gateway_direct",
            "kind": "agent_utterance",
            "person_id": person_id,
            "confidence": 1.0,
            "payload": {
                "text": line,
                "channel": "outbound",
                "via": "presence_outbound",
                "nudge_id": enqueue.nudge_id,
                "channels": list(enqueue.channels),
            },
        }
    )
    events = [
        progress_event(phase="say", label="声をかけた"),
        activity_event(
            kind="say",
            label="声を出した",
            detail=line[:120],
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="talk_to_companion",
        summary=line,
        detail=speak_detail or enqueue.nudge_id or "",
        events=events,
        desire_satisfied="miss_companion",
    )


async def remind_commitment_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    text: str | None = None,
) -> DirectActionOutcome:
    """Deliver a due commitment reminder to まー (OL2)."""
    if not ctx.commitments_due:
        return DirectActionOutcome(
            ok=False,
            action="remind_commitment",
            summary="No due commitment in context.",
        )

    commitment = ctx.commitments_due[0]
    allowed, reasons = boundary_allows(
        stores, action_type="say", person_id=person_id, urgency="moderate"
    )
    if not allowed:
        return DirectActionOutcome(
            ok=False,
            action="remind_commitment",
            summary="Boundary denied say.",
            detail="; ".join(reasons),
            events=[
                activity_event(
                    kind="say",
                    label="リマインドできなかった",
                    detail="; ".join(reasons)[:200],
                    ok=False,
                )
            ],
        )

    line = (text or "").strip()
    if not line:
        speak_line = (commitment.speak_line or "").strip()
        if speak_line:
            line = speak_line
        else:
            label = commitment.text.strip()
            line = f"まー、{label} の時間やで" if label else "まー、リマインドの時間やで"

    use_say = commitment.delivery != "nudge_only"
    channels = default_surface_channels()
    enqueue = enqueue_outbound_nudge(
        stores,
        person_id=person_id,
        text=line,
        speak=outbound_nudge_speak_enabled(want_speak=use_say),
        channels=channels,
        desire="reminder",
        skip_cooldown=True,
    )
    if not enqueue.ok:
        return DirectActionOutcome(
            ok=False,
            action="remind_commitment",
            summary=enqueue.reason or "Outbound enqueue failed.",
            detail=enqueue.reason,
            events=[
                activity_event(
                    kind="say",
                    label="リマインドできなかった",
                    detail=(enqueue.reason or "enqueue failed")[:200],
                    ok=False,
                )
            ],
        )

    from presence_ui.services.outbound_kiosk import should_deliver_pc_local
    from presence_ui.services.tts import speak_text

    spoke_local = False
    speak_detail = ""
    if use_say and voice_local_enabled() and should_deliver_pc_local():
        spoke_local, speak_detail = await speak_text(line, speaker="local")

    if use_say:
        try:
            from presence_ui.services.kiosk_say import deliver_speak_to_kiosk
            from presence_ui.services.outbound_kiosk import kiosk_primary_active

            if kiosk_primary_active():
                deliver_speak_to_kiosk(line, source="reminder")
        except Exception as exc:
            logger.warning("kiosk reminder say failed: %s", exc)

    commitment_id = commitment.commitment_id
    if commitment_id:
        try:
            stores.relationship.complete_commitment(commitment_id)
        except Exception as exc:
            logger.warning("complete_commitment failed for %s: %s", commitment_id, exc)

    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_voice_utterance",
            summary=line[:240],
            public_summary=line[:240],
            importance=4,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=outbound_delivery_artifacts(
                nudge_id=enqueue.nudge_id or "",
                channels=list(enqueue.channels),
                speak=use_say,
                delivered_local=spoke_local,
            ),
        )
    )
    stores.social_state.ingest_social_event(
        {
            "ts": utc_now(),
            "source": "gateway_direct",
            "kind": "agent_utterance",
            "person_id": person_id,
            "confidence": 1.0,
            "payload": {
                "text": line,
                "channel": "outbound",
                "via": "remind_commitment",
                "commitment_id": commitment_id,
                "nudge_id": enqueue.nudge_id,
                "channels": list(enqueue.channels),
            },
        }
    )
    events = [
        progress_event(phase="say", label="リマインドした"),
        activity_event(
            kind="say",
            label="リマインドを伝えた",
            detail=line[:120],
            ok=True,
        ),
    ]
    return DirectActionOutcome(
        ok=True,
        action="remind_commitment",
        summary=line,
        detail=speak_detail or enqueue.nudge_id or "",
        events=events,
    )


def satisfy_desire_direct(
    *,
    desire_name: str,
    action_summary: str,
    person_id: str | None = None,
) -> tuple[bool, str]:
    """Recompute desires.json after a bounded gateway action (desire-system logic)."""
    desire_dir = _REPO_ROOT / "desire-system"
    if not desire_dir.is_dir():
        return False, "desire-system not found"

    if str(desire_dir) not in sys.path:
        sys.path.insert(0, str(desire_dir))

    try:
        from backend import make_default_adapter  # type: ignore[import-not-found]
        from desire_updater import (  # type: ignore[import-not-found]
            DESIRE_CONFIGS,
            DESIRES_PATH,
            compute_desires,
            save_desires,
        )
    except ImportError as exc:
        return False, f"desire-system import failed: {exc}"

    if desire_name not in DESIRE_CONFIGS:
        return False, f"unknown desire: {desire_name}"

    try:
        adapter = make_default_adapter()
        cfg = DESIRE_CONFIGS[desire_name]
        marker = cfg.keywords[0]
        summary_text = action_summary or marker
        adapter.record_satisfaction(
            desire_name=desire_name,
            summary=f"{marker}。{summary_text}",
            ts=datetime.now(timezone.utc),
            metadata={"outcome": "satisfied", "person_id": person_id, "via": "gateway"},
        )
        state = compute_desires(adapter)
        save_desires(state, DESIRES_PATH)
        return True, desire_name
    except Exception as exc:  # noqa: BLE001
        logger.warning("satisfy_desire_direct failed: %s", exc)
        return False, str(exc)


SMOKE_ACTIONS = frozenset(
    {
        "observe_room",
        "look_outside",
        "look_desk",
        "look_dining",
        "miss_companion",
        "write_private_reflection",
    }
)

_PRESET_SMOKE: dict[str, PresetLocation] = {
    "look_outside": "window",
    "look_desk": "desk",
    "look_dining": "dining",
}


async def look_preset_direct(
    stores: PresenceStores,
    *,
    person_id: str,
    location: PresetLocation,
) -> DirectActionOutcome:
    from presence_ui.services.vision_capture import capture_and_describe, remember_vision_capture

    spec = CAMERA_LOCATIONS[location]
    action = f"camera_look_{location}" if location != "window" else "camera_look_outside"
    activity_label = spec.label_ja

    vision = await capture_and_describe(mode=location, label=spec.capture_label)
    if not vision.ok:
        return DirectActionOutcome(
            ok=False,
            action=action,
            summary=vision.error or "capture failed",
            detail=vision.error or "",
            events=[
                activity_event(
                    kind="see",
                    label=activity_label,
                    detail=(vision.error or "failed")[:200],
                    ok=False,
                )
            ],
        )

    remember_ok = remember_vision_capture(vision)
    summary = vision.caption or vision.mcp_text[:240] or f"{location} capture"
    stores.orchestrator.record_agent_experience(
        RecordAgentExperienceInput(
            ts=utc_now(),
            person_id=person_id,
            kind="agent_observation",
            summary=summary,
            public_summary=summary,
            importance=3,
            privacy_level="relationship",
            related_event_ids=[],
            artifacts=[{"file_path": vision.file_path, "mode": location}],
        )
    )
    return DirectActionOutcome(
        ok=True,
        action=action,
        summary=summary,
        detail=vision.file_path or "",
        desire_satisfied=location if remember_ok and location != "window" else (
            "look_outside" if remember_ok and location == "window" else None
        ),
        events=[
            progress_event(phase="see", label=activity_label),
            activity_event(
                kind="see",
                label=activity_label,
                detail=summary[:120],
                ok=True,
            ),
        ],
    )


async def look_outside_direct(
    stores: PresenceStores,
    *,
    person_id: str,
) -> DirectActionOutcome:
    return await look_preset_direct(stores, person_id=person_id, location="window")


async def execute_smoke_action(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    smoke_action: str,
    speech_text: str | None = None,
) -> DirectActionOutcome:
    """Run one gateway action explicitly (smoke / manual verification)."""
    key = smoke_action.strip()
    if key not in SMOKE_ACTIONS:
        return DirectActionOutcome(
            ok=False,
            action=key,
            summary=f"Unknown smoke_action. Valid: {sorted(SMOKE_ACTIONS)}",
        )

    if key == "observe_room":
        outcome = await observe_room_direct(stores, person_id=person_id)
        if outcome.ok and not outcome.desire_satisfied:
            outcome.desire_satisfied = "observe_room"
    elif key == "look_outside":
        outcome = await look_outside_direct(stores, person_id=person_id)
    elif key in _PRESET_SMOKE:
        outcome = await look_preset_direct(
            stores,
            person_id=person_id,
            location=_PRESET_SMOKE[key],
        )
    elif key == "miss_companion":
        outcome = await talk_to_companion_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            text=speech_text,
            skip_cooldown=True,
        )
    else:
        outcome = write_private_reflection_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )

    return await _finalize_autonomous_outcome(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        outcome=outcome,
        record_experience=True,
    )


async def _finalize_autonomous_outcome(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    outcome: DirectActionOutcome,
    record_experience: bool,
) -> DirectActionOutcome:
    if outcome.desire_satisfied:
        ok, detail = await asyncio.to_thread(
            satisfy_desire_direct,
            desire_name=outcome.desire_satisfied,
            action_summary=outcome.summary,
            person_id=person_id,
        )
        if ok:
            outcome.events.append(
                activity_event(
                    kind="desire",
                    label="欲求を満たした",
                    detail=outcome.desire_satisfied or "",
                    ok=True,
                )
            )
        else:
            logger.info("desire satisfy skipped: %s", detail)

    followup = plan.followup_action or {}
    dominant = ctx.agent_state.dominant_desire
    if followup.get("kind") == "satisfy_desire" and not outcome.desire_satisfied:
        name = str(followup.get("desire_name") or dominant or "")
        if name:
            await asyncio.to_thread(
                satisfy_desire_direct,
                desire_name=name,
                action_summary=outcome.summary,
                person_id=person_id,
            )

    if (
        record_experience
        and outcome.ok
        and outcome.action
        not in {
            "stay_silent",
            "defer",
            "quietly_prepare",
            "recall_memories",
        }
    ):
        stores.orchestrator.record_agent_experience(
            RecordAgentExperienceInput(
                ts=utc_now(),
                person_id=person_id,
                kind="agent_autonomous_action",
                summary=outcome.summary[:240],
                public_summary=outcome.summary[:240],
                importance=3,
                privacy_level="relationship",
                related_event_ids=[],
            )
        )
    return outcome


async def execute_autonomous_plan(
    stores: PresenceStores,
    *,
    person_id: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    speech_text: str | None = None,
) -> DirectActionOutcome:
    """Run one bounded action from an autonomous compose/plan result."""
    move = plan.primary_move

    if move == "write_private_reflection":
        return write_private_reflection_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )

    if move in {"stay_silent", "defer", "quietly_prepare"}:
        return DirectActionOutcome(
            ok=True,
            action=move,
            summary=f"No action ({move}).",
            events=[progress_event(phase="silent", label="静かに過ごす")],
        )

    if move != "act_autonomously":
        return DirectActionOutcome(
            ok=False,
            action=move,
            summary=f"Unsupported autonomous move: {move}",
        )

    allowed = list(plan.initiative.allowed_actions or [])
    dominant = ctx.agent_state.dominant_desire

    if "remind_commitment" in allowed and ctx.commitments_due:
        outcome = await remind_commitment_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            text=speech_text,
        )
    elif "camera_look_around" in allowed or dominant == "observe_room":
        outcome = await observe_room_direct(stores, person_id=person_id)
    elif "camera_look_outside" in allowed or dominant == "look_outside":
        outcome = await look_outside_direct(stores, person_id=person_id)
    elif "talk_to_companion" in allowed or dominant == "miss_companion":
        outcome = await talk_to_companion_direct(
            stores,
            person_id=person_id,
            ctx=ctx,
            plan=plan,
            text=speech_text,
        )
    elif "write_private_reflection" in allowed:
        outcome = write_private_reflection_direct(
            stores, person_id=person_id, ctx=ctx, plan=plan
        )
    elif "recall_memories" in allowed or dominant == "identity_coherence":
        outcome = DirectActionOutcome(
            ok=True,
            action="recall_memories",
            summary="Recall handled via compose memory adapter on next turn.",
            events=[progress_event(phase="recall", label="記憶をなぞった")],
        )
    else:
        outcome = DirectActionOutcome(
            ok=True,
            action="act_autonomously",
            summary="No executable allowed_action; skipped.",
        )

    return await _finalize_autonomous_outcome(
        stores,
        person_id=person_id,
        ctx=ctx,
        plan=plan,
        outcome=outcome,
        record_experience=(move == "act_autonomously"),
    )
