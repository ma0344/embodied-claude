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

_GATEWAY_WRAPPER_RE = re.compile(r"^\[gateway_turn_context\b", re.I)
_INJECTION_HEADER_RE = re.compile(
    r"^\[(?:Social context|interaction_context|stm_recent|dream_digest|"
    r"recent_experiences|relevant_memories|desire_hint|associative_recall)\b",
    re.I,
)


def strip_gateway_enriched_message(message: str) -> str:
    """Extract plain user utterance from gateway-wrapped text (MEM-5g)."""
    raw = (message or "").strip()
    if not raw:
        return ""
    lines = raw.split("\n")
    if not lines or not _GATEWAY_WRAPPER_RE.match(lines[0].strip()):
        return raw
    remainder = "\n".join(lines[1:])
    if "\n\n" not in remainder:
        tail = remainder.strip()
        if not tail or _looks_like_injection_only(tail):
            return ""
        return tail
    _head, tail = remainder.rsplit("\n\n", 1)
    tail = tail.strip()
    if not tail or _looks_like_injection_only(tail):
        return ""
    return tail


def _looks_like_injection_only(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    first = stripped.split("\n", 1)[0].strip()
    if _GATEWAY_WRAPPER_RE.match(first):
        return True
    if _INJECTION_HEADER_RE.match(first):
        return True
    if first.startswith("[") and first.endswith("]"):
        return True
    return False


def sanitize_episode_summary_text(text: str) -> str:
    """Clean stored episode_close summaries (gateway injection, koyori echo)."""
    raw = (text or "").strip()
    if not raw:
        return raw

    needs_gateway_scrub = "[gateway_turn_context" in raw.lower()
    if not needs_gateway_scrub and "こより:" not in raw:
        return raw

    lines = raw.split("\n")
    out: list[str] = []
    i = 0
    last_ma_message: str | None = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("まー: "):
            msg_lines = [line[4:]]
            i += 1
            while i < len(lines) and not lines[i].startswith(("まー: ", "こより: ")):
                msg_lines.append(lines[i])
                i += 1
            msg = strip_gateway_enriched_message("\n".join(msg_lines))
            if msg.strip() and not is_trivial_turn(msg):
                last_ma_message = msg.strip()
                out.append(f"まー: {last_ma_message[:180]}")
            else:
                last_ma_message = msg.strip() or None
            continue
        if line.startswith("こより: "):
            content = line[4:].strip()
            i += 1
            while i < len(lines) and not lines[i].startswith(("まー: ", "こより: ")):
                content = f"{content}\n{lines[i]}".strip()
                i += 1
            if last_ma_message and content.strip() == last_ma_message.strip():
                continue
            if content.strip():
                out.append(f"こより: {content[:180]}")
            continue
        if line.strip() == "【会話の一区切り】":
            if not out or out[0] != line:
                out.insert(0, line)
        elif line.strip() and (not needs_gateway_scrub or not _looks_like_injection_only(line)):
            out.append(line)
        i += 1
    cleaned = "\n".join(out).strip()
    return cleaned[:2000] if cleaned else raw[:2000]


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


def drop_adjacent_echo_turns(cleaned: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop koyori turns that mirror the immediately preceding ma message."""
    if not cleaned:
        return cleaned
    out: list[tuple[str, str]] = []
    for sender, message in cleaned:
        if (
            sender == "koyori"
            and out
            and out[-1][0] == "ma"
            and out[-1][1].strip() == message.strip()
        ):
            continue
        out.append((sender, message))
    return out


def normalize_episode_turns(turns: list[dict[str, Any]]) -> list[tuple[str, str]]:
    cleaned: list[tuple[str, str]] = []
    for turn in turns:
        sender = str(turn.get("sender") or "").strip().lower()
        message = str(turn.get("message") or "").strip()
        if sender == "ma":
            message = strip_gateway_enriched_message(message)
        if sender not in {"ma", "koyori"} or not message:
            continue
        cleaned.append((sender, message))
    return drop_adjacent_echo_turns(cleaned)


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
