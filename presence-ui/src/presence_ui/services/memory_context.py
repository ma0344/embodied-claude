"""MEM-4 — dream digest + STM into compose compact_prompt_block."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from interaction_orchestrator_mcp.schemas import InteractionContext
from social_core.stm import StmStore, build_stm_prompt_block

from presence_ui.deps import get_stores
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
    return record.summary.strip()


def build_live_stm_block(*, person_id: str = "ma", limit: int = 10) -> str:
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
    return build_stm_prompt_block(entries)


def enrich_memory_context(
    ctx: InteractionContext,
    *,
    person_id: str = "ma",
    channel: str | None = None,
) -> InteractionContext:
    blocks: list[str] = []
    dream_block = build_dream_digest_block(local_time=ctx.local_time, timezone=ctx.timezone)
    if dream_block:
        blocks.append(dream_block)
    stm_block = build_live_stm_block(person_id=person_id)
    if stm_block:
        blocks.append(stm_block)
    if not blocks:
        return ctx
    extra = "\n\n".join(blocks)
    compact = ctx.compact_prompt_block.strip()
    compact = f"{compact}\n\n{extra}" if compact else extra
    return ctx.model_copy(update={"compact_prompt_block": compact[:12000]})
