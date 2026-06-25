"""STM → LTM promotion rules for Dreaming (MEM-3 / MEM-5c / MEM-5e)."""

from __future__ import annotations

import json

from social_core.stm import StmEntry
from social_core.stm_episode import sanitize_episode_summary_text
from social_core.stm_scoring import (
    StmScoreBreakdown,
    detect_topics,
    score_stm_batch,
    score_stm_entry,
)

# MEM-5e: episodic digest — exclude inner-voice ticks and WM noise.
DIGEST_EXCLUDE_KINDS = frozenset(
    {
        "agent_private_reflection",
        "wm_turn_ma",
        "wm_turn_koyori",
    }
)

# Lower number = higher priority in morning [dream_digest].
DIGEST_KIND_PRIORITY: dict[str, int] = {
    "episode_close": 10,
    "self_disclosure": 12,
    "interpretation_shift": 15,
    "body_affliction": 20,
    "agent_boundary": 20,
    "open_loop_progress": 30,
    "agent_observation": 40,
    "agent_autonomous_action": 45,
    "desire_satisfied": 50,
    "agent_response": 55,
}

DEFAULT_DIGEST_MAX_CHARS = 2800


def _digest_priority(entry: StmEntry) -> int:
    if entry.kind in DIGEST_KIND_PRIORITY:
        return DIGEST_KIND_PRIORITY[entry.kind]
    if entry.source == "episode_summary":
        return 10
    return 60


def _dedupe_open_loop_entries(entries: list[StmEntry]) -> list[StmEntry]:
    """Keep newest open_loop_progress per overlapping topic (MEM-5 merge rule)."""
    loops = [e for e in entries if e.kind == "open_loop_progress"]
    if len(loops) <= 1:
        return entries
    rest = [e for e in entries if e.kind != "open_loop_progress"]
    kept: list[StmEntry] = []
    for entry in sorted(loops, key=lambda e: e.ts, reverse=True):
        topics = set(detect_topics(entry.summary))
        if not topics:
            kept.append(entry)
            continue
        if any(set(detect_topics(prev.summary)) & topics for prev in kept):
            continue
        kept.append(entry)
    return rest + kept


def select_episodic_digest_entries(entries: list[StmEntry]) -> list[StmEntry]:
    """Filter + order STM rows for outward-facing [dream_digest] (MEM-5e)."""
    filtered = [e for e in entries if e.kind not in DIGEST_EXCLUDE_KINDS]
    filtered = _dedupe_open_loop_entries(filtered)
    return sorted(filtered, key=lambda e: (_digest_priority(e), e.ts))


def _metadata_map(entries: list[StmEntry], metadata_by_id: dict[str, str] | None) -> dict[str, str]:
    if metadata_by_id:
        return metadata_by_id
    return {entry.entry_id: entry.metadata_json or "{}" for entry in entries}


def score_stm_for_dreaming(
    entries: list[StmEntry],
    *,
    metadata_by_id: dict[str, str] | None = None,
) -> list[StmScoreBreakdown]:
    """Score all STM rows for one dreaming pass."""
    return score_stm_batch(entries, metadata_by_id=_metadata_map(entries, metadata_by_id))


def entries_to_promote(
    entries: list[StmEntry],
    *,
    metadata_by_id: dict[str, str] | None = None,
) -> list[StmEntry]:
    """Return STM rows that should be written to LTM (MEM-5c)."""
    scores = score_stm_for_dreaming(entries, metadata_by_id=metadata_by_id)
    promote_ids = {score.entry_id for score in scores if score.decision == "promote"}
    return [entry for entry in entries if entry.entry_id in promote_ids]


def should_promote_stm_to_ltm(
    entry: StmEntry,
    *,
    day_entries: list[StmEntry] | None = None,
    metadata_json: str | None = None,
) -> bool:
    """Whether an STM row should be written to LTM during Dreaming."""
    meta = metadata_json if metadata_json is not None else (entry.metadata_json or "{}")
    result = score_stm_entry(
        entry,
        day_entries=day_entries,
        metadata_json=meta,
    )
    return result.decision == "promote"


def emotion_for_ltm(entry: StmEntry, *, metadata_json: str | None = None) -> str:
    """Pick memory-mcp emotion tag for LTM remember."""
    raw = metadata_json if metadata_json is not None else (entry.metadata_json or "{}")
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        meta = {}
    tag = meta.get("emotion_tag") if isinstance(meta, dict) else None
    if isinstance(tag, str) and tag:
        return tag
    if entry.source == "episode_summary":
        return "nostalgic"
    return "neutral"


def build_dream_digest(
    entries: list[StmEntry],
    *,
    max_chars: int = DEFAULT_DIGEST_MAX_CHARS,
) -> str:
    """Overnight episodic digest for MEM-4 morning compose injection (MEM-5e)."""
    selected = select_episodic_digest_entries(entries)
    if not selected:
        if not entries:
            return ""
        return (
            "[dream_digest]\n"
            "- (note) no episodic rows — overnight STM was mostly private reflection or WM noise\n"
            "[/dream_digest]"
        )
    lines = ["[dream_digest]"]
    total = len("[dream_digest]\n[/dream_digest]")
    for entry in selected:
        summary = entry.summary
        if entry.kind == "episode_close":
            summary = sanitize_episode_summary_text(summary)
        line = f"- ({entry.kind}) {summary[:220]}"
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    lines.append("[/dream_digest]")
    return "\n".join(lines)


def memory_category_for_stm(entry: StmEntry) -> str:
    if entry.kind == "self_disclosure":
        return "memory"
    if entry.kind in {"body_affliction", "agent_boundary"}:
        return "feeling"
    if entry.kind in {"interpretation_shift", "agent_private_reflection"}:
        return "philosophical"
    if entry.source == "episode_summary":
        return "conversation"
    return "daily"
