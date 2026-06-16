"""LM Studio vision describe + MCP-compatible capture text (shared with gateway)."""

from __future__ import annotations

import base64
import io
import logging
import os
import sys
from pathlib import Path

import httpx
from PIL import Image

from ._behavior import get_behavior
from .camera import CaptureResult

logger = logging.getLogger(__name__)


def text_only_tool_results() -> bool:
    """LM Studio /v1/messages rejects image blocks inside tool_result arrays."""
    raw = os.environ.get("WIFI_CAM_TEXT_ONLY_TOOL_RESULT", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    if not raw and sys.platform == "win32":
        return True
    return bool(get_behavior("wifi-cam", "text_only_tool_result", False))


def vision_describe_enabled() -> bool:
    raw = os.environ.get("WIFI_CAM_VISION_DESCRIBE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return text_only_tool_results()


def lm_studio_settings() -> tuple[str, str, str]:
    base = (
        os.environ.get("LM_STUDIO_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "http://127.0.0.1:1234"
    ).rstrip("/")
    model = (
        os.environ.get("LM_STUDIO_VISION_MODEL")
        or os.environ.get("CLAUDE_MODEL")
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


def resize_image_base64(image_base64: str, max_side: int = 768) -> str:
    raw = base64.standard_b64decode(image_base64)
    img = Image.open(io.BytesIO(raw))
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def _lm_auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-api-key": token,
        "Content-Type": "application/json",
    }


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
        joined = "\n".join(p for p in parts if p).strip()
        return joined or None
    return None


def _parse_anthropic_message_content(data: dict) -> str | None:
    content = (data.get("content") or []) if isinstance(data, dict) else []
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text and str(text).strip():
                parts.append(str(text).strip())
    return "\n".join(parts).strip() or None


async def _describe_via_chat(
    client: httpx.AsyncClient,
    base: str,
    model: str,
    headers: dict[str, str],
    prompt: str,
    image_b64: str,
    *,
    max_tokens: int,
) -> str | None:
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return _parse_openai_chat_content(resp.json())


async def _describe_via_messages(
    client: httpx.AsyncClient,
    base: str,
    model: str,
    headers: dict[str, str],
    prompt: str,
    image_b64: str,
    *,
    max_tokens: int,
) -> str | None:
    url = f"{base}/v1/messages"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                ],
            }
        ],
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return _parse_anthropic_message_content(resp.json())


async def describe_image_via_lm_studio(image_base64: str) -> str | None:
    """Send JPEG to LM Studio vision; return text-only caption."""
    base, model, token = lm_studio_settings()
    max_side = int(os.environ.get("WIFI_CAM_VISION_MAX_SIDE", "1024"))
    max_tokens = int(os.environ.get("WIFI_CAM_VISION_MAX_TOKENS", "720"))
    prompt = os.environ.get(
        "WIFI_CAM_VISION_PROMPT",
        "この画像を説明して。実際に見えるものだけ。見えないことは書かない。",
    )
    image_b64 = resize_image_base64(image_base64, max_side=max_side)
    headers = _lm_auth_headers(token)
    api_pref = os.environ.get("WIFI_CAM_VISION_API", "auto").strip().lower()
    if api_pref in ("chat", "openai", "completions"):
        order = ["chat"]
    elif api_pref in ("messages", "anthropic"):
        order = ["messages"]
    else:
        order = ["chat", "messages"]

    async with httpx.AsyncClient(timeout=120.0) as client:
        for kind in order:
            try:
                if kind == "chat":
                    caption = await _describe_via_chat(
                        client, base, model, headers, prompt, image_b64, max_tokens=max_tokens
                    )
                    label = "/v1/chat/completions"
                else:
                    caption = await _describe_via_messages(
                        client, base, model, headers, prompt, image_b64, max_tokens=max_tokens
                    )
                    label = "/v1/messages"
                if caption:
                    logger.info("Vision describe OK via %s (%d chars)", label, len(caption))
                    return caption
                logger.warning("Vision describe %s: empty content", label)
            except Exception as exc:
                logger.warning("Vision describe %s failed: %s", kind, exc)

    return None


def format_capture_text(
    result: CaptureResult,
    label: str = "",
    *,
    vision_caption: str | None = None,
) -> str:
    lines: list[str] = []
    if label:
        lines.append(label)
    lines.append(
        f"Captured image at {result.timestamp} ({result.width}x{result.height})."
    )
    if result.file_path:
        lines.append(f"file_path: {result.file_path}")
    if vision_caption:
        lines.append("")
        lines.append("=== VISION_CAPTION (唯一の根拠。ここに無い内容を推測で述べない) ===")
        lines.append(vision_caption)
        lines.append("=== END VISION_CAPTION ===")
    elif text_only_tool_results() and vision_describe_enabled():
        lines.append("")
        lines.append("=== VISION_DESCRIBE_FAILED ===")
        lines.append(
            "LM Studio への画像説明リクエストが失敗しました。"
            " 部屋の様子・物体を推測で述べないこと。"
            " ユーザーには file_path の JPEG を開いて確認するよう伝えてください。"
        )
        lines.append("=== END VISION_DESCRIBE_FAILED ===")
    return "\n".join(lines)
