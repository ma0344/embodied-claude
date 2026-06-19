"""Dreaming job — MEM-3 STM replay → LTM + consolidate + daybook."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from social_core import utc_now
from social_core.stm import StmStore
from social_core.stm_dreaming import (
    build_dream_digest,
    emotion_for_ltm,
    entries_to_promote,
    memory_category_for_stm,
)

from presence_ui.deps import get_stores
from presence_ui.gateway.memory_http import http_consolidate, http_remember
from presence_ui.services.dream_digest import DreamDigestRecord, save_dream_digest

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DreamingResult:
    ok: bool
    skipped: bool = False
    reason: str | None = None
    remembered_count: int = 0
    stm_marked: int = 0
    consolidate_ok: bool = False
    consolidate_stats: dict[str, Any] | None = None
    digest_summary: str = ""
    daybook_day: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skipped": self.skipped,
            "reason": self.reason,
            "remembered_count": self.remembered_count,
            "stm_marked": self.stm_marked,
            "consolidate_ok": self.consolidate_ok,
            "consolidate_stats": self.consolidate_stats,
            "digest_summary": self.digest_summary,
            "daybook_day": self.daybook_day,
        }


def _policy_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(get_stores().policy_timezone)
    except Exception:
        return ZoneInfo("Asia/Tokyo")


def _dream_target_day(*, tz: ZoneInfo, now: datetime | None = None) -> str:
    """During night pulse, dream the calendar day that just ended."""
    current = now or datetime.now(tz)
    return (current - timedelta(days=1)).date().isoformat()


def run_dreaming_job(
    *,
    person_id: str = "ma",
    local_day: str | None = None,
    force: bool = False,
) -> DreamingResult:
    stores = get_stores()
    tz = _policy_timezone()
    stm = StmStore(stores.db)
    day = local_day or _dream_target_day(tz=tz)

    entries = stm.recent(person_id=person_id, limit=80, local_day=day, undreamed_only=True)
    if not entries and force:
        entries = stm.recent(person_id=person_id, limit=80, undreamed_only=True)
        if entries:
            day = entries[0].local_day
    if not entries:
        return DreamingResult(ok=True, skipped=True, reason="no_undreamed_stm")

    promote = entries_to_promote(entries)
    remembered = 0
    for entry in promote:
        result = http_remember(
            content=entry.summary,
            category=memory_category_for_stm(entry),
            emotion=emotion_for_ltm(entry),
            importance=max(2, min(entry.importance, 5)),
        )
        if result.get("ok") is True or result.get("memory_id"):
            remembered += 1
        else:
            logger.warning(
                "Dreaming remember failed for %s: %s",
                entry.entry_id,
                result.get("error"),
            )

    consolidate = http_consolidate()
    consolidate_ok = bool(consolidate.get("ok"))
    stats = consolidate.get("stats")
    consolidate_stats = stats if isinstance(stats, dict) else None
    if not consolidate_ok:
        logger.warning("Dreaming consolidate failed: %s", consolidate.get("error"))

    daybook_day: str | None = None
    try:
        daybook = stores.self_narrative.append_daybook(day=day)
        daybook_day = daybook.day
    except Exception as exc:
        logger.warning("Dreaming daybook failed: %s", exc)

    digest_summary = build_dream_digest(entries)
    dreamed_at = utc_now()
    marked = stm.mark_dreamed([entry.entry_id for entry in entries], dreamed_at=dreamed_at)

    save_dream_digest(
        DreamDigestRecord(
            dreamed_at=dreamed_at,
            local_day=day,
            summary=digest_summary,
            stm_entry_ids=[entry.entry_id for entry in entries],
            remembered_count=remembered,
            consolidate_ok=consolidate_ok,
            consolidate_stats=consolidate_stats,
            daybook_day=daybook_day,
        )
    )

    return DreamingResult(
        ok=True,
        skipped=False,
        remembered_count=remembered,
        stm_marked=marked,
        consolidate_ok=consolidate_ok,
        consolidate_stats=consolidate_stats,
        digest_summary=digest_summary,
        daybook_day=daybook_day,
    )
