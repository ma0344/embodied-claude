"""STM → LTM promotion rules for Dreaming (MEM-3 / MEM-5c)."""

from __future__ import annotations

import json

from social_core.stm import StmEntry
from social_core.stm_scoring import StmScoreBreakdown, score_stm_batch, score_stm_entry


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


def build_dream_digest(entries: list[StmEntry], *, max_chars: int = 2400) -> str:
    """Overnight digest for MEM-4 morning compose injection."""
    if not entries:
        return ""
    lines = ["[dream_digest]"]
    total = len("[dream_digest]\n[/dream_digest]")
    for entry in entries:
        line = f"- ({entry.kind}) {entry.summary[:220]}"
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    lines.append("[/dream_digest]")
    return "\n".join(lines)


def memory_category_for_stm(entry: StmEntry) -> str:
    if entry.kind in {"body_affliction", "agent_boundary"}:
        return "feeling"
    if entry.kind in {"interpretation_shift", "agent_private_reflection"}:
        return "philosophical"
    if entry.source == "episode_summary":
        return "conversation"
    return "daily"
