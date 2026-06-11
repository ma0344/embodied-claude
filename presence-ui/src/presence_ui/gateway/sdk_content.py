"""Structural extraction from Claude Code SDK message content blocks."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DISPLAY_BLOCK_TYPE = "text"
SKIPPED_BLOCK_TYPES = frozenset({"thinking", "tool_use", "tool_result"})


def extract_text_blocks(content: Any) -> list[str]:
    """Return assistant/user speech from content[type=text] blocks, verbatim."""
    if isinstance(content, str):
        text = content.strip()
        return [text] if text else []

    if not isinstance(content, list):
        return []

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type in SKIPPED_BLOCK_TYPES:
            logger.debug("skipped sdk content block type=%s", block_type)
            continue
        if block_type != DISPLAY_BLOCK_TYPE:
            logger.debug("skipped sdk content block type=%s", block_type)
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return parts


def build_text_only_content(text_blocks: list[str]) -> list[dict[str, str]]:
    return [{"type": DISPLAY_BLOCK_TYPE, "text": text} for text in text_blocks if text]


def join_text_blocks(content: Any) -> str:
    return "\n".join(extract_text_blocks(content)).strip()


def resolve_user_utterance(*, content: Any, user_text: str = "") -> str:
    """Prefer the original room utterance when the gateway enriched the prompt."""
    user_text = user_text.strip()
    if user_text:
        return user_text
    return join_text_blocks(content)
