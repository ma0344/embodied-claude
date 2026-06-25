"""MEM-8e encode path — STM + relationship profile gist (+ optional LTM promote)."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from social_core import utc_now
from social_core.stm import StmStore

from presence_ui.deps import get_stores

_HOOKS = Path(__file__).resolve().parents[4] / ".claude" / "hooks"
if _HOOKS.is_dir() and str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

import memory_auto_save as _mas  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SelfDisclosureEncodeOutcome:
    encoded: bool = False
    gist: str | None = None
    stm_entry_id: str | None = None
    ltm_saved: bool = False
    ltm_memory_id: str | None = None
    duplicate_ltm: bool = False


def encode_self_disclosure_if_any(
    *,
    person_id: str,
    text: str,
    session_id: str | None,
    ts: str | None = None,
    source_event_id: str | None = None,
    skip_ltm: bool = False,
) -> SelfDisclosureEncodeOutcome:
    """Broad encode for declarative self-disclosure / entity corrections."""
    if _mas.detect_remember_intent(text) or _mas.detect_personal_fact_intent(text):
        return SelfDisclosureEncodeOutcome(encoded=False)

    intent = _mas.detect_self_disclosure(text)
    if not intent:
        return SelfDisclosureEncodeOutcome(encoded=False)

    when = ts or utc_now()
    stores = get_stores()
    try:
        stores.relationship.record_self_disclosure_gist(
            person_id=person_id,
            text=intent.text,
            gist=intent.gist,
            ts=when,
            source_event_id=source_event_id,
        )
    except Exception:
        logger.exception("record_self_disclosure_gist failed")

    stm_entry_id: str | None = None
    try:
        entry = StmStore(stores.db).append(
            summary=f"(self_disclosure) {intent.gist}",
            kind="self_disclosure",
            source="manual",
            ts=when,
            person_id=person_id,
            session_id=session_id,
            importance=4 if intent.promote_ltm else 3,
            metadata={"full_text": intent.text[:500]},
        )
        stm_entry_id = entry.entry_id
    except Exception:
        logger.exception("STM self_disclosure append failed")

    ltm_saved = False
    ltm_memory_id: str | None = None
    duplicate_ltm = False
    if not skip_ltm and intent.promote_ltm and intent.ltm_content:
        outcome = _mas.persist_remember_intent(
            _mas.RememberIntent(content=intent.ltm_content, category="memory")
        )
        ltm_saved = outcome.ok
        ltm_memory_id = outcome.memory_id
        duplicate_ltm = outcome.duplicate

    return SelfDisclosureEncodeOutcome(
        encoded=True,
        gist=intent.gist,
        stm_entry_id=stm_entry_id,
        ltm_saved=ltm_saved,
        ltm_memory_id=ltm_memory_id,
        duplicate_ltm=duplicate_ltm,
    )
