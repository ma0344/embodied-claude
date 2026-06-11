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


def _load_soul_excerpt(*, max_chars: int = 2200) -> str:
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


def build_social_prompt_prefix(*, ctx: InteractionContext, plan: ResponsePlan) -> str:
    """Compact sociality block prepended to the user message for Claude Code."""
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
    return "\n\n".join(parts)


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
