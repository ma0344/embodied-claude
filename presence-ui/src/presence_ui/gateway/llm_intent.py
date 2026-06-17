"""C12 — LM Studio JSON intent classifier (offline benchmark + gateway fallback)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx

from presence_ui.gateway.intent_labels import LLM_INTENT_SYSTEM_PROMPT, normalize_intent_labels


def _lm_settings() -> tuple[str, str, str]:
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


def lm_studio_available(*, timeout: float = 2.0) -> bool:
    base, _, token = _lm_settings()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
                f"{base}/v1/models",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def _extract_json_object(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def classify_with_llm(
    user_text: str,
    *,
    timeout: float | None = None,
) -> tuple[list[str], float | None, str]:
    """Return (labels, confidence, raw_or_error)."""
    if timeout is None:
        try:
            timeout = float(os.getenv("PRESENCE_LLM_INTENT_TIMEOUT", "20"))
        except ValueError:
            timeout = 20.0
    base, model, token = _lm_settings()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": LLM_INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_text.strip()},
        ],
        "temperature": 0.1,
        "max_tokens": 120,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{base}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return [], None, f"http_error: {exc}"

    choices = data.get("choices") or []
    if not choices:
        return [], None, "empty_choices"
    content = (choices[0].get("message") or {}).get("content")
    if not isinstance(content, str):
        return [], None, "no_text_content"

    parsed = _extract_json_object(content)
    if not parsed:
        return [], None, f"json_parse_failed: {content[:200]}"

    labels = normalize_intent_labels(parsed.get("labels"))
    conf_raw = parsed.get("confidence")
    confidence = float(conf_raw) if isinstance(conf_raw, (int, float)) else None
    return labels, confidence, content.strip()
