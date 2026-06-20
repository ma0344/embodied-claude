"""Compute next wake time — こより decides when, not only Windows Task."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import InteractionContext, ResponsePlan

from presence_ui.heartbeat.pulse_state import AgentPulseState, parse_iso, save_pulse_state

_DEFAULT_TZ = "Asia/Tokyo"


def pulse_runner_enabled() -> bool:
    return os.getenv("PRESENCE_PULSE_RUNNER", "1").lower() not in {"0", "false", "no", "off"}


def pulse_min_seconds() -> int:
    return max(60, int(os.getenv("PRESENCE_PULSE_MIN_SEC", "300")))


def pulse_max_seconds() -> int:
    return max(pulse_min_seconds(), int(os.getenv("PRESENCE_PULSE_MAX_SEC", "21600")))


def policy_timezone() -> ZoneInfo:
    from presence_ui.deps import get_stores

    try:
        return ZoneInfo(get_stores().policy_timezone)
    except Exception:
        return ZoneInfo(_DEFAULT_TZ)


def _load_desires() -> dict[str, float]:
    path = Path(os.getenv("DESIRES_PATH", str(Path.home() / ".claude" / "desires.json")))
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    desires = data.get("desires")
    if not isinstance(desires, dict):
        return {}
    return {str(k): float(v) for k, v in desires.items() if isinstance(v, (int, float))}


def _clamp_wake_seconds(seconds: int) -> int:
    return max(pulse_min_seconds(), min(pulse_max_seconds(), seconds))


_QUIET_INWARD_ACTIONS = frozenset(
    {
        "write_private_reflection",
        "think_or_discuss_topic",
        "recall_memories",
        "consolidate_memories",
    }
)


def _is_quiet_inward_action(
    *,
    plan_move: str | None,
    action: str | None,
) -> bool:
    if action in _QUIET_INWARD_ACTIONS:
        return True
    if plan_move == "write_private_reflection":
        return True
    if plan_move == "act_autonomously" and action in _QUIET_INWARD_ACTIONS:
        return True
    return False


def _quiet_hours_delay(now: datetime, tz: ZoneInfo) -> int:
    """Quiet hours 23:00–07:00 — defer non-chat wakes toward 07:30."""
    hour = now.hour
    if 7 <= hour < 23:
        return 0
    if hour >= 23:
        target = (now + timedelta(days=1)).replace(
            hour=7, minute=30, second=0, microsecond=0
        )
    else:
        target = now.replace(hour=7, minute=30, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
    return max(0, int((target - now).total_seconds()))


def compute_next_pulse(
    *,
    channel: str,
    plan_move: str | None,
    ctx: InteractionContext | None = None,
    action: str | None = None,
    reason_suffix: str = "",
) -> AgentPulseState:
    tz = policy_timezone()
    now = datetime.now(tz)
    desires = _load_desires()
    dominant = (ctx.agent_state.dominant_desire if ctx else None) or None
    discomforts: dict[str, float] = {}
    if ctx and ctx.agent_state.discomforts:
        discomforts = dict(ctx.agent_state.discomforts)

    wake_sec = 1800  # 30m default
    reason_parts: list[str] = [channel]

    if channel == "chat":
        wake_sec = 1200
        reason_parts.append("after_chat")
        if dominant:
            level = desires.get(dominant, 0.0)
            disc = discomforts.get(dominant, 0.0)
            if disc > 0.35 or level > 0.55:
                wake_sec = 900
                reason_parts.append(f"desire:{dominant}")
    elif plan_move == "write_private_reflection" or action == "write_private_reflection":
        wake_sec = 7200
        reason_parts.append("private_reflection")
    elif action in {"observe_room", "camera_look_around", "look_outside"}:
        wake_sec = 2700
        reason_parts.append("observed_room")
    elif action in {"recall_memories", "think_or_discuss_topic"}:
        wake_sec = 3600
        reason_parts.append("inner_processing")
    elif action == "consolidate_memories":
        wake_sec = 86400
        reason_parts.append("consolidated")
    elif plan_move == "act_autonomously":
        wake_sec = 1500
        reason_parts.append("autonomous_tick")
        if dominant == "miss_companion":
            wake_sec = 1200
        elif dominant == "observe_room":
            wake_sec = 2400

    quiet_delay = _quiet_hours_delay(now, tz)
    inward = _is_quiet_inward_action(plan_move=plan_move, action=action)
    if quiet_delay > 0 and channel != "chat":
        if inward:
            wake_sec = min(wake_sec, 3600)
            reason_parts.append("quiet_inward")
        else:
            wake_sec = max(wake_sec, quiet_delay)
            reason_parts.append("quiet_hours")

    wake_sec = _clamp_wake_seconds(wake_sec)
    if reason_suffix:
        reason_parts.append(reason_suffix)

    next_wake = now + timedelta(seconds=wake_sec)
    return AgentPulseState(
        next_wake_at=next_wake.isoformat(),
        reason="; ".join(reason_parts),
        last_wake_at=now.isoformat(),
        last_action=action or plan_move,
        dominant_desire=dominant,
        channel=channel,
    )


def apply_pulse_schedule(
    *,
    channel: str,
    plan: ResponsePlan | None = None,
    ctx: InteractionContext | None = None,
    action: str | None = None,
    reason_suffix: str = "",
) -> AgentPulseState:
    plan_move = plan.primary_move if plan else None
    state = compute_next_pulse(
        channel=channel,
        plan_move=plan_move,
        ctx=ctx,
        action=action,
        reason_suffix=reason_suffix,
    )
    existing = None
    from presence_ui.heartbeat.pulse_state import load_pulse_state

    existing = load_pulse_state()
    if existing and existing.last_consolidate_at:
        state.last_consolidate_at = existing.last_consolidate_at
    if existing and existing.last_dream_at:
        state.last_dream_at = existing.last_dream_at
    if existing and existing.last_dream_summary:
        state.last_dream_summary = existing.last_dream_summary
    save_pulse_state(state)
    return state


def seconds_until_wake(state: AgentPulseState | None = None) -> float:
    tz = policy_timezone()
    now = datetime.now(tz)
    pulse = state
    if pulse is None:
        from presence_ui.heartbeat.pulse_state import load_pulse_state

        pulse = load_pulse_state()
    if pulse is None or not pulse.next_wake_at:
        return float(pulse_min_seconds())
    try:
        target = parse_iso(pulse.next_wake_at, tz=tz)
    except ValueError:
        return float(pulse_min_seconds())
    delta = (target - now).total_seconds()
    if delta <= 0:
        return 0.0
    return min(float(pulse_max_seconds()), delta)


def _maintenance_hour() -> int:
    return max(0, min(23, int(os.getenv("PRESENCE_NIGHTLY_MAINTENANCE_HOUR", "3"))))


def _maintenance_catchup_hour() -> int:
    catchup = int(os.getenv("PRESENCE_NIGHTLY_MAINTENANCE_CATCHUP_HOUR", "7"))
    return max(_maintenance_hour() + 1, min(24, catchup))


def _auto_dream_enabled() -> bool:
    return os.getenv("PRESENCE_AUTO_DREAM", "1").lower() not in {"0", "false", "no"}


def _auto_consolidate_enabled() -> bool:
    return os.getenv("PRESENCE_AUTO_CONSOLIDATE", "1").lower() not in {"0", "false", "no"}


def _maintenance_recently_done(
    now: datetime,
    last_iso: str | None,
    *,
    min_hours: int = 20,
) -> bool:
    if not last_iso:
        return False
    try:
        last = parse_iso(last_iso, tz=now.tzinfo or policy_timezone())
        return (now - last).total_seconds() < min_hours * 3600
    except ValueError:
        return False


def _in_nightly_maintenance_window(now: datetime) -> bool:
    """03:00 slot plus catch-up until quiet hours end (~07:00)."""
    return _maintenance_hour() <= now.hour < _maintenance_catchup_hour()


def _needs_nightly_dream(pulse: AgentPulseState | None, now: datetime) -> bool:
    if not _auto_dream_enabled():
        return False
    last = pulse.last_dream_at if pulse else None
    return not _maintenance_recently_done(now, last)


def _needs_nightly_consolidate(pulse: AgentPulseState | None, now: datetime) -> bool:
    if not _auto_consolidate_enabled():
        return False
    last = pulse.last_consolidate_at if pulse else None
    return not _maintenance_recently_done(now, last)


def seconds_until_maintenance_wake(state: AgentPulseState | None = None) -> float | None:
    """Seconds until the fixed nightly maintenance slot (default 03:00 JST).

    Returns None when dream and consolidate were both done recently.
    Returns 0 during the catch-up window if maintenance was missed.
    """
    if not _auto_dream_enabled() and not _auto_consolidate_enabled():
        return None
    from presence_ui.heartbeat.pulse_state import load_pulse_state

    pulse = state or load_pulse_state()
    tz = policy_timezone()
    now = datetime.now(tz)
    need_dream = _needs_nightly_dream(pulse, now)
    need_consolidate = _needs_nightly_consolidate(pulse, now)
    if not need_dream and not need_consolidate:
        return None

    if _in_nightly_maintenance_window(now):
        return 0.0

    hour = _maintenance_hour()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target = (now + timedelta(days=1)).replace(
            hour=hour, minute=0, second=0, microsecond=0
        )
    return max(0.0, (target - now).total_seconds())


def seconds_until_next_sleep(state: AgentPulseState | None = None) -> float:
    """Sleep until the sooner of the next pulse or nightly maintenance wake."""
    pulse_delay = seconds_until_wake(state)
    maint_delay = seconds_until_maintenance_wake(state)
    if maint_delay is None:
        return pulse_delay
    return min(pulse_delay, maint_delay)


def should_run_consolidate_now(state: AgentPulseState | None = None) -> bool:
    """Once per day at the nightly maintenance slot if not done recently."""
    if not _auto_consolidate_enabled():
        return False
    tz = policy_timezone()
    now = datetime.now(tz)
    if not _in_nightly_maintenance_window(now):
        return False
    from presence_ui.heartbeat.pulse_state import load_pulse_state

    pulse = state or load_pulse_state()
    return _needs_nightly_consolidate(pulse, now)


def mark_consolidated() -> None:
    from presence_ui.heartbeat.pulse_state import load_pulse_state

    tz = policy_timezone()
    now = datetime.now(tz).isoformat()
    pulse = load_pulse_state()
    if pulse:
        pulse.last_consolidate_at = now
        save_pulse_state(pulse)
    else:
        save_pulse_state(
            AgentPulseState(
                next_wake_at=(datetime.now(tz) + timedelta(hours=6)).isoformat(),
                reason="consolidate_only",
                last_consolidate_at=now,
            )
        )


def should_run_dream_now(state: AgentPulseState | None = None) -> bool:
    """Once per day at the nightly maintenance slot if not dreamed recently."""
    if not _auto_dream_enabled():
        return False
    tz = policy_timezone()
    now = datetime.now(tz)
    if not _in_nightly_maintenance_window(now):
        return False
    from presence_ui.heartbeat.pulse_state import load_pulse_state

    pulse = state or load_pulse_state()
    return _needs_nightly_dream(pulse, now)


def mark_dreamed(*, summary: str = "") -> None:
    from presence_ui.heartbeat.pulse_state import load_pulse_state

    tz = policy_timezone()
    now = datetime.now(tz).isoformat()
    pulse = load_pulse_state()
    digest = summary.strip()[:1200] if summary else None
    if pulse:
        pulse.last_dream_at = now
        if digest:
            pulse.last_dream_summary = digest
        save_pulse_state(pulse)
    else:
        save_pulse_state(
            AgentPulseState(
                next_wake_at=(datetime.now(tz) + timedelta(hours=6)).isoformat(),
                reason="dream_only",
                last_dream_at=now,
                last_dream_summary=digest,
            )
        )
