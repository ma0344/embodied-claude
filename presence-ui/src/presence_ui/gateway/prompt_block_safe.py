"""Safe truncation / repair for paired prompt injection blocks."""

from __future__ import annotations

import re

# Open/close tags that must stay balanced in compose + JSONL audit logs.
PAIRED_PROMPT_TAGS: tuple[tuple[str, str], ...] = (
    ("[stm_recent]", "[/stm_recent]"),
    ("[dream_digest]", "[/dream_digest]"),
    ("[somatic_state]", "[/somatic_state]"),
)

_GATEWAY_WRAPPER_RE = re.compile(r"^\[gateway_turn_context\b", re.I)


def _tag_count(text: str, tag: str) -> int:
    return text.lower().count(tag.lower())


def close_open_paired_tags(text: str) -> str:
    """Append missing close tags when truncation split inside a block."""
    result = (text or "").rstrip()
    for open_tag, close_tag in PAIRED_PROMPT_TAGS:
        while _tag_count(result, open_tag) > _tag_count(result, close_tag):
            result = f"{result}\n{close_tag}"
    return result


def truncate_prompt_text(text: str, max_chars: int) -> str:
    """Truncate without leaving orphaned [stm_recent] / [dream_digest] openers."""
    raw = text or ""
    if max_chars <= 0 or len(raw) <= max_chars:
        return raw
    cut = raw[:max_chars]
    if len(cut) < len(raw) and cut and raw[len(cut)] not in {"", "\n"}:
        parts = cut.rsplit("\n", 1)
        cut = parts[0] if len(parts) > 1 else cut
    cut = cut.rstrip()
    closed = close_open_paired_tags(cut)
    if len(closed) < len(raw):
        return f"{closed}…"
    return closed


def _split_gateway_user_tail(text: str) -> tuple[str, str]:
    """Return (head, user_tail) when text matches gateway wrapper + final utterance."""
    lines = text.split("\n")
    if not lines or not _GATEWAY_WRAPPER_RE.match(lines[0].strip()):
        return text, ""
    remainder = "\n".join(lines[1:])
    if "\n\n" not in remainder:
        return text, ""
    head, tail = remainder.rsplit("\n\n", 1)
    tail = tail.strip()
    if not tail:
        return text, ""
    from presence_ui.gateway.user_prompt import looks_like_injected_prompt

    if looks_like_injected_prompt(tail):
        return text, ""
    return f"{lines[0]}\n{head}", tail


def repair_enriched_user_prompt(text: str) -> str:
    """Close orphaned paired tags in stored gateway prompts (JSONL repair)."""
    raw = text or ""
    if not raw.strip():
        return raw
    head, tail = _split_gateway_user_tail(raw)
    repaired_head = close_open_paired_tags(head)
    if tail:
        return f"{repaired_head}\n\n{tail}"
    return close_open_paired_tags(raw)


def has_unclosed_paired_tags(text: str) -> bool:
    for open_tag, close_tag in PAIRED_PROMPT_TAGS:
        if _tag_count(text, open_tag) > _tag_count(text, close_tag):
            return True
    return False
