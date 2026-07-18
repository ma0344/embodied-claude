"""MEM-8e — surface [person_profile_gists] only when the turn cues identity/work."""

from __future__ import annotations

import re

from interaction_orchestrator_mcp.recall_query import is_temporal_question

# Deterministic entity / identity cues — not open-ended NL topic filters.
_PROFILE_SURFACE_CUES = re.compile(
    r"ここっち|こっち|ねっとわん|ネットワン|netone|"
    r"グループホーム|コモンセンス|COMMON\s*SENSE|"
    r"仕事|会社|所属|どこ勤務|何の会社|誰の|何者",
    re.IGNORECASE,
)


def profile_surface_cued(user_text: str | None) -> bool:
    text = (user_text or "").strip()
    if len(text) < 2:
        return False
    if _PROFILE_SURFACE_CUES.search(text):
        return True
    if is_temporal_question(text) and any(
        token in text for token in ("ねっとわん", "ネットワン", "仕事", "ここっち")
    ):
        return True
    return False


def select_profile_gists_for_surface(
    gists: list[str],
    *,
    user_text: str | None,
    max_gists: int = 3,
) -> list[str]:
    """Return gists for compose inject — empty unless the turn cues profile topics.

    Backend recall / schedule_facts still use the full gist list separately.
    """
    cleaned = [g.strip() for g in gists if g and g.strip()]
    if not cleaned or not profile_surface_cued(user_text):
        return []
    text = (user_text or "").strip()
    overlapping = [g for g in cleaned if any(tok in g for tok in _cue_tokens(text))]
    if overlapping:
        return overlapping[:max_gists]
    return cleaned[:max_gists]


def _cue_tokens(text: str) -> list[str]:
    tokens = [
        "ここっち",
        "こっち",
        "ねっとわん",
        "ネットワン",
        "グループホーム",
        "コモンセンス",
        "仕事",
        "会社",
    ]
    return [tok for tok in tokens if tok in text]
