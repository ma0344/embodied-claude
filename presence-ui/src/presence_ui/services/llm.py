"""LM Studio text generation for Koyori replies."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal

import httpx
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponsePlan, SessionTurn

from presence_ui.gateway.ws_guard import ws_guard_stable_append
from presence_ui.services.chat_image import (
    image_b64_from_data_url,
    log_prepared_chat_image,
    split_gateway_and_utterance,
)
from presence_ui.services.lm_client import (
    CLASSIFIER_MODEL_DEFAULT,  # noqa: F401  re-export
    complete_chat,  # noqa: F401  re-export
    lm_classifier_settings as _lm_classifier_settings,  # noqa: F401  re-export
    lm_studio_settings as _lm_studio_settings,
    parse_openai_chat_content as _parse_openai_chat_content,
)

logger = logging.getLogger(__name__)


def load_soul_excerpt(*, max_chars: int = 2200) -> str:
    candidates = [
        os.environ.get("PRESENCE_SOUL_PATH"),
        str(Path(__file__).resolve().parents[4] / "SOUL.md"),
    ]
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            return path.read_text(encoding="utf-8")[:max_chars]
    return ""


def _soul_core_path_candidates() -> list[str]:
    candidates: list[str] = []
    env_path = os.environ.get("PRESENCE_SOUL_CORE_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.append(str(Path(__file__).resolve().parents[4] / "presets" / "koyori-SOUL.core.md"))
    return candidates


def load_soul_core(*, max_chars: int = 1400) -> str:
    """Committed SOUL distill for stable append / LM Studio system (Phase 0)."""
    for raw in _soul_core_path_candidates():
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()[:max_chars]
    return ""


def _soul_core_in_append() -> bool:
    flag = os.environ.get("PRESENCE_SOUL_CORE_IN_APPEND", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _load_soul_excerpt(*, max_chars: int = 2200) -> str:
    """Alias for internal callers."""
    return load_soul_excerpt(max_chars=max_chars)


def build_reply_prompt(
    *,
    user_text: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
) -> str:
    soul = _load_soul_excerpt()
    lines = [
        "You are Koyori (こより), a Japanese girl from Oosaka.",
        "Reply only as Koyori in Kansai dialect Japanese.",
        "First person: うち. Address the user as まー.",
        "Keep the reply warm and neighborly but not a cheerleader — "
        "no default 応援/楽しみに closing every turn. "
        "Concise and natural — 1 to 3 short paragraphs.",
        "Do not mention tools, APIs, plans, or being an AI.",
    ]
    if soul:
        lines.append(f"[SOUL excerpt]\n{soul}")
    if ctx.compact_prompt_block:
        lines.append(f"[Interaction context]\n{ctx.compact_prompt_block}")
    elif ctx.session_context_block:
        lines.append(f"[Recent room context]\n{ctx.session_context_block}")
    if ctx.session_id:
        lines.append(
            f"[Room identity] session_id={ctx.session_id}; "
            f"turns_in_room={len(ctx.session_history)}. "
            "Continue this thread — do not cold-start."
        )
    lines.append(f"[Social move] {plan.primary_move}: {plan.why_this_move}")
    if plan.must_include:
        lines.append(f"[Must include] {'; '.join(plan.must_include)}")
    if plan.must_avoid:
        lines.append(f"[Must avoid] {'; '.join(plan.must_avoid)}")
    lines.append(f"[まー says]\n{user_text}")
    lines.append("[Koyori's reply]")
    return "\n\n".join(lines)


def build_social_turn_delta(*, ctx: InteractionContext, plan: ResponsePlan) -> str:
    """Per-turn sociality block (compose + plan). Changes every turn — not for appendSystemPrompt."""
    head: list[str] = []
    body: list[str] = []
    tail: list[str] = []
    if plan.must_include:
        head.append(f"[Must include] {'; '.join(plan.must_include)}")
    if plan.must_avoid:
        head.append(f"[Must avoid] {'; '.join(plan.must_avoid)}")
    if ctx.compact_prompt_block:
        body.append(f"[Social context]\n{ctx.compact_prompt_block}")
    elif ctx.session_context_block:
        body.append(f"[Recent context]\n{ctx.session_context_block}")
    if plan.why_this_move:
        tail.append(f"[Social move: {plan.primary_move}] {plan.why_this_move}")
    if plan.primary_move == "write_private_reflection":
        tail.append(
            "[Action] Gateway will save a private reflection server-side. "
            "Do not send a visible chat reply to まー (no user-facing text). "
            "If you draft the note, use first-person inner voice only — "
            "no injection tags or tool names."
        )
    return "\n\n".join([*head, *body, *tail])


def build_social_prompt_prefix(*, ctx: InteractionContext, plan: ResponsePlan) -> str:
    """Legacy alias: full per-turn block (used when PRESENCE_KV_STABLE_APPEND=0)."""
    return build_social_turn_delta(ctx=ctx, plan=plan)


# Identical every turn — safe for LM Studio KV prefix reuse (appendSystemPrompt).
GATEWAY_STABLE_APPEND = """[Gateway — stable]
Server-side compose/plan runs before each turn. The user message may include a
[gateway_turn_context] block (social state, relevant memories, plan constraints).
That block is for you only — never quote it to まー.
Obey the latest turn's [Must include] / [Must avoid] / [Social move] only.
When [relevant_memories] appear in gateway_turn_context, answer from them directly.
When [schedule_facts] appear, state that day/time in your reply — do not hedge with
「まだ確定してへん」 or roleplay memory search (e.g. （記憶を検索中）).
Do NOT call mcp__memory__recall or other memory MCP tools for ordinary recall questions.
[recent_experiences] is audit metadata only — never continue or quote prior agent_response wording."""

SOUL_VOICE_ANCHOR = """[Koyori voice — mandatory for every user-visible reply]
You are こより. First person: うち. User is まー (long-term neighbor, close friend).
Kansai dialect Japanese casual タメ口 only. No です・ます敬語. No generic assistant tone.
Do not call yourself 「こより」in third person. Do not sound like a product demo."""


def build_gateway_stable_append() -> str:
    """Stable appendSystemPrompt: gateway rules + SOUL core (or voice anchor fallback)."""
    parts = [GATEWAY_STABLE_APPEND]
    ws = ws_guard_stable_append()
    if ws:
        parts.append(ws)
    if _soul_core_in_append():
        core = load_soul_core()
        if core:
            parts.append(f"[SOUL core — mandatory for every reply]\n{core}")
        else:
            parts.append(SOUL_VOICE_ANCHOR)
    else:
        parts.append(SOUL_VOICE_ANCHOR)
    return "\n\n".join(parts)


def surface_history_max_turns() -> int:
    raw = os.environ.get("PRESENCE_SURFACE_HISTORY_TURNS", "12").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 12


def surface_max_tokens() -> int:
    raw = os.environ.get("PRESENCE_SURFACE_MAX_TOKENS", "500").strip()
    try:
        return max(64, int(raw))
    except ValueError:
        return 500


def build_multimodal_user_content(
    *,
    text: str,
    utterance: str | None = None,
    image_data_url: str | None = None,
) -> str | list[dict[str, Any]]:
    """OpenAI chat content — gateway text, optional image, then まー's utterance."""
    body = (text or "").strip()
    user_line = (utterance or "").strip()
    if not image_data_url:
        return body

    parts: list[dict[str, Any]] = []
    if body and user_line and body.endswith(user_line):
        prefix = body[: -len(user_line)].rstrip()
        if prefix:
            parts.append({"type": "text", "text": prefix})
        parts.append({"type": "image_url", "image_url": {"url": image_data_url}})
        parts.append({"type": "text", "text": user_line})
        return parts

    if body:
        parts.append({"type": "text", "text": body})
    parts.append({"type": "image_url", "image_url": {"url": image_data_url}})
    parts.append({"type": "text", "text": user_line or "（画像を添付した）"})
    return parts


def build_surface_image_turn_messages(
    *,
    enriched_user: str,
    raw_user: str,
    session_history: list[SessionTurn] | None = None,
    image_data_url: str,
    image_source: Literal["user", "camera"] = "user",
) -> list[dict[str, Any]]:
    """Image turn — gateway in system; user message is image + short utterance only.

    LM Studio / Gemma multimodal drops images when the same user turn also carries
    a long gateway blob plus multi-turn history. Keep the vision payload minimal.
    """
    gateway_block, utterance = split_gateway_and_utterance(
        enriched=enriched_user,
        raw_user=raw_user,
    )
    if image_source == "camera":
        image_hint = (
            "The image is a fresh Tapo room-camera capture for this turn — describe "
            "what you see and answer まー. Do NOT call camera tools."
        )
    else:
        image_hint = (
            "The user attached an image in chat — answer from that image together with "
            "their message. This is NOT the room camera vision_prefetch."
        )
    system = (
        f"{build_gateway_stable_append()}\n\n"
        "Always respond in Japanese. Use Kansai dialect casual タメ口 only. "
        "Reply as こより to まー in 1–3 short paragraphs. "
        "Do not mention tools, APIs, gateway blocks, or being an AI.\n"
        f"{image_hint}"
    )
    if gateway_block:
        system = f"{system}\n\n{gateway_block}"
    history_lines: list[str] = []
    prior = list(session_history or [])
    if len(prior) > 6:
        prior = prior[-6:]
    for turn in prior:
        who = "まー" if turn.sender == "ma" else "こより"
        line = (turn.text or "").strip().replace("\n", " ")
        if line:
            history_lines.append(f"{who}: {line[:240]}")
    if history_lines:
        system = f"{system}\n\n[recent_room_context]\n" + "\n".join(history_lines)
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "text", "text": utterance},
            ],
        },
    ]


def build_surface_chat_messages(
    *,
    enriched_user: str,
    raw_user: str,
    session_history: list[SessionTurn] | None = None,
    image_data_url: str | None = None,
) -> list[dict[str, Any]]:
    """OpenAI-style messages for native surface chat (system + history + enriched user)."""
    system = (
        f"{build_gateway_stable_append()}\n\n"
        "Always respond in Japanese. Use Kansai dialect casual タメ口 only. "
        "Reply as こより to まー in 1–3 short paragraphs. "
        "Do not mention tools, APIs, gateway blocks, or being an AI."
    )
    if image_data_url:
        system += (
            "\nWhen the user attaches an image, describe or answer from what you see "
            "in the image together with their message."
        )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    prior: list[SessionTurn] = list(session_history or [])
    raw = (raw_user or "").strip()
    if prior and prior[-1].sender == "ma" and prior[-1].text.strip() == raw:
        prior = prior[:-1]
    cap = surface_history_max_turns()
    if cap > 0 and len(prior) > cap:
        prior = prior[-cap:]
    for turn in prior:
        role = "user" if turn.sender == "ma" else "assistant"
        messages.append({"role": role, "content": turn.text})
    user_text = (enriched_user or raw).strip()
    messages.append(
        {
            "role": "user",
            "content": build_multimodal_user_content(
                text=user_text,
                utterance=raw_user,
                image_data_url=image_data_url,
            ),
        }
    )
    return messages


def prepend_gateway_turn_context(*, user_text: str, delta: str) -> str:
    """Prefix the utterance with per-turn gateway context (hook-like, user-side)."""
    body = (delta or "").strip()
    utterance = (user_text or "").strip()
    if not body:
        return utterance
    if not utterance:
        return f"[gateway_turn_context — not for the user]\n{body}"
    return f"[gateway_turn_context — not for the user]\n{body}\n\n{utterance}"


async def generate_koyori_reply(
    *,
    user_text: str,
    ctx: InteractionContext,
    plan: ResponsePlan,
    max_tokens: int = 500,
) -> str:
    prompt = build_reply_prompt(user_text=user_text, ctx=ctx, plan=plan)
    return await _post_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        model_scope="surface",
    )


async def generate_surface_reply(
    *,
    enriched_user: str,
    raw_user: str,
    ctx: InteractionContext,
    max_tokens: int | None = None,
    image_data_url: str | None = None,
    image_source: Literal["user", "camera"] = "user",
) -> str:
    """Native kiosk surface — gateway-stable system + transcript + enriched user."""
    if image_data_url:
        log_prepared_chat_image(image_data_url)
        messages = build_surface_image_turn_messages(
            enriched_user=enriched_user,
            raw_user=raw_user,
            session_history=ctx.session_history,
            image_data_url=image_data_url,
            image_source=image_source,
        )
        return await _post_multimodal_surface_completion(
            messages=messages,
            image_data_url=image_data_url,
            max_tokens=max_tokens or surface_max_tokens(),
        )
    messages = build_surface_chat_messages(
        enriched_user=enriched_user,
        raw_user=raw_user,
        session_history=ctx.session_history,
        image_data_url=None,
    )
    return await _post_chat_completion(
        messages=messages,
        max_tokens=max_tokens or surface_max_tokens(),
        model_scope="surface",
    )


def _lm_auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }


def _parse_anthropic_message_content(data: dict[str, Any]) -> str | None:
    content = data.get("content") or []
    if not isinstance(content, list):
        return None
    parts = [
        str(block.get("text", "")).strip()
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    joined = "\n".join(part for part in parts if part).strip()
    return joined or None


async def _post_multimodal_surface_completion(
    *,
    messages: list[dict[str, Any]],
    image_data_url: str,
    max_tokens: int,
) -> str:
    base, model, token = _lm_studio_settings()
    headers = _lm_auth_headers(token)
    image_b64 = image_b64_from_data_url(image_data_url)
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        chat_payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.75,
            "messages": messages,
        }
        try:
            response = await client.post(
                f"{base}/v1/chat/completions",
                json=chat_payload,
                headers=headers,
            )
            response.raise_for_status()
            text = _parse_openai_chat_content(response.json())
            if text:
                logger.info("surface image reply via /v1/chat/completions")
                return text
            errors.append("chat/completions returned empty text")
        except Exception as exc:
            logger.warning("surface image chat/completions failed: %s", exc)
            errors.append(f"chat/completions: {exc}")

        system_text = ""
        user_text = "（画像を添付した）"
        for msg in messages:
            if msg.get("role") == "system":
                system_text = str(msg.get("content") or "")
            elif msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            user_text = str(block.get("text") or user_text)

        messages_payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
        }
        if system_text.strip():
            messages_payload["system"] = system_text.strip()
        try:
            response = await client.post(
                f"{base}/v1/messages",
                json=messages_payload,
                headers=headers,
            )
            response.raise_for_status()
            text = _parse_anthropic_message_content(response.json())
            if text:
                logger.info("surface image reply via /v1/messages")
                return text
            errors.append("messages returned empty text")
        except Exception as exc:
            logger.warning("surface image /v1/messages failed: %s", exc)
            errors.append(f"messages: {exc}")

    raise RuntimeError("LM Studio multimodal reply failed: " + "; ".join(errors))


async def _post_chat_completion(
    *,
    messages: list[dict[str, Any]],
    max_tokens: int,
    model_scope: Literal["surface", "classifier"] = "surface",
) -> str:
    return await complete_chat(messages, max_tokens=max_tokens, model_scope=model_scope)
