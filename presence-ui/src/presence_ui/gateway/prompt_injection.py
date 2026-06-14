"""Gateway prompt injection — stable append vs per-turn user delta (KV cache friendly)."""

from __future__ import annotations

import os

from presence_ui.services.llm import GATEWAY_STABLE_APPEND, prepend_gateway_turn_context


def kv_stable_append_enabled() -> bool:
    """When True (default), dynamic compose/plan lives in user message, not appendSystemPrompt."""
    raw = os.getenv("PRESENCE_KV_STABLE_APPEND", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def apply_gateway_prompt_injection(
    *,
    user_text: str,
    turn_delta: str,
    extra_append: str = "",
) -> tuple[str, str | None]:
    """Return (enriched_message, append_system_prompt).

    Stable mode: appendSystemPrompt is constant; turn_delta is prepended to user_text.
    Legacy mode: turn_delta (+ extra_append) goes to appendSystemPrompt; message unchanged.
    """
    message = user_text.strip()
    delta = turn_delta.strip()
    if extra_append.strip():
        delta = f"{delta}\n\n{extra_append.strip()}".strip() if delta else extra_append.strip()

    if kv_stable_append_enabled():
        enriched = prepend_gateway_turn_context(user_text=message, delta=delta)
        return enriched, GATEWAY_STABLE_APPEND

    append = delta or None
    return message, append
