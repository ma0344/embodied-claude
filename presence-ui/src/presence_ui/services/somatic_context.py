"""Inject somatic / body_state into compose + plan (BIO-8c)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import InteractionContext

from presence_ui.services.body_state import (
    load_body_state,
    mark_reports_reflected,
    mark_reports_reported,
    save_body_state,
    somatic_state_dict,
    unreported_pending,
)


def _local_hour(local_time: str, timezone: str) -> int | None:
    try:
        dt = datetime.fromisoformat(local_time.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone))
        return dt.astimezone(ZoneInfo(timezone)).hour
    except (ValueError, KeyError):
        return None


def is_morning_digest_window(*, local_time: str, timezone: str) -> bool:
    hour = _local_hour(local_time, timezone)
    return hour is not None and 6 <= hour < 10


def build_somatic_prompt_block(
    *,
    somatic: dict[str, Any],
    quiet_active: bool,
    local_time: str,
    timezone: str,
    channel: str,
    user_text: str | None,
) -> str:
    lines = ["[somatic_state]"]
    degraded = somatic.get("degraded_organs") or []
    if degraded:
        for item in degraded[:4]:
            organ_ja = item.get("organ_ja") or item.get("organ")
            lines.append(
                f"- {organ_ja}: {item.get('status')} — {(item.get('summary') or '')[:120]}"
            )
    else:
        lines.append("- 器官はおおむね正常（直近 probe）")

    pending = somatic.get("pending_unreported") or []
    if pending:
        lines.append("[pending_body_reports — まだまーに伝えていない]")
        for item in pending[:5]:
            lines.append(f"- {item.get('summary', '')[:160]}")
        if quiet_active:
            lines.append(
                "夜間: まーに話さない。内省に一行だけ触れる。朝になったら短く報告。"
            )
        elif channel in ("chat", "voice") and (user_text or "").strip():
            lines.append("日中・会話中: 自然に一声で伝えてよい（騒がしくしない）。")
        elif is_morning_digest_window(local_time=local_time, timezone=timezone):
            lines.append("朝: 未報告の体のことは短くまとめて伝える。")

    escalation = somatic.get("escalation") or {}
    esc_level = str(escalation.get("level") or "none")
    if esc_level != "none":
        lines.append(f"[somatic_escalation: {esc_level}]")
        for reason in (escalation.get("reasons") or [])[:3]:
            lines.append(f"- {reason}")
        if esc_level == "critical":
            lines.append(
                "複数器官が同時にダメ: health_safety としてまーに助けを求めてよい "
                "（quiet hours でも push / 一声は boundary が許す場合）"
            )
        elif esc_level == "elevated":
            lines.append("複数の不調: 自己対処が効かなければまーに頼る。")

    lines.append("[/somatic_state]")
    return "\n".join(lines)


def quiet_from_context(ctx: InteractionContext) -> bool:
    return bool(ctx.boundary_hints and any("quiet" in h.lower() for h in ctx.boundary_hints))


def enrich_interaction_context(
    ctx: InteractionContext,
    *,
    quiet_active: bool | None = None,
    channel: str | None = None,
    user_text: str | None = None,
) -> InteractionContext:
    """Append somatic block and attach somatic_state for plan."""
    state = load_body_state()
    somatic = somatic_state_dict(state)
    quiet = quiet_active
    if quiet is None:
        quiet = bool(ctx.boundary_hints and any("quiet" in h.lower() for h in ctx.boundary_hints))
    block = build_somatic_prompt_block(
        somatic=somatic,
        quiet_active=bool(quiet),
        local_time=ctx.local_time,
        timezone=ctx.timezone,
        channel=channel or "chat",
        user_text=user_text,
    )
    compact = ctx.compact_prompt_block.strip()
    if compact:
        compact = f"{compact}\n\n{block}"
    else:
        compact = block
    from presence_ui.gateway.prompt_block_safe import truncate_prompt_text

    max_len = 12000
    ctx = ctx.model_copy(
        update={
            "compact_prompt_block": truncate_prompt_text(compact, max_len),
            "somatic_state": somatic,
        }
    )
    from presence_ui.services.memory_context import enrich_memory_context

    return enrich_memory_context(ctx, person_id=ctx.person_id or "ma", channel=channel)


def apply_somatic_plan_side_effects(
    *,
    primary_move: str,
    channel: str,
    quiet_active: bool,
    local_time: str,
    timezone: str,
    user_text: str | None,
) -> None:
    """Mark pending reports after plan chose to tell ma or reflect."""
    state = load_body_state()
    pending = unreported_pending(state)
    if not pending:
        return
    if primary_move == "write_private_reflection" and quiet_active:
        mark_reports_reflected(state)
        save_body_state(state)
        return
    if primary_move in {"answer_directly", "answer_with_empathy", "talk_to_companion"}:
        if channel in ("chat", "voice") and (user_text or "").strip():
            mark_reports_reported(state)
            if is_morning_digest_window(local_time=local_time, timezone=timezone):
                state.last_morning_digest_at = state.updated_at
            save_body_state(state)
