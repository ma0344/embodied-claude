"""MEM-4 — dream digest + STM into compose compact_prompt_block."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import InteractionContext
from social_core.stm import StmStore, build_stm_prompt_block

from presence_ui.deps import get_stores
from presence_ui.gateway.context_limits import enrich_max_chars, lite_stm_max_chars
from presence_ui.gateway.prompt_block_safe import truncate_prompt_text
from presence_ui.services.dream_digest import load_dream_digest
from presence_ui.services.somatic_context import is_morning_digest_window


def _parse_local_ts(ts: str, timezone: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone))
        return dt.astimezone(ZoneInfo(timezone))
    except (ValueError, KeyError):
        return None


def _local_date_iso(local_time: str, timezone: str) -> str | None:
    parsed = _parse_local_ts(local_time, timezone)
    return parsed.date().isoformat() if parsed else None


def _morning_temporal_fence(*, source_day: str, today: str, kind: str) -> str:
    """Label overnight blocks so the model does not treat yesterday as today."""
    if not source_day or not today or source_day == today:
        return ""
    return (
        f"[morning_context — {kind} は {source_day} の記録。"
        f"今日は {today}。昨日の予定・会話を今日の予定として言わない]"
    )


def build_dream_digest_block(*, local_time: str, timezone: str) -> str:
    """Surface overnight dream summary during morning compose (MEM-4)."""
    if not is_morning_digest_window(local_time=local_time, timezone=timezone):
        return ""
    record = load_dream_digest()
    if record is None or not record.summary.strip():
        return ""
    dreamed = _parse_local_ts(record.dreamed_at, timezone)
    if dreamed is None:
        return ""
    now = _parse_local_ts(local_time, timezone)
    if now is None:
        return ""
    if (now - dreamed).total_seconds() > 36 * 3600:
        return ""
    body = record.summary.strip()
    today = _local_date_iso(local_time, timezone) or ""
    fence = _morning_temporal_fence(
        source_day=record.local_day,
        today=today,
        kind="dream_digest",
    )
    if fence:
        return f"{fence}\n{body}"
    return body


def build_overnight_inner_voice_block(*, local_time: str, timezone: str) -> str:
    """Surface synthesized overnight inner voice during morning compose (MEM-5f-c)."""
    if not is_morning_digest_window(local_time=local_time, timezone=timezone):
        return ""
    record = load_dream_digest()
    if record is None or not (record.inner_voice_summary or "").strip():
        return ""
    dreamed = _parse_local_ts(record.dreamed_at, timezone)
    if dreamed is None:
        return ""
    now = _parse_local_ts(local_time, timezone)
    if now is None:
        return ""
    if (now - dreamed).total_seconds() > 36 * 3600:
        return ""
    body = (record.inner_voice_summary or "").strip()
    today = _local_date_iso(local_time, timezone) or ""
    fence = _morning_temporal_fence(
        source_day=record.local_day,
        today=today,
        kind="overnight_inner_voice",
    )
    if fence:
        return f"{fence}\n{body}"
    return body


def build_live_stm_block(
    *,
    person_id: str = "ma",
    limit: int = 10,
    max_chars: int | None = None,
) -> str:
    """Today's undreamed STM buffer for conversational continuity."""
    stores = get_stores()
    stm = StmStore(stores.db)
    tz = stores.policy_timezone
    try:
        today = datetime.now(ZoneInfo(tz)).date().isoformat()
    except Exception:
        today = None
    entries = stm.recent(
        person_id=person_id,
        limit=limit,
        local_day=today,
        undreamed_only=True,
    )
    if not entries:
        entries = stm.recent(person_id=person_id, limit=limit, undreamed_only=True)
    block = build_stm_prompt_block(entries)
    if max_chars and len(block) > max_chars:
        block = truncate_prompt_text(block, max_chars)
    return block


def enrich_memory_context(
    ctx: InteractionContext,
    *,
    person_id: str = "ma",
    channel: str | None = None,
    user_text: str | None = None,
) -> InteractionContext:
    blocks: list[str] = []
    dream_block = build_dream_digest_block(local_time=ctx.local_time, timezone=ctx.timezone)
    if dream_block:
        blocks.append(dream_block)
    inner_voice_block = build_overnight_inner_voice_block(
        local_time=ctx.local_time,
        timezone=ctx.timezone,
    )
    if inner_voice_block:
        blocks.append(inner_voice_block)
    stm_limit = 10
    stm_max_chars = lite_stm_max_chars() if channel == "chat" else None
    stm_block = build_live_stm_block(
        person_id=person_id,
        limit=stm_limit,
        max_chars=stm_max_chars,
    )
    if stm_block:
        blocks.append(stm_block)
    if not blocks:
        return ctx
    extra = "\n\n".join(blocks)
    compact = ctx.compact_prompt_block.strip()
    compact = f"{compact}\n\n{extra}" if compact else extra
    return ctx.model_copy(
        update={"compact_prompt_block": truncate_prompt_text(compact, enrich_max_chars())}
    )
