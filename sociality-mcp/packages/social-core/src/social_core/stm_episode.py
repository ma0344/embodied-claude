"""Episode closure helpers — MEM-2 rule-based WM→STM summarization."""

from __future__ import annotations

import re
from typing import Any

_TRIVIAL_EXACT = frozenset(
    {
        "ok",
        "okay",
        "うん",
        "はい",
        "いいえ",
        "ん",
        "んー",
        "うーん",
        "了解",
        "りょ",
        "りょう",
        "なるほど",
        "そう",
        "そっか",
        "そうだね",
        "そうだな",
        "ありがと",
        "ありがとう",
        "どうも",
        "おはよう",
        "おはようございます",
        "こんにちは",
        "こんばんは",
        "おやすみ",
        "おやすみなさい",
        "やあ",
        "hi",
        "hello",
        "bye",
        "バイバイ",
    }
)

_GREETING_PREFIX = re.compile(
    r"^(おはよう|こんにちは|こんばんは|やあ|hi|hello|おやすみ)[!！。…~\s]*$",
    re.IGNORECASE,
)


def is_trivial_turn(message: str) -> bool:
    text = message.strip()
    if not text:
        return True
    if len(text) <= 2:
        return True
    lowered = text.lower()
    if lowered in _TRIVIAL_EXACT:
        return True
    if _GREETING_PREFIX.match(text):
        return True
    return False


def normalize_episode_turns(turns: list[dict[str, Any]]) -> list[tuple[str, str]]:
    cleaned: list[tuple[str, str]] = []
    for turn in turns:
        sender = str(turn.get("sender") or "").strip().lower()
        message = str(turn.get("message") or "").strip()
        if sender not in {"ma", "koyori"} or not message:
            continue
        cleaned.append((sender, message))
    return cleaned


def summarize_episode_turns(turns: list[dict[str, Any]]) -> str | None:
    """Build a compact episode summary without LLM. None if not worth storing."""
    cleaned = normalize_episode_turns(turns)
    if not cleaned:
        return None

    substantive = [(sender, message) for sender, message in cleaned if not is_trivial_turn(message)]
    total_chars = sum(len(message) for _, message in cleaned)
    if len(substantive) < 2 and total_chars < 48:
        return None

    selected = substantive if substantive else cleaned
    lines = ["【会話の一区切り】"]
    for sender, message in selected[:8]:
        label = "まー" if sender == "ma" else "こより"
        lines.append(f"{label}: {message[:180]}")
    return "\n".join(lines)[:2000]
