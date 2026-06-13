"""Deterministic long-term memory saves for explicit remember requests.

When the user asks to remember something, persist via memory-mcp HTTP without
waiting for the local LLM to call ``mcp__memory__remember``.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

_VALID_CATEGORIES = frozenset(
    {
        "core",
        "daily",
        "philosophical",
        "technical",
        "memory",
        "observation",
        "feeling",
        "conversation",
    }
)

# Content before/after remember imperatives (Japanese + English).
_CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(.+?)(?:を|って)?(?:覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて)[。．!！]?$",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:覚えておいて|覚えといて|記憶して|記憶しといて)[：:\s]+(.+)$",
        re.DOTALL,
    ),
    re.compile(
        r"^(?:remember(?:\s+this|\s+forever)?|store\s+this(?:\s+permanently)?)"
        r"[：:\s]+(.+)$",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"^(.+?)\s+(?:please\s+)?remember(?:\s+this|\s+forever)?[.!]?$",
        re.IGNORECASE | re.DOTALL,
    ),
)

_IMPERATIVE_ONLY = re.compile(
    r"^(?:これ|それ|あれ)?(?:を)?(?:覚えておいて|覚えといて|記憶して|記憶しといて)[。．!！]?$",
)

_TRIGGER_HINT = re.compile(
    r"(覚えておいて|覚えといて|覚えとく|記憶して|記憶しといて|"
    r"remember\s+forever|remember\s+this|store\s+this)",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class RememberIntent:
    content: str
    category: str = "conversation"


@dataclass(slots=True, frozen=True)
class RememberOutcome:
    ok: bool
    content: str
    memory_id: str | None = None
    duplicate: bool = False
    error: str | None = None


def detect_remember_intent(user_text: str) -> RememberIntent | None:
    """Return content to save when the message is an explicit remember request."""

    text = (user_text or "").strip()
    if len(text) < 4 or not _TRIGGER_HINT.search(text):
        return None
    if _IMPERATIVE_ONLY.match(text):
        return None

    for pattern in _CONTENT_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        content = match.group(1).strip()
        content = re.sub(r"^[「『\"']+|[」』\"']+$", "", content).strip()
        if len(content) >= 2:
            category = _guess_category(content)
            return RememberIntent(content=content, category=category)
    return None


def _guess_category(content: str) -> str:
    lowered = content.lower()
    if any(k in content for k in ("作戦", "Cursor", "実装", "調査", "プロンプト", "技術")):
        return "technical"
    if any(k in lowered for k in ("feel", "感情", "嬉し", "悲し")):
        return "feeling"
    return "conversation"


def _memory_http_base() -> str:
    override = os.getenv("MEMORY_HTTP_RECALL_BASE", "").strip()
    if override:
        return override.rstrip("/")
    port = os.getenv("MEMORY_HTTP_PORT", "18900")
    return f"http://127.0.0.1:{port}"


def _http_timeout() -> float:
    raw = os.getenv("MEMORY_HTTP_REMEMBER_TIMEOUT", "20")
    try:
        return max(2.0, float(raw))
    except ValueError:
        return 20.0


def persist_remember_intent(intent: RememberIntent) -> RememberOutcome:
    """POST to memory-mcp HTTP ``/remember`` (falls back gracefully on failure)."""

    category = intent.category if intent.category in _VALID_CATEGORIES else "conversation"
    payload = json.dumps(
        {
            "content": intent.content,
            "category": category,
            "emotion": "neutral",
            "importance": 4,
            "auto_link": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    url = f"{_memory_http_base()}/remember"
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_http_timeout()) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return RememberOutcome(ok=False, content=intent.content, error=str(exc))

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return RememberOutcome(
            ok=False,
            content=intent.content,
            error="invalid JSON from memory HTTP",
        )

    if not data.get("ok"):
        return RememberOutcome(
            ok=False,
            content=intent.content,
            error=str(data.get("error") or "remember failed"),
        )
    return RememberOutcome(
        ok=True,
        content=intent.content,
        memory_id=str(data.get("id") or "") or None,
        duplicate=bool(data.get("duplicate")),
    )


def memory_saved_prompt_note(outcome: RememberOutcome) -> str:
    if not outcome.ok:
        return (
            "[memory_save_failed]\n"
            f"Server-side remember failed for: {outcome.content[:200]}\n"
            f"Error: {outcome.error or 'unknown'}"
        )
    dup = " (already stored)" if outcome.duplicate else ""
    mid = outcome.memory_id or "unknown"
    return (
        "[memory_saved_server]\n"
        f"Persisted{dup} (id={mid}): {outcome.content}\n"
        "Do not call mcp__memory__remember again for this same fact."
    )
