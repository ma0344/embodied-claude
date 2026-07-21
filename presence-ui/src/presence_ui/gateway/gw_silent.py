"""GW-SILENT — silent internal turns (interpret layer)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from dataclasses import dataclass
from typing import Literal

import httpx

from presence_ui.gateway.gateway_llm_log import append_gateway_llm_log
from presence_ui.gateway.llm_intent import _extract_json_object, lm_studio_available
from presence_ui.services.llm import (
    _lm_classifier_settings,
    _lm_studio_settings,
    _parse_openai_chat_content,
    build_gateway_stable_append,
)

logger = logging.getLogger(__name__)

VALID_NEXT_MOVES = frozenset({"advance", "reread_same", "close_book"})

_INTERNAL_RULES = """[Gateway internal — not for まー]
This turn is private inner processing. Reply with JSON only as instructed.
No user-visible chat, no tool calls, no markdown fences."""


def gw_s1_claude_enabled() -> bool:
    flag = os.environ.get("PRESENCE_GW_S1_CLAUDE", "0").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def gw_after_chat_enabled() -> bool:
    flag = os.environ.get("PRESENCE_GW_AFTER_CHAT", "0").strip().lower()
    return flag not in {"0", "false", "no", "off"}


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


def run_classifier_turn(
    *,
    system: str,
    user: str,
    max_tokens: int = 420,
    temperature: float = 0.35,
    timeout: float | None = None,
    log_label: str = "GW classifier",
    model_scope: Literal["classifier", "surface"] = "classifier",
    reasoning: bool | None = None,
) -> str | None:
    """Stateless LM Studio completion (OL-GATE — no SOUL / no session history).

    ``model_scope="classifier"`` (default): ``PRESENCE_CLASSIFIER_*`` when set,
    else ``google/gemma-4-e4b-qat`` (PFC-1 default — not surface 12B).
    GW-S1 uses ``model_scope="surface"``.

    ``reasoning``: optional Gemma 4 thinking via OpenAI-compat ``reasoning_effort``
    (``medium`` / ``none``). ``None`` leaves the field unset so other classifiers
    are unchanged. Brief S0 callers pass ``brief_s0_reasoning_enabled()``.
    """
    if not lm_studio_available(timeout=2.0):
        logger.warning("%s: LM Studio unavailable", log_label)
        return None
    if timeout is None:
        timeout = float(os.environ.get("PRESENCE_GW_S2_TIMEOUT", "45"))

    if model_scope == "surface":
        base, model, token = _lm_studio_settings()
    else:
        base, model, token = _lm_classifier_settings()
    messages = [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": user.strip()},
    ]
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if reasoning is not None:
        from presence_ui.gateway.brief_s0_reasoning import reasoning_effort_for_openai

        payload["reasoning_effort"] = reasoning_effort_for_openai(reasoning)
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
            text = _parse_openai_chat_content(response.json())
            append_gateway_llm_log(
                log_label=log_label,
                model=model,
                system=system,
                user=user,
                output=text,
                ok=bool(text),
            )
            return text
    except Exception as exc:
        append_gateway_llm_log(
            log_label=log_label,
            model=model,
            system=system,
            user=user,
            output=str(exc)[:200],
            ok=False,
        )
        logger.warning("%s failed: %s", log_label, exc)
        return None


def run_silent_internal_turn(
    *,
    task: str,
    session_id: str | None = None,
    max_tokens: int = 480,
    temperature: float = 0.55,
    timeout: float | None = None,
) -> str | None:
    """Run one gateway internal turn (Claude --resume or LM Studio fallback)."""
    coro = run_silent_internal_turn_async(
        task=task,
        session_id=session_id,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        wait_timeout = timeout or float(os.environ.get("PRESENCE_GW_S1_TIMEOUT", "90"))
        return pool.submit(asyncio.run, coro).result(timeout=wait_timeout + 15)


def _internal_claude_config(*, max_turns: int | None = None):
    from presence_ui.gateway.ccs_integration import default_agent_config

    stable = build_gateway_stable_append()
    append = f"{stable}\n\n{_INTERNAL_RULES}"
    turns = max_turns
    if turns is None:
        turns = int(os.environ.get("PRESENCE_GW_INTERNAL_MAX_TURNS", "1"))
    base = default_agent_config()
    return base.model_copy(
        update={
            "append_system_prompt": append,
            "max_turns": max(1, turns),
        }
    )


async def _run_claude_resume_internal(
    *,
    session_id: str,
    task: str,
    timeout: float | None,
) -> str | None:
    from claude_code_server.agent import ClaudeAgent

    sid = session_id.strip()
    if not sid:
        return None
    cfg = _internal_claude_config()
    agent = ClaudeAgent()
    parts: list[str] = []
    try:
        async for event in agent.chat(
            prompt=task.strip(),
            session_id=sid,
            config=cfg,
            is_new=False,
        ):
            if event.get("event") == "text":
                content = event.get("data", {}).get("content")
                if content:
                    parts.append(str(content))
    except Exception as exc:
        logger.warning("GW Claude resume failed: %s", exc)
        return None
    finally:
        await agent.cancel()
    text = "".join(parts).strip()
    return text or None


async def run_silent_internal_turn_async(
    *,
    task: str,
    session_id: str | None = None,
    max_tokens: int = 480,
    temperature: float = 0.55,
    timeout: float | None = None,
) -> str | None:
    """Async internal turn — Claude --resume when session_id + flag, else LM Studio."""
    del max_tokens  # Claude CLI uses max_turns; LM path uses max_tokens below
    if session_id and gw_s1_claude_enabled():
        if timeout is None:
            timeout = float(os.environ.get("PRESENCE_GW_S1_TIMEOUT", "90"))
        text = await _run_claude_resume_internal(
            session_id=session_id,
            task=task,
            timeout=timeout,
        )
        if text:
            return text
        logger.warning("GW Claude resume empty/failed; falling back to LM Studio")

    if not lm_studio_available(timeout=2.0):
        logger.warning("GW-S1: LM Studio unavailable")
        return None
    if timeout is None:
        timeout = float(os.environ.get("PRESENCE_GW_S1_TIMEOUT", "90"))

    stable = build_gateway_stable_append()
    return run_classifier_turn(
        system=f"{stable}\n\n{_INTERNAL_RULES}",
        user=task.strip(),
        max_tokens=480,
        temperature=temperature,
        timeout=timeout,
        log_label="GW-S1",
        model_scope="surface",
    )
