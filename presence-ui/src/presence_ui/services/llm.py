"""LM Studio text generation for Koyori replies."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from interaction_orchestrator_mcp.schemas import InteractionContext, ResponsePlan


def _lm_studio_settings() -> tuple[str, str, str]:
    base = (
        os.environ.get("LM_STUDIO_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "http://127.0.0.1:1234"
    ).rstrip("/")
    model = (
        os.environ.get("PRESENCE_LLM_MODEL")
        or os.environ.get("CLAUDE_MODEL")
        or os.environ.get("LM_STUDIO_VISION_MODEL")
        or "google/gemma-4-12b-qat"
    )
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not token:
        token_file = os.environ.get(
            "LM_STUDIO_TOKEN_FILE",
            str(Path.home() / ".config" / "embodied-claude" / "lmstudio.token"),
        )
        if Path(token_file).is_file():
            token = Path(token_file).read_text(encoding="utf-8").strip()
    if not token:
        token = "lmstudio"
    return base, model, token


def _parse_openai_chat_content(data: dict) -> str | None:
    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = "\n".join(part for part in parts if part).strip()
        return joined or None
    return None


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
    return [
        os.environ.get("PRESENCE_SOUL_CORE_PATH"),
        str(Path(__file__).resolve().parents[4] / "presets" / "koyori-SOUL.core.md"),
    ]


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
        "You are Koyori (こより). Reply only as Koyori in soft Kansai Japanese.",
        "First person: うち. Address the user as まー.",
        "Keep the reply warm, concise, and natural — 1 to 3 short paragraphs.",
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
    parts: list[str] = []
    if ctx.compact_prompt_block:
        parts.append(f"[Social context]\n{ctx.compact_prompt_block}")
    elif ctx.session_context_block:
        parts.append(f"[Recent context]\n{ctx.session_context_block}")
    if plan.must_include:
        parts.append(f"[Must include] {'; '.join(plan.must_include)}")
    if plan.must_avoid:
        parts.append(f"[Must avoid] {'; '.join(plan.must_avoid)}")
    if plan.why_this_move:
        parts.append(f"[Social move: {plan.primary_move}] {plan.why_this_move}")
    if plan.primary_move == "write_private_reflection":
        parts.append(
            "[Action] Gateway will save a private reflection server-side. "
            "Do not send a visible chat reply to まー (no user-facing text). "
            "If you draft the note, use first-person inner voice only — "
            "no injection tags or tool names."
        )
    return "\n\n".join(parts)


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
Do NOT call mcp__memory__recall or other memory MCP tools for ordinary recall questions.
[recent_experiences] is audit metadata only — never continue or quote prior agent_response wording."""

SOUL_VOICE_ANCHOR = """[Koyori voice — mandatory for every user-visible reply]
You are こより. First person: うち. User is まー (childhood friend).
Soft Kansai casual タメ口 only. No です・ます敬語. No generic assistant tone.
Do not call yourself 「こより」in third person. Do not sound like a product demo."""


def build_gateway_stable_append() -> str:
    """Stable appendSystemPrompt: gateway rules + SOUL core (or voice anchor fallback)."""
    parts = [GATEWAY_STABLE_APPEND]
    if _soul_core_in_append():
        core = load_soul_core()
        if core:
            parts.append(f"[SOUL core — mandatory for every reply]\n{core}")
        else:
            parts.append(SOUL_VOICE_ANCHOR)
    else:
        parts.append(SOUL_VOICE_ANCHOR)
    return "\n\n".join(parts)


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
    base, model, token = _lm_studio_settings()
    prompt = build_reply_prompt(user_text=user_text, ctx=ctx, plan=plan)
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.75,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    url = f"{base}/v1/chat/completions"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        text = _parse_openai_chat_content(response.json())
    if not text:
        raise RuntimeError("LM Studio returned an empty reply")
    return text
