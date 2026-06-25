"""Repair polluted STM episode_close rows and rebuild saved dream digest."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from social_core import SocialDB
from social_core.stm import StmStore
from social_core.stm_dreaming import build_dream_digest

from presence_ui.deps import reset_stores
from presence_ui.services.dream_digest import DreamDigestRecord, load_dream_digest, save_dream_digest
from presence_ui.services.overnight_inner_voice import synthesize_overnight_inner_voice


def _db_path() -> Path:
    for candidate in (
        Path.home() / ".claude" / "sociality" / "social.db",
        Path.home() / ".claude" / "social.db",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("social.db not found")


def _wire_stores(db: SocialDB) -> None:
    import presence_ui.deps as deps
    from boundary_mcp.store import BoundaryStore
    from interaction_orchestrator_mcp.store import InteractionOrchestratorStore
    from joint_attention_mcp.store import JointAttentionStore
    from relationship_mcp.store import RelationshipStore
    from self_narrative_mcp.store import SelfNarrativeStore
    from social_core.events import EventStore
    from social_state_mcp.store import SocialStateStore

    reset_stores()
    deps._local.stores = deps.PresenceStores(
        db=db,
        events=EventStore(db=db),
        social_state=SocialStateStore(db=db, quiet_hours_windows=[], policy_timezone="Asia/Tokyo"),
        relationship=RelationshipStore(db=db),
        joint_attention=JointAttentionStore(db=db),
        boundary=BoundaryStore(db=db),
        self_narrative=SelfNarrativeStore(db=db),
        orchestrator=InteractionOrchestratorStore(db=db),
        policy_timezone="Asia/Tokyo",
    )


def main() -> int:
    use_llm = os.environ.get("PRESENCE_REBUILD_INNER_VOICE_LLM", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    db = SocialDB(_db_path())
    _wire_stores(db)
    stm = StmStore(db)
    scanned, updated = stm.repair_episode_close_summaries()
    print(f"episode_close repair: scanned={scanned} updated={updated}")

    record = load_dream_digest()
    if record is None or not record.stm_entry_ids:
        print("rebuild: no saved dream digest")
        return 0

    entries = [entry for eid in record.stm_entry_ids if (entry := stm.get_entry(eid)) is not None]
    if not entries:
        print("rebuild: no stm entries for saved ids")
        return 1

    summary = build_dream_digest(entries)
    inner_voice = synthesize_overnight_inner_voice(
        entries,
        person_id="ma",
        local_day=record.local_day,
        timezone="Asia/Tokyo",
        use_llm=use_llm,
    )
    updated_record = DreamDigestRecord(
        dreamed_at=record.dreamed_at,
        local_day=record.local_day,
        summary=summary,
        stm_entry_ids=record.stm_entry_ids,
        remembered_count=record.remembered_count,
        consolidate_ok=record.consolidate_ok,
        consolidate_stats=record.consolidate_stats,
        daybook_day=record.daybook_day,
        inner_voice_summary=inner_voice or None,
    )
    save_dream_digest(updated_record)
    print("rebuild: ok")
    print("gateway in digest:", "gateway_turn_context" in summary)
    print("inner_voice:", bool(inner_voice))

    pulse = Path.home() / ".claude" / "presence-ui" / "agent_pulse.json"
    if pulse.is_file():
        data = json.loads(pulse.read_text(encoding="utf-8"))
        data["last_dream_summary"] = summary
        pulse.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("agent_pulse.json updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
