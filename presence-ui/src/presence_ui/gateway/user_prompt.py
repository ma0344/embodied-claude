"""User prompt cleanup until Phase 2 moves sociality out of message text."""

from __future__ import annotations

import re

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


def _is_system_block_header(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in _SYSTEM_BLOCK_RES)


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


def _block_indices(lines: list[str], header_index: int, next_header: int | None) -> range:
    if next_header is not None:
        return range(header_index, next_header)

    header = lines[header_index]
    start = header_index + 1
    end = len(lines)

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

    return range(header_index, header_index + 1)


def strip_enriched_user_prompt(text: str) -> str:
    """Remove prepended sociality blocks from stored user prompts (Phase 1 only)."""
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
