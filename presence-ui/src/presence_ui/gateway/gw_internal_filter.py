"""Filter gateway internal turns from Room-visible chat history."""

from __future__ import annotations

import re

from presence_ui.gateway.llm_intent import _extract_json_object

_GATEWAY_INTERNAL_MARKERS = (
    "[gateway_internal",
    "[gateway_internal — not for まー]",
    "[gateway_internal - not for",
)

_GW_PAUSE_NEXT_MOVES = frozenset({"advance", "reread_same", "close_book"})

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?", re.IGNORECASE | re.MULTILINE)


def is_gateway_internal_user_text(text: str) -> bool:
    """True when JSONL user turn is a GW internal task (not まー)."""
    hay = (text or "").strip()
    if not hay:
        return False
    return any(marker in hay for marker in _GATEWAY_INTERNAL_MARKERS)


def _pause_reflection_payload(text: str) -> dict | None:
    """Parse GW-S1 PAUSE JSON from assistant text (raw, fenced, or embedded)."""
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = _JSON_FENCE_RE.sub("", raw, count=1).strip()
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")].strip()
    data = _extract_json_object(raw)
    if not isinstance(data, dict):
        return None
    return data


def is_gateway_internal_assistant_reply(text: str) -> bool:
    """True when assistant turn is GW-S1 PAUSE JSON (hook/felt/next_move)."""
    data = _pause_reflection_payload(text)
    if not data:
        return False
    hook = data.get("hook")
    felt = data.get("felt")
    next_move = str(data.get("next_move") or "").strip()
    return (
        isinstance(hook, str)
        and bool(hook.strip())
        and isinstance(felt, str)
        and bool(felt.strip())
        and next_move in _GW_PAUSE_NEXT_MOVES
    )


def filter_room_visible_messages(messages: list[dict]) -> list[dict]:
    """Drop gateway internal user/assistant rows from Room chat arrays."""
    visible: list[dict] = []
    for msg in messages:
        sender = str(msg.get("sender") or "")
        body = str(msg.get("message") or "")
        if sender == "ma" and is_gateway_internal_user_text(body):
            continue
        if sender == "koyori" and is_gateway_internal_assistant_reply(body):
            continue
        visible.append(msg)
    return visible
