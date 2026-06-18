"""STM → LTM promotion rules for Dreaming (MEM-3)."""

from __future__ import annotations

from social_core.stm import STM_AUTO_MIRROR_KINDS, STM_AUTO_MIRROR_MIN_IMPORTANCE, StmEntry

DREAM_PROMOTE_SOURCES = frozenset({"episode_summary", "experience_mirror"})


def should_promote_stm_to_ltm(entry: StmEntry) -> bool:
    """Whether an STM row should be written to LTM during Dreaming."""
    if entry.source in DREAM_PROMOTE_SOURCES:
        return True
    if entry.kind in STM_AUTO_MIRROR_KINDS:
        return True
    if entry.importance >= STM_AUTO_MIRROR_MIN_IMPORTANCE:
        return True
    if entry.source == "wm_flush" and entry.kind.startswith("wm_turn_"):
        return False
    return False


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
