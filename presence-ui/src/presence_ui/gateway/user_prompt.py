"""User prompt cleanup until Phase 2 moves sociality out of message text."""

from __future__ import annotations

import re


def _normalize_newlines(text: str) -> str:
    """CRLF/CR → LF so ``\\n\\n`` utterance anchors work on Windows JSONL."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


# Phase 1 fallback for history JSONL where sociality was prepended to user text.
_SYSTEM_BLOCK_RES = (
    re.compile(r"^\[Social context\]\s*$", re.I),
    re.compile(r"^\[gateway_turn_context\b", re.I),
    re.compile(r"^\[interaction_context\]\s*$", re.I),
    re.compile(r"^\[response_contract\]\s*$", re.I),
    re.compile(r"^\[recent_room_context\b", re.I),
    re.compile(r"^\[Must include\]", re.I),
    re.compile(r"^\[Must avoid\]", re.I),
    re.compile(r"^\[Social move\b", re.I),
    re.compile(r"^\[memory_saved_server\]", re.I),
    re.compile(r"^\[memory_save_failed\]", re.I),
    re.compile(r"^\[memory_list_prefetch\]", re.I),
    re.compile(r"^\[vision_prefetch\]\s*$", re.I),
    re.compile(r"^\[web_search_prefetch\]\s*$", re.I),
    re.compile(r"^\[/web_search_prefetch\]", re.I),
    re.compile(r"^\[calendar_prefetch\]\s*$", re.I),
    re.compile(r"^\[/calendar_prefetch\]", re.I),
    re.compile(r"^\[calendar_write_result\]\s*$", re.I),
    re.compile(r"^\[/calendar_write_result\]", re.I),
    re.compile(r"^\[calendar_confirm_pending\]\s*$", re.I),
    re.compile(r"^\[/calendar_confirm_pending\]", re.I),
    re.compile(r"^\[url_prefetch\]\s*$", re.I),
    re.compile(r"^\[/url_prefetch\]", re.I),
    re.compile(r"^\[Gateway directive\b", re.I),
    re.compile(r"^\[stm_recent\]\s*$", re.I),
    re.compile(r"^\[/stm_recent\]", re.I),
    re.compile(r"^\[dream_digest\]\s*$", re.I),
    re.compile(r"^\[/dream_digest\]", re.I),
    re.compile(r"^\[overnight_inner_voice\]\s*$", re.I),
    re.compile(r"^\[/overnight_inner_voice\]", re.I),
    re.compile(r"^\[inbound_nudge\b", re.I),
    re.compile(r"^\[inbound_reply\b", re.I),
    re.compile(r"^\[somatic_state\]\s*$", re.I),
    re.compile(r"^\[relevant_memories\]\s*$", re.I),
    re.compile(r"^\[commitments_due\]\s*$", re.I),
    re.compile(r"^\[interpretation_shifts\]\s*$", re.I),
    re.compile(r"^\[desires\]\s*$", re.I),
)

_DIRECTIVE_BLOCK_RES = (
    re.compile(r"^\[memory_saved_server\]", re.I),
    re.compile(r"^\[memory_save_failed\]", re.I),
    re.compile(r"^\[memory_list_prefetch\]", re.I),
    re.compile(r"^\[vision_prefetch\]\s*$", re.I),
    re.compile(r"^\[web_search_prefetch\]\s*$", re.I),
    re.compile(r"^\[/web_search_prefetch\]", re.I),
    re.compile(r"^\[calendar_prefetch\]\s*$", re.I),
    re.compile(r"^\[/calendar_prefetch\]", re.I),
    re.compile(r"^\[calendar_write_result\]\s*$", re.I),
    re.compile(r"^\[/calendar_write_result\]", re.I),
    re.compile(r"^\[calendar_confirm_pending\]\s*$", re.I),
    re.compile(r"^\[/calendar_confirm_pending\]", re.I),
    re.compile(r"^\[url_prefetch\]\s*$", re.I),
    re.compile(r"^\[/url_prefetch\]", re.I),
    re.compile(r"^\[Gateway directive\b", re.I),
)

_PAIRED_BLOCK_OPENERS = {
    "[stm_recent]": "[/stm_recent]",
    "[dream_digest]": "[/dream_digest]",
    "[overnight_inner_voice]": "[/overnight_inner_voice]",
}

_STM_BULLET_RE = re.compile(r"^- \([a-z_]+\)", re.I)

_STM_ORPHAN_LINE_RES = (
    _STM_BULLET_RE,
    re.compile(r"^(まー|こより):\s+", re.I),
    re.compile(r"^【会話の一区切り】"),
)

_GATEWAY_WRAPPER_RE = re.compile(r"^\[gateway_turn_context\b", re.I)

_TAIL_PREFETCH_RES = (
    re.compile(r"\n\[url_prefetch\][\s\S]*$", re.I),
    re.compile(r"\n\[web_search_prefetch\][\s\S]*$", re.I),
    re.compile(r"\n\[calendar_prefetch\][\s\S]*$", re.I),
    re.compile(r"\n\[calendar_write_result\][\s\S]*$", re.I),
    re.compile(r"\n\[calendar_confirm_pending\][\s\S]*$", re.I),
    re.compile(r"\n\[vision_prefetch\][\s\S]*$", re.I),
)

_ROOM_CONTEXT_BODY_RES = (
    re.compile(r"^Room arc:", re.I),
    re.compile(r"^Last speaker:", re.I),
    re.compile(r"^Conversation in THIS room only", re.I),
    re.compile(r"^(まー|こより):\s+"),
)

_CONTRACT_BODY_RES = (
    re.compile(r"^treat_user_as:", re.I),
    re.compile(r"^avoid:", re.I),
    re.compile(r"^prefer:", re.I),
    re.compile(r"^initiative:", re.I),
    re.compile(r"^[a-z_]+=", re.I),
)

_CONTEXT_HEADER_RES = (
    re.compile(r"^\[Social context\]\s*$", re.I),
    re.compile(r"^\[interaction_context\]\s*$", re.I),
)

_AGENT_SLASH_COMMAND_RE = re.compile(r"^#\s*/\w+", re.MULTILINE)


def _is_system_block_header(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in _SYSTEM_BLOCK_RES)


def _is_directive_block_header(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in _DIRECTIVE_BLOCK_RES)


def _is_context_header(header_line: str) -> bool:
    stripped = header_line.strip()
    return any(pattern.match(stripped) for pattern in _CONTEXT_HEADER_RES)


def _is_room_context_body(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(pattern.search(stripped) for pattern in _ROOM_CONTEXT_BODY_RES)


def _is_contract_body(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(pattern.search(stripped) for pattern in _CONTRACT_BODY_RES)


def _paired_block_close(header: str) -> str | None:
    key = header.strip().casefold()
    for opener, closer in _PAIRED_BLOCK_OPENERS.items():
        if key == opener:
            return closer
    return None


def _block_indices(lines: list[str], header_index: int, next_header: int | None) -> range:
    if next_header is not None:
        return range(header_index, next_header)

    header = lines[header_index]
    start = header_index + 1
    end = len(lines)

    paired_close = _paired_block_close(header)
    if paired_close is not None:
        close_cf = paired_close.casefold()
        while start < end:
            line_cf = lines[start].strip().casefold()
            if line_cf == close_cf or line_cf.startswith(close_cf):
                start += 1
                break
            start += 1
        return range(header_index, start)

    if header.strip().startswith("[recent_room_context"):
        while start < end and _is_room_context_body(lines[start]):
            start += 1
        return range(header_index, start)

    if header.strip().casefold() == "[response_contract]":
        while start < end and _is_contract_body(lines[start]):
            start += 1
        return range(header_index, start)

    if _is_context_header(header):
        while start < end and lines[start].strip():
            start += 1
        while start < end and not lines[start].strip():
            start += 1
        return range(header_index, start)

    if header.strip().startswith("[gateway_turn_context"):
        # Wrapper only — nested blocks are stripped on later passes.
        return range(header_index, header_index + 1)

    if header.strip().startswith("[inbound_nudge"):
        while start < end and lines[start].strip():
            start += 1
        while start < end and not lines[start].strip():
            start += 1
        return range(header_index, start)

    if header.strip().startswith("[inbound_reply"):
        while start < end and lines[start].strip():
            start += 1
        while start < end and not lines[start].strip():
            start += 1
        return range(header_index, start)

    if _is_directive_block_header(header):
        while start < end and lines[start].strip():
            start += 1
        while start < end and not lines[start].strip():
            start += 1
        return range(header_index, start)

    return range(header_index, header_index + 1)


def _strip_one_trailing_tail_prefetch(remainder: str) -> tuple[str, bool]:
    """Drop KV-tail prefetch blocks appended after the user utterance."""
    for pattern in _TAIL_PREFETCH_RES:
        match = pattern.search(remainder)
        if match:
            return remainder[: match.start()].rstrip(), True
    return remainder, False


def _strip_trailing_tail_prefetch(remainder: str) -> str:
    out = remainder or ""
    for _ in range(5):
        out, changed = _strip_one_trailing_tail_prefetch(out)
        if not changed:
            break
    return out


def _strip_gateway_wrapper_tail(text: str) -> str | None:
    """Extract user utterance from prepend_gateway_turn_context format.

    Enriched prompts are ``[gateway_turn_context…]\\n{body}\\n\\n{utterance}``.
    The body may contain blank lines, unclosed [stm_recent], and nested headers;
    the reliable anchor is the final ``\\n\\n`` before the user's words.
    """
    raw = _normalize_newlines(text)
    if not raw.strip():
        return ""
    lines = raw.split("\n")
    if not lines or not _GATEWAY_WRAPPER_RE.match(lines[0].strip()):
        return None
    remainder = "\n".join(lines[1:])
    remainder = _strip_trailing_tail_prefetch(remainder)
    if "\n\n" not in remainder:
        tail = remainder.strip()
        return tail if tail and not looks_like_injected_prompt(tail) else None
    _head, tail = remainder.rsplit("\n\n", 1)
    tail = tail.strip()
    if not tail or looks_like_injected_prompt(tail):
        return None
    return tail


def _strip_enriched_user_prompt_once(text: str) -> str:
    raw = text or ""
    if not raw.strip():
        return ""

    lines = raw.split("\n")
    header_indices = [index for index, line in enumerate(lines) if _is_system_block_header(line)]
    if not header_indices:
        return raw.strip()

    blocked: set[int] = set()
    for position, header_index in enumerate(header_indices):
        next_header = (
            header_indices[position + 1] if position + 1 < len(header_indices) else None
        )
        for index in _block_indices(lines, header_index, next_header):
            blocked.add(index)

    kept = [lines[index] for index in range(len(lines)) if index not in blocked]
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept).strip()


def _strip_leading_orphan_injection_lines(text: str) -> str:
    lines = text.split("\n")
    while lines:
        line = lines[0].strip()
        if not line:
            lines.pop(0)
            continue
        if any(pattern.search(line) for pattern in _STM_ORPHAN_LINE_RES):
            lines.pop(0)
            continue
        break
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def strip_enriched_user_prompt(text: str) -> str:
    """Remove prepended sociality blocks from stored user prompts (Phase 1 only)."""
    raw = _normalize_newlines(text)
    if not raw.strip():
        return ""

    # Gateway-wrapped prompts: final ``\n\n`` segment is authoritative. Truncated
    # compose may leave orphan episode prose and ``[/stm_recent]…`` that iterative
    # strip mis-identifies as the user's utterance.
    first_line = raw.split("\n", 1)[0].strip()
    if _GATEWAY_WRAPPER_RE.match(first_line):
        tail = _strip_gateway_wrapper_tail(raw)
        if tail is not None:
            return tail

    current = raw
    for _ in range(12):
        nxt = _strip_enriched_user_prompt_once(current)
        nxt = _strip_leading_orphan_injection_lines(nxt)
        if nxt == current.strip():
            break
        current = nxt
    iterative = current.strip()

    if iterative and not looks_like_injected_prompt(iterative):
        return iterative
    return iterative


def looks_like_injected_prompt(text: str) -> bool:
    """True when stored user text contains gateway/sociality block headers."""
    for line in (text or "").split("\n"):
        if _is_system_block_header(line):
            return True
        if _STM_BULLET_RE.match(line.strip()):
            return True
    return False


def looks_like_agent_slash_command(text: str) -> bool:
    """True when Claude Code logged an expanded slash command as a user turn.

    Agent-initiated ``/observe``, ``/see``, etc. appear in session JSONL as
    ``type: user`` with the full command markdown — not something まー typed.
    """
    body = (text or "").strip()
    if not body:
        return False
    if _AGENT_SLASH_COMMAND_RE.match(body):
        return True
    return body.startswith("---") and bool(_AGENT_SLASH_COMMAND_RE.search(body))


def plain_user_first_line(text: str, *, max_len: int = 48) -> str:
    """First line of the user's utterance after stripping injected blocks."""
    plain = strip_enriched_user_prompt(text)
    if not plain:
        return ""
    line = plain.splitlines()[0].strip()
    if not line:
        return ""
    if len(line) > max_len:
        return f"{line[: max_len - 1]}…"
    return line


def session_title_from_context(
    *,
    history_title: str,
    messages: list,
    session_id: str,
    max_len: int = 48,
) -> str:
    """Pick a human-readable session title (plain first user line preferred)."""
    title = plain_user_first_line(history_title, max_len=max_len) if history_title else ""
    if not title and history_title.strip() and not looks_like_injected_prompt(history_title):
        raw = history_title.strip().splitlines()[0]
        title = raw if len(raw) <= max_len else f"{raw[: max_len - 1]}…"

    if not title:
        for msg in messages:
            sender = getattr(msg, "sender", None) or (
                msg.get("sender") if isinstance(msg, dict) else None
            )
            body = getattr(msg, "message", None) or (
                msg.get("message") if isinstance(msg, dict) else ""
            )
            if sender == "ma" and str(body or "").strip():
                title = plain_user_first_line(str(body), max_len=max_len)
                if title:
                    break

    return title or session_id[:8]
