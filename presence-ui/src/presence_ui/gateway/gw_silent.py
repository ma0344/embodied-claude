"""GW-SILENT — silent internal turns (interpret layer)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from presence_ui.gateway.llm_intent import _extract_json_object, lm_studio_available
from presence_ui.services.llm import (
    _lm_studio_settings,
    _parse_openai_chat_content,
    build_gateway_stable_append,
)

logger = logging.getLogger(__name__)

VALID_NEXT_MOVES = frozenset({"advance", "reread_same", "close_book"})

_INTERNAL_RULES = """[Gateway internal — not for まー]
This turn is private inner processing. Reply with JSON only as instructed.
No user-visible chat, no tool calls, no markdown fences."""


@dataclass(frozen=True, slots=True)
class PauseReflectionParsed:
    hook: str
    felt: str
    next_move: str
    interest_tags: tuple[str, ...] = ()
    followup_query: str = ""


def gw_s1_enabled() -> bool:
    flag = os.environ.get("PRESENCE_GW_S1_ENABLED", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def parse_pause_response(text: str) -> PauseReflectionParsed | None:
    """Parse GW-S1 PAUSE JSON into a normalized result."""
    data = _extract_json_object(text)
    if not data:
        return None
    hook = str(data.get("hook") or "").strip()
    felt = str(data.get("felt") or "").strip()
    if not hook or not felt:
        return None
    next_move = str(data.get("next_move") or "advance").strip()
    if next_move not in VALID_NEXT_MOVES:
        next_move = "advance"
    tags_raw = data.get("interest_tags")
    tags: list[str] = []
    if isinstance(tags_raw, list):
        tags = [str(item).strip() for item in tags_raw if str(item).strip()][:8]
    followup = str(data.get("followup_query") or "").strip()
    return PauseReflectionParsed(
        hook=hook,
        felt=felt,
        next_move=next_move,
        interest_tags=tuple(tags),
        followup_query=followup,
    )


def run_silent_internal_turn(
    *,
    task: str,
    session_id: str | None = None,
    max_tokens: int = 480,
    temperature: float = 0.55,
    timeout: float | None = None,
) -> str | None:
    """Run one gateway internal turn via LM Studio (forward=False semantics).

    ``session_id`` is reserved for future Claude ``--resume`` wiring; v1 uses a
    stateless LM Studio completion with stable system append (autonomous tick).
    """
    del session_id
    if not lm_studio_available(timeout=2.0):
        logger.warning("GW-S1: LM Studio unavailable")
        return None
    if timeout is None:
        timeout = float(os.environ.get("PRESENCE_GW_S1_TIMEOUT", "90"))

    base, model, token = _lm_studio_settings()
    stable = build_gateway_stable_append()
    messages = [
        {"role": "system", "content": f"{stable}\n\n{_INTERNAL_RULES}"},
        {"role": "user", "content": task.strip()},
    ]
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
            response = client.post(
                f"{base}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return _parse_openai_chat_content(response.json())
    except Exception as exc:
        logger.warning("GW-S1 silent turn failed: %s", exc)
        return None
