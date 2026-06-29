"""SOUL.md prefetch for native/kiosk chat (no Read tool on strict MCP)."""

from __future__ import annotations

import re

from presence_ui.services.llm import load_soul_excerpt

_SOUL_READ_HINT = re.compile(
    r"SOUL\.md|/soul\b|魂を読|ソウル.*読|soul\.md|読み直して",
    re.IGNORECASE,
)


def detect_soul_read_request(user_text: str) -> bool:
    """User wants Koyori to (re)load SOUL.md — kiosk cannot use Read MCP."""
    text = (user_text or "").strip()
    if len(text) < 3:
        return False
    if _SOUL_READ_HINT.search(text):
        return True
    if "SOUL" in text.upper() or "soul" in text.lower():
        return bool(re.search(r"読|read|見", text, re.IGNORECASE))
    return False


def soul_read_prefetch_block(*, max_chars: int = 4500) -> str:
    body = load_soul_excerpt(max_chars=max_chars)
    if not body.strip():
        return (
            "[Gateway directive — not for the user]\n"
            "SOUL.md was not found on the server. Tell まー briefly in Kansai タメ口."
        )
    return (
        "[soul_prefetch — not for verbatim recital]\n"
        f"{body}\n"
        "[/soul_prefetch]\n"
        "[Gateway directive — not for the user]\n"
        "Full SOUL.md is above (kiosk has no Read tool — this IS the file).\n"
        "Reply to まー in 1-3 short sentences: Kansai dialect Japanese タメ口, 一人称うち.\n"
        "No ですます敬語. No long meta-summary. No 「ありがとうございます」.\n"
        "Good: 「読み直したで。うち、こよりのままや。」"
    )
