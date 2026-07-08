"""Minimal LM Studio HTTP client (no gateway imports — safe for DOC-READ, scripts)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import httpx

CLASSIFIER_MODEL_DEFAULT = "google/gemma-4-e4b-qat"


def lm_studio_settings() -> tuple[str, str, str]:
    base = (
        os.environ.get("LM_STUDIO_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "http://127.0.0.1:1234"
    ).rstrip("/")
    model = (
        os.environ.get("PRESENCE_LLM_MODEL")
        or os.environ.get("CLAUDE_MODEL")
        or os.environ.get("LMSTUDIO_MODEL")
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


def lm_classifier_settings() -> tuple[str, str, str]:
    base, _surface_model, token = lm_studio_settings()
    override_base = os.environ.get("PRESENCE_CLASSIFIER_BASE_URL", "").strip().rstrip("/")
    override_model = os.environ.get("PRESENCE_CLASSIFIER_MODEL", "").strip()
    if override_base:
        base = override_base
    model = override_model or CLASSIFIER_MODEL_DEFAULT
    return base, model, token


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }


def parse_openai_chat_content(data: dict) -> str | None:
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


async def complete_chat(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 1024,
    model_scope: Literal["surface", "classifier"] = "surface",
    timeout_sec: float = 120.0,
) -> str:
    if model_scope == "classifier":
        base, model, token = lm_classifier_settings()
    else:
        base, model, token = lm_studio_settings()
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.75,
        "messages": messages,
    }
    headers = _auth_headers(token)
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_sec)) as client:
        response = await client.post(f"{base}/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        text = parse_openai_chat_content(response.json())
    if not text:
        raise RuntimeError("LM Studio returned an empty reply")
    return text
