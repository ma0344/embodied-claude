"""Agent LW-READ encode markers — conversational surface / overnight must skip.

Conversational LTM / compose / dream_digest / memory_bridge / overnight synthesis
should not treat Aozora reading dumps as speakable material. Keep しおり /
experience.private_summary for on-demand retrieve.

Finite agent prefixes only (not open-ended NL topic filters).
"""

from __future__ import annotations

# Keep in sync with scripts/purge-literary-*.py
LITERARY_AGENT_PREFIXES: tuple[str, ...] = (
    "青空文庫で読んだ",
    "青空『",
    "（青空を読んだあと",
    "（青空 — ",
)

# Synthesized overnight prose (not prefix-shaped) that is still reading pollution.
_LITERARY_OVERNIGHT_MARKERS: tuple[str, ...] = (
    "羅生門",
    "青空文庫",
    "芥川",
    "青空『",
)


def is_literary_agent_surface(text: str) -> bool:
    """True for agent LW-READ / PAUSE encode lines (not user book talk)."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    return any(cleaned.startswith(prefix) for prefix in LITERARY_AGENT_PREFIXES)


def is_literary_overnight_contaminated(text: str) -> bool:
    """True when overnight inner-voice prose is mostly a reading chew."""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if is_literary_agent_surface(cleaned):
        return True
    return any(marker in cleaned for marker in ("羅生門", "青空文庫", "芥川龍之介"))
